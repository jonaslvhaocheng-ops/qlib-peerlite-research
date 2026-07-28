from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

INDEX_NAMES = ("datetime", "instrument")


def ensure_panel_index(frame: pd.DataFrame | pd.Series) -> None:
    if not isinstance(frame.index, pd.MultiIndex):
        raise ValueError("panel must use a MultiIndex")
    if tuple(frame.index.names) != INDEX_NAMES:
        raise ValueError(f"panel index names must be {INDEX_NAMES}")
    if not frame.index.is_unique:
        raise ValueError("panel index must be unique")
    dates = frame.index.get_level_values("datetime")
    if dates.tz is not None:
        raise ValueError("daily panel datetime must be timezone-naive normalized session dates")
    if not dates.is_monotonic_increasing:
        raise ValueError("panel must be sorted by datetime then instrument")


def validate_training_panel(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    label_column: str,
    *,
    allow_missing_features: bool = False,
) -> None:
    ensure_panel_index(frame)
    required = [*feature_columns, label_column]
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    numeric = frame[required].apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError("training panel contains infinite values")
    if not allow_missing_features and numeric[list(feature_columns)].isna().any().any():
        raise ValueError("training features contain missing values")
    if numeric[label_column].isna().any():
        raise ValueError("training label contains missing values")


def score_frame(
    index: pd.MultiIndex,
    scores: np.ndarray,
    model_id: str,
    fold_id: str,
) -> pd.DataFrame:
    output = pd.DataFrame(
        {
            "score": np.asarray(scores, dtype=float).reshape(-1),
            "model_id": model_id,
            "fold_id": fold_id,
        },
        index=index,
    ).reset_index()
    if not np.isfinite(output["score"]).all():
        raise ValueError("model produced non-finite scores")
    return output[["datetime", "instrument", "score", "model_id", "fold_id"]]
