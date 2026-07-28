from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .common import dataset_features, dataset_xy


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
        colsample_bytree: float = 0.9,
        early_stopping_rounds: int = 50,
        model_id: str = "B0_LIGHTGBM",
        **kwargs: Any,
    ) -> None:
        from lightgbm import LGBMRegressor

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
            colsample_bytree=colsample_bytree,
            deterministic=True,
            force_col_wise=True,
            n_jobs=-1,
            verbosity=-1,
            **kwargs,
        )
        self.fitted = False

    def fit(self, dataset: object, **kwargs: Any) -> LightGBMBaseline:
        del kwargs
        from lightgbm import early_stopping, log_evaluation

        x_train, y_train = dataset_xy(dataset, "train")
        x_valid, y_valid = dataset_xy(dataset, "valid")
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
        self.fitted = True
        return self

    def predict(self, dataset: object, segment: str = "test") -> pd.Series:
        if not self.fitted:
            raise RuntimeError("model is not fitted")
        features = dataset_features(dataset, segment)
        prediction = np.asarray(self.model.predict(features), dtype=float)
        return pd.Series(prediction, index=features.index, name="score")
