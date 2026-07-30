#!/usr/bin/env python3
"""Verify and qualify one immutable pre-final-OOS M7 market-state product."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qlib_peerlite.data.market_state import DAILY_PRODUCT_COLUMNS, validate_state_product
from qlib_peerlite.governance.artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)
from scripts.server.build_m7_market_state_product import build_state_frames


def _content_sha256(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def _state(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if tuple(frame.columns) != ("datetime", *DAILY_PRODUCT_COLUMNS):
        raise RuntimeError("market-state parquet schema/order mismatch")
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.tz_localize(None).dt.normalize()
    result = frame.set_index("datetime")
    validate_state_product(result)
    return result


def _future_poison(protected_through: pd.Timestamp):
    def transform(raw: pd.DataFrame) -> pd.DataFrame:
        future = raw["trade_date"] > protected_through
        if not future.any():
            raise RuntimeError("future-poison probe has no future rows")
        raw.loc[future, ["open", "high", "low", "close"]] *= 1.03125
        raw.loc[future, "universe_member"] = ~raw.loc[future, "universe_member"]
        raw.loc[future, "special_status_forbidden"] = ~raw.loc[
            future, "special_status_forbidden"
        ]
        return raw

    return transform


def verify(
    *,
    project_root: Path,
    snapshot_dir: Path,
    required_product_dir: Path,
    product_dir: Path,
    output_dir: Path,
    protected_through: pd.Timestamp,
) -> None:
    if output_dir.exists():
        raise RuntimeError("market-state verification output must not already exist")
    manifest_path = product_dir / "market_state_manifest.json"
    manifest = _load_json(manifest_path)
    if (
        manifest.get("schema_version") != "qlib_peerlite_market_state_product_v1"
        or manifest.get("status") != "BUILT_NOT_PIT_QUALIFIED"
        or manifest.get("content_sha256") != _content_sha256(manifest)
        or manifest.get("oos_seal", {}).get("final_oos_market_partitions_opened") is not False
    ):
        raise RuntimeError("market-state product manifest identity/status is invalid")
    state_item = manifest["state"]
    population_item = manifest["population"]
    state_path = product_dir / state_item["path"]
    population_path = product_dir / population_item["path"]
    if sha256_file(state_path) != state_item["sha256"]:
        raise RuntimeError("market-state file hash mismatch")
    if sha256_file(population_path) != population_item["sha256"]:
        raise RuntimeError("market-state population file hash mismatch")
    stored_state = _state(state_path)
    stored_population = pd.read_parquet(population_path).set_index(
        ["datetime", "instrument"]
    )
    recomputed_state, recomputed_population, bindings = build_state_frames(
        snapshot_dir=snapshot_dir,
        required_product_dir=required_product_dir,
    )
    pd.testing.assert_frame_equal(stored_state, recomputed_state, check_exact=True)
    pd.testing.assert_frame_equal(
        stored_population,
        recomputed_population,
        check_exact=True,
    )
    if (
        sha256_file(snapshot_dir / "snapshot_bundle_manifest.json")
        != manifest["source_snapshot"]["bundle_sha256"]
        or bindings["required_product_manifest_sha256"]
        != manifest["required_model_date_axis"]["product_manifest_sha256"]
        or bindings["required_dates_sha256"]
        != manifest["required_model_date_axis"]["dates_sha256"]
    ):
        raise RuntimeError("market-state source/date binding mismatch")

    poisoned_state, _, _ = build_state_frames(
        snapshot_dir=snapshot_dir,
        required_product_dir=required_product_dir,
        diagnostic_transform=_future_poison(protected_through),
        verify_source=False,
    )
    protected = stored_state.index <= protected_through
    pd.testing.assert_frame_equal(
        stored_state.loc[protected],
        poisoned_state.loc[protected],
        check_exact=True,
    )
    future = stored_state.index > protected_through
    if not future.any() or np.array_equal(
        stored_state.loc[future, list(DAILY_PRODUCT_COLUMNS)].to_numpy(),
        poisoned_state.loc[future, list(DAILY_PRODUCT_COLUMNS)].to_numpy(),
    ):
        raise RuntimeError("future-poison probe did not alter the future suffix")

    fixed_path = (
        project_root
        / "evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json"
    )
    behavior_path = (
        project_root
        / "evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json"
    )
    fixed = _load_json(fixed_path)
    behavior = _load_json(behavior_path)
    if fixed.get("status") != "PASS" or fixed.get("claim") != "MARKET_RECONSTRUCTIBLE":
        raise RuntimeError("parent fixed PIT evidence is not a qualifying PASS")
    if behavior.get("status") != "PASS":
        raise RuntimeError("parent feature-behavior evidence is not a qualifying PASS")
    receipt: dict[str, Any] = {
        "schema_version": "qlib_peerlite_market_state_qualification_receipt_v1",
        "semantic_version": "m7_market_state_qualification_v1",
        "status": "PASS",
        "claim": "MARKET_RECONSTRUCTIBLE",
        "product_manifest_path": str(manifest_path.relative_to(project_root)),
        "product_manifest_file_sha256": sha256_file(manifest_path),
        "product_manifest_content_sha256": manifest["content_sha256"],
        "state_file_sha256": state_item["sha256"],
        "population_file_sha256": population_item["sha256"],
        "parent_fixed_pit_manifest_sha256": sha256_file(fixed_path),
        "parent_fixed_pit_content_sha256": fixed["content_sha256"],
        "parent_behavior_manifest_sha256": sha256_file(behavior_path),
        "parent_behavior_content_sha256": behavior["content_sha256"],
        "protected_through": str(protected_through.date()),
        "checks": {
            "source_snapshot_binding": "PASS",
            "parent_fixed_pit": "PASS",
            "parent_behavior_pit": "PASS",
            "independent_recompute": "PASS",
            "future_poison_prefix": "PASS",
            "date_coverage": "PASS",
            "schema_and_digests": "PASS",
        },
        "limitations": [
            "Qualification is MARKET_RECONSTRUCTIBLE, not SYSTEM_REPLAYABLE.",
            "The product is authorized only as the frozen four-dimensional M7 Gate input.",
        ],
        "final_oos_market_partitions_opened": False,
        "final_oos_metrics_computed": False,
    }
    receipt["content_sha256"] = _content_sha256(receipt)
    output_dir.mkdir(parents=True, exist_ok=False)
    atomic_write_json(output_dir / "qualification_receipt.json", receipt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--required-product-dir", type=Path, required=True)
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protected-through", default="2023-12-29")
    args = parser.parse_args()
    verify(
        project_root=args.project_root.resolve(),
        snapshot_dir=args.snapshot_dir.resolve(),
        required_product_dir=args.required_product_dir.resolve(),
        product_dir=args.product_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        protected_through=pd.Timestamp(args.protected_through),
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "claim": "MARKET_RECONSTRUCTIBLE",
                "final_oos_market_partitions_opened": False,
            }
        )
    )


if __name__ == "__main__":
    main()
