#!/usr/bin/env python3
"""Run the two frozen M5 baselines on the qualified pre-final-OOS product."""

from __future__ import annotations

import argparse
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
from qlib_peerlite.governance.m5_spec import load_and_verify_m5_spec
from qlib_peerlite.models.common import seed_everything
from qlib_peerlite.models.lightgbm_model import LightGBMBaseline
from qlib_peerlite.models.mlp import MLPBaseline
from qlib_peerlite.qlib_integration import (
    initialize_qlib,
    record_run_with_qlib,
)

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
        raise RuntimeError("baseline diagnostics contain a non-finite value")
    return output


def build_model(candidate: dict[str, Any]) -> LightGBMBaseline | MLPBaseline:
    model_id = candidate["model_id"]
    parameters = dict(candidate["parameters"])
    if model_id == "B0_LIGHTGBM":
        return LightGBMBaseline(**parameters)
    if model_id == "B1_MLP":
        return MLPBaseline(**parameters)
    raise RuntimeError(f"unregistered M5 candidate: {model_id}")


def load_checkpoint(
    model_id: str,
    checkpoint_dir: Path,
    *,
    device: str,
) -> LightGBMBaseline | MLPBaseline:
    if model_id == "B0_LIGHTGBM":
        return LightGBMBaseline.load_checkpoint(checkpoint_dir)
    if model_id == "B1_MLP":
        return MLPBaseline.load_checkpoint(checkpoint_dir, device=device)
    raise RuntimeError(f"unregistered M5 checkpoint: {model_id}")


def checkpoint_inventory(path: Path) -> dict[str, str]:
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise RuntimeError("checkpoint inventory is empty")
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
    with tempfile.TemporaryDirectory(prefix=f"qlib-readback-{recorder_id}-") as directory:
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
            "event": "M5_RUN_STARTED",
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
        spec = load_and_verify_m5_spec(project_root, spec_path)
        seed_everything(spec["schedule"]["seed"])
        assert_empirical_ready(evidence_paths(project_root, product_dir))
        m4 = json.loads(
            (project_root / "evidence/gates/M4_qlib_foundation_gate.json").read_text(
                encoding="utf-8"
            )
        )
        if m4.get("status") != "PASS" or m4.get("passed") is not True:
            raise RuntimeError("M4 Qlib foundation gate is not PASS")
        product = load_bound_product_frame(product_dir, verify_all_files=True)
        if product.frame.index.get_level_values("datetime").max() >= pd.Timestamp(
            "2025-01-01"
        ):
            raise RuntimeError("M5 product crosses the final-OOS boundary")
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
            deterministic_reference: pd.Series | None = None

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
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.reset_peak_memory_stats()
                qlib_fold = build_qlib_fold(
                    product,
                    fold_specs[fold_id],
                    embargo_sessions=spec["schedule"]["embargo_sessions"],
                )
                model = build_model(candidate)
                model.fit(qlib_fold.dataset)
                scores = model.predict(qlib_fold.dataset, segment="test")
                labels = qlib_fold.dataset.prepare("test", col_set="label").iloc[:, 0]
                labels = labels.loc[scores.index].astype(float)
                metrics = finite_metrics(evaluate_predictions(scores, labels))
                checkpoint_dir = fold_dir / "checkpoint"
                model.save_checkpoint(checkpoint_dir)
                device = candidate["parameters"].get("device", "auto")
                restored = load_checkpoint(model_id, checkpoint_dir, device=device)
                replay_scores = restored.predict(qlib_fold.dataset, segment="test")
                if not np.array_equal(
                    scores.to_numpy(dtype=float),
                    replay_scores.to_numpy(dtype=float),
                ):
                    raise RuntimeError(f"checkpoint replay mismatch: {model_id}/{fold_id}")

                table = score_frame(
                    scores.index,
                    scores.to_numpy(),
                    model_id,
                    fold_id,
                )
                if table["datetime"].max() >= pd.Timestamp("2025-01-01"):
                    raise RuntimeError("prediction output crosses final OOS")
                prediction_tables.append(table)
                score_parts.append(scores)
                label_parts.append(labels)
                replay_spec = spec["deterministic_refit"]
                if (
                    model_id == replay_spec["model_id"]
                    and fold_id == replay_spec["fold_id"]
                ):
                    deterministic_reference = scores.copy()
                elapsed = time.monotonic() - started
                gpu_peak = (
                    int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
                )
                training_summary = model.training_summary()
                receipt = {
                    "schema_version": "qlib_peerlite_m5_fold_receipt_v1",
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
                    "training_summary": training_summary,
                    "checkpoint": checkpoint_inventory(checkpoint_dir),
                    "checkpoint_replay": "PASS_EXACT",
                    "resources": {
                        "elapsed_seconds": elapsed,
                        "process_max_rss": int(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        ),
                        "process_max_rss_unit": "KiB_ON_LINUX",
                        "gpu_peak_allocated_bytes": gpu_peak,
                    },
                    "final_oos_market_partitions_opened": False,
                    "cost_adjusted_metrics_computed": False,
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
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            deterministic_refit_receipt: dict[str, Any] | None = None
            replay_spec = spec["deterministic_refit"]
            if model_id == replay_spec["model_id"]:
                replay_fold_id = replay_spec["fold_id"]
                if deterministic_reference is None:
                    raise RuntimeError("deterministic-refit reference scores are missing")
                replay_dir = candidate_dir / "deterministic_refit" / replay_fold_id
                replay_dir.mkdir(parents=True)
                replay_fit_id = f"{evaluation_id}:{replay_fold_id}:deterministic_refit"
                active_fit_id = replay_fit_id
                active_fold_id = replay_fold_id
                append_jsonl(
                    journal_path,
                    {
                        "event": "MODEL_FIT_STARTED",
                        "timestamp": now(),
                        "family_id": "qlib-peerlite-a-share-daily-v0",
                        "evaluation_id": evaluation_id,
                        "fit_id": replay_fit_id,
                        "model_id": model_id,
                        "fold_id": replay_fold_id,
                        "purpose": "DETERMINISTIC_REFIT",
                        "seed": 7,
                        "counts_as_candidate_evaluation": False,
                        "counts_as_model_fit": True,
                    },
                )
                replay_started = time.monotonic()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.reset_peak_memory_stats()
                replay_fold = build_qlib_fold(
                    product,
                    fold_specs[replay_fold_id],
                    embargo_sessions=spec["schedule"]["embargo_sessions"],
                )
                replay_model = build_model(candidate)
                replay_model.fit(replay_fold.dataset)
                refit_scores = replay_model.predict(replay_fold.dataset, segment="test")
                same_index = deterministic_reference.index.equals(refit_scores.index)
                same_values = np.array_equal(
                    deterministic_reference.to_numpy(dtype=float),
                    refit_scores.to_numpy(dtype=float),
                )
                if not same_index or not same_values:
                    raise RuntimeError("B1 deterministic refit score mismatch")
                deterministic_refit = {
                    "schema_version": "qlib_peerlite_m5_deterministic_refit_v1",
                    "status": "PASS_EXACT",
                    "evaluation_id": evaluation_id,
                    "fit_id": replay_fit_id,
                    "model_id": model_id,
                    "fold_id": replay_fold_id,
                    "seed": 7,
                    "reference_score_sha256": score_digest(deterministic_reference),
                    "refit_score_sha256": score_digest(refit_scores),
                    "score_rows": len(refit_scores),
                    "training_summary": replay_model.training_summary(),
                    "resources": {
                        "elapsed_seconds": time.monotonic() - replay_started,
                        "process_max_rss": int(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        ),
                        "process_max_rss_unit": "KiB_ON_LINUX",
                        "gpu_peak_allocated_bytes": (
                            int(torch.cuda.max_memory_allocated())
                            if torch.cuda.is_available()
                            else 0
                        ),
                    },
                    "final_oos_market_partitions_opened": False,
                }
                deterministic_refit["content_sha256"] = content_hash(deterministic_refit)
                deterministic_refit_path = replay_dir / "deterministic_refit_receipt.json"
                atomic_write_json(deterministic_refit_path, deterministic_refit)
                deterministic_refit_receipt = {
                    "path": str(deterministic_refit_path.relative_to(output_dir)),
                    "sha256": sha256_file(deterministic_refit_path),
                    "content_sha256": deterministic_refit["content_sha256"],
                }
                append_jsonl(
                    journal_path,
                    {
                        "event": "MODEL_FIT_COMPLETED",
                        "timestamp": now(),
                        "evaluation_id": evaluation_id,
                        "fit_id": replay_fit_id,
                        "model_id": model_id,
                        "fold_id": replay_fold_id,
                        "purpose": "DETERMINISTIC_REFIT",
                        "status": "PASS_EXACT",
                        "receipt_sha256": sha256_file(deterministic_refit_path),
                        "counts_as_candidate_evaluation": False,
                        "counts_as_model_fit": False,
                    },
                )
                active_fit_id = None
                active_fold_id = None
                del replay_model, replay_fold, refit_scores
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            predictions = pd.concat(prediction_tables, ignore_index=True)
            predictions = predictions.sort_values(
                ["datetime", "instrument"], ignore_index=True
            )
            if predictions.duplicated(["datetime", "instrument"]).any():
                raise RuntimeError(f"duplicate rolling predictions: {model_id}")
            prediction_path = candidate_dir / "predictions.parquet"
            predictions.to_parquet(prediction_path, index=False)

            all_scores = pd.concat(score_parts).sort_index()
            all_labels = pd.concat(label_parts).sort_index()
            overall_metrics = finite_metrics(evaluate_predictions(all_scores, all_labels))
            metrics_payload = {
                "schema_version": "qlib_peerlite_m5_diagnostic_metrics_v1",
                "model_id": model_id,
                "role": "PRE_FINAL_OOS_DIAGNOSTIC_ONLY",
                "overall": overall_metrics,
                "by_fold": {
                    item["fold_id"]: json.loads(
                        (output_dir / item["path"]).read_text(encoding="utf-8")
                    )["diagnostic_metrics"]
                    for item in fold_receipts
                },
                "cost_adjusted_metrics_computed": False,
                "final_oos_metrics_computed": False,
            }
            metrics_path = candidate_dir / "metrics.json"
            atomic_write_json(metrics_path, metrics_payload)
            candidate_receipt = {
                "schema_version": "qlib_peerlite_m5_candidate_receipt_v1",
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
                "deterministic_refit": deterministic_refit_receipt,
                "model_fits": len(fold_receipts)
                + (1 if deterministic_refit_receipt is not None else 0),
                "diagnostic_metrics_computed": True,
                "cost_adjusted_metrics_computed": False,
                "portfolio_backtests": 0,
                "final_oos_market_partitions_opened": False,
                "final_oos_metrics_computed": False,
            }
            candidate_receipt["content_sha256"] = content_hash(candidate_receipt)
            candidate_receipt_path = candidate_dir / "candidate_receipt.json"
            atomic_write_json(candidate_receipt_path, candidate_receipt)

            experiment_name = "qlib_peerlite_m5_baselines"
            recorder_id = record_run_with_qlib(
                experiment_name=experiment_name,
                recorder_name=f"{model_id.lower()}-seed7-{output_dir.name}",
                parameters={
                    "stage": "M5-STRICT_BASELINES",
                    "model_id": model_id,
                    "seed": 7,
                    "fold_count": len(fold_receipts),
                    "spec_content_sha256": spec["content_sha256"],
                    "product_manifest_sha256": product.product_manifest_sha256,
                    "final_oos_opened": False,
                    "cost_adjusted_metrics_computed": False,
                },
                metrics=overall_metrics,
                artifacts=[candidate_receipt_path, metrics_path, prediction_path],
            )
            expected_recorder_artifacts = {
                candidate_receipt_path.name: sha256_file(candidate_receipt_path),
                metrics_path.name: sha256_file(metrics_path),
                prediction_path.name: sha256_file(prediction_path),
            }
            recorder_readback(
                recorder_id=recorder_id,
                experiment_name=experiment_name,
                expected=expected_recorder_artifacts,
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
            "schema_version": "qlib_peerlite_m5_run_manifest_v1",
            "status": "PASS",
            "stage": "M5-STRICT_BASELINES",
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
                "date_max": str(
                    product.frame.index.get_level_values("datetime").max().date()
                ),
            },
            "candidate_evaluations": len(candidate_results),
            "model_fits": sum(item["model_fits"] for item in candidate_results),
            "candidates": candidate_results,
            "ledger_events": {
                "path": journal_path.name,
                "sha256_before_terminal_event": sha256_file(journal_path),
            },
            "safeguards": {
                "final_oos_market_partitions_opened": False,
                "final_oos_metrics_computed": False,
                "portfolio_backtests": 0,
                "cost_adjusted_metrics_computed": False,
                "model_selection_performed": False,
            },
            "limitations": [
                "M5 results are pre-final-OOS development diagnostics, not final evidence.",
                (
                    "No portfolio or cost-adjusted comparison was run because the fee "
                    "receipt is unresolved."
                ),
                "The two baselines establish references; they do not promote PeerLite.",
            ],
        }
        run_manifest["content_sha256"] = content_hash(run_manifest)
        run_manifest_path = output_dir / "run_manifest.json"
        atomic_write_json(run_manifest_path, run_manifest)
        append_jsonl(
            journal_path,
            {
                "event": "M5_RUN_COMPLETED",
                "timestamp": now(),
                "status": "PASS",
                "run_manifest_sha256": sha256_file(run_manifest_path),
                "candidate_evaluations": len(candidate_results),
                "model_fits": run_manifest["model_fits"],
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
            "schema_version": "qlib_peerlite_m5_failure_v1",
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
                "event": "M5_RUN_FAILED",
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
