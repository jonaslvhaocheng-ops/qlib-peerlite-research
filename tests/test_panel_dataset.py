from __future__ import annotations

import pandas as pd
import pytest

from qlib_peerlite.data.dataset import PanelDataset


def _dataset() -> PanelDataset:
    dates = pd.bdate_range("2024-01-02", periods=2)
    index = pd.MultiIndex.from_product(
        [dates, ["000001.SZ", "000002.SZ"]], names=["datetime", "instrument"]
    )
    frame = pd.DataFrame(
        {
            "f0": [1.0, 2.0, 3.0, 4.0],
            "label": [0.1, 0.2, 0.3, 0.4],
            "old_market": [9.0] * 4,
            "mkt_trend_20": [0.01, 0.01, 0.02, 0.02],
            "mkt_vol_20": [0.1, 0.1, 0.2, 0.2],
        },
        index=index,
    )
    return PanelDataset(
        frame=frame,
        segments={"train": (dates[0], dates[-1])},
        feature_columns=["f0"],
        market_columns=["old_market"],
        market_state_columns=["mkt_trend_20", "mkt_vol_20"],
    )


def test_panel_dataset_exposes_separate_market_state_colset_and_rejects_unknown_strings() -> None:
    dataset = _dataset()

    state = dataset.prepare("train", col_set="market_state")
    assert list(state.columns) == ["mkt_trend_20", "mkt_vol_20"]
    assert list(dataset.prepare("train", col_set="market").columns) == ["old_market"]
    with pytest.raises(ValueError, match="unsupported col_set"):
        dataset.prepare("train", col_set="definitely_not_a_colset")
