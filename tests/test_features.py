from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from qlib_peerlite.data.features import FEATURE_COLUMNS, build_causal_daily_features


def raw_panel(days: int = 90, instruments: int = 3) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=days)
    names = [f"S{i}" for i in range(instruments)]
    index = pd.MultiIndex.from_product([dates, names], names=["datetime", "instrument"])
    rng = np.random.default_rng(11)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, size=(days, instruments)), axis=0))
    close = close.reshape(-1)
    frame = pd.DataFrame(index=index)
    frame["open"] = close * (1 + rng.normal(0, 0.002, len(index)))
    frame["high"] = np.maximum(frame["open"], close) * 1.01
    frame["low"] = np.minimum(frame["open"], close) * 0.99
    frame["close"] = close
    frame["volume"] = rng.lognormal(14, 0.2, len(index))
    frame["amount"] = frame["volume"] * frame["close"]
    frame["turnover"] = rng.uniform(0.001, 0.08, len(index))
    frame["corporate_action"] = False
    return frame.sort_index()


def test_feature_registry_has_exactly_50_features() -> None:
    assert len(FEATURE_COLUMNS) == 50
    assert len(set(FEATURE_COLUMNS)) == 50


def test_future_poison_does_not_change_protected_prefix() -> None:
    baseline = raw_panel()
    poison = baseline.copy()
    cutoff = baseline.index.get_level_values("datetime").unique()[70]
    future = poison.index.get_level_values("datetime") > cutoff
    poison.loc[future, "close"] *= 50.0
    poison.loc[future, "amount"] *= 20.0

    base_features = build_causal_daily_features(baseline)
    poison_features = build_causal_daily_features(poison)
    protected = base_features.index.get_level_values("datetime") <= cutoff
    assert_frame_equal(
        base_features.loc[protected],
        poison_features.loc[protected],
        check_exact=True,
    )


def test_corporate_action_masks_trailing_window() -> None:
    raw = raw_panel(days=80, instruments=1)
    event_date = raw.index.get_level_values("datetime").unique()[65]
    raw.loc[(event_date, "S0"), "corporate_action"] = True
    features = build_causal_daily_features(raw)
    assert not bool(features.loc[(event_date, "S0"), "feature_eligible"])
    assert features.loc[(event_date, "S0"), list(FEATURE_COLUMNS)].isna().all()
