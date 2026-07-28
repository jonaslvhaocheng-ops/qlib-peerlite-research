from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

from qlib_peerlite.governance.artifacts import atomic_write_json

from .common import (
    TrainOnlyStandardizer,
    dataset_features,
    dataset_xy,
    resolve_device,
    seed_everything,
)


class MLPNetwork(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64, dropout: float = 0.1) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.layers(values).squeeze(-1)


class MLPBaseline:
    """Train-fold-standardized PyTorch MLP baseline."""

    def __init__(
        self,
        input_dim: int,
        *,
        hidden_dim: int = 64,
        dropout: float = 0.1,
        seed: int = 7,
        epochs: int = 100,
        patience: int = 12,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
        batch_size: int = 2048,
        gradient_clip_norm: float = 1.0,
        device: str = "auto",
        model_id: str = "B1_MLP",
    ) -> None:
        seed_everything(seed)
        self.input_dim = input_dim
        self.seed = seed
        self.epochs = epochs
        self.patience = patience
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.gradient_clip_norm = gradient_clip_norm
        self.device = resolve_device(device)
        self.model_id = model_id
        self.config = {
            "input_dim": input_dim,
            "hidden_dim": hidden_dim,
            "dropout": dropout,
            "seed": seed,
            "epochs": epochs,
            "patience": patience,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "batch_size": batch_size,
            "gradient_clip_norm": gradient_clip_norm,
            "model_id": model_id,
        }
        self.network = MLPNetwork(input_dim, hidden_dim, dropout).to(self.device)
        self.standardizer = TrainOnlyStandardizer()
        self.feature_names: tuple[str, ...] = ()
        self.fitted = False
        self.training_history: list[dict[str, float]] = []
        self.best_epoch = -1
        self.best_valid_loss = float("nan")

    def fit(self, dataset: object, **kwargs: Any) -> MLPBaseline:
        del kwargs
        seed_everything(self.seed)
        x_train, y_train = dataset_xy(dataset, "train")
        x_valid, y_valid = dataset_xy(dataset, "valid")
        self.feature_names = tuple(str(column) for column in x_train.columns)
        x_train = self.standardizer.fit_transform(x_train)
        x_valid = self.standardizer.transform(x_valid)

        train_x = torch.as_tensor(x_train.to_numpy(np.float32), device=self.device)
        train_y = torch.as_tensor(y_train.to_numpy(np.float32), device=self.device)
        valid_x = torch.as_tensor(x_valid.to_numpy(np.float32), device=self.device)
        valid_y = torch.as_tensor(y_valid.to_numpy(np.float32), device=self.device)

        optimizer = torch.optim.AdamW(
            self.network.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay
        )
        loss_fn = nn.MSELoss()
        generator = torch.Generator(device="cpu").manual_seed(self.seed)
        best_loss = float("inf")
        best_state: dict[str, torch.Tensor] | None = None
        stale = 0

        for epoch in range(self.epochs):
            self.network.train()
            permutation = torch.randperm(len(train_x), generator=generator)
            losses: list[float] = []
            for start in range(0, len(permutation), self.batch_size):
                idx = permutation[start : start + self.batch_size].to(self.device)
                optimizer.zero_grad(set_to_none=True)
                loss = loss_fn(self.network(train_x[idx]), train_y[idx])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.network.parameters(), self.gradient_clip_norm
                )
                optimizer.step()
                losses.append(float(loss.detach().cpu()))

            self.network.eval()
            with torch.no_grad():
                valid_loss = float(loss_fn(self.network(valid_x), valid_y).cpu())
            self.training_history.append(
                {
                    "epoch": float(epoch),
                    "train_loss": float(np.mean(losses)),
                    "valid_loss": valid_loss,
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
        features = dataset_features(dataset, segment)
        if tuple(str(column) for column in features.columns) != self.feature_names:
            raise ValueError("prediction feature order differs from fitted MLP")
        transformed = self.standardizer.transform(features)
        tensor = torch.as_tensor(transformed.to_numpy(np.float32), device=self.device)
        self.network.eval()
        with torch.no_grad():
            values = self.network(tensor).cpu().numpy()
        return pd.Series(values, index=features.index, name="score")

    def training_summary(self) -> dict[str, float | int]:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        return {
            "best_epoch": self.best_epoch,
            "best_valid_loss": self.best_valid_loss,
            "epochs_completed": len(self.training_history),
        }

    def save_checkpoint(self, path: str | Path) -> None:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        target = Path(path)
        target.mkdir(parents=True, exist_ok=False)
        weights_path = target / "state_dict.pt"
        torch.save(self.network.state_dict(), weights_path)
        atomic_write_json(
            target / "metadata.json",
            {
                "schema_version": "qlib_peerlite_mlp_checkpoint_v1",
                "model_id": self.model_id,
                "config": self.config,
                "feature_names": list(self.feature_names),
                "standardizer": self.standardizer.to_payload(),
                "training_summary": self.training_summary(),
                "training_history": self.training_history,
            },
        )

    @classmethod
    def load_checkpoint(
        cls,
        path: str | Path,
        *,
        device: str = "auto",
    ) -> MLPBaseline:
        target = Path(path)
        metadata = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
        if metadata.get("schema_version") != "qlib_peerlite_mlp_checkpoint_v1":
            raise ValueError("unsupported MLP checkpoint")
        config = metadata.get("config")
        if not isinstance(config, dict):
            raise ValueError("MLP checkpoint config is missing")
        instance = cls(**config, device=device)
        state = torch.load(
            target / "state_dict.pt",
            map_location=instance.device,
            weights_only=True,
        )
        instance.network.load_state_dict(state)
        instance.standardizer = TrainOnlyStandardizer.from_payload(metadata["standardizer"])
        instance.feature_names = tuple(metadata["feature_names"])
        summary = metadata.get("training_summary", {})
        instance.best_epoch = int(summary.get("best_epoch", -1))
        instance.best_valid_loss = float(summary.get("best_valid_loss", float("nan")))
        history = metadata.get("training_history", [])
        if not isinstance(history, list):
            raise ValueError("MLP checkpoint training history is invalid")
        instance.training_history = history
        instance.fitted = True
        return instance
