#!/usr/bin/env python3
"""Verify the M4 Qlib data, rolling-fold and Recorder foundation.

This command performs no model fit, signal evaluation, portfolio evaluation or
final-OOS access.  It loads only the M3-qualified 2012-2024 product, constructs
all seven declared rolling folds, repeats one fold for deterministic replay,
and records the mechanics receipt through Qlib's MLflow-backed Recorder.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qlib_peerlite.data.qlib_dataset import build_qlib_fold, load_bound_product_frame
from qlib_peerlite.data.splits import annual_folds
from qlib_peerlite.governance.artifacts import sha256_file
from qlib_peerlite.governance.gates import EmpiricalEvidence, assert_empirical_ready
from qlib_peerlite.qlib_integration import (
    initialize_qlib,
    qlib_version,
    record_run_with_qlib,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def empirical_evidence(project_root: Path, product_dir: Path) -> EmpiricalEvidence:
    return EmpiricalEvidence(
        contract_path=project_root / "contracts/immutable/research_contract_pit_v2.json",
        contract_receipt_path=project_root / "contracts/immutable/contract_validation_pit_v2.json",
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


def fold_receipt(fold: Any) -> dict[str, Any]:
    return {
        "fold_id": fold.fold_id,
        "segments": {
            key: [value[0].date().isoformat(), value[1].date().isoformat()]
            for key, value in fold.segments.items()
        },
        "row_counts": fold.row_counts,
        "key_sha256": fold.key_sha256,
        "feature_count": len(fold.feature_columns),
    }


def publish(
    *,
    project_root: Path,
    product_dir: Path,
    output_dir: Path,
    tracking_dir: Path,
) -> None:
    project_root = project_root.resolve()
    product_dir = product_dir.resolve()
    output_dir = output_dir.resolve()
    tracking_dir = tracking_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("output directory must be new or empty")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        evidence = empirical_evidence(project_root, product_dir)
        assert_empirical_ready(evidence)
        product = load_bound_product_frame(product_dir, verify_all_files=True)
        if product.frame.empty:
            raise RuntimeError("qualified product is empty")

        folds: list[dict[str, Any]] = []
        replay_reference: dict[str, Any] | None = None
        for spec in annual_folds():
            built = build_qlib_fold(product, spec, embargo_sessions=5)
            receipt = fold_receipt(built)
            folds.append(receipt)
            if spec.fold_id == "wf_2018":
                replay_reference = receipt
            del built
            gc.collect()
        if len(folds) != 7 or replay_reference is None:
            raise RuntimeError("declared seven-fold schedule was not constructed")

        replay = build_qlib_fold(product, annual_folds()[0], embargo_sessions=5)
        replay_receipt = fold_receipt(replay)
        del replay
        gc.collect()
        if replay_receipt != replay_reference:
            raise RuntimeError("Qlib fold replay is not deterministic")

        receipt = {
            "schema_version": "qlib_peerlite_qlib_foundation_receipt_v1",
            "created_at": datetime.now(SHANGHAI).isoformat(),
            "status": "PASS",
            "gate": "M4_QLIB_FOUNDATION",
            "claim_ceiling": "MECHANICS_ONLY",
            "empirical_gate": {
                "result": "PASS",
                "m3_gate_sha256": sha256_file(evidence.m3_gate_path),
                "contract_sha256": sha256_file(evidence.contract_path),
                "fixed_pit_manifest_sha256": sha256_file(evidence.pit_manifest_path),
                "behavior_manifest_sha256": sha256_file(evidence.behavior_manifest_path),
            },
            "qlib": {
                "version": qlib_version(),
                "dataset_class": "qlib.data.dataset.DatasetH",
                "handler_class": "qlib.data.dataset.handler.DataHandlerLP",
                "loader_class": "qlib.data.dataset.loader.StaticDataLoader",
                "recorder_backend": "Qlib MLflowExpManager with SQLite tracking",
            },
            "code_binding": {
                "mode": "EXPLICIT_SHA256",
                "qlib_automatic_git_capture": "UNAVAILABLE_SERVER_COPY_HAS_NO_GIT_METADATA",
                "files": {
                    "scripts/server/verify_qlib_foundation.py": sha256_file(
                        Path(__file__).resolve()
                    ),
                    "src/qlib_peerlite/data/qlib_dataset.py": sha256_file(
                        project_root / "src/qlib_peerlite/data/qlib_dataset.py"
                    ),
                    "src/qlib_peerlite/data/splits.py": sha256_file(
                        project_root / "src/qlib_peerlite/data/splits.py"
                    ),
                    "src/qlib_peerlite/governance/gates.py": sha256_file(
                        project_root / "src/qlib_peerlite/governance/gates.py"
                    ),
                    "src/qlib_peerlite/qlib_integration.py": sha256_file(
                        project_root / "src/qlib_peerlite/qlib_integration.py"
                    ),
                    "uv.lock": sha256_file(project_root / "uv.lock"),
                },
            },
            "data_product": {
                "product_id": product.product_id,
                "manifest_sha256": product.product_manifest_sha256,
                "rows": len(product.frame),
                "feature_count": len(product.feature_columns),
                "partition_sha256": list(product.source_file_sha256),
                "date_min": str(product.frame.index.get_level_values("datetime").min().date()),
                "date_max": str(product.frame.index.get_level_values("datetime").max().date()),
            },
            "rolling_folds": folds,
            "deterministic_replay": {
                "fold_id": "wf_2018",
                "result": "PASS",
                "receipt_sha256": hashlib.sha256(
                    canonical_json(replay_receipt).encode("utf-8")
                ).hexdigest(),
            },
            "safeguards": {
                "model_fits": 0,
                "signals_evaluated": 0,
                "portfolio_backtests": 0,
                "performance_metrics_computed": False,
                "final_oos_market_partitions_opened": False,
            },
            "limitations": [
                "M4 verifies Qlib data, split and Recorder mechanics only.",
                "No real-data model, signal metric, backtest metric or Alpha claim was produced.",
                "Capacity metadata and portfolio execution semantics remain later-gate work.",
            ],
        }
        receipt["content_sha256"] = hashlib.sha256(
            canonical_json(receipt).encode("utf-8")
        ).hexdigest()
        receipt_path = staging / "qlib_foundation_receipt.json"
        write_json(receipt_path, receipt)

        initialize_qlib(
            provider_dir=tracking_dir / "empty_provider",
            tracking_dir=tracking_dir / "mlflow",
        )
        experiment_name = "qlib_peerlite_m4_foundation"
        recorder_id = record_run_with_qlib(
            experiment_name=experiment_name,
            recorder_name=f"m4-{receipt['content_sha256'][:12]}",
            parameters={
                "gate": "M4_QLIB_FOUNDATION",
                "claim_ceiling": "MECHANICS_ONLY",
                "product_id": product.product_id,
                "product_manifest_sha256": product.product_manifest_sha256,
                "fold_count": len(folds),
                "feature_count": len(product.feature_columns),
                "final_oos_opened": False,
                "performance_metrics_computed": False,
            },
            metrics=None,
            artifacts=[receipt_path],
        )
        from qlib.workflow import R

        recorder = R.get_recorder(
            recorder_id=recorder_id,
            experiment_name=experiment_name,
        )
        artifacts = recorder.list_artifacts()
        if "qlib_foundation_receipt.json" not in artifacts:
            raise RuntimeError("Qlib Recorder did not retain the foundation receipt")
        downloaded = Path(recorder.download_artifact("qlib_foundation_receipt.json"))
        if sha256_file(downloaded) != sha256_file(receipt_path):
            raise RuntimeError("Qlib Recorder artifact bytes differ from the receipt")

        manifest = {
            "schema_version": "qlib_peerlite_qlib_foundation_manifest_v1",
            "status": "PASS",
            "receipt": {
                "path": receipt_path.name,
                "sha256": sha256_file(receipt_path),
                "content_sha256": receipt["content_sha256"],
            },
            "qlib_recorder": {
                "experiment_name": experiment_name,
                "recorder_id": recorder_id,
                "artifact": "qlib_foundation_receipt.json",
                "artifact_sha256": sha256_file(downloaded),
                "tracking_backend": "SQLITE",
            },
            "final_oos_market_partitions_opened": False,
            "performance_metrics_computed": False,
        }
        manifest["content_sha256"] = hashlib.sha256(
            canonical_json(manifest).encode("utf-8")
        ).hexdigest()
        manifest_path = staging / "foundation_manifest.json"
        write_json(manifest_path, manifest)

        for path in staging.iterdir():
            if path.is_file():
                path.chmod(0o440)
        staging.chmod(0o550)
        if output_dir.exists():
            output_dir.rmdir()
        os.replace(staging, output_dir)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "folds": len(folds),
                    "rows": len(product.frame),
                    "recorder_id": recorder_id,
                    "final_oos_market_partitions_opened": False,
                    "performance_metrics_computed": False,
                    "manifest_sha256": sha256_file(output_dir / "foundation_manifest.json"),
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path, required=True)
    args = parser.parse_args()
    publish(
        project_root=args.project_root,
        product_dir=args.product_dir,
        output_dir=args.output_dir,
        tracking_dir=args.tracking_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
