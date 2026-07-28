from __future__ import annotations

import numpy as np
import pandas as pd

from qlib_peerlite.evaluation.bootstrap import bootstrap_ir_difference
from qlib_peerlite.evaluation.gates import promotion_decision
from qlib_peerlite.evaluation.portfolio import backtest_weekly_top_fraction


def portfolio_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=40)
    instruments = [f"S{i:03d}" for i in range(100)]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(index=index)
    frame["score"] = rng.normal(size=len(index))
    frame["forward_return"] = 0.002 * frame["score"] + rng.normal(0, 0.01, len(index))
    frame["tradable"] = True
    frame["adv20"] = 1_000_000_000.0
    return frame


def test_portfolio_respects_name_cap_and_charges_cost() -> None:
    returns, holdings = backtest_weekly_top_fraction(portfolio_panel())
    assert not returns.empty
    assert not holdings.empty
    assert holdings["weight"].max() <= 0.02 + 1e-12
    assert (returns["transaction_cost"] >= 0).all()
    assert (returns["net_return"] <= returns["gross_return"] + 1e-12).all()


def test_block_bootstrap_and_promotion_gate() -> None:
    rng = np.random.default_rng(9)
    benchmark = pd.Series(rng.normal(0.001, 0.01, 120))
    candidate = benchmark + 0.004
    result = bootstrap_ir_difference(candidate, benchmark, draws=200, block_length=4)
    assert result["ir_delta_ci_2_5"] > 0

    comparisons = pd.DataFrame(
        {
            "seed": np.repeat([7, 19, 42, 73, 101], 5),
            "fold_id": np.tile([f"f{i}" for i in range(5)], 5),
            "net_ir_delta": 0.2,
        }
    )
    decision = promotion_decision(
        comparisons,
        bootstrap_ci_low=0.01,
        best_year_contribution=0.4,
        stress_net_ir=0.2,
    )
    assert decision.decision == "PROMOTE"


def test_hard_data_failure_rejects_candidate() -> None:
    comparisons = pd.DataFrame(
        {"seed": [7], "fold_id": ["f1"], "net_ir_delta": [1.0]}
    )
    decision = promotion_decision(
        comparisons,
        bootstrap_ci_low=1.0,
        best_year_contribution=0.1,
        stress_net_ir=1.0,
        hard_gate_failures=["PIT manifest missing"],
    )
    assert decision.decision == "REJECT"
