#!/usr/bin/env python3
"""Independently verify a completed M6 PeerLite-MSE run."""

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

import pandas as pd

from qlib_peerlite.qlib_integration import initialize_qlib

SHANGHAI = ZoneInfo("Asia/Shanghai")
PREDICTION_COLUMNS = ["datetime", "instrument", "score", "model_id", "fold_id"]
MODEL_FITS = {"PEERLITE_K16_MSE": 8, "PEERLITE_K32_MSE": 7}
FOLD_IDS = [f"wf_{year}" for year in range(2018, 2025)]
EXPECTED_SAFEGUARDS = {
    "final_oos_market_partitions_opened": False,
    "final_oos_metrics_computed": False,
    "portfolio_backtests": 0,
    "cost_adjusted_selection": False,
    "model_selection_performed": False,
    "ccc_allowed": False,
    "market_gate_allowed": False,
    "text_or_llm_allowed": False,
    "high_frequency_data_allowed": False,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def verify_content_receipt(
    path: Path,
    *,
    expected_file_hash: str | None = None,
) -> dict[str, Any]:
    if expected_file_hash is not None and sha256_file(path) != expected_file_hash:
        raise RuntimeError(f"file hash mismatch: {path}")
    value = load_json(path)
    if value.get("content_sha256") != content_hash(value):
        raise RuntimeError(f"content hash mismatch: {path}")
    return value


def require_finite_metrics(value: Any, *, location: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            require_finite_metrics(item, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            require_finite_metrics(item, location=f"{location}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise RuntimeError(f"non-finite metric at {location}")


def verify_prediction_file(
    path: Path,
    *,
    model_id: str,
    expected_rows: int,
    expected_hash: str,
) -> dict[str, Any]:
    if sha256_file(path) != expected_hash:
        raise RuntimeError(f"prediction hash mismatch: {model_id}")
    frame = pd.read_parquet(path)
    if list(frame.columns) != PREDICTION_COLUMNS:
        raise RuntimeError(f"prediction schema mismatch: {model_id}")
    if len(frame) != expected_rows:
        raise RuntimeError(f"prediction row count mismatch: {model_id}")
    if frame.duplicated(["datetime", "instrument"]).any():
        raise RuntimeError(f"duplicate prediction keys: {model_id}")
    if frame[PREDICTION_COLUMNS].isna().any().any():
        raise RuntimeError(f"null prediction values: {model_id}")
    if not frame["score"].map(math.isfinite).all():
        raise RuntimeError(f"non-finite prediction scores: {model_id}")
    if set(frame["model_id"].unique()) != {model_id}:
        raise RuntimeError(f"prediction model identity mismatch: {model_id}")
    if set(frame["fold_id"].unique()) != set(FOLD_IDS):
        raise RuntimeError(f"prediction fold identity mismatch: {model_id}")
    date_min = pd.Timestamp(frame["datetime"].min())
    date_max = pd.Timestamp(frame["datetime"].max())
    if date_max >= pd.Timestamp("2025-01-01"):
        raise RuntimeError(f"final-OOS boundary crossed: {model_id}")
    return {
        "path": str(path),
        "sha256": expected_hash,
        "rows": len(frame),
        "columns": list(frame.columns),
        "date_min": date_min.date().isoformat(),
        "date_max": date_max.date().isoformat(),
        "duplicate_keys": 0,
        "null_values": 0,
        "non_finite_scores": 0,
        "final_oos_market_partitions_opened": False,
    }


def verify_recorder(
    *,
    recorder_id: str,
    experiment_name: str,
    expected: dict[str, str],
) -> dict[str, Any]:
    from qlib.workflow import R

    recorder = R.get_recorder(
        recorder_id=recorder_id,
        experiment_name=experiment_name,
    )
    available = set(recorder.list_artifacts())
    with tempfile.TemporaryDirectory(prefix=f"m6-verify-{recorder_id}-") as directory:
        for name, expected_hash in expected.items():
            if name not in available:
                raise RuntimeError(f"Qlib Recorder artifact missing: {name}")
            downloaded = Path(recorder.download_artifact(name, dst_path=directory))
            if sha256_file(downloaded) != expected_hash:
                raise RuntimeError(f"Qlib Recorder artifact hash mismatch: {name}")
    return {
        "experiment_name": experiment_name,
        "recorder_id": recorder_id,
        "artifact_names": sorted(expected),
        "artifact_readback": "PASS_INDEPENDENT",
    }


def verify_journal(path: Path, expected_pre_terminal_hash: str) -> dict[str, Any]:
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    events = [json.loads(line) for line in lines]
    counts = Counter(item["event"] for item in events)
    expected = {
        "M6_RUN_STARTED": 1,
        "CANDIDATE_EVALUATION_STARTED": 2,
        "MODEL_FIT_STARTED": 15,
        "MODEL_FIT_COMPLETED": 15,
        "CANDIDATE_EVALUATION_COMPLETED": 2,
        "M6_RUN_COMPLETED": 1,
    }
    if counts != Counter(expected):
        raise RuntimeError(f"unexpected M6 journal counts: {dict(counts)}")
    if events[-1]["event"] != "M6_RUN_COMPLETED":
        raise RuntimeError("M6 terminal event is not the final journal event")
    before_terminal = hashlib.sha256(b"".join(lines[:-1])).hexdigest()
    if before_terminal != expected_pre_terminal_hash:
        raise RuntimeError("pre-terminal M6 journal hash mismatch")
    candidate_evaluations = sum(
        item.get("counts_as_candidate_evaluation") is True for item in events
    )
    model_fits = sum(item.get("counts_as_model_fit") is True for item in events)
    if candidate_evaluations != 2 or model_fits != 15:
        raise RuntimeError("M6 journal trial accounting mismatch")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "event_counts": dict(counts),
        "counted_candidate_evaluations": candidate_evaluations,
        "counted_model_fits": model_fits,
        "failed_events": 0,
        "pre_terminal_sha256": before_terminal,
    }


def verify_fold(
    *,
    run_dir: Path,
    model_id: str,
    binding: dict[str, Any],
) -> dict[str, Any]:
    path = run_dir / binding["path"]
    fold = verify_content_receipt(path, expected_file_hash=binding["sha256"])
    summary = fold.get("training_summary", {})
    if (
        fold.get("status") != "PASS"
        or fold.get("model_id") != model_id
        or fold.get("fold_id") != binding["fold_id"]
        or fold.get("feature_count") != 50
        or fold.get("checkpoint_replay") != "PASS_EXACT"
        or fold.get("final_oos_market_partitions_opened") is not False
        or fold.get("cost_adjusted_metrics_computed") is not False
        or fold.get("portfolio_backtests") != 0
        or summary.get("best_epoch", 0) < 1
        or summary.get("epochs_ran", 0) < summary.get("best_epoch", 0)
    ):
        raise RuntimeError(f"M6 fold receipt mismatch: {model_id}/{binding['fold_id']}")
    parameter_count = summary.get("parameter_count")
    if not isinstance(parameter_count, int) or not 0 < parameter_count < 500_000:
        raise RuntimeError(f"M6 parameter budget mismatch: {model_id}")
    checkpoint_dir = path.parent / "checkpoint"
    for relative_path, expected_hash in fold["checkpoint"].items():
        if sha256_file(checkpoint_dir / relative_path) != expected_hash:
            raise RuntimeError(
                f"M6 checkpoint hash mismatch: {model_id}/{binding['fold_id']}"
            )
    require_finite_metrics(
        fold["diagnostic_metrics"],
        location=f"{model_id}.{binding['fold_id']}",
    )
    return {
        "fold_id": binding["fold_id"],
        "receipt_sha256": binding["sha256"],
        "checkpoint_replay": "PASS_EXACT",
        "checkpoint_inventory": len(fold["checkpoint"]),
        "parameter_count": parameter_count,
    }


def verify(
    *,
    project_root: Path,
    run_dir: Path,
    tracking_dir: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    run_dir = run_dir.resolve()
    tracking_dir = tracking_dir.resolve()
    receipt_path = receipt_path.resolve()
    manifest_path = run_dir / "run_manifest.json"
    manifest = verify_content_receipt(manifest_path)
    if (
        manifest.get("status") != "PASS"
        or manifest.get("stage") != "M6-PEERLITE-MSE"
        or manifest.get("claim_ceiling") != "PRE_FINAL_OOS_DIAGNOSTIC"
        or manifest.get("candidate_evaluations") != 2
        or manifest.get("model_fits") != 15
        or manifest.get("safeguards") != EXPECTED_SAFEGUARDS
    ):
        raise RuntimeError("M6 run identity, trial count or safeguards mismatch")

    spec_path = project_root / "contracts/immutable/m6_peerlite_execution_spec_v1.json"
    spec = load_json(spec_path)
    if (
        sha256_file(spec_path) != manifest["spec"]["sha256"]
        or spec["content_sha256"] != manifest["spec"]["content_sha256"]
    ):
        raise RuntimeError("M6 run is not bound to the frozen specification")
    environment_path = run_dir / "environment.json"
    environment = load_json(environment_path)
    if environment.get("determinism") != {
        "cublas_workspace_config": ":4096:8",
        "deterministic_algorithms": True,
        "deterministic_algorithms_warn_only": False,
        "cudnn_benchmark": False,
        "cudnn_deterministic": True,
    }:
        raise RuntimeError("M6 environment lacks strict deterministic controls")

    initialize_qlib(
        provider_dir=tracking_dir / "empty_provider",
        tracking_dir=tracking_dir / "mlflow",
    )
    candidate_checks: list[dict[str, Any]] = []
    for candidate in manifest["candidates"]:
        model_id = candidate["model_id"]
        if model_id not in MODEL_FITS or candidate["model_fits"] != MODEL_FITS[model_id]:
            raise RuntimeError(f"M6 candidate fit count mismatch: {model_id}")
        receipt_path_for_candidate = run_dir / candidate["candidate_receipt"]["path"]
        candidate_receipt = verify_content_receipt(
            receipt_path_for_candidate,
            expected_file_hash=candidate["candidate_receipt"]["sha256"],
        )
        if (
            candidate_receipt.get("status") != "PASS"
            or candidate_receipt.get("model_id") != model_id
            or candidate_receipt.get("model_fits") != MODEL_FITS[model_id]
            or candidate_receipt.get("portfolio_backtests") != 0
            or candidate_receipt.get("selection_allowed") is not False
            or candidate_receipt.get("cost_adjusted_metrics_computed") is not False
            or candidate_receipt.get("final_oos_market_partitions_opened") is not False
        ):
            raise RuntimeError(f"M6 candidate receipt mismatch: {model_id}")

        fold_checks = [
            verify_fold(
                run_dir=run_dir,
                model_id=model_id,
                binding=binding,
            )
            for binding in candidate_receipt["fold_receipts"]
        ]
        if [item["fold_id"] for item in fold_checks] != FOLD_IDS:
            raise RuntimeError(f"M6 fold order mismatch: {model_id}")
        prediction = verify_prediction_file(
            run_dir / candidate["predictions"]["path"],
            model_id=model_id,
            expected_rows=candidate["predictions"]["rows"],
            expected_hash=candidate["predictions"]["sha256"],
        )
        metrics_path = run_dir / candidate["metrics"]["path"]
        if sha256_file(metrics_path) != candidate["metrics"]["sha256"]:
            raise RuntimeError(f"M6 metrics hash mismatch: {model_id}")
        metrics = load_json(metrics_path)
        require_finite_metrics(metrics.get("overall"), location=f"{model_id}.overall")
        recorder = verify_recorder(
            recorder_id=candidate["qlib_recorder"]["recorder_id"],
            experiment_name=candidate["qlib_recorder"]["experiment_name"],
            expected={
                "candidate_receipt.json": candidate["candidate_receipt"]["sha256"],
                "metrics.json": candidate["metrics"]["sha256"],
                "predictions.parquet": candidate["predictions"]["sha256"],
            },
        )
        candidate_checks.append(
            {
                "model_id": model_id,
                "model_fits": candidate["model_fits"],
                "folds": fold_checks,
                "predictions": prediction,
                "metrics_sha256": candidate["metrics"]["sha256"],
                "qlib_recorder": recorder,
            }
        )
    if [item["model_id"] for item in candidate_checks] != list(MODEL_FITS):
        raise RuntimeError("M6 candidate order mismatch")

    k16_binding = manifest["candidates"][0]
    k16_receipt = load_json(run_dir / k16_binding["candidate_receipt"]["path"])
    refit_binding = k16_receipt.get("deterministic_refit")
    if not isinstance(refit_binding, dict):
        raise RuntimeError("K16 deterministic refit binding is missing")
    refit = verify_content_receipt(
        run_dir / refit_binding["path"],
        expected_file_hash=refit_binding["sha256"],
    )
    if (
        refit.get("status") != "PASS_EXACT"
        or refit.get("model_id") != "PEERLITE_K16_MSE"
        or refit.get("fold_id") != "wf_2018"
        or refit.get("reference_score_sha256") != refit.get("refit_score_sha256")
        or refit.get("final_oos_market_partitions_opened") is not False
    ):
        raise RuntimeError("K16 deterministic refit proof is invalid")

    journal = verify_journal(
        run_dir / manifest["ledger_events"]["path"],
        manifest["ledger_events"]["sha256_before_terminal_event"],
    )
    receipt = {
        "schema_version": "qlib_peerlite_m6_verification_receipt_v1",
        "status": "PASS",
        "created_at": datetime.now(SHANGHAI).isoformat(),
        "verifier": {
            "path": "scripts/server/verify_m6_peerlite.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "run_manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
            "content_sha256": manifest["content_sha256"],
        },
        "spec_content_sha256": manifest["spec"]["content_sha256"],
        "environment_sha256": sha256_file(environment_path),
        "candidate_checks": candidate_checks,
        "deterministic_refit": {
            "path": refit_binding["path"],
            "sha256": refit_binding["sha256"],
            "status": "PASS_EXACT",
            "score_sha256": refit["reference_score_sha256"],
            "score_rows": refit["score_rows"],
        },
        "journal": journal,
        "safeguards": manifest["safeguards"],
        "prediction_rows_total": sum(
            item["predictions"]["rows"] for item in candidate_checks
        ),
        "final_oos_market_partitions_opened": False,
        "selection_performed": False,
        "portfolio_backtests": 0,
        "cost_adjusted_metrics_computed": False,
        "claim_ceiling": "PRE_FINAL_OOS_DIAGNOSTIC",
    }
    receipt["content_sha256"] = content_hash(receipt)
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite verification receipt: {receipt_path}")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(
        project_root=args.project_root,
        run_dir=args.run_dir,
        tracking_dir=args.tracking_dir,
        receipt_path=args.receipt,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "content_sha256": receipt["content_sha256"],
                "prediction_rows_total": receipt["prediction_rows_total"],
                "model_fits": receipt["journal"]["counted_model_fits"],
                "final_oos_market_partitions_opened": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
