from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qlib_peerlite.evaluation.institutional import (
    AShareCostSchedule,
    backtest_weekly_executable,
)


def _panel() -> pd.DataFrame:
    dates = pd.bdate_range("2023-08-21", periods=15)
    instruments = ["A", "B", "C", "D"]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    frame = pd.DataFrame(index=index)
    frame["score"] = np.tile([4.0, 3.0, 2.0, 1.0], len(dates))
    frame["forward_return"] = 0.01
    frame["carry_return"] = 0.01
    frame["overnight_return"] = 0.0
    frame["eligible"] = True
    frame["can_buy"] = True
    frame["can_sell"] = True
    frame["adv20"] = 1_000_000_000.0
    return frame


def test_cost_schedule_is_side_and_effective_date_aware() -> None:
    costs = AShareCostSchedule()
    before = pd.Timestamp("2023-08-25")
    after = pd.Timestamp("2023-09-01")
    assert costs.side_cost_bps(before, side="sell") == pytest.approx(23.1)
    assert costs.side_cost_bps(after, side="sell") == pytest.approx(18.1)
    assert costs.side_cost_bps(after, side="buy") == pytest.approx(13.1)
    assert costs.side_cost_bps(after, side="buy", stress=True) == pytest.approx(23.1)


def test_unfilled_order_retains_position_and_capacity_caps_trade() -> None:
    frame = _panel()
    friday = pd.Timestamp("2023-08-25")
    next_friday = pd.Timestamp("2023-09-01")
    frame.loc[(next_friday, "A"), "score"] = 0.0
    frame.loc[(next_friday, "D"), "score"] = 9.0
    frame.loc[(next_friday, "A"), "can_sell"] = False
    frame.loc[(next_friday, "D"), "can_buy"] = False
    returns, holdings, trades = backtest_weekly_executable(
        frame,
        top_fraction=0.25,
        max_name_weight=1.0,
    )
    first = holdings.loc[holdings["datetime"] == friday].set_index("instrument")
    second = holdings.loc[holdings["datetime"] == next_friday].set_index("instrument")
    assert first.loc["A", "weight"] == pytest.approx(0.5)
    assert second.loc["A", "weight"] == pytest.approx(0.5)
    failed = trades.loc[
        (trades["datetime"] == next_friday) & (trades["instrument"].isin(["A", "D"]))
    ]
    assert (failed["filled_weight"] == 0.0).all()
    assert returns.loc[next_friday, "unfilled_orders"] == 2


def test_equal_weight_benchmark_is_distinct_from_top_fraction() -> None:
    frame = _panel()
    candidate, candidate_holdings, _ = backtest_weekly_executable(
        frame,
        mode="top_fraction",
        top_fraction=0.25,
        max_name_weight=1.0,
    )
    benchmark, benchmark_holdings, _ = backtest_weekly_executable(
        frame,
        mode="equal_weight_universe",
        max_name_weight=1.0,
    )
    assert candidate_holdings.groupby("datetime").size().eq(1).all()
    assert benchmark_holdings.groupby("datetime").size().eq(4).all()
    assert (candidate["transaction_cost"] >= 0).all()
    assert (benchmark["transaction_cost"] >= 0).all()


def test_blocked_sell_cannot_fund_replacement_or_create_leverage() -> None:
    frame = _panel()
    next_friday = pd.Timestamp("2023-09-01")
    frame.loc[(next_friday, "A"), "score"] = 0.0
    frame.loc[(next_friday, "D"), "score"] = 9.0
    frame.loc[(next_friday, "A"), "can_sell"] = False

    returns, holdings, trades = backtest_weekly_executable(
        frame,
        top_fraction=0.25,
        max_name_weight=1.0,
    )

    second = holdings.loc[holdings["datetime"] == next_friday].set_index("instrument")
    assert second.loc["A", "weight"] == pytest.approx(0.5)
    assert second.loc["D", "weight"] == pytest.approx(0.5)
    assert returns.loc[next_friday, "invested_weight"] == pytest.approx(1.0)
    assert returns.loc[next_friday, "cash_weight"] == pytest.approx(0.0)
    assert returns["invested_weight"].le(1.0 + 1e-12).all()
    blocked_replacement = trades.loc[
        (trades["datetime"] == next_friday) & (trades["instrument"] == "D")
    ].iloc[0]
    assert blocked_replacement["filled_weight"] == pytest.approx(0.5)
    assert blocked_replacement["unfilled_weight"] == pytest.approx(0.5)
