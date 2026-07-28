from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FoldSpec:
    fold_id: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    valid_start: pd.Timestamp
    valid_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def annual_folds(
    *,
    first_train_year: int = 2012,
    first_test_year: int = 2018,
    last_test_year: int = 2024,
    train_years: int = 5,
) -> list[FoldSpec]:
    folds: list[FoldSpec] = []
    for test_year in range(first_test_year, last_test_year + 1):
        valid_year = test_year - 1
        train_end_year = valid_year - 1
        train_start_year = max(first_train_year, train_end_year - train_years + 1)
        folds.append(
            FoldSpec(
                fold_id=f"wf_{test_year}",
                train_start=pd.Timestamp(f"{train_start_year}-01-01"),
                train_end=pd.Timestamp(f"{train_end_year}-12-31"),
                valid_start=pd.Timestamp(f"{valid_year}-01-01"),
                valid_end=pd.Timestamp(f"{valid_year}-12-31"),
                test_start=pd.Timestamp(f"{test_year}-01-01"),
                test_end=pd.Timestamp(f"{test_year}-12-31"),
            )
        )
    return folds


def purged_segment_masks(
    dates: pd.DatetimeIndex,
    label_end: pd.Series,
    fold: FoldSpec,
    *,
    embargo_sessions: int = 5,
) -> dict[str, pd.Series]:
    """Return temporal masks with explicit label purge and unassigned embargo."""

    date_series = pd.Series(dates, index=label_end.index)
    calendar = pd.DatetimeIndex(sorted(pd.unique(dates)))

    def shift_start(start: pd.Timestamp) -> pd.Timestamp:
        candidates = calendar[calendar >= start]
        if len(candidates) <= embargo_sessions:
            return pd.Timestamp.max
        return pd.Timestamp(candidates[embargo_sessions])

    effective_valid_start = shift_start(fold.valid_start)
    effective_test_start = shift_start(fold.test_start)

    train = (
        date_series.between(fold.train_start, fold.train_end)
        & (pd.to_datetime(label_end) < fold.valid_start)
    )
    valid = (
        date_series.between(effective_valid_start, fold.valid_end)
        & (pd.to_datetime(label_end) < fold.test_start)
    )
    test = date_series.between(effective_test_start, fold.test_end)
    return {"train": train, "valid": valid, "test": test}
