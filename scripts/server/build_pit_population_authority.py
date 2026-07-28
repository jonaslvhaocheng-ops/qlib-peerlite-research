#!/usr/bin/env python3
"""Freeze the complete eligible development population as a separate authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def sha_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def utc_iso(value: pd.Timestamp) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tz is None:
        timestamp = timestamp.tz_localize("Asia/Shanghai")
    return timestamp.tz_convert("UTC").isoformat()


def path_get(root: dict[str, Any], dotted: str) -> Any:
    value: Any = root
    for part in dotted.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def selection_rule(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "universe_definition": path_get(contract, "scope.universe.definition"),
        "membership_rule": path_get(contract, "scope.universe.pit_membership_rule"),
        "listing_rule": "at least 60 completed eligible trading sessions",
        "status_rule": ("exclude PIT-known ST, *ST, PT and delisting-consolidation names"),
        "feature_rule": (
            "all 50 RAW-derived features finite after the 60-session corporate-action mask"
        ),
        "label_rule": (
            "finite raw_open(T+1)/raw_close(T+5) interval, no action crossing, "
            "no halt or opening price-limit execution"
        ),
        "split_rule": path_get(contract, "splits.purge_embargo_rule"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--authority-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("output authority already exists")

    manifest_path = args.product_dir / "data_product_manifest.json"
    product_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    population_path = args.product_dir / product_manifest["population"]["path"]
    if sha_file(population_path) != product_manifest["population"]["sha256"]:
        raise RuntimeError("population artifact hash mismatch")
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    population = pd.read_parquet(population_path, columns=["security_id", "prediction_time"])
    keys = sorted(
        [
            [str(row.security_id), utc_iso(row.prediction_time)]
            for row in population.itertuples(index=False)
        ]
    )
    source_uri = f"project://pit-data-product-population/{sha_file(manifest_path)}"
    authority = {
        "schema_version": "pit_population_source_v1",
        "authority_id": args.authority_id,
        "version": args.version,
        "source_uri": source_uri,
        "selection_rule_sha256": sha_value(selection_rule(contract)),
        "history_mode": "PIT_HISTORY",
        "includes_inactive_and_delisted": True,
        "records": [
            {
                "security_id": security_id,
                "prediction_time": prediction_time,
                "security_status": "ACTIVE",
                "eligible": True,
                "source_locator": (f"{source_uri}#{security_id}@{prediction_time}"),
            }
            for security_id, prediction_time in keys
        ],
    }
    authority["receipt_hash"] = sha_value(authority)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "authority_id": args.authority_id,
                "version": args.version,
                "records": len(keys),
                "sha256": sha_file(args.output),
                "receipt_hash": authority["receipt_hash"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
