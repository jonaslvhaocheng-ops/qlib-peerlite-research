#!/usr/bin/env python3
"""Evaluate the five frozen PeerLite seeds against frozen LightGBM."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from qlib_peerlite.evaluation.bootstrap import bootstrap_ir_difference
from qlib_peerlite.evaluation.institutional import backtest_weekly_executable
from qlib_peerlite.evaluation.metrics import information_ratio, max_drawdown
from qlib_peerlite.governance.artifacts import atomic_write_json, sha256_file


def canonical_hash(value: dict[str, object]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(
        json.dumps(
            unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def load_scores(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["datetime", "instrument", "score", "fold_id"])
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.normalize()
    frame["instrument"] = frame["instrument"].astype(str)
    if frame.duplicated(["datetime", "instrument"]).any():
        raise RuntimeError(f"duplicate predictions: {path}")
    return frame


def portfolio(panel: pd.DataFrame, scores: pd.DataFrame, stress: bool) -> pd.DataFrame:
    merged = panel.merge(scores[["datetime", "instrument", "score"]], on=["datetime", "instrument"])
    indexed = merged.set_index(["datetime", "instrument"]).sort_index()
    returns, _, _ = backtest_weekly_executable(indexed, stress=stress)
    return returns


def run(
    execution_panel: Path,
    baseline_predictions: Path,
    seed7_predictions: Path,
    confirmation_dir: Path,
    output: Path,
) -> None:
    raise RuntimeError(
        "M8 complete-path evaluation is permanently closed; "
        "the retained confirmation is incomplete"
    )
    # The frozen implementation remains below for forensic review only.
    panel = pd.read_parquet(execution_panel)
    panel["datetime"] = pd.to_datetime(panel["datetime"]).dt.normalize()
    panel["instrument"] = panel["instrument"].astype(str)
    baseline_scores = load_scores(baseline_predictions)
    baseline_base = portfolio(panel, baseline_scores, False)
    baseline_stress = portfolio(panel, baseline_scores, True)
    seed_paths = {7: seed7_predictions}
    for seed in (19, 42, 73, 101):
        seed_paths[seed] = confirmation_dir / f"seed_{seed}/predictions.parquet"
    seed_rows: list[dict[str, object]] = []
    fold_positive: list[bool] = []
    seed_base_returns: list[pd.Series] = []
    seed_base_frames: list[pd.DataFrame] = []
    for seed, path in seed_paths.items():
        scores = load_scores(path)
        base = portfolio(panel, scores, False)
        stress = portfolio(panel, scores, True)
        aligned = base["net_return"].align(baseline_base["net_return"], join="inner")
        delta = information_ratio(aligned[0]) - information_ratio(aligned[1])
        boot = bootstrap_ir_difference(aligned[0], aligned[1])
        by_fold: dict[str, float] = {}
        for fold_id, part in scores.groupby("fold_id"):
            candidate_fold = portfolio(panel, part, False)["net_return"]
            baseline_fold_scores = baseline_scores[
                (baseline_scores["datetime"] >= part["datetime"].min())
                & (baseline_scores["datetime"] <= part["datetime"].max())
            ]
            benchmark_fold = portfolio(panel, baseline_fold_scores, False)["net_return"]
            pair = candidate_fold.align(benchmark_fold, join="inner")
            fold_delta = information_ratio(pair[0]) - information_ratio(pair[1])
            by_fold[str(fold_id)] = fold_delta
            fold_positive.append(fold_delta > 0)
        seed_base_returns.append(base["net_return"].rename(str(seed)))
        seed_base_frames.append(base)
        seed_rows.append(
            {
                "seed": seed,
                "base_net_ir": information_ratio(base["net_return"]),
                "stress_net_ir": information_ratio(stress["net_return"]),
                "baseline_base_net_ir": information_ratio(baseline_base["net_return"]),
                "net_ir_delta": delta,
                "bootstrap": boot,
                "fold_ir_deltas": by_fold,
                "prediction_sha256": sha256_file(path),
            }
        )
    positive_seed_fraction = float(np.mean([row["net_ir_delta"] > 0 for row in seed_rows]))
    positive_fold_fraction = float(np.mean(fold_positive))
    mean_candidate = pd.concat(seed_base_returns, axis=1).mean(axis=1)
    mean_bootstrap = bootstrap_ir_difference(mean_candidate, baseline_base["net_return"])
    excess = mean_candidate.align(baseline_base["net_return"], join="inner")
    excess_returns = excess[0] - excess[1]
    annual_excess = excess_returns.groupby(excess_returns.index.year).sum()
    cumulative_excess = float(annual_excess.sum())
    best_year_contribution: float | None = (
        float(annual_excess.max() / cumulative_excess)
        if cumulative_excess > 0
        else None
    )
    gates = {
        "positive_seed_fraction": positive_seed_fraction >= 0.8,
        "positive_fold_fraction": positive_fold_fraction >= 0.6,
        "bootstrap_lower_bound": mean_bootstrap["ir_delta_ci_2_5"] > 0,
        "stress_positive": all(float(row["stress_net_ir"]) > 0 for row in seed_rows),
        "best_year_contribution": (
            best_year_contribution is not None and best_year_contribution <= 0.5
        ),
    }
    result = {
        "schema_version": "qlib_peerlite_m8_confirmation_evaluation_v1",
        "status": "PASS" if all(gates.values()) else "HOLD",
        "candidate": "PEERLITE_K16_MSE",
        "benchmark": "B0_LIGHTGBM",
        "seeds": seed_rows,
        "positive_seed_fraction": positive_seed_fraction,
        "positive_fold_fraction": positive_fold_fraction,
        "mean_seed_bootstrap": mean_bootstrap,
        "annual_excess_returns": {str(year): float(value) for year, value in annual_excess.items()},
        "cumulative_excess_return": cumulative_excess,
        "best_year_contribution": best_year_contribution,
        "mean_seed_max_drawdown": max_drawdown(mean_candidate),
        "mean_seed_average_turnover": float(
            pd.concat([frame["turnover"] for frame in seed_base_frames], axis=1)
            .mean(axis=1)
            .mean()
        ),
        "gates": gates,
        "final_oos_opening_authorized": all(gates.values()),
        "final_oos_market_partitions_opened": False,
        "baseline_stress_net_ir": information_ratio(baseline_stress["net_return"]),
    }
    result["content_sha256"] = canonical_hash(result)
    atomic_write_json(output, result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-panel", type=Path, required=True)
    parser.add_argument("--baseline-predictions", type=Path, required=True)
    parser.add_argument("--seed7-predictions", type=Path, required=True)
    parser.add_argument("--confirmation-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(**vars(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
