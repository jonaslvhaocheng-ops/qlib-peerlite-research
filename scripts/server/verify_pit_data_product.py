#!/usr/bin/env python3
"""Independently verify a built, pre-final-OOS Qlib PeerLite data product."""

from __future__ import annotations

import argparse
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

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from qlib_peerlite.data.features import FEATURE_COLUMNS

TZ = ZoneInfo("Asia/Shanghai")
FINAL_OOS_START = pd.Timestamp("2025-01-01")
EXPECTED_SOURCE_BUNDLE = "2575e52c7375fe28c06ccc6305da34e3328f025e7397ae735264f06cf62dc040"
EXPECTED_UNIVERSE_HASH = "4c4fde609a8ee6cf21fdc40114f368fdbb5a102d661d6c630e223a785b7dee97"


def sha256_file(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def verify(product_dir: Path) -> dict[str, Any]:
    failures: list[str] = []
    manifest_path = product_dir / "data_product_manifest.json"
    manifest_hash = sha256_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    content = dict(manifest)
    declared_content_hash = content.pop("content_sha256", None)
    if canonical_json_sha256(content) != declared_content_hash:
        failures.append("manifest content_sha256 mismatch")
    if manifest.get("status") != "BUILT_NOT_PIT_QUALIFIED":
        failures.append("unexpected data-product status")
    source = manifest.get("source_snapshot", {})
    if source.get("bundle_sha256") != EXPECTED_SOURCE_BUNDLE:
        failures.append("source snapshot bundle mismatch")
    if source.get("universe_hash") != EXPECTED_UNIVERSE_HASH:
        failures.append("universe hash mismatch")
    seal = manifest.get("oos_seal", {})
    if seal.get("final_oos_market_partitions_opened") is not False:
        failures.append("final OOS market partitions were marked opened")
    if seal.get("performance_metrics_computed") is not False:
        failures.append("performance metrics were marked computed")

    matrix_meta = manifest.get("matrix", {})
    if matrix_meta.get("feature_count") != 50:
        failures.append("feature count is not 50")
    if matrix_meta.get("features") != list(FEATURE_COLUMNS):
        failures.append("feature axis differs from frozen implementation")

    total_rows = 0
    keys: list[pd.DataFrame] = []
    split_counts: dict[str, int] = {}
    schema_names: list[str] | None = None
    date_min: pd.Timestamp | None = None
    date_max: pd.Timestamp | None = None
    for item in matrix_meta.get("files", []):
        path = product_dir / item["path"]
        if not path.is_file():
            failures.append(f"missing matrix file {item['path']}")
            continue
        if sha256_file(path) != item.get("sha256"):
            failures.append(f"matrix file hash mismatch {item['path']}")
        parquet = pq.ParquetFile(path)
        if parquet.metadata.num_rows != item.get("rows"):
            failures.append(f"matrix row metadata mismatch {item['path']}")
        names = parquet.schema_arrow.names
        if schema_names is None:
            schema_names = names
        elif names != schema_names:
            failures.append(f"matrix schema drift {item['path']}")
        required = {
            "datetime",
            "instrument",
            "split",
            "label",
            "prediction_time",
            "event_time",
            "published_time",
            "vendor_available_time",
            "tradable_time",
            "label_start_time",
            "label_end_time",
            *FEATURE_COLUMNS,
        }
        if not required.issubset(names):
            failures.append(f"matrix missing required columns {item['path']}")
            continue
        frame = pd.read_parquet(path)
        total_rows += len(frame)
        keys.append(frame[["datetime", "instrument"]])
        year = int(item["year"])
        if not (frame["datetime"].dt.year == year).all():
            failures.append(f"year partition mismatch {item['path']}")
        if (frame["datetime"] >= FINAL_OOS_START).any():
            failures.append(f"final OOS row found in {item['path']}")
        if frame[["datetime", "instrument"]].duplicated().any():
            failures.append(f"duplicate matrix key within {item['path']}")
        numeric = frame[[*FEATURE_COLUMNS, "label"]].to_numpy(dtype=np.float64)
        if not np.isfinite(numeric).all():
            failures.append(f"non-finite feature or label in {item['path']}")
        if not (frame["event_time"] <= frame["published_time"]).all():
            failures.append(f"event/publication order violation in {item['path']}")
        if not (frame["published_time"] <= frame["vendor_available_time"]).all():
            failures.append(f"publication/vendor order violation in {item['path']}")
        if not (frame["vendor_available_time"] <= frame["prediction_time"]).all():
            failures.append(f"vendor/prediction order violation in {item['path']}")
        if not (frame["prediction_time"] < frame["tradable_time"]).all():
            failures.append(f"prediction/tradable order violation in {item['path']}")
        if not (frame["tradable_time"] == frame["label_start_time"]).all():
            failures.append(f"tradable/label-start mismatch in {item['path']}")
        if not (frame["label_start_time"] < frame["label_end_time"]).all():
            failures.append(f"label interval violation in {item['path']}")
        counts = frame["split"].value_counts()
        for key, value in counts.items():
            split_counts[str(key)] = split_counts.get(str(key), 0) + int(value)
        current_min = frame["datetime"].min()
        current_max = frame["datetime"].max()
        date_min = current_min if date_min is None else min(date_min, current_min)
        date_max = current_max if date_max is None else max(date_max, current_max)

    if total_rows != matrix_meta.get("rows"):
        failures.append("total matrix row count mismatch")
    if split_counts != matrix_meta.get("split_counts"):
        failures.append("matrix split counts mismatch")
    if date_min is None or str(date_min.date()) != matrix_meta.get("date_min"):
        failures.append("matrix minimum date mismatch")
    if date_max is None or str(date_max.date()) != matrix_meta.get("date_max"):
        failures.append("matrix maximum date mismatch")
    if keys:
        combined_keys = pd.concat(keys, ignore_index=True)
        if combined_keys.duplicated().any():
            failures.append("duplicate matrix key across partitions")
    else:
        combined_keys = pd.DataFrame(columns=["datetime", "instrument"])

    population_meta = manifest.get("population", {})
    population_path = product_dir / population_meta.get("path", "")
    if not population_path.is_file():
        failures.append("population artifact is missing")
        population = pd.DataFrame()
    else:
        if sha256_file(population_path) != population_meta.get("sha256"):
            failures.append("population artifact hash mismatch")
        population = pd.read_parquet(population_path)
        if len(population) != population_meta.get("rows"):
            failures.append("population row count mismatch")
        population_keys = population[["prediction_time", "security_id"]].copy()
        population_keys["datetime"] = (
            population_keys["prediction_time"].dt.tz_localize(None).dt.normalize()
        )
        population_keys["instrument"] = population_keys["security_id"].astype(str)
        if not population_keys[["datetime", "instrument"]].equals(
            combined_keys[["datetime", "instrument"]].reset_index(drop=True)
        ):
            failures.append("population keys differ from matrix keys")

    calendar_meta = manifest.get("calendar", {})
    calendar_path = product_dir / calendar_meta.get("path", "")
    if not calendar_path.is_file():
        failures.append("calendar artifact is missing")
    else:
        if sha256_file(calendar_path) != calendar_meta.get("sha256"):
            failures.append("calendar artifact hash mismatch")
        calendar = pd.read_csv(calendar_path)
        if len(calendar) != calendar_meta.get("rows"):
            failures.append("calendar row count mismatch")
        if calendar["session_id"].duplicated().any():
            failures.append("calendar session IDs are not unique")

    return {
        "schema_version": "qlib_peerlite_pit_data_product_verification_v1",
        "verified_at": datetime.now(TZ).isoformat(),
        "product_id": manifest.get("product_id"),
        "product_manifest_sha256": manifest_hash,
        "status": "PASS" if not failures else "FAIL",
        "passed": not failures,
        "checks": {
            "manifest_binding": declared_content_hash is not None,
            "source_snapshot_binding": source.get("bundle_sha256") == EXPECTED_SOURCE_BUNDLE,
            "universe_binding": source.get("universe_hash") == EXPECTED_UNIVERSE_HASH,
            "final_oos_partition_opened": seal.get("final_oos_market_partitions_opened"),
            "performance_metrics_computed": seal.get("performance_metrics_computed"),
            "matrix_rows": total_rows,
            "matrix_feature_count": matrix_meta.get("feature_count"),
            "matrix_split_counts": split_counts,
            "population_rows": int(len(population)),
        },
        "failures": failures,
        "interpretation": (
            "This receipt proves product integrity and declared pre-OOS mechanics only. "
            "It is not a point-in-time qualification."
        ),
    }


def publish(output_dir: Path, receipt: dict[str, Any]) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("output directory must be new or empty")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)
    )
    try:
        receipt_path = temporary / "data_product_verification.json"
        write_json(receipt_path, receipt)
        manifest = {
            "schema_version": "qlib_peerlite_evidence_manifest_v1",
            "files": {
                receipt_path.name: sha256_file(receipt_path),
            },
        }
        write_json(temporary / "manifest.json", manifest)
        for path in temporary.iterdir():
            path.chmod(0o440)
        temporary.chmod(0o550)
        if output_dir.exists():
            output_dir.rmdir()
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.product_dir)
    publish(args.output_dir, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "product_id": receipt["product_id"],
                "manifest_sha256": sha256_file(args.output_dir / "manifest.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if receipt["passed"] else 3


if __name__ == "__main__":
    sys.exit(main())
