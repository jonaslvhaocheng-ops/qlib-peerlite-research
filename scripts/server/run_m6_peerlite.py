#!/usr/bin/env python3
"""Run the two frozen M6 PeerLite-MSE candidates on qualified development data."""

from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import os
import resource
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import torch

from qlib_peerlite.data.qlib_dataset import build_qlib_fold, load_bound_product_frame
from qlib_peerlite.data.schema import score_frame
from qlib_peerlite.data.splits import annual_folds
from qlib_peerlite.evaluation.metrics import evaluate_predictions
from qlib_peerlite.governance.artifacts import (
    append_jsonl,
    atomic_write_json,
    environment_report,
    sha256_file,
)
from qlib_peerlite.governance.gates import EmpiricalEvidence, assert_empirical_ready
from qlib_peerlite.governance.m6_spec import load_and_verify_m6_spec
from qlib_peerlite.models.common import seed_everything
from qlib_peerlite.models.peerlite import PeerLiteModel
from qlib_peerlite.qlib_integration import initialize_qlib, record_run_with_qlib

SHANGHAI = ZoneInfo("Asia/Shanghai")
CUBLAS_WORKSPACE_CONFIG = ":4096:8"


def now() -> str:
    return datetime.now(SHANGHAI).isoformat()


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


def evidence_paths(project_root: Path, product_dir: Path) -> EmpiricalEvidence:
    return EmpiricalEvidence(
        contract_path=project_root / "contracts/immutable/research_contract_pit_v2.json",
        contract_receipt_path=project_root
        / "contracts/immutable/contract_validation_pit_v2.json",
        pit_manifest_path=project_root
        / "evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json",
        behavior_manifest_path=project_root
        / "evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json",
        m3_gate_path=project_root / "evidence/gates/M3_pit_data_gate.json",
        data_product_manifest_path=product_dir / "data_product_manifest.json",
        data_product_verification_path=project_root
        / "evidence/data_products/pit_data_product_verify_20260728_v3"
        / "data_product_verification.json",
    )


def finite_metrics(metrics: dict[str, float]) -> dict[str, float]:
    output = {key: float(value) for key, value in metrics.items()}
    if not all(np.isfinite(value) for value in output.values()):
        raise RuntimeError("PeerLite diagnostics contain a non-finite value")
    return output


def checkpoint_inventory(path: Path) -> dict[str, str]:
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise RuntimeError("PeerLite checkpoint inventory is empty")
    return {str(item.relative_to(path)): sha256_file(item) for item in files}


def score_digest(scores: pd.Series) -> str:
    digest = hashlib.sha256()
    for (timestamp, instrument), value in scores.items():
        digest.update(pd.Timestamp(timestamp).isoformat().encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(str(instrument).encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(float(value).hex().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def recorder_readback(
    *,
    recorder_id: str,
    experiment_name: str,
    expected: dict[str, str],
) -> None:
    from qlib.workflow import R

    recorder = R.get_recorder(
        recorder_id=recorder_id,
        experiment_name=experiment_name,
    )
    available = set(recorder.list_artifacts())
    with tempfile.TemporaryDirectory(prefix=f"m6-readback-{recorder_id}-") as directory:
        for name, expected_hash in expected.items():
            if name not in available:
                raise RuntimeError(f"Qlib Recorder artifact missing: {name}")
            downloaded = Path(recorder.download_artifact(name, dst_path=directory))
            if sha256_file(downloaded) != expected_hash:
                raise RuntimeError(f"Qlib Recorder artifact hash mismatch: {name}")


def run(
    *,
    project_root: Path,
    product_dir: Path,
    spec_path: Path,
    output_dir: Path,
    tracking_dir: Path,
) -> None:
    project_root = project_root.resolve()
    product_dir = product_dir.resolve()
    spec_path = spec_path.resolve()
    output_dir = output_dir.resolve()
    tracking_dir = tracking_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    journal_path = output_dir / "ledger_events.jsonl"
    append_jsonl(
        journal_path,
        {
            "event": "M6_RUN_STARTED",
            "timestamp": now(),
            "counts_as_candidate_evaluation": False,
            "counts_as_model_fit": False,
        },
    )

    active_evaluation_id: str | None = None
    active_fit_id: str | None = None
    active_model_id: str | None = None
    active_fold_id: str | None = None
    try:
        if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != CUBLAS_WORKSPACE_CONFIG:
            raise RuntimeError(
                f"CUBLAS_WORKSPACE_CONFIG must equal {CUBLAS_WORKSPACE_CONFIG}"
            )
        spec = load_and_verify_m6_spec(project_root, spec_path)
        seed_everything(spec["schedule"]["seed"])
        assert_empirical_ready(evidence_paths(project_root, product_dir))
        m5 = json.loads(
            (project_root / "evidence/gates/M5_baseline_gate.json").read_text(
                encoding="utf-8"
            )
        )
        if (
            m5.get("status") != "PASS"
            or m5.get("passed") is not True
            or m5.get("verification", {}).get("final_oos_market_partitions_opened")
            is not False
        ):
            raise RuntimeError("M5 baseline gate is not a final-OOS-safe PASS")

        product = load_bound_product_frame(product_dir, verify_all_files=True)
        if product.frame.index.get_level_values("datetime").max() >= pd.Timestamp(
            "2025-01-01"
        ):
            raise RuntimeError("M6 product crosses the final-OOS boundary")
        initialize_qlib(
            provider_dir=tracking_dir / "empty_provider",
            tracking_dir=tracking_dir / "mlflow",
        )
        environment = environment_report(project_root)
        environment["determinism"] = {
            "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "deterministic_algorithms_warn_only": (
                torch.is_deterministic_algorithms_warn_only_enabled()
            ),
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
        }
        if environment["determinism"] != {
            "cublas_workspace_config": CUBLAS_WORKSPACE_CONFIG,
            "deterministic_algorithms": True,
            "deterministic_algorithms_warn_only": False,
            "cudnn_benchmark": False,
            "cudnn_deterministic": True,
        }:
            raise RuntimeError("strict CUDA determinism controls are not active")
        atomic_write_json(output_dir / "environment.json", environment)

        fold_specs = {fold.fold_id: fold for fold in annual_folds()}
        candidate_results: list[dict[str, Any]] = []
        deterministic_reference: pd.Series | None = None
        for candidate in spec["candidates"]:
            model_id = candidate["model_id"]
            candidate_dir = output_dir / model_id
            candidate_dir.mkdir()
            evaluation_id = f"{output_dir.name}:{model_id}:seed7"
            active_evaluation_id = evaluation_id
            active_model_id = model_id
            append_jsonl(
                journal_path,
                {
                    "event": "CANDIDATE_EVALUATION_STARTED",
                    "timestamp": now(),
                    "family_id": "qlib-peerlite-a-share-daily-v0",
                    "evaluation_id": evaluation_id,
                    "model_id": model_id,
                    "seed": 7,
                    "counts_as_candidate_evaluation": True,
                    "counts_as_model_fit": False,
                },
            )
            prediction_tables: list[pd.DataFrame] = []
            score_parts: list[pd.Series] = []
            label_parts: list[pd.Series] = []
            fold_receipts: list[dict[str, Any]] = []

            for fold_id in spec["schedule"]["fold_ids"]:
                fold_dir = candidate_dir / "folds" / fold_id
                fold_dir.mkdir(parents=True)
                fit_id = f"{evaluation_id}:{fold_id}"
                active_fit_id = fit_id
                active_fold_id = fold_id
                append_jsonl(
                    journal_path,
                    {
                        "event": "MODEL_FIT_STARTED",
                        "timestamp": now(),
                        "family_id": "qlib-peerlite-a-share-daily-v0",
                        "evaluation_id": evaluation_id,
                        "fit_id": fit_id,
                        "model_id": model_id,
                        "fold_id": fold_id,
                        "seed": 7,
                        "counts_as_candidate_evaluation": False,
                        "counts_as_model_fit": True,
                    },
                )
                started = time.monotonic()
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                qlib_fold = build_qlib_fold(
                    product,
                    fold_specs[fold_id],
                    embargo_sessions=spec["schedule"]["embargo_sessions"],
                )
                model = PeerLiteModel(**candidate["parameters"])
                model.fit(qlib_fold.dataset)
                scores = model.predict(qlib_fold.dataset, segment="test")
                labels = qlib_fold.dataset.prepare("test", col_set="label").iloc[:, 0]
                labels = labels.loc[scores.index].astype(float)
                metrics = finite_metrics(evaluate_predictions(scores, labels))
                checkpoint_dir = fold_dir / "checkpoint"
                model.save_checkpoint(checkpoint_dir)
                restored = PeerLiteModel.load_checkpoint(
                    checkpoint_dir,
                    device=candidate["parameters"]["device"],
                )
                replay_scores = restored.predict(qlib_fold.dataset, segment="test")
                if not scores.index.equals(replay_scores.index) or not np.array_equal(
                    scores.to_numpy(dtype=float),
                    replay_scores.to_numpy(dtype=float),
                ):
                    raise RuntimeError(f"checkpoint replay mismatch: {model_id}/{fold_id}")
                if (
                    model_id == spec["deterministic_refit"]["model_id"]
                    and fold_id == spec["deterministic_refit"]["fold_id"]
                ):
                    deterministic_reference = scores.copy()

                table = score_frame(
                    scores.index,
                    scores.to_numpy(),
                    model_id,
                    fold_id,
                )
                if table["datetime"].max() >= pd.Timestamp("2025-01-01"):
                    raise RuntimeError("M6 prediction output crosses final OOS")
                prediction_tables.append(table)
                score_parts.append(scores)
                label_parts.append(labels)
                receipt = {
                    "schema_version": "qlib_peerlite_m6_fold_receipt_v1",
                    "status": "PASS",
                    "evaluation_id": evaluation_id,
                    "fit_id": fit_id,
                    "model_id": model_id,
                    "fold_id": fold_id,
                    "seed": 7,
                    "segments": {
                        key: [value[0].date().isoformat(), value[1].date().isoformat()]
                        for key, value in qlib_fold.segments.items()
                    },
                    "row_counts": qlib_fold.row_counts,
                    "key_sha256": qlib_fold.key_sha256,
                    "feature_count": len(qlib_fold.feature_columns),
                    "diagnostic_metrics": metrics,
                    "training_summary": model.training_summary(),
                    "checkpoint": checkpoint_inventory(checkpoint_dir),
                    "checkpoint_replay": "PASS_EXACT",
                    "resources": {
                        "elapsed_seconds": time.monotonic() - started,
                        "process_max_rss": int(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        ),
                        "process_max_rss_unit": "KiB_ON_LINUX",
                        "gpu_peak_allocated_bytes": int(
                            torch.cuda.max_memory_allocated()
                        ),
                    },
                    "final_oos_market_partitions_opened": False,
                    "cost_adjusted_metrics_computed": False,
                    "portfolio_backtests": 0,
                }
                receipt["content_sha256"] = content_hash(receipt)
                receipt_path = fold_dir / "fold_receipt.json"
                atomic_write_json(receipt_path, receipt)
                fold_receipts.append(
                    {
                        "fold_id": fold_id,
                        "path": str(receipt_path.relative_to(output_dir)),
                        "sha256": sha256_file(receipt_path),
                        "content_sha256": receipt["content_sha256"],
                    }
                )
                append_jsonl(
                    journal_path,
                    {
                        "event": "MODEL_FIT_COMPLETED",
                        "timestamp": now(),
                        "evaluation_id": evaluation_id,
                        "fit_id": fit_id,
                        "model_id": model_id,
                        "fold_id": fold_id,
                        "status": "PASS",
                        "fold_receipt_sha256": sha256_file(receipt_path),
                        "counts_as_candidate_evaluation": False,
                        "counts_as_model_fit": False,
                    },
                )
                active_fit_id = None
                active_fold_id = None
                del restored, model, qlib_fold, replay_scores
                gc.collect()
                torch.cuda.empty_cache()

            deterministic_refit_binding: dict[str, Any] | None = None
            refit_spec = spec["deterministic_refit"]
            if model_id == refit_spec["model_id"]:
                if deterministic_reference is None:
                    raise RuntimeError("M6 deterministic reference is missing")
                fold_id = refit_spec["fold_id"]
                refit_dir = candidate_dir / "deterministic_refit" / fold_id
                refit_dir.mkdir(parents=True)
                fit_id = f"{evaluation_id}:{fold_id}:deterministic_refit"
                active_fit_id = fit_id
                active_fold_id = fold_id
                append_jsonl(
                    journal_path,
                    {
                        "event": "MODEL_FIT_STARTED",
                        "timestamp": now(),
                        "family_id": "qlib-peerlite-a-share-daily-v0",
                        "evaluation_id": evaluation_id,
                        "fit_id": fit_id,
                        "model_id": model_id,
                        "fold_id": fold_id,
                        "purpose": "DETERMINISTIC_REFIT",
                        "seed": 7,
                        "counts_as_candidate_evaluation": False,
                        "counts_as_model_fit": True,
                    },
                )
                started = time.monotonic()
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                qlib_fold = build_qlib_fold(
                    product,
                    fold_specs[fold_id],
                    embargo_sessions=spec["schedule"]["embargo_sessions"],
                )
                refit_model = PeerLiteModel(**candidate["parameters"])
                refit_model.fit(qlib_fold.dataset)
                refit_scores = refit_model.predict(qlib_fold.dataset, segment="test")
                if not deterministic_reference.index.equals(
                    refit_scores.index
                ) or not np.array_equal(
                    deterministic_reference.to_numpy(dtype=float),
                    refit_scores.to_numpy(dtype=float),
                ):
                    raise RuntimeError("M6 PeerLite deterministic refit mismatch")
                refit_receipt = {
                    "schema_version": "qlib_peerlite_m6_deterministic_refit_v1",
                    "status": "PASS_EXACT",
                    "evaluation_id": evaluation_id,
                    "fit_id": fit_id,
                    "model_id": model_id,
                    "fold_id": fold_id,
                    "seed": 7,
                    "reference_score_sha256": score_digest(deterministic_reference),
                    "refit_score_sha256": score_digest(refit_scores),
                    "score_rows": len(refit_scores),
                    "training_summary": refit_model.training_summary(),
                    "resources": {
                        "elapsed_seconds": time.monotonic() - started,
                        "process_max_rss": int(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        ),
                        "process_max_rss_unit": "KiB_ON_LINUX",
                        "gpu_peak_allocated_bytes": int(
                            torch.cuda.max_memory_allocated()
                        ),
                    },
                    "final_oos_market_partitions_opened": False,
                }
                refit_receipt["content_sha256"] = content_hash(refit_receipt)
                refit_path = refit_dir / "deterministic_refit_receipt.json"
                atomic_write_json(refit_path, refit_receipt)
                deterministic_refit_binding = {
                    "path": str(refit_path.relative_to(output_dir)),
                    "sha256": sha256_file(refit_path),
                    "content_sha256": refit_receipt["content_sha256"],
                }
                append_jsonl(
                    journal_path,
                    {
                        "event": "MODEL_FIT_COMPLETED",
                        "timestamp": now(),
                        "evaluation_id": evaluation_id,
                        "fit_id": fit_id,
                        "model_id": model_id,
                        "fold_id": fold_id,
                        "purpose": "DETERMINISTIC_REFIT",
                        "status": "PASS_EXACT",
                        "receipt_sha256": sha256_file(refit_path),
                        "counts_as_candidate_evaluation": False,
                        "counts_as_model_fit": False,
                    },
                )
                active_fit_id = None
                active_fold_id = None
                del refit_model, qlib_fold, refit_scores
                gc.collect()
                torch.cuda.empty_cache()

            predictions = pd.concat(prediction_tables, ignore_index=True)
            predictions = predictions.sort_values(
                ["datetime", "instrument"],
                ignore_index=True,
            )
            if predictions.duplicated(["datetime", "instrument"]).any():
                raise RuntimeError(f"duplicate rolling predictions: {model_id}")
            prediction_path = candidate_dir / "predictions.parquet"
            predictions.to_parquet(prediction_path, index=False)
            all_scores = pd.concat(score_parts).sort_index()
            all_labels = pd.concat(label_parts).sort_index()
            overall_metrics = finite_metrics(evaluate_predictions(all_scores, all_labels))
            metrics_payload = {
                "schema_version": "qlib_peerlite_m6_diagnostic_metrics_v1",
                "model_id": model_id,
                "role": "PRE_FINAL_OOS_DIAGNOSTIC_ONLY",
                "overall": overall_metrics,
                "by_fold": {
                    item["fold_id"]: json.loads(
                        (output_dir / item["path"]).read_text(encoding="utf-8")
                    )["diagnostic_metrics"]
                    for item in fold_receipts
                },
                "selection_allowed": False,
                "cost_adjusted_metrics_computed": False,
                "final_oos_metrics_computed": False,
            }
            metrics_path = candidate_dir / "metrics.json"
            atomic_write_json(metrics_path, metrics_payload)
            candidate_receipt = {
                "schema_version": "qlib_peerlite_m6_candidate_receipt_v1",
                "status": "PASS",
                "evaluation_id": evaluation_id,
                "model_id": model_id,
                "seed": 7,
                "spec_content_sha256": spec["content_sha256"],
                "product_manifest_sha256": product.product_manifest_sha256,
                "prediction_rows": len(predictions),
                "prediction_columns": list(predictions.columns),
                "prediction_sha256": sha256_file(prediction_path),
                "metrics_sha256": sha256_file(metrics_path),
                "fold_receipts": fold_receipts,
                "deterministic_refit": deterministic_refit_binding,
                "model_fits": len(fold_receipts)
                + (1 if deterministic_refit_binding is not None else 0),
                "diagnostic_metrics_computed": True,
                "selection_allowed": False,
                "cost_adjusted_metrics_computed": False,
                "portfolio_backtests": 0,
                "final_oos_market_partitions_opened": False,
                "final_oos_metrics_computed": False,
            }
            candidate_receipt["content_sha256"] = content_hash(candidate_receipt)
            candidate_receipt_path = candidate_dir / "candidate_receipt.json"
            atomic_write_json(candidate_receipt_path, candidate_receipt)

            experiment_name = "qlib_peerlite_m6_peerlite_mse"
            recorder_id = record_run_with_qlib(
                experiment_name=experiment_name,
                recorder_name=f"{model_id.lower()}-seed7-{output_dir.name}",
                parameters={
                    "stage": "M6-PEERLITE-MSE",
                    "model_id": model_id,
                    "seed": 7,
                    "fold_count": len(fold_receipts),
                    "spec_content_sha256": spec["content_sha256"],
                    "product_manifest_sha256": product.product_manifest_sha256,
                    "final_oos_opened": False,
                    "cost_adjusted_metrics_computed": False,
                    "selection_allowed": False,
                },
                metrics=overall_metrics,
                artifacts=[candidate_receipt_path, metrics_path, prediction_path],
            )
            expected_artifacts = {
                candidate_receipt_path.name: sha256_file(candidate_receipt_path),
                metrics_path.name: sha256_file(metrics_path),
                prediction_path.name: sha256_file(prediction_path),
            }
            recorder_readback(
                recorder_id=recorder_id,
                experiment_name=experiment_name,
                expected=expected_artifacts,
            )
            candidate_results.append(
                {
                    "model_id": model_id,
                    "evaluation_id": evaluation_id,
                    "candidate_receipt": {
                        "path": str(candidate_receipt_path.relative_to(output_dir)),
                        "sha256": sha256_file(candidate_receipt_path),
                        "content_sha256": candidate_receipt["content_sha256"],
                    },
                    "predictions": {
                        "path": str(prediction_path.relative_to(output_dir)),
                        "sha256": sha256_file(prediction_path),
                        "rows": len(predictions),
                    },
                    "metrics": {
                        "path": str(metrics_path.relative_to(output_dir)),
                        "sha256": sha256_file(metrics_path),
                    },
                    "qlib_recorder": {
                        "experiment_name": experiment_name,
                        "recorder_id": recorder_id,
                        "artifact_readback": "PASS",
                    },
                    "model_fits": candidate_receipt["model_fits"],
                }
            )
            append_jsonl(
                journal_path,
                {
                    "event": "CANDIDATE_EVALUATION_COMPLETED",
                    "timestamp": now(),
                    "family_id": "qlib-peerlite-a-share-daily-v0",
                    "evaluation_id": evaluation_id,
                    "model_id": model_id,
                    "seed": 7,
                    "status": "PASS",
                    "model_fits": candidate_receipt["model_fits"],
                    "candidate_receipt_sha256": sha256_file(candidate_receipt_path),
                    "counts_as_candidate_evaluation": False,
                    "counts_as_model_fit": False,
                },
            )
            active_evaluation_id = None
            active_model_id = None

        run_manifest = {
            "schema_version": "qlib_peerlite_m6_run_manifest_v1",
            "status": "PASS",
            "stage": "M6-PEERLITE-MSE",
            "created_at": now(),
            "claim_ceiling": "PRE_FINAL_OOS_DIAGNOSTIC",
            "spec": {
                "path": str(spec_path),
                "sha256": sha256_file(spec_path),
                "content_sha256": spec["content_sha256"],
            },
            "product": {
                "product_id": product.product_id,
                "manifest_sha256": product.product_manifest_sha256,
                "rows": len(product.frame),
                "feature_count": len(product.feature_columns),
                "date_max": product.frame.index.get_level_values(
                    "datetime"
                ).max().date().isoformat(),
            },
            "candidate_evaluations": len(candidate_results),
            "model_fits": sum(item["model_fits"] for item in candidate_results),
            "candidates": candidate_results,
            "ledger_events": {
                "path": journal_path.name,
                "sha256_before_terminal_event": sha256_file(journal_path),
            },
            "safeguards": copy.deepcopy(spec["safeguards"]),
            "limitations": [
                "M6 diagnostics stop before final OOS and cannot establish Alpha.",
                "K16 remains the parsimonious registered primary; M6 performs no model selection.",
                "CCC, market gating, portfolios and costs are prohibited in this run.",
            ],
        }
        if run_manifest["model_fits"] != spec["schedule"]["model_fits"]:
            raise RuntimeError("M6 completed model-fit count differs from frozen schedule")
        run_manifest["content_sha256"] = content_hash(run_manifest)
        run_manifest_path = output_dir / "run_manifest.json"
        atomic_write_json(run_manifest_path, run_manifest)
        append_jsonl(
            journal_path,
            {
                "event": "M6_RUN_COMPLETED",
                "timestamp": now(),
                "status": "PASS",
                "candidate_evaluations": len(candidate_results),
                "model_fits": run_manifest["model_fits"],
                "run_manifest_sha256": sha256_file(run_manifest_path),
                "counts_as_candidate_evaluation": False,
                "counts_as_model_fit": False,
            },
        )
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "run_manifest": str(run_manifest_path),
                    "run_manifest_sha256": sha256_file(run_manifest_path),
                    "candidate_evaluations": len(candidate_results),
                    "model_fits": run_manifest["model_fits"],
                    "final_oos_market_partitions_opened": False,
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        failure = {
            "schema_version": "qlib_peerlite_m6_failure_v1",
            "status": "FAIL",
            "created_at": now(),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "final_oos_market_partitions_opened": False,
        }
        atomic_write_json(output_dir / "failure_receipt.json", failure)
        if active_fit_id is not None:
            append_jsonl(
                journal_path,
                {
                    "event": "MODEL_FIT_FAILED",
                    "timestamp": now(),
                    "evaluation_id": active_evaluation_id,
                    "fit_id": active_fit_id,
                    "model_id": active_model_id,
                    "fold_id": active_fold_id,
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "counts_as_candidate_evaluation": False,
                    "counts_as_model_fit": False,
                },
            )
        elif active_evaluation_id is not None:
            append_jsonl(
                journal_path,
                {
                    "event": "CANDIDATE_EVALUATION_FAILED",
                    "timestamp": now(),
                    "evaluation_id": active_evaluation_id,
                    "model_id": active_model_id,
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "counts_as_candidate_evaluation": False,
                    "counts_as_model_fit": False,
                },
            )
        append_jsonl(
            journal_path,
            {
                "event": "M6_RUN_FAILED",
                "timestamp": now(),
                "status": "FAIL",
                "error_type": type(exc).__name__,
                "failure_receipt_sha256": sha256_file(
                    output_dir / "failure_receipt.json"
                ),
                "counts_as_candidate_evaluation": False,
                "counts_as_model_fit": False,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path, required=True)
    args = parser.parse_args()
    run(
        project_root=args.project_root,
        product_dir=args.product_dir,
        spec_path=args.spec,
        output_dir=args.output_dir,
        tracking_dir=args.tracking_dir,
    )


if __name__ == "__main__":
    main()
