#!/usr/bin/env python3
"""Independently verify the completed M7 isolated-increment screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from qlib_peerlite.evaluation.bootstrap import bootstrap_ir_difference
from qlib_peerlite.evaluation.institutional import AShareCostSchedule
from qlib_peerlite.evaluation.metrics import information_ratio
from qlib_peerlite.governance.artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)
from qlib_peerlite.qlib_integration import initialize_qlib

SHANGHAI = ZoneInfo("Asia/Shanghai")
MODELS = ("PEERLITE_K16_CCC", "PEERLITE_K16_MSE_GATE")
FOLDS = tuple(f"wf_{year}" for year in range(2018, 2025))
PREDICTION_COLUMNS = ["datetime", "instrument", "score", "model_id", "fold_id"]
EXPECTED_OOS_LOG_SHA256 = (
    "6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190"
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def _require_finite(value: Any, *, location: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _require_finite(item, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _require_finite(item, location=f"{location}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise RuntimeError(f"non-finite value at {location}")


def _close(left: float, right: float, *, name: str) -> None:
    if not math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError(f"{name} mismatch: {left} != {right}")


def _verify_recorder(
    *,
    recorder_id: str,
    expected: dict[str, str],
) -> dict[str, Any]:
    from qlib.workflow import R

    recorder = R.get_recorder(
        recorder_id=recorder_id,
        experiment_name="qlib_peerlite_m7_isolated_increments",
    )
    available = set(recorder.list_artifacts())
    with tempfile.TemporaryDirectory(prefix=f"m7-verify-{recorder_id}-") as directory:
        for name, expected_hash in expected.items():
            if name not in available:
                raise RuntimeError(f"Qlib Recorder artifact missing: {name}")
            downloaded = Path(recorder.download_artifact(name, dst_path=directory))
            if sha256_file(downloaded) != expected_hash:
                raise RuntimeError(f"Qlib Recorder artifact hash mismatch: {name}")
    return {
        "recorder_id": recorder_id,
        "artifact_names": sorted(expected),
        "artifact_readback": "PASS_INDEPENDENT",
    }


def _verify_predictions(
    path: Path,
    *,
    model_id: str,
    expected_hash: str,
    expected_rows: int,
) -> dict[str, Any]:
    if sha256_file(path) != expected_hash:
        raise RuntimeError(f"prediction hash mismatch: {model_id}")
    frame = pd.read_parquet(path)
    if (
        list(frame.columns) != PREDICTION_COLUMNS
        or len(frame) != expected_rows
        or frame.duplicated(["datetime", "instrument"]).any()
        or frame.isna().any().any()
        or not np.isfinite(frame["score"].to_numpy(dtype=float)).all()
        or set(frame["model_id"]) != {model_id}
        or set(frame["fold_id"]) != set(FOLDS)
    ):
        raise RuntimeError(f"prediction integrity mismatch: {model_id}")
    date_min = pd.Timestamp(frame["datetime"].min())
    date_max = pd.Timestamp(frame["datetime"].max())
    if date_max >= pd.Timestamp("2025-01-01"):
        raise RuntimeError(f"prediction crossed final OOS: {model_id}")
    return {
        "rows": len(frame),
        "sha256": expected_hash,
        "date_min": date_min.date().isoformat(),
        "date_max": date_max.date().isoformat(),
        "unique_keys": True,
        "finite_scores": True,
    }


def _verify_portfolio_path(
    *,
    candidate_dir: Path,
    prefix: str,
    execution: pd.DataFrame,
    stress: bool,
) -> dict[str, Any]:
    returns = pd.read_parquet(candidate_dir / f"{prefix}_returns.parquet")
    holdings = pd.read_parquet(candidate_dir / f"{prefix}_holdings.parquet")
    trades = pd.read_parquet(candidate_dir / f"{prefix}_trades.parquet")
    returns["datetime"] = pd.to_datetime(returns["datetime"])
    holdings["datetime"] = pd.to_datetime(holdings["datetime"])
    trades["datetime"] = pd.to_datetime(trades["datetime"])
    numeric_returns = returns.drop(columns=["datetime"]).to_numpy(dtype=float)
    if not np.isfinite(numeric_returns).all():
        raise RuntimeError(f"non-finite portfolio return path: {prefix}")
    if (
        returns["datetime"].max() >= pd.Timestamp("2025-01-01")
        or (returns["invested_weight"] > 1.0 + 1e-12).any()
        or (returns["cash_weight"] < -1e-12).any()
    ):
        raise RuntimeError(f"portfolio boundary or cash constraint failed: {prefix}")
    np.testing.assert_allclose(
        returns["net_return"],
        returns["gross_return"] - returns["transaction_cost"],
        rtol=0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        returns["cash_weight"],
        1.0 - returns["invested_weight"],
        rtol=0,
        atol=1e-15,
    )
    if (
        (holdings["weight"] < -1e-12).any()
        or (holdings["weight"] > 0.02 + 1e-12).any()
        or holdings.duplicated(["datetime", "instrument"]).any()
    ):
        raise RuntimeError(f"holding constraint failed: {prefix}")
    holding_sums = holdings.groupby("datetime")["weight"].sum()
    observed = returns.set_index("datetime")["invested_weight"].reindex(holding_sums.index)
    np.testing.assert_allclose(holding_sums, observed, rtol=0, atol=1e-12)

    costs = AShareCostSchedule()
    expected_cost = []
    for row in returns.itertuples(index=False):
        buy = row.buy_turnover * costs.side_cost_bps(
            row.datetime,
            side="buy",
            stress=stress,
        )
        sell = row.sell_turnover * costs.side_cost_bps(
            row.datetime,
            side="sell",
            stress=stress,
        )
        expected_cost.append((buy + sell) / 10_000)
    np.testing.assert_allclose(
        returns["transaction_cost"],
        expected_cost,
        rtol=0,
        atol=1e-15,
    )

    panel = execution.set_index(["datetime", "instrument"])
    joined = trades.join(panel[["adv20"]], on=["datetime", "instrument"])
    nonzero = joined["filled_weight"].abs() > 1e-15
    if joined.loc[nonzero, "adv20"].isna().any():
        raise RuntimeError(f"filled trade lacks ADV evidence: {prefix}")
    capacity = joined["adv20"].fillna(0.0) * 0.05 / 100_000_000.0
    if (joined["filled_weight"].abs() > capacity + 1e-12).any():
        raise RuntimeError(f"ADV participation constraint failed: {prefix}")
    return {
        "weekly_rows": len(returns),
        "holding_rows": len(holdings),
        "trade_rows": len(trades),
        "max_invested_weight": float(returns["invested_weight"].max()),
        "min_cash_weight": float(returns["cash_weight"].min()),
        "max_name_weight": float(holdings["weight"].max()),
        "cost_identity": "PASS_EXACT",
        "adv_5pct_constraint": "PASS",
        "net_ir": information_ratio(returns.set_index("datetime")["net_return"]),
    }


def _verify_candidate(
    *,
    run_dir: Path,
    binding: dict[str, Any],
    execution: pd.DataFrame,
) -> dict[str, Any]:
    model_id = binding["model_id"]
    candidate_dir = run_dir / model_id
    prediction = _verify_predictions(
        candidate_dir / "predictions.parquet",
        model_id=model_id,
        expected_hash=binding["prediction_sha256"],
        expected_rows=binding["prediction_rows"],
    )
    fold_ids = []
    for fold_binding in binding["fold_receipts"]:
        path = run_dir / fold_binding["path"]
        if sha256_file(path) != fold_binding["sha256"]:
            raise RuntimeError(f"fold receipt hash mismatch: {model_id}")
        receipt = _load_json(path)
        summary = receipt["training_summary"]
        if (
            receipt.get("status") != "PASS"
            or receipt.get("model_id") != model_id
            or receipt.get("fold_id") != fold_binding["fold_id"]
            or receipt.get("checkpoint_replay") != "PASS_EXACT"
            or receipt.get("final_oos_market_partitions_opened") is not False
            or summary.get("parameter_count", 500_001) >= 500_000
            or summary.get("best_epoch", 0) < 1
            or summary.get("epochs_completed", 0) < summary.get("best_epoch", 0)
        ):
            raise RuntimeError(f"fold receipt mismatch: {model_id}")
        _require_finite(receipt["diagnostic_metrics"], location=f"{model_id}.fold")
        fold_ids.append(receipt["fold_id"])
    if tuple(fold_ids) != FOLDS:
        raise RuntimeError(f"fold order mismatch: {model_id}")
    refit = _load_json(candidate_dir / "deterministic_refit_receipt.json")
    if (
        refit.get("status") != "PASS_EXACT"
        or refit.get("model_id") != model_id
        or refit.get("fold_id") != "wf_2018"
        or refit.get("score_rows") != 125_413
    ):
        raise RuntimeError(f"deterministic refit mismatch: {model_id}")

    metrics_path = candidate_dir / "metrics.json"
    if sha256_file(metrics_path) != binding["metrics_sha256"]:
        raise RuntimeError(f"metrics hash mismatch: {model_id}")
    metrics = _load_json(metrics_path)
    _require_finite(metrics, location=f"{model_id}.metrics")
    if (
        metrics.get("status") != "PASS"
        or metrics.get("model_id") != model_id
        or metrics.get("claim_ceiling") != "PRE_FINAL_OOS_SCREENING_ONLY"
        or metrics["portfolio_screen"]["final_oos_metrics_computed"] is not False
    ):
        raise RuntimeError(f"metrics identity mismatch: {model_id}")

    candidate_base = _verify_portfolio_path(
        candidate_dir=candidate_dir,
        prefix="candidate_base",
        execution=execution,
        stress=False,
    )
    candidate_stress = _verify_portfolio_path(
        candidate_dir=candidate_dir,
        prefix="candidate_stress",
        execution=execution,
        stress=True,
    )
    baseline_base = _verify_portfolio_path(
        candidate_dir=candidate_dir,
        prefix="baseline_base",
        execution=execution,
        stress=False,
    )
    _verify_portfolio_path(
        candidate_dir=candidate_dir,
        prefix="baseline_stress",
        execution=execution,
        stress=True,
    )
    market = _verify_portfolio_path(
        candidate_dir=candidate_dir,
        prefix="market_reference",
        execution=execution,
        stress=False,
    )
    screen = metrics["portfolio_screen"]
    _close(
        candidate_base["net_ir"],
        screen["candidate_base_net_ir"],
        name=f"{model_id}.candidate_base_ir",
    )
    _close(
        candidate_stress["net_ir"],
        screen["candidate_stress_net_ir"],
        name=f"{model_id}.candidate_stress_ir",
    )
    _close(
        baseline_base["net_ir"],
        screen["baseline_base_net_ir"],
        name=f"{model_id}.baseline_ir",
    )
    _close(
        market["net_ir"],
        screen["market_reference_base_net_ir"],
        name=f"{model_id}.market_ir",
    )

    candidate_returns = pd.read_parquet(
        candidate_dir / "candidate_base_returns.parquet"
    ).set_index("datetime")["net_return"]
    baseline_returns = pd.read_parquet(
        candidate_dir / "baseline_base_returns.parquet"
    ).set_index("datetime")["net_return"]
    aligned = pd.concat(
        [candidate_returns.rename("candidate"), baseline_returns.rename("baseline")],
        axis=1,
    ).dropna()
    bootstrap = bootstrap_ir_difference(
        aligned["candidate"],
        aligned["baseline"],
        block_length=4,
        draws=2_000,
        seed=7,
    )
    for key, value in bootstrap.items():
        _close(value, screen["bootstrap"][key], name=f"{model_id}.bootstrap.{key}")
    folds = pd.read_parquet(candidate_dir / "fold_comparison.parquet")
    positive_fraction = float((folds["net_ir_delta"] > 0).mean())
    delta = candidate_base["net_ir"] - baseline_base["net_ir"]
    _close(
        positive_fraction,
        screen["positive_fold_fraction"],
        name=f"{model_id}.positive_fold_fraction",
    )
    _close(
        delta,
        screen["overall_net_ir_delta_vs_peerlite_mse"],
        name=f"{model_id}.net_ir_delta",
    )
    screen_pass = (
        delta > 0
        and positive_fraction >= 0.60
        and bootstrap["ir_delta_ci_2_5"] > 0
        and candidate_stress["net_ir"] > 0
    )
    expected_decision = "SCREEN_PASS" if screen_pass else "HOLD"
    if binding["decision"] != expected_decision or screen["decision"] != expected_decision:
        raise RuntimeError(f"screen decision mismatch: {model_id}")
    recorder = _verify_recorder(
        recorder_id=binding["qlib_recorder_id"],
        expected={
            "predictions.parquet": binding["prediction_sha256"],
            "metrics.json": binding["metrics_sha256"],
        },
    )
    return {
        "model_id": model_id,
        "decision": expected_decision,
        "fold_receipts": len(fold_ids),
        "deterministic_refit": "PASS_EXACT",
        "prediction": prediction,
        "portfolio": {
            "candidate_base": candidate_base,
            "candidate_stress": candidate_stress,
            "baseline_base": baseline_base,
            "market_reference": market,
            "net_ir_delta": delta,
            "positive_fold_fraction": positive_fraction,
            "bootstrap_ci_2_5": bootstrap["ir_delta_ci_2_5"],
        },
        "qlib_recorder": recorder,
    }


def _verify_accounting(
    *,
    run_dir: Path,
    ledger_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    if sha256_file(ledger_path) != manifest["trial_ledger_sha256_after"]:
        raise RuntimeError("authoritative trial ledger hash mismatch")
    ledger = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    candidates = sum(item.get("counts_as_candidate_evaluation") is True for item in ledger)
    fits = sum(item.get("counts_as_model_fit") is True for item in ledger)
    if (candidates, fits) != (8, 61):
        raise RuntimeError(f"cumulative trial count mismatch: {(candidates, fits)}")
    journal_path = run_dir / "trial_journal.jsonl"
    journal = [
        json.loads(line)
        for line in journal_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    counts = Counter(item["event"] for item in journal)
    if counts != Counter({"MODEL_FIT_STARTED": 16, "CANDIDATE_EVALUATION_STARTED": 1}):
        raise RuntimeError(f"M7 recovery journal counts mismatch: {dict(counts)}")
    if len({item["source_event_id"] for item in journal}) != len(journal):
        raise RuntimeError("duplicate M7 source event identity")
    for item in journal:
        unsigned = dict(item)
        event_hash = unsigned.pop("event_sha256")
        if hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest() != event_hash:
            raise RuntimeError("M7 journal event hash mismatch")
    return {
        "ledger_sha256": sha256_file(ledger_path),
        "cumulative_candidate_evaluations": candidates,
        "cumulative_model_fits": fits,
        "recovery_run_candidate_starts": counts["CANDIDATE_EVALUATION_STARTED"],
        "recovery_run_fit_starts": counts["MODEL_FIT_STARTED"],
        "step_eight_candidate_evaluations": 2,
        "step_eight_fit_starts_including_failed_harness_fit": 17,
    }


def verify(
    *,
    project_root: Path,
    run_dir: Path,
    tracking_dir: Path,
    execution_panel: Path,
    ledger_path: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    run_dir = run_dir.resolve()
    tracking_dir = tracking_dir.resolve()
    receipt_path = receipt_path.resolve()
    manifest_path = run_dir / "run_manifest.json"
    manifest = _load_json(manifest_path)
    spec_path = project_root / "contracts/immutable/m7_empirical_execution_spec_v3.json"
    if (
        manifest.get("status") != "PASS"
        or manifest.get("stage") != "M7-ISOLATED-INCREMENTS"
        or manifest.get("claim_ceiling") != "PRE_FINAL_OOS_SCREENING_ONLY"
        or manifest.get("combination_authorized") is not False
        or manifest.get("final_oos_market_partitions_opened") is not False
        or manifest.get("final_oos_metrics_computed") is not False
        or sha256_file(spec_path) != manifest["execution_spec_sha256"]
        or tuple(item["model_id"] for item in manifest["candidates"]) != MODELS
    ):
        raise RuntimeError("M7 run manifest identity or boundary mismatch")
    environment = _load_json(run_dir / "environment.json")
    determinism = environment.get("determinism", {})
    if (
        determinism.get("cublas_workspace_config") != ":4096:8"
        or determinism.get("cudnn_benchmark") is not False
    ):
        raise RuntimeError("M7 deterministic environment mismatch")
    oos_log = project_root / "contracts/oos_access_log.jsonl"
    oos_events = [
        json.loads(line)
        for line in oos_log.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if sha256_file(oos_log) != EXPECTED_OOS_LOG_SHA256 or oos_events != [
        {
            "access_count": 0,
            "event": "OOS_LOG_INITIALIZED",
            "interval_end": "2026-06-30",
            "interval_start": "2025-01-01",
            "selection_uses": 0,
            "status": "UNTOUCHED",
            "timestamp": "2026-07-28T00:00:00+08:00",
        }
    ]:
        raise RuntimeError("final-OOS access seal changed")

    execution = pd.read_parquet(execution_panel)
    execution["datetime"] = pd.to_datetime(execution["datetime"])
    initialize_qlib(
        provider_dir=tracking_dir / "empty_provider",
        tracking_dir=tracking_dir / "mlflow",
    )
    candidate_checks = [
        _verify_candidate(
            run_dir=run_dir,
            binding=binding,
            execution=execution,
        )
        for binding in manifest["candidates"]
    ]
    accounting = _verify_accounting(
        run_dir=run_dir,
        ledger_path=ledger_path,
        manifest=manifest,
    )
    receipt: dict[str, Any] = {
        "schema_version": "qlib_peerlite_m7_verification_receipt_v1",
        "status": "PASS",
        "created_at": datetime.now(SHANGHAI).isoformat(),
        "verifier": {
            "path": "scripts/server/verify_m7_empirical.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "run_manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
        },
        "execution_spec_sha256": sha256_file(spec_path),
        "environment_sha256": sha256_file(run_dir / "environment.json"),
        "determinism_evidence": {
            "cublas_workspace_config": determinism["cublas_workspace_config"],
            "environment_capture_timing": "BEFORE_FIRST_FOLD_SEEDING",
            "environment_capture_deterministic_algorithms": determinism.get(
                "deterministic_algorithms"
            ),
            "runtime_control": (
                "seed_everything enables torch deterministic algorithms and cuDNN "
                "determinism before every fit"
            ),
            "runtime_proof": "TWO_CANDIDATE_WF_2018_REFITS_PASS_EXACT",
            "seed_control_sha256": sha256_file(
                project_root / "src/qlib_peerlite/models/common.py"
            ),
            "runner_sha256": sha256_file(
                project_root / "scripts/server/run_m7_empirical.py"
            ),
        },
        "candidate_checks": candidate_checks,
        "accounting": accounting,
        "qlib_recorder_readbacks": 2,
        "prediction_rows_total": sum(
            item["prediction"]["rows"] for item in candidate_checks
        ),
        "decisions": {
            item["model_id"]: item["decision"] for item in candidate_checks
        },
        "combination_authorized": False,
        "final_oos_access_log_sha256": EXPECTED_OOS_LOG_SHA256,
        "final_oos_access_count": 0,
        "claim_ceiling": "PRE_FINAL_OOS_SCREENING_ONLY",
    }
    receipt["content_sha256"] = hashlib.sha256(
        canonical_json_bytes(receipt)
    ).hexdigest()
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite verification receipt: {receipt_path}")
    atomic_write_json(receipt_path, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path, required=True)
    parser.add_argument("--execution-panel", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(
        project_root=args.project_root,
        run_dir=args.run_dir,
        tracking_dir=args.tracking_dir,
        execution_panel=args.execution_panel,
        ledger_path=args.ledger,
        receipt_path=args.receipt,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "content_sha256": receipt["content_sha256"],
                "prediction_rows_total": receipt["prediction_rows_total"],
                "decisions": receipt["decisions"],
                "cumulative_trial_counts": [
                    receipt["accounting"]["cumulative_candidate_evaluations"],
                    receipt["accounting"]["cumulative_model_fits"],
                ],
                "final_oos_access_count": receipt["final_oos_access_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
