from __future__ import annotations

import copy
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
        device: str = "auto",
        model_id: str = "B1_MLP",
    ) -> None:
        self.input_dim = input_dim
        self.seed = seed
        self.epochs = epochs
        self.patience = patience
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.device = resolve_device(device)
        self.model_id = model_id
        self.network = MLPNetwork(input_dim, hidden_dim, dropout).to(self.device)
        self.standardizer = TrainOnlyStandardizer()
        self.fitted = False
        self.training_history: list[dict[str, float]] = []

    def fit(self, dataset: object, **kwargs: Any) -> MLPBaseline:
        del kwargs
        seed_everything(self.seed)
        x_train, y_train = dataset_xy(dataset, "train")
        x_valid, y_valid = dataset_xy(dataset, "valid")
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
                torch.nn.utils.clip_grad_norm_(self.network.parameters(), 1.0)
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
        features = dataset_features(dataset, segment)
        transformed = self.standardizer.transform(features)
        tensor = torch.as_tensor(transformed.to_numpy(np.float32), device=self.device)
        self.network.eval()
        with torch.no_grad():
            values = self.network(tensor).cpu().numpy()
        return pd.Series(values, index=features.index, name="score")
