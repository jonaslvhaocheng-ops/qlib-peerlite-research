from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qlib_peerlite.data.market_state import (
    DAILY_STATE_COLUMNS,
    MarketStateError,
    aggregate_daily_state,
    join_market_state,
    select_state_population,
    validate_state_product,
)


def _state_input() -> pd.DataFrame:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2024-01-02"), "000001.SZ"),
            (pd.Timestamp("2024-01-02"), "000002.SZ"),
            (pd.Timestamp("2024-01-02"), "000003.SZ"),
            (pd.Timestamp("2024-01-03"), "000001.SZ"),
            (pd.Timestamp("2024-01-03"), "000002.SZ"),
            (pd.Timestamp("2024-01-03"), "000003.SZ"),
        ],
        names=["datetime", "instrument"],
    )
    return pd.DataFrame(
        {
            "universe_member": True,
            "listing_age_eligible": True,
            "is_active": True,
            "special_status_forbidden": False,
            "special_status_unknown": False,
            "price_domain_valid": True,
            "feature_eligible": True,
            "ret_mean_20": [0.01, 0.02, 0.03, -0.02, 0.01, 0.04],
            "ret_std_20": [0.10, 0.30, 0.20, 0.25, 0.15, 0.35],
            "ret_1d": [0.01, -0.02, 0.00, 0.03, -0.01, 0.02],
            "turnover_mean_20": [0.50, 0.20, 0.40, 0.60, 0.10, 0.30],
        },
        index=index,
    )


def test_state_population_and_daily_aggregation_are_formula_and_order_stable() -> None:
    selected = select_state_population(_state_input())
    state = aggregate_daily_state(
        selected,
        required_dates=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]),
    )
    validate_state_product(
        state,
        expected_dates=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]),
    )

    first = state.loc[pd.Timestamp("2024-01-02")]
    assert first["mkt_trend_20"] == pytest.approx(0.02)
    assert first["mkt_vol_20"] == pytest.approx(0.20)
    assert first["mkt_breadth_1d"] == pytest.approx(1.0 / 3.0)
    assert first["mkt_turnover_20"] == pytest.approx(0.40)
    assert first["population_count"] == 3
    assert list(state.columns) == [
        *DAILY_STATE_COLUMNS,
        "population_count",
        "population_keyset_sha256",
        "state_sha256",
    ]

    reordered = selected.sort_index(level=["datetime", "instrument"], ascending=[True, False])
    reordered_state = aggregate_daily_state(
        reordered.sort_index(),
        required_dates=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]),
    )
    pd.testing.assert_frame_equal(state, reordered_state)


def test_state_population_is_t_known_and_physically_rejects_forbidden_fields() -> None:
    frame = _state_input()
    frame.loc[(pd.Timestamp("2024-01-02"), "000002.SZ"), "universe_member"] = False
    frame.loc[(pd.Timestamp("2024-01-02"), "000003.SZ"), "listing_age_eligible"] = False
    frame.loc[(pd.Timestamp("2024-01-03"), "000001.SZ"), "special_status_forbidden"] = True
    frame.loc[(pd.Timestamp("2024-01-03"), "000002.SZ"), "special_status_unknown"] = True
    frame.loc[(pd.Timestamp("2024-01-03"), "000003.SZ"), "price_domain_valid"] = False
    selected = select_state_population(frame)

    assert selected.index.tolist() == [(pd.Timestamp("2024-01-02"), "000001.SZ")]

    for forbidden in (
        "label",
        "label_open",
        "execution_at_price_limit",
        "execution_halted",
        "label_crosses_corporate_action",
        "purge_or_embargo",
    ):
        poisoned = _state_input()
        poisoned[forbidden] = 0
        with pytest.raises(MarketStateError, match="forbidden"):
            select_state_population(poisoned)


def test_future_rows_and_label_like_poison_cannot_change_past_daily_state() -> None:
    baseline = aggregate_daily_state(select_state_population(_state_input()))
    future_poison = _state_input()
    future_mask = future_poison.index.get_level_values("datetime") == pd.Timestamp("2024-01-03")
    future_poison.loc[future_mask, "ret_mean_20"] = 999.0
    future_poison.loc[future_mask, "ret_std_20"] = 999.0
    future_poison.loc[future_mask, "ret_1d"] = -999.0
    future_poison.loc[future_mask, "turnover_mean_20"] = 999.0
    poisoned_state = aggregate_daily_state(select_state_population(future_poison))

    pd.testing.assert_series_equal(
        baseline.loc[pd.Timestamp("2024-01-02")],
        poisoned_state.loc[pd.Timestamp("2024-01-02")],
    )
    with_label = _state_input()
    with_label["label"] = np.arange(len(with_label), dtype=float)
    with pytest.raises(MarketStateError, match="forbidden"):
        select_state_population(with_label)


def test_state_product_fails_closed_for_empty_dates_nonfinite_or_bad_keys() -> None:
    frame = _state_input()
    frame.loc[
        frame.index.get_level_values("datetime") == pd.Timestamp("2024-01-03"), "feature_eligible"
    ] = False
    selected = select_state_population(frame)
    with pytest.raises(MarketStateError, match="empty"):
        aggregate_daily_state(
            selected,
            required_dates=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]),
        )

    nonfinite = _state_input()
    nonfinite.loc[(pd.Timestamp("2024-01-02"), "000001.SZ"), "ret_mean_20"] = np.inf
    selected_nonfinite = select_state_population(nonfinite)
    assert (pd.Timestamp("2024-01-02"), "000001.SZ") not in selected_nonfinite.index

    duplicate = _state_input()
    duplicate = pd.concat([duplicate, duplicate.iloc[[0]]]).sort_index()
    with pytest.raises(ValueError, match="unique"):
        select_state_population(duplicate)


def test_exact_date_join_broadcasts_one_daily_state_and_rejects_missing_dates() -> None:
    state = aggregate_daily_state(select_state_population(_state_input()))
    model_index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2024-01-02"), "000001.SZ"),
            (pd.Timestamp("2024-01-02"), "000009.SZ"),
            (pd.Timestamp("2024-01-03"), "000001.SZ"),
        ],
        names=["datetime", "instrument"],
    )
    model_rows = pd.DataFrame({"f0": [1.0, 2.0, 3.0]}, index=model_index)
    joined = join_market_state(model_rows, state)

    assert list(joined.columns) == list(DAILY_STATE_COLUMNS)
    assert joined.loc[(pd.Timestamp("2024-01-02"), "000001.SZ")].equals(
        joined.loc[(pd.Timestamp("2024-01-02"), "000009.SZ")]
    )
    with pytest.raises(MarketStateError, match="missing"):
        join_market_state(model_rows, state.drop(pd.Timestamp("2024-01-03")))
