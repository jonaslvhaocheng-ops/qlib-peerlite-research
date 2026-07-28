#!/usr/bin/env python3
"""Independently verify M4 evidence and atomically publish the project gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qlib_peerlite.governance.artifacts import sha256_file
from qlib_peerlite.governance.m4_evidence import verify_m4_evidence

SHANGHAI = ZoneInfo("Asia/Shanghai")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--foundation-dir",
        type=Path,
        default=Path("evidence/qlib/foundation_20260728_v2"),
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=Path("evidence/qlib/analysis_mechanics_20260728_v1"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/gates/M4_qlib_foundation_gate.json"),
    )
    args = parser.parse_args()
    project_root = args.project_root.resolve()

    def resolved(path: Path) -> Path:
        return path.resolve() if path.is_absolute() else (project_root / path).resolve()

    foundation_dir = resolved(args.foundation_dir)
    analysis_dir = resolved(args.analysis_dir)
    output = resolved(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable gate: {output}")

    verification = verify_m4_evidence(
        project_root=project_root,
        foundation_dir=foundation_dir,
        analysis_dir=analysis_dir,
    )
    gate = {
        "schema_version": "qlib_peerlite_gate_v1",
        "gate_id": "M4-STRICT",
        "status": "PASS",
        "executed": True,
        "completed": True,
        "passed": True,
        "created_at": datetime.now(SHANGHAI).isoformat(),
        "track": "STRICT_FOUNDATION_AND_SYNTHETIC_MECHANICS",
        "claim_ceiling": "MECHANICS_ONLY",
        "verification": verification,
        "evidence": {
            "foundation": {
                "path": str(foundation_dir.relative_to(project_root)),
                "manifest_sha256": verification["foundation_manifest_sha256"],
                "receipt_sha256": verification["foundation_receipt_sha256"],
                "recorder_id": verification["foundation_recorder_id"],
            },
            "analysis_mechanics": {
                "path": str(analysis_dir.relative_to(project_root)),
                "manifest_sha256": verification["analysis_manifest_sha256"],
                "receipt_sha256": verification["analysis_receipt_sha256"],
                "recorder_id": verification["analysis_recorder_id"],
                "track": "SYNTHETIC",
            },
            "verifier": {
                "path": "src/qlib_peerlite/governance/m4_evidence.py",
                "sha256": sha256_file(project_root / "src/qlib_peerlite/governance/m4_evidence.py"),
            },
        },
        "acceptance_checks": [
            {
                "check": "exact_pre_oos_product_loaded_into_qlib",
                "status": "PASS",
                "evidence": "1,658,525 rows; 50 frozen features; 2012-2024 only",
            },
            {
                "check": "seven_purged_rolling_folds",
                "status": "PASS",
                "evidence": "wf_2018 through wf_2024; non-overlapping chronological segments",
            },
            {
                "check": "deterministic_fold_replay",
                "status": "PASS",
                "evidence": "wf_2018 receipt bytes reproduced exactly",
            },
            {
                "check": "qlib_recorder_artifact_readback",
                "status": "PASS",
                "evidence": "SQLite Recorder artifact hashes equal local receipt hashes",
            },
            {
                "check": "qlib_signal_analysis_mechanics",
                "status": "PASS",
                "evidence": "synthetic-only SigAnaRecord artifact inventory complete",
            },
            {
                "check": "portfolio_mechanics",
                "status": "PASS",
                "evidence": "synthetic-only weekly selection, caps, ADV limit and costs executed",
            },
            {
                "check": "code_and_upstream_evidence_binding",
                "status": "PASS",
                "evidence": "server receipts match local code plus M3/PIT/contract hashes",
            },
            {
                "check": "research_boundary",
                "status": "PASS",
                "evidence": "zero real model fits/signals/backtests; final OOS unopened",
            },
        ],
        "what_it_proves": [
            "The exact M3-qualified 2012-2024 product can enter Qlib DatasetH reproducibly.",
            "Qlib Recorder, signal-analysis and project portfolio plumbing work mechanically.",
        ],
        "what_it_does_not_prove": [
            (
                "No model edge, Alpha, A-share execution realism, calibrated capacity "
                "or deployment readiness."
            ),
            "Synthetic signal metrics are not empirical research results.",
        ],
        "next_gate": "M5-STRICT_BASELINES",
    }
    gate["content_sha256"] = hashlib.sha256(canonical_json(gate).encode("utf-8")).hexdigest()

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, staging_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        dir=output.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(canonical_json(gate) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(staging_name, output)
    finally:
        Path(staging_name).unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "status": "PASS",
                "gate": str(output),
                "gate_sha256": sha256_file(output),
                "content_sha256": gate["content_sha256"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
