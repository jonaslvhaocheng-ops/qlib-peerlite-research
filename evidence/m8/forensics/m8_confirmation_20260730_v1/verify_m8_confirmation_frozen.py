#!/usr/bin/env python3
"""Independently verify M8 confirmation evidence without opening final OOS."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from qlib_peerlite.governance.artifacts import atomic_write_json, sha256_file


def canonical_hash(value: dict[str, object]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(
        json.dumps(
            unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def run(project_root: Path, run_dir: Path, evaluation: Path, output: Path) -> None:
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("model_fits") != 28:
        raise RuntimeError("confirmation manifest is not a complete 28-fit PASS")
    if manifest.get("new_seeds") != [19, 42, 73, 101] or manifest.get("reused_seed") != 7:
        raise RuntimeError("confirmation seed inventory mismatch")
    if manifest.get("content_sha256") != canonical_hash(manifest):
        raise RuntimeError("confirmation manifest content hash mismatch")
    prediction_rows = 0
    fold_receipts = 0
    for item in manifest["outputs"]:
        path = run_dir / item["prediction_path"]
        if sha256_file(path) != item["prediction_sha256"]:
            raise RuntimeError("prediction hash mismatch")
        frame = pd.read_parquet(path)
        if len(frame) != 949_014 or item["rows"] != len(frame):
            raise RuntimeError("unexpected prediction row count")
        if frame.duplicated(["datetime", "instrument"]).any():
            raise RuntimeError("duplicate prediction key")
        if pd.to_datetime(frame["datetime"]).max() >= pd.Timestamp("2025-01-01"):
            raise RuntimeError("confirmation prediction crosses final OOS")
        if not np.isfinite(frame["score"].to_numpy(dtype=float)).all():
            raise RuntimeError("non-finite confirmation score")
        prediction_rows += len(frame)
        for receipt_item in item["fold_receipts"]:
            receipt_path = run_dir / receipt_item["path"]
            if sha256_file(receipt_path) != receipt_item["sha256"]:
                raise RuntimeError("fold receipt hash mismatch")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if (
                receipt.get("status") != "PASS"
                or receipt.get("checkpoint_replay") != "PASS_EXACT"
                or receipt.get("final_oos_market_partitions_opened") is not False
                or receipt.get("content_sha256") != canonical_hash(receipt)
            ):
                raise RuntimeError("fold receipt invariant failed")
            fold_receipts += 1
    result = json.loads(evaluation.read_text(encoding="utf-8"))
    if result.get("content_sha256") != canonical_hash(result):
        raise RuntimeError("evaluation content hash mismatch")
    oos_log = project_root / "contracts/oos_access_log.jsonl"
    expected = "6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190"
    if sha256_file(oos_log) != expected:
        raise RuntimeError("final-OOS log changed during confirmation")
    receipt = {
        "schema_version": "qlib_peerlite_m8_confirmation_verification_v1",
        "status": "PASS",
        "run_manifest_sha256": sha256_file(manifest_path),
        "evaluation_sha256": sha256_file(evaluation),
        "evaluation_status": result["status"],
        "prediction_rows": prediction_rows,
        "fold_receipts": fold_receipts,
        "checkpoint_replays": fold_receipts,
        "oos_access_log_sha256": expected,
        "final_oos_market_partitions_opened": False,
    }
    receipt["content_sha256"] = canonical_hash(receipt)
    atomic_write_json(output, receipt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(**vars(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
