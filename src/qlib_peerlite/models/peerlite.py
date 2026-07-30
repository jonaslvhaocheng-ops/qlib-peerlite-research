from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

from qlib_peerlite.governance.artifacts import atomic_write_json
from qlib_peerlite.m7.adapter import (
    authorize_synthetic_fit,
    checkpoint_config_for_load,
    checkpoint_context_after_state_load,
    checkpoint_context_for_fit,
    checkpoint_payload_for_load,
    market_frame,
    validate_candidate_config,
    validate_prediction_dataset,
)
from qlib_peerlite.m7.checkpoint import (
    M7CheckpointContext,
    build_checkpoint_v2_metadata,
)

from .common import (
    TrainOnlyStandardizer,
    dataset_features,
    dataset_xy,
    resolve_device,
    seed_everything,
)
from .losses import ConcordanceCorrelationLoss


class MarketStateGate(nn.Module):
    def __init__(self, market_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(market_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Sigmoid(),
        )

    def forward(self, market_state: torch.Tensor) -> torch.Tensor:
        return 2.0 * self.net(market_state)


class PeerLiteNetwork(nn.Module):
    """O(NK) cross-sectional peer-prototype network."""

    def __init__(
        self,
        input_dim: int,
        *,
        hidden_dim: int = 64,
        num_peers: int = 16,
        num_heads: int = 4,
        dropout: float = 0.1,
        market_dim: int = 0,
        market_gate: bool = False,
    ) -> None:
        super().__init__()
        if hidden_dim % num_heads:
            raise ValueError("hidden_dim must be divisible by num_heads")
        if num_peers not in (16, 32):
            raise ValueError("num_peers must be one of {16, 32}")
        if market_gate and market_dim <= 0:
            raise ValueError("market_dim must be positive when market_gate is enabled")

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_peers = num_peers
        self.num_heads = num_heads
        self.market_dim = market_dim
        self.market_gate_enabled = market_gate
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.market_gate = MarketStateGate(market_dim, hidden_dim) if market_gate else None
        self.assignment = nn.Linear(hidden_dim, num_peers)
        self.attention = nn.MultiheadAttention(
            hidden_dim,
            num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    @property
    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def forward(
        self,
        features: torch.Tensor,
        market_state: torch.Tensor | None = None,
        valid_mask: torch.Tensor | None = None,
        *,
        return_attention: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        unbatched = features.ndim == 2
        if unbatched:
            features = features.unsqueeze(0)
        elif features.ndim != 3:
            raise ValueError(
                "features must have shape [stocks, features] or [dates, stocks, features]"
            )
        n_dates, n_stocks, input_dim = features.shape
        if n_stocks == 0:
            raise ValueError("cross-section cannot be empty")
        if input_dim != self.input_dim:
            raise ValueError("feature dimension does not match PeerLite input_dim")
        if valid_mask is None:
            valid_mask = torch.ones(
                n_dates,
                n_stocks,
                dtype=torch.bool,
                device=features.device,
            )
        elif unbatched and valid_mask.shape == (n_stocks,):
            valid_mask = valid_mask.unsqueeze(0)
        if valid_mask.shape != (n_dates, n_stocks):
            raise ValueError("valid_mask must have shape [stocks] or [dates, stocks]")
        valid_mask = valid_mask.to(device=features.device, dtype=torch.bool)
        if not valid_mask.any(dim=1).all():
            raise ValueError("each cross-section must contain at least one valid stock")
        if not torch.isfinite(features[valid_mask]).all():
            raise ValueError("valid stock features must be finite")

        safe_features = torch.where(
            valid_mask.unsqueeze(-1),
            features,
            torch.zeros_like(features),
        )
        hidden = self.encoder(safe_features)
        if self.market_gate_enabled:
            if market_state is None:
                raise ValueError("market_state is required for the enabled market gate")
            if unbatched and market_state.ndim == 1:
                market_state = market_state.unsqueeze(0)
            if market_state.shape != (n_dates, self.market_dim):
                raise ValueError(
                    "market_state must have shape [market_features] or [dates, market_features]"
                )
            gate = self.market_gate(market_state).reshape(
                n_dates,
                1,
                self.hidden_dim,
            )
            hidden = hidden * gate

        assignment = torch.softmax(self.assignment(hidden), dim=-1)
        assignment = assignment * valid_mask.unsqueeze(-1)
        denominator = assignment.sum(dim=1).clamp_min(1e-8).unsqueeze(-1)
        prototypes = torch.einsum("bnk,bnh->bkh", assignment, hidden) / denominator
        context, attention = self.attention(
            hidden,
            prototypes,
            prototypes,
            need_weights=True,
            average_attn_weights=False,
        )
        relative = torch.cat([hidden, hidden - context], dim=-1)
        score = self.head(relative).squeeze(-1)
        score = torch.where(valid_mask, score, torch.zeros_like(score))
        if return_attention:
            attention = torch.where(
                valid_mask.reshape(n_dates, 1, n_stocks, 1),
                attention,
                torch.zeros_like(attention),
            )
            if unbatched:
                return score.squeeze(0), assignment.squeeze(0), attention.squeeze(0)
            return score, assignment, attention
        return score.squeeze(0) if unbatched else score


class PeerLiteModel:
    """Qlib-compatible date-batched PeerLite estimator."""

    def __init__(
        self,
        input_dim: int,
        *,
        hidden_dim: int = 64,
        num_peers: int = 16,
        num_heads: int = 4,
        dropout: float = 0.1,
        market_dim: int = 0,
        market_gate: bool = False,
        loss: str = "mse",
        seed: int = 7,
        epochs: int = 100,
        patience: int = 12,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
        gradient_clip_norm: float = 1.0,
        cross_section_batch_size: int = 16,
        device: str = "auto",
        model_id: str | None = None,
    ) -> None:
        if loss not in {"mse", "ccc"}:
            raise ValueError("loss must be mse or ccc")
        if cross_section_batch_size <= 0:
            raise ValueError("cross_section_batch_size must be positive")
        seed_everything(seed)
        self.input_dim = input_dim
        self.loss_name = loss
        self.seed = seed
        self.epochs = epochs
        self.patience = patience
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.gradient_clip_norm = gradient_clip_norm
        self.cross_section_batch_size = cross_section_batch_size
        self.device = resolve_device(device)
        self.model_id = model_id or (
            f"PEERLITE_K{num_peers}_{loss.upper()}" + ("_GATE" if market_gate else "")
        )
        self.config = {
            "input_dim": input_dim,
            "hidden_dim": hidden_dim,
            "num_peers": num_peers,
            "num_heads": num_heads,
            "dropout": dropout,
            "market_dim": market_dim,
            "market_gate": market_gate,
            "loss": loss,
            "seed": seed,
            "epochs": epochs,
            "patience": patience,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "gradient_clip_norm": gradient_clip_norm,
            "cross_section_batch_size": cross_section_batch_size,
            "model_id": self.model_id,
        }
        validate_candidate_config(self.config)
        self.network = PeerLiteNetwork(
            input_dim,
            hidden_dim=hidden_dim,
            num_peers=num_peers,
            num_heads=num_heads,
            dropout=dropout,
            market_dim=market_dim,
            market_gate=market_gate,
        ).to(self.device)
        if self.network.parameter_count >= 500_000:
            raise ValueError("PeerLite parameter budget must remain below 500,000")
        self.standardizer = TrainOnlyStandardizer()
        self.market_standardizer = TrainOnlyStandardizer()
        self.market_gate_enabled = market_gate
        self.feature_names: tuple[str, ...] = ()
        self.fitted = False
        self.training_history: list[dict[str, float]] = []
        self.best_epoch = -1
        self.best_valid_loss = float("nan")
        self.m7_context: M7CheckpointContext | None = None
        self.m7_fixture_sha256: str | None = None
        self.m7_state_binding_sha256: str | None = None

    def _market_frame(self, dataset: object, segment: str) -> pd.DataFrame | None:
        return market_frame(self.config, dataset, segment)

    @staticmethod
    def _date_batches(
        features: pd.DataFrame,
        target: pd.Series | None,
        market: pd.DataFrame | None,
    ) -> Iterable[tuple[pd.MultiIndex, np.ndarray, np.ndarray | None, np.ndarray | None]]:
        for _, cross_section in features.groupby(level="datetime", sort=True):
            index = cross_section.index
            x = cross_section.to_numpy(np.float32)
            y = None if target is None else target.loc[index].to_numpy(np.float32)
            market_row = None
            if market is not None:
                market_rows = market.loc[index]
                first = market_rows.iloc[0].to_numpy(np.float32)
                if not np.allclose(market_rows.to_numpy(np.float32), first, equal_nan=True):
                    raise ValueError("market state must be constant within each date")
                market_row = first
            yield index, x, y, market_row

    def _loss(self, prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        if self.loss_name == "ccc":
            return ConcordanceCorrelationLoss()(prediction, target)
        return nn.functional.mse_loss(prediction, target)

    @staticmethod
    def _pack_date_batches(
        batches: list[tuple[pd.MultiIndex, np.ndarray, np.ndarray | None, np.ndarray | None]],
    ) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None, np.ndarray]:
        if not batches:
            raise ValueError("cannot pack an empty date batch")
        max_stocks = max(len(item[1]) for item in batches)
        feature_dim = batches[0][1].shape[1]
        features = np.zeros((len(batches), max_stocks, feature_dim), dtype=np.float32)
        valid_mask = np.zeros((len(batches), max_stocks), dtype=bool)
        has_target = batches[0][2] is not None
        targets = np.zeros((len(batches), max_stocks), dtype=np.float32) if has_target else None
        has_market = batches[0][3] is not None
        market = np.stack([item[3] for item in batches]).astype(np.float32) if has_market else None
        for batch_index, (_, x, y, _) in enumerate(batches):
            size = len(x)
            features[batch_index, :size] = x
            valid_mask[batch_index, :size] = True
            if targets is not None:
                if y is None:
                    raise ValueError("date batch target presence is inconsistent")
                targets[batch_index, :size] = y
        return features, targets, market, valid_mask

    def _batched_objective(
        self,
        prediction: torch.Tensor,
        target: torch.Tensor,
        valid_mask: torch.Tensor,
    ) -> torch.Tensor:
        losses = [
            self._loss(prediction[index][valid_mask[index]], target[index][valid_mask[index]])
            for index in range(len(prediction))
        ]
        return torch.stack(losses).mean()

    def _validation_loss(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        market: pd.DataFrame | None,
    ) -> float:
        self.network.eval()
        values: list[float] = []
        date_batches = list(self._date_batches(features, target, market))
        with torch.no_grad():
            for start in range(0, len(date_batches), self.cross_section_batch_size):
                packed = self._pack_date_batches(
                    date_batches[start : start + self.cross_section_batch_size]
                )
                x, y, market_rows, valid_mask = packed
                if y is None:
                    raise RuntimeError("validation targets are missing")
                x_tensor = torch.as_tensor(x, device=self.device)
                y_tensor = torch.as_tensor(y, device=self.device)
                mask_tensor = torch.as_tensor(valid_mask, device=self.device)
                market_tensor = (
                    None
                    if market_rows is None
                    else torch.as_tensor(market_rows, device=self.device)
                )
                prediction = self.network(
                    x_tensor,
                    market_tensor,
                    valid_mask=mask_tensor,
                )
                values.extend(
                    float(
                        nn.functional.mse_loss(
                            prediction[index][mask_tensor[index]],
                            y_tensor[index][mask_tensor[index]],
                        ).cpu()
                    )
                    for index in range(len(prediction))
                )
        return float(np.mean(values))

    def fit(self, dataset: object, **kwargs: Any) -> PeerLiteModel:
        authority = kwargs.pop("m7_authority", None)
        if kwargs:
            raise TypeError(f"unexpected fit keyword arguments: {sorted(kwargs)}")
        dataset, checked_authority = authorize_synthetic_fit(self.config, dataset, authority)
        seed_everything(self.seed)
        x_train, y_train = dataset_xy(dataset, "train")
        x_valid, y_valid = dataset_xy(dataset, "valid")
        (
            self.m7_context,
            self.m7_fixture_sha256,
            self.m7_state_binding_sha256,
        ) = checkpoint_context_for_fit(
            self.config,
            checked_authority,
            dataset,
            x_train,
            x_valid,
        )
        self.feature_names = tuple(str(column) for column in x_train.columns)
        x_train = self.standardizer.fit_transform(x_train)
        x_valid = self.standardizer.transform(x_valid)

        market_train = self._market_frame(dataset, "train")
        market_valid = self._market_frame(dataset, "valid")
        if market_train is not None and market_valid is not None:
            unique_train = market_train.groupby(level="datetime", sort=True).first()
            self.market_standardizer.fit(unique_train)
            market_train = self.market_standardizer.transform(market_train)
            market_valid = self.market_standardizer.transform(market_valid)

        optimizer = torch.optim.AdamW(
            self.network.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay
        )
        rng = np.random.default_rng(self.seed)
        best_loss = float("inf")
        best_state: dict[str, torch.Tensor] | None = None
        stale = 0

        for epoch in range(self.epochs):
            self.network.train()
            batches = list(self._date_batches(x_train, y_train, market_train))
            rng.shuffle(batches)
            train_losses: list[float] = []
            for start in range(0, len(batches), self.cross_section_batch_size):
                x, y, market_rows, valid_mask = self._pack_date_batches(
                    batches[start : start + self.cross_section_batch_size]
                )
                if y is None:
                    raise RuntimeError("training targets are missing")
                x_tensor = torch.as_tensor(x, device=self.device)
                y_tensor = torch.as_tensor(y, device=self.device)
                mask_tensor = torch.as_tensor(valid_mask, device=self.device)
                market_tensor = (
                    None
                    if market_rows is None
                    else torch.as_tensor(market_rows, device=self.device)
                )
                optimizer.zero_grad(set_to_none=True)
                prediction = self.network(
                    x_tensor,
                    market_tensor,
                    valid_mask=mask_tensor,
                )
                objective = self._batched_objective(
                    prediction,
                    y_tensor,
                    mask_tensor,
                )
                objective.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.network.parameters(),
                    self.gradient_clip_norm,
                    error_if_nonfinite=True,
                )
                optimizer.step()
                train_losses.append(float(objective.detach().cpu()))

            valid_loss = self._validation_loss(x_valid, y_valid, market_valid)
            self.training_history.append(
                {
                    "epoch": float(epoch),
                    "train_loss": float(np.mean(train_losses)),
                    "valid_mse": valid_loss,
                }
            )
            if valid_loss < best_loss - 1e-10:
                best_loss = valid_loss
                best_state = copy.deepcopy(self.network.state_dict())
                self.best_epoch = epoch
                stale = 0
            else:
                stale += 1
                if stale >= self.patience:
                    break

        if best_state is None:
            raise RuntimeError("training produced no valid checkpoint")
        self.network.load_state_dict(best_state)
        self.best_valid_loss = best_loss
        self.fitted = True
        return self

    def predict(self, dataset: object, segment: str = "test") -> pd.Series:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        validate_prediction_dataset(
            self.config,
            dataset,
            fixture_sha256=self.m7_fixture_sha256,
            state_binding_sha256=self.m7_state_binding_sha256,
        )
        features = dataset_features(dataset, segment)
        if tuple(str(column) for column in features.columns) != self.feature_names:
            raise ValueError("prediction feature order differs from fitted PeerLite")
        features = self.standardizer.transform(features)
        market = self._market_frame(dataset, segment)
        if market is not None:
            market = self.market_standardizer.transform(market)

        series: list[pd.Series] = []
        self.network.eval()
        with torch.no_grad():
            for index, x, _, market_row in self._date_batches(features, None, market):
                x_tensor = torch.as_tensor(x, device=self.device)
                market_tensor = (
                    None if market_row is None else torch.as_tensor(market_row, device=self.device)
                )
                prediction = self.network(x_tensor, market_tensor).cpu().numpy()
                series.append(pd.Series(prediction, index=index))
        output = pd.concat(series).sort_index()
        output.name = "score"
        return output

    def training_summary(self) -> dict[str, float | int]:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        return {
            "best_epoch": self.best_epoch,
            "best_valid_loss": self.best_valid_loss,
            "epochs_completed": len(self.training_history),
            "parameter_count": self.network.parameter_count,
        }

    def save_checkpoint(self, path: str | Path) -> None:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        target = Path(path)
        target.mkdir(parents=True, exist_ok=False)
        torch.save(self.network.state_dict(), target / "state_dict.pt")
        if self.m7_context is None:
            metadata = {
                "schema_version": "qlib_peerlite_checkpoint_v1",
                "model_id": self.model_id,
                "config": self.config,
                "feature_names": list(self.feature_names),
                "standardizer": self.standardizer.to_payload(),
                "market_standardizer": (
                    self.market_standardizer.to_payload() if self.market_gate_enabled else None
                ),
                "training_summary": self.training_summary(),
                "training_history": self.training_history,
            }
        else:
            metadata = build_checkpoint_v2_metadata(
                config=self.config,
                feature_names=list(self.feature_names),
                standardizer=self.standardizer.to_payload(),
                market_standardizer=(
                    self.market_standardizer.to_payload() if self.market_gate_enabled else None
                ),
                training_summary=self.training_summary(),
                training_history=self.training_history,
                state_dict=self.network.state_dict(),
                context=self.m7_context,
            )
        atomic_write_json(target / "metadata.json", metadata)

    @classmethod
    def load_checkpoint(
        cls,
        path: str | Path,
        *,
        device: str = "auto",
    ) -> PeerLiteModel:
        target = Path(path)
        metadata = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
        config = checkpoint_config_for_load(metadata)
        instance = cls(**config, device=device)
        state = torch.load(
            target / "state_dict.pt",
            map_location=instance.device,
            weights_only=True,
        )
        context = checkpoint_context_after_state_load(metadata, state)
        if context is not None:
            instance.m7_context = context
            instance.m7_fixture_sha256 = context.lease_event_sha256
            instance.m7_state_binding_sha256 = context.state_binding_sha256
        instance.network.load_state_dict(state)
        payload_owner = checkpoint_payload_for_load(metadata)
        instance.standardizer = TrainOnlyStandardizer.from_payload(payload_owner["standardizer"])
        if instance.market_gate_enabled:
            market_payload = payload_owner.get("market_standardizer")
            if not isinstance(market_payload, dict):
                raise ValueError("PeerLite market standardizer is missing")
            instance.market_standardizer = TrainOnlyStandardizer.from_payload(market_payload)
        feature_names = payload_owner.get("feature_names")
        if not isinstance(feature_names, list) or not feature_names:
            raise ValueError("PeerLite checkpoint feature names are invalid")
        instance.feature_names = tuple(str(name) for name in feature_names)
        summary = metadata.get("training_summary", {})
        instance.best_epoch = int(summary.get("best_epoch", -1))
        instance.best_valid_loss = float(summary.get("best_valid_loss", float("nan")))
        history = metadata.get("training_history")
        if not isinstance(history, list):
            raise ValueError("PeerLite checkpoint training history is invalid")
        instance.training_history = history
        instance.fitted = True
        return instance
