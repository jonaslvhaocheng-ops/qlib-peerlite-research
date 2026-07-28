from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

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
        if features.ndim != 2:
            raise ValueError("features must have shape [stocks, features]")
        n_stocks = features.shape[0]
        if n_stocks == 0:
            raise ValueError("cross-section cannot be empty")
        if valid_mask is None:
            valid_mask = torch.ones(n_stocks, dtype=torch.bool, device=features.device)
        if valid_mask.shape != (n_stocks,):
            raise ValueError("valid_mask must have shape [stocks]")
        if not valid_mask.any():
            raise ValueError("cross-section must contain at least one valid stock")

        hidden = self.encoder(features)
        if self.market_gate_enabled:
            if market_state is None:
                raise ValueError("market_state is required for the enabled market gate")
            if market_state.ndim == 1:
                market_state = market_state.unsqueeze(0)
            gate = self.market_gate(market_state).reshape(1, self.hidden_dim)
            hidden = hidden * gate

        valid_hidden = hidden[valid_mask]
        assignment = torch.softmax(self.assignment(valid_hidden), dim=-1)
        denominator = assignment.sum(dim=0).clamp_min(1e-8).unsqueeze(-1)
        prototypes = assignment.transpose(0, 1) @ valid_hidden / denominator
        context, attention = self.attention(
            hidden.unsqueeze(0),
            prototypes.unsqueeze(0),
            prototypes.unsqueeze(0),
            need_weights=True,
            average_attn_weights=False,
        )
        context = context.squeeze(0)
        relative = torch.cat([hidden, hidden - context], dim=-1)
        score = self.head(relative).squeeze(-1)
        score = torch.where(valid_mask, score, torch.zeros_like(score))
        if return_attention:
            return score, assignment, attention.squeeze(0)
        return score


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
        device: str = "auto",
        model_id: str | None = None,
    ) -> None:
        if loss not in {"mse", "ccc"}:
            raise ValueError("loss must be mse or ccc")
        self.input_dim = input_dim
        self.loss_name = loss
        self.seed = seed
        self.epochs = epochs
        self.patience = patience
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.gradient_clip_norm = gradient_clip_norm
        self.device = resolve_device(device)
        self.model_id = model_id or (
            f"PEERLITE_K{num_peers}_{loss.upper()}" + ("_GATE" if market_gate else "")
        )
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
        self.fitted = False
        self.training_history: list[dict[str, float]] = []

    def _market_frame(self, dataset: object, segment: str) -> pd.DataFrame | None:
        if not self.market_gate_enabled:
            return None
        market = dataset.prepare(segment, col_set="market").sort_index()
        if market.empty or market.shape[1] == 0:
            raise ValueError("market-gated PeerLite requires market columns")
        return market

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

    def _validation_loss(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        market: pd.DataFrame | None,
    ) -> float:
        self.network.eval()
        values: list[float] = []
        with torch.no_grad():
            for _, x, y, market_row in self._date_batches(features, target, market):
                x_tensor = torch.as_tensor(x, device=self.device)
                y_tensor = torch.as_tensor(y, device=self.device)
                market_tensor = (
                    None if market_row is None else torch.as_tensor(market_row, device=self.device)
                )
                prediction = self.network(x_tensor, market_tensor)
                values.append(float(nn.functional.mse_loss(prediction, y_tensor).cpu()))
        return float(np.mean(values))

    def fit(self, dataset: object, **kwargs: Any) -> PeerLiteModel:
        del kwargs
        seed_everything(self.seed)
        x_train, y_train = dataset_xy(dataset, "train")
        x_valid, y_valid = dataset_xy(dataset, "valid")
        x_train = self.standardizer.fit_transform(x_train)
        x_valid = self.standardizer.transform(x_valid)

        market_train = self._market_frame(dataset, "train")
        market_valid = self._market_frame(dataset, "valid")
        if market_train is not None and market_valid is not None:
            market_train = self.market_standardizer.fit_transform(market_train)
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
            for _, x, y, market_row in batches:
                x_tensor = torch.as_tensor(x, device=self.device)
                y_tensor = torch.as_tensor(y, device=self.device)
                market_tensor = (
                    None if market_row is None else torch.as_tensor(market_row, device=self.device)
                )
                optimizer.zero_grad(set_to_none=True)
                prediction = self.network(x_tensor, market_tensor)
                objective = self._loss(prediction, y_tensor)
                objective.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.network.parameters(), self.gradient_clip_norm
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
                stale = 0
            else:
                stale += 1
                if stale >= self.patience:
                    break

        if best_state is None:
            raise RuntimeError("training produced no valid checkpoint")
        self.network.load_state_dict(best_state)
        self.fitted = True
        return self

    def predict(self, dataset: object, segment: str = "test") -> pd.Series:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        features = self.standardizer.transform(dataset_features(dataset, segment))
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
