#!/usr/bin/env python3
"""Materialize the frozen M6 and executable CSI800 reference portfolios for M7."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from qlib_peerlite.evaluation.institutional import (
    AShareCostSchedule,
    backtest_weekly_executable,
)
from qlib_peerlite.evaluation.metrics import information_ratio
from qlib_peerlite.governance.artifacts import atomic_write_json, sha256_file


def _content_hash(value: dict[str, object]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def run(*, predictions: Path, execution_panel: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    prediction = pd.read_parquet(predictions)
    execution = pd.read_parquet(execution_panel)
    if (
        prediction["datetime"].max() >= pd.Timestamp("2025-01-01")
        or execution["datetime"].max() >= pd.Timestamp("2025-01-01")
    ):
        raise RuntimeError("reference portfolio input crosses final OOS")
    scores = prediction.set_index(["datetime", "instrument"])["score"].sort_index()
    panel = execution.set_index(["datetime", "instrument"]).sort_index()
    score_dates = scores.index.get_level_values("datetime").unique()
    panel = panel.loc[
        panel.index.get_level_values("datetime").isin(score_dates)
    ].copy()
    aligned_scores = scores.reindex(panel.index)
    panel["eligible"] = panel["eligible"].astype(bool) & aligned_scores.notna()
    panel["score"] = aligned_scores.fillna(-1e30)
    panel = panel[
        [
            "score",
            "forward_return",
            "carry_return",
            "overnight_return",
            "eligible",
            "can_buy",
            "can_sell",
            "adv20",
        ]
    ]
    inventory: dict[str, dict[str, object]] = {}
    for name, mode, stress in (
        ("peerlite_mse_base", "top_fraction", False),
        ("peerlite_mse_stress", "top_fraction", True),
        ("csi800_equal_weight_base", "equal_weight_universe", False),
        ("csi800_equal_weight_stress", "equal_weight_universe", True),
    ):
        returns, holdings, trades = backtest_weekly_executable(
            panel,
            mode=mode,
            costs=AShareCostSchedule(),
            stress=stress,
        )
        returns_path = output_dir / f"{name}_returns.parquet"
        holdings_path = output_dir / f"{name}_holdings.parquet"
        trades_path = output_dir / f"{name}_trades.parquet"
        returns.reset_index().to_parquet(returns_path, index=False)
        holdings.to_parquet(holdings_path, index=False)
        trades.to_parquet(trades_path, index=False)
        max_invested_weight = float(returns["invested_weight"].max())
        min_cash_weight = float(returns["cash_weight"].min())
        if max_invested_weight > 1.0 + 1e-12 or min_cash_weight < -1e-12:
            raise RuntimeError(f"{name} violates the frozen cash constraint")
        inventory[name] = {
            "returns_sha256": sha256_file(returns_path),
            "holdings_sha256": sha256_file(holdings_path),
            "trades_sha256": sha256_file(trades_path),
            "weekly_observations": len(returns),
            "net_information_ratio": information_ratio(returns["net_return"]),
            "average_turnover": float(returns["turnover"].mean()),
            "average_invested_weight": float(returns["invested_weight"].mean()),
            "max_invested_weight": max_invested_weight,
            "minimum_cash_weight": min_cash_weight,
            "unfilled_orders": int(returns["unfilled_orders"].sum()),
        }
    receipt: dict[str, object] = {
        "schema_version": "qlib_peerlite_m7_reference_portfolios_v1",
        "semantic_version": "m7_reference_portfolios_v1",
        "status": "PASS",
        "prediction_sha256": sha256_file(predictions),
        "execution_panel_sha256": sha256_file(execution_panel),
        "cost_spec": "contracts/immutable/m7_cost_spec_v1.json",
        "benchmark_spec": "contracts/immutable/m7_benchmark_spec_v1.json",
        "inventory": inventory,
        "final_oos_market_partitions_opened": False,
        "final_oos_metrics_computed": False,
    }
    receipt["content_sha256"] = _content_hash(receipt)
    atomic_write_json(output_dir / "reference_portfolios_receipt.json", receipt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--execution-panel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(
        predictions=args.predictions.resolve(),
        execution_panel=args.execution_panel.resolve(),
        output_dir=args.output_dir.resolve(),
    )


if __name__ == "__main__":
    main()
