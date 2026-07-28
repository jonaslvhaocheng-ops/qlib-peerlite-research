#!/usr/bin/env python3
"""Verify a sealed source snapshot using metadata and cryptographic hashes only."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: dict[str, Any], digest_field: str) -> str:
    unsigned = {key: item for key, item in value.items() if key != digest_field}
    payload = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def writable_mode(path: Path) -> bool:
    return bool(path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    overall_path = args.snapshot_dir / "snapshot_bundle_manifest.json"
    overall = json.loads(overall_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    overall_hash_ok = overall.get("content_sha256") == canonical_sha256(overall, "content_sha256")
    overall_read_only = not writable_mode(overall_path)
    checks.append({"check": "overall_content_hash", "passed": overall_hash_ok})

    source_results: dict[str, Any] = {}
    all_files_ok = True
    for source_id, locator in overall["sources"].items():
        manifest_path = args.snapshot_dir / locator["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        locator_hash_ok = sha256_file(manifest_path) == locator["manifest_sha256"]
        content_hash_ok = manifest.get("content_sha256") == canonical_sha256(
            manifest, "content_sha256"
        )
        manifest_read_only = not writable_mode(manifest_path)
        file_checks: list[dict[str, Any]] = []
        for expected in manifest["files"]:
            data_path = args.snapshot_dir / expected["path"]
            metadata_rows = pq.ParquetFile(data_path).metadata.num_rows
            result = {
                "path": expected["path"],
                "exists": data_path.is_file(),
                "sha256_matches": sha256_file(data_path) == expected["sha256"],
                "bytes_match": data_path.stat().st_size == expected["bytes"],
                "rows_match": metadata_rows == expected["rows"],
                "read_only": not writable_mode(data_path),
            }
            result["passed"] = all(result.values())
            file_checks.append(result)
        source_passed = bool(
            locator_hash_ok
            and content_hash_ok
            and manifest_read_only
            and all(item["passed"] for item in file_checks)
        )
        all_files_ok = all_files_ok and source_passed
        source_results[source_id] = {
            "manifest": locator["manifest"],
            "manifest_locator_hash_ok": locator_hash_ok,
            "manifest_content_hash_ok": content_hash_ok,
            "manifest_read_only": manifest_read_only,
            "files": file_checks,
            "passed": source_passed,
        }

    universe_locator = overall["universe"]
    universe_path = args.snapshot_dir / universe_locator["path"]
    universe = json.loads(universe_path.read_text(encoding="utf-8"))
    universe_file_hash_ok = sha256_file(universe_path) == universe_locator["sha256"]
    universe_content_hash_ok = universe.get("universe_hash") == canonical_sha256(
        universe, "universe_hash"
    )
    universe_binding_ok = (
        universe["source_manifest"] == overall["sources"]["datayes-index-constituents"]
    )
    universe_read_only = not writable_mode(universe_path)
    snapshot_dir_read_only = not writable_mode(args.snapshot_dir)

    passed = bool(
        overall_hash_ok
        and overall_read_only
        and all_files_ok
        and universe_file_hash_ok
        and universe_content_hash_ok
        and universe_binding_ok
        and universe_read_only
        and snapshot_dir_read_only
        and overall.get("status") == "SEALED_NOT_PIT_QUALIFIED"
        and overall.get("value_exposure") == "NONE_COUNTS_AND_HASHES_ONLY"
    )
    receipt = {
        "schema_version": "qlib_peerlite_sealed_snapshot_verification_v1",
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "snapshot_manifest": str(overall_path),
        "snapshot_manifest_sha256": sha256_file(overall_path),
        "status": "PASS" if passed else "FAIL",
        "value_access": "PARQUET_METADATA_AND_FILE_BYTES_ONLY",
        "checks": {
            "overall_content_hash": overall_hash_ok,
            "overall_manifest_read_only": overall_read_only,
            "all_source_manifests_and_files": all_files_ok,
            "universe_file_hash": universe_file_hash_ok,
            "universe_content_hash": universe_content_hash_ok,
            "universe_source_binding": universe_binding_ok,
            "universe_manifest_read_only": universe_read_only,
            "snapshot_directory_read_only": snapshot_dir_read_only,
            "not_claimed_pit_qualified": (overall.get("status") == "SEALED_NOT_PIT_QUALIFIED"),
        },
        "sources": source_results,
        "limitations": [
            "This receipt proves snapshot integrity and binding only.",
            "It does not prove historical vendor revision retention or PIT eligibility.",
            "It does not inspect data values, calculate labels or evaluate final OOS.",
        ],
    }
    receipt_path = args.output_dir / "sealed_snapshot_verification.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "qlib_peerlite_evidence_manifest_v1",
        "files": {
            receipt_path.name: sha256_file(receipt_path),
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": receipt["status"], **manifest}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
