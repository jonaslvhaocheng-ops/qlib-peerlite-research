from __future__ import annotations

import pandas as pd

from qlib_peerlite.data.splits import FoldSpec, annual_folds, purged_segment_masks


def test_annual_fold_boundaries() -> None:
    folds = annual_folds(first_test_year=2018, last_test_year=2020)
    assert [fold.fold_id for fold in folds] == ["wf_2018", "wf_2019", "wf_2020"]
    assert folds[0].train_start == pd.Timestamp("2012-01-01")
    assert folds[0].train_end == pd.Timestamp("2016-12-31")


def test_cross_boundary_labels_are_purged_and_embargoed() -> None:
    dates = pd.bdate_range("2020-12-01", "2022-01-31")
    index = pd.RangeIndex(len(dates))
    label_end = pd.Series(dates + pd.offsets.BDay(5), index=index)
    fold = FoldSpec(
        "test",
        pd.Timestamp("2020-12-01"),
        pd.Timestamp("2020-12-31"),
        pd.Timestamp("2021-01-01"),
        pd.Timestamp("2021-12-31"),
        pd.Timestamp("2022-01-01"),
        pd.Timestamp("2022-01-31"),
    )
    masks = purged_segment_masks(
        pd.DatetimeIndex(dates),
        label_end,
        fold,
        embargo_sessions=5,
    )
    assert (label_end[masks["train"]] < fold.valid_start).all()
    assert (label_end[masks["valid"]] < fold.test_start).all()
    first_valid = dates[masks["valid"].to_numpy()][0]
    assert first_valid > fold.valid_start
