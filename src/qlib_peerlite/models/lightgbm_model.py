from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qlib_peerlite.governance.artifacts import atomic_write_json

from .common import TrainOnlyStandardizer, dataset_features, dataset_xy


class LightGBMBaseline:
    """Qlib-compatible LightGBM regression baseline."""

    def __init__(
        self,
        *,
        seed: int = 7,
        learning_rate: float = 0.03,
        n_estimators: int = 500,
        num_leaves: int = 31,
        max_depth: int = -1,
        min_child_samples: int = 50,
        subsample: float = 0.9,
        subsample_freq: int = 1,
        colsample_bytree: float = 0.9,
        reg_alpha: float = 0.0,
        reg_lambda: float = 0.0,
        early_stopping_rounds: int = 50,
        n_jobs: int = 16,
        model_id: str = "B0_LIGHTGBM",
        **kwargs: Any,
    ) -> None:
        from lightgbm import LGBMRegressor

        self.config = {
            "seed": seed,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "num_leaves": num_leaves,
            "max_depth": max_depth,
            "min_child_samples": min_child_samples,
            "subsample": subsample,
            "subsample_freq": subsample_freq,
            "colsample_bytree": colsample_bytree,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "early_stopping_rounds": early_stopping_rounds,
            "n_jobs": n_jobs,
            "model_id": model_id,
        }
        self.model_id = model_id
        self.early_stopping_rounds = early_stopping_rounds
        self.model = LGBMRegressor(
            objective="regression",
            random_state=seed,
            learning_rate=learning_rate,
            n_estimators=n_estimators,
            num_leaves=num_leaves,
            max_depth=max_depth,
            min_child_samples=min_child_samples,
            subsample=subsample,
            subsample_freq=subsample_freq,
            colsample_bytree=colsample_bytree,
            reg_alpha=reg_alpha,
            reg_lambda=reg_lambda,
            deterministic=True,
            force_col_wise=True,
            n_jobs=n_jobs,
            verbosity=-1,
            **kwargs,
        )
        self.standardizer = TrainOnlyStandardizer()
        self.feature_names: tuple[str, ...] = ()
        self.booster: Any | None = None
        self.best_iteration = 0
        self.best_valid_l2 = float("nan")
        self.fitted = False

    def fit(self, dataset: object, **kwargs: Any) -> LightGBMBaseline:
        del kwargs
        from lightgbm import early_stopping, log_evaluation

        x_train, y_train = dataset_xy(dataset, "train")
        x_valid, y_valid = dataset_xy(dataset, "valid")
        self.feature_names = tuple(str(column) for column in x_train.columns)
        x_train = self.standardizer.fit_transform(x_train)
        x_valid = self.standardizer.transform(x_valid)
        self.model.fit(
            x_train,
            y_train,
            eval_set=[(x_valid, y_valid)],
            eval_metric="l2",
            callbacks=[
                early_stopping(self.early_stopping_rounds, verbose=False),
                log_evaluation(period=0),
            ],
        )
        self.booster = self.model.booster_
        self.best_iteration = int(self.model.best_iteration_ or self.config["n_estimators"])
        self.best_valid_l2 = float(self.model.best_score_["valid_0"]["l2"])
        self.fitted = True
        return self

    def predict(self, dataset: object, segment: str = "test") -> pd.Series:
        if not self.fitted or self.booster is None:
            raise RuntimeError("model is not fitted")
        features = dataset_features(dataset, segment)
        if tuple(str(column) for column in features.columns) != self.feature_names:
            raise ValueError("prediction feature order differs from fitted LightGBM")
        transformed = self.standardizer.transform(features)
        prediction = np.asarray(self.booster.predict(transformed), dtype=float)
        return pd.Series(prediction, index=features.index, name="score")

    def training_summary(self) -> dict[str, float | int]:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        return {
            "best_iteration": self.best_iteration,
            "best_valid_l2": self.best_valid_l2,
        }

    def save_checkpoint(self, path: str | Path) -> None:
        if not self.fitted or self.booster is None:
            raise RuntimeError("model is not fitted")
        target = Path(path)
        target.mkdir(parents=True, exist_ok=False)
        self.booster.save_model(str(target / "model.txt"))
        atomic_write_json(
            target / "metadata.json",
            {
                "schema_version": "qlib_peerlite_lightgbm_checkpoint_v1",
                "model_id": self.model_id,
                "config": self.config,
                "feature_names": list(self.feature_names),
                "standardizer": self.standardizer.to_payload(),
                "training_summary": self.training_summary(),
            },
        )

    @classmethod
    def load_checkpoint(cls, path: str | Path) -> LightGBMBaseline:
        from lightgbm import Booster

        target = Path(path)
        metadata = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
        if metadata.get("schema_version") != "qlib_peerlite_lightgbm_checkpoint_v1":
            raise ValueError("unsupported LightGBM checkpoint")
        config = metadata.get("config")
        if not isinstance(config, dict):
            raise ValueError("LightGBM checkpoint config is missing")
        instance = cls(**config)
        instance.booster = Booster(model_file=str(target / "model.txt"))
        instance.standardizer = TrainOnlyStandardizer.from_payload(metadata["standardizer"])
        instance.feature_names = tuple(metadata["feature_names"])
        summary = metadata.get("training_summary", {})
        instance.best_iteration = int(summary.get("best_iteration", 0))
        instance.best_valid_l2 = float(summary.get("best_valid_l2", float("nan")))
        instance.fitted = True
        return instance
