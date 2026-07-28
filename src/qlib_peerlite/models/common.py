from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import torch


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def resolve_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@dataclass
class TrainOnlyStandardizer:
    mean_: pd.Series | None = None
    scale_: pd.Series | None = None

    def fit(self, frame: pd.DataFrame) -> TrainOnlyStandardizer:
        numeric = frame.astype(float)
        self.mean_ = numeric.mean(axis=0)
        scale = numeric.std(axis=0, ddof=0)
        self.scale_ = scale.mask(scale < 1e-12, 1.0).fillna(1.0)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.mean_ is None or self.scale_ is None:
            raise RuntimeError("standardizer is not fitted")
        return (frame.astype(float) - self.mean_) / self.scale_

    def fit_transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        return self.fit(frame).transform(frame)

    def to_payload(self) -> dict[str, Any]:
        if self.mean_ is None or self.scale_ is None:
            raise RuntimeError("standardizer is not fitted")
        return {
            "columns": [str(column) for column in self.mean_.index],
            "mean": [float(value) for value in self.mean_.to_numpy()],
            "scale": [float(value) for value in self.scale_.to_numpy()],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TrainOnlyStandardizer:
        columns = payload.get("columns")
        mean = payload.get("mean")
        scale = payload.get("scale")
        if (
            not isinstance(columns, list)
            or not isinstance(mean, list)
            or not isinstance(scale, list)
            or not columns
            or len(columns) != len(mean)
            or len(columns) != len(scale)
            or len(set(columns)) != len(columns)
        ):
            raise ValueError("invalid standardizer payload")
        mean_series = pd.Series(np.asarray(mean, dtype=float), index=columns)
        scale_series = pd.Series(np.asarray(scale, dtype=float), index=columns)
        if (
            not np.isfinite(mean_series.to_numpy()).all()
            or not np.isfinite(scale_series.to_numpy()).all()
            or (scale_series <= 0).any()
        ):
            raise ValueError("standardizer payload contains invalid statistics")
        return cls(mean_=mean_series, scale_=scale_series)


def dataset_xy(dataset: object, segment: str) -> tuple[pd.DataFrame, pd.Series]:
    features = dataset.prepare(segment, col_set="feature")
    labels = dataset.prepare(segment, col_set="label")
    if isinstance(labels, pd.Series):
        target = labels
    else:
        if labels.shape[1] != 1:
            raise ValueError("label segment must contain exactly one column")
        target = labels.iloc[:, 0]
    common = features.index.intersection(target.index)
    features = features.loc[common].sort_index()
    target = target.loc[common].sort_index()
    valid = features.notna().all(axis=1) & target.notna()
    return features.loc[valid], target.loc[valid].astype(float)


def dataset_features(dataset: object, segment: str) -> pd.DataFrame:
    features = dataset.prepare(segment, col_set="feature").sort_index()
    if features.isna().any().any():
        raise ValueError("prediction features contain missing values")
    return features
