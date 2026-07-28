#!/usr/bin/env python3
"""Build a hash-bound FUTURE_POISON replay for the real feature pipeline.

The command is intentionally restricted to the 2011/2012 development
partitions.  It selects one security that is present in the verified training
matrix, rebuilds the frozen 50-feature pipeline from the sealed raw snapshot,
poisons one strictly later raw amount observation, and emits the exact
artifacts required by ``audit_behavior.py``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from qlib_peerlite.data.features import FEATURE_COLUMNS, build_causal_daily_features

SHANGHAI = ZoneInfo("Asia/Shanghai")
PROTECTED_TARGET = pd.Timestamp("2012-06-29")
MUTATION_NOT_BEFORE = pd.Timestamp("2012-08-01")
RAW_END_EXCLUSIVE = pd.Timestamp("2013-01-01")
RAW_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover",
    "corporate_action",
)


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
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


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def canonical_record_sha256(record: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def prediction_time(trade_date: pd.Timestamp) -> str:
    stamp = datetime.combine(
        trade_date.date(),
        datetime.min.time().replace(hour=16),
        tzinfo=SHANGHAI,
    )
    return stamp.isoformat(timespec="seconds")


def available_time(trade_date: pd.Timestamp) -> str:
    stamp = datetime.combine(
        trade_date.date(),
        datetime.min.time().replace(hour=15, minute=15),
        tzinfo=SHANGHAI,
    )
    return stamp.isoformat(timespec="seconds")


def canonical_utc_time(value: str) -> str:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timestamp must be offset-aware")
    return stamp.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def key_digest(keys: set[tuple[str, str, str]]) -> str:
    payload = [[sample, prediction, feature] for sample, prediction, feature in sorted(keys)]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def verify_source_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    # Importing here keeps the feature module usable without the server scripts.
    from scripts.server.build_pit_data_product import verify_snapshot

    bindings = verify_snapshot(snapshot_dir)
    bundle_path = snapshot_dir / "snapshot_bundle_manifest.json"
    return {
        "snapshot_dir_name": snapshot_dir.name,
        "snapshot_bundle_manifest_sha256": sha256_file(bundle_path),
        "verified_sources": bindings,
    }


def load_training_matrix(data_product_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest_path = data_product_dir / "data_product_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "BUILT_NOT_PIT_QUALIFIED":
        raise RuntimeError("unexpected data-product status")
    if manifest.get("oos_seal", {}).get("final_oos_market_partitions_opened") is not False:
        raise RuntimeError("data product does not preserve the final-OOS seal")
    matrix_path = data_product_dir / "matrix" / "matrix_2012.parquet"
    expected = next(
        (
            item["sha256"]
            for item in manifest["matrix"]["files"]
            if item["path"] == "matrix/matrix_2012.parquet"
        ),
        None,
    )
    if expected is None or sha256_file(matrix_path) != expected:
        raise RuntimeError("2012 matrix partition does not match its sealed manifest")
    columns = ["datetime", "instrument", "security_id", *FEATURE_COLUMNS]
    matrix = pd.read_parquet(matrix_path, columns=columns)
    matrix["datetime"] = pd.to_datetime(matrix["datetime"]).dt.normalize()
    return matrix, {
        "product_id": manifest["product_id"],
        "product_content_sha256": manifest["content_sha256"],
        "product_manifest_sha256": sha256_file(manifest_path),
        "matrix_2012_sha256": expected,
    }


def choose_security(matrix: pd.DataFrame) -> tuple[int, str, pd.Timestamp, pd.Timestamp]:
    protected = matrix[matrix["datetime"] <= PROTECTED_TARGET]
    future = matrix[matrix["datetime"] >= MUTATION_NOT_BEFORE]
    candidates = sorted(set(protected["security_id"]) & set(future["security_id"]))
    if not candidates:
        raise RuntimeError("no training security spans the protected and mutation periods")
    counts = (
        protected[protected["security_id"].isin(candidates)]
        .groupby("security_id")
        .size()
        .sort_values(ascending=False)
    )
    security_id = int(counts.index[0])
    rows = matrix[matrix["security_id"] == security_id].sort_values("datetime")
    protected_through = rows.loc[rows["datetime"] <= PROTECTED_TARGET, "datetime"].max()
    mutation_date = rows.loc[rows["datetime"] >= MUTATION_NOT_BEFORE, "datetime"].min()
    instrument_values = rows["instrument"].astype(str).unique()
    if len(instrument_values) != 1:
        raise RuntimeError("selected permanent security ID maps to multiple instruments")
    return security_id, instrument_values[0], protected_through, mutation_date


def load_raw_panel(
    snapshot_dir: Path,
    security_id: int,
) -> pd.DataFrame:
    source_columns = [
        "security_id",
        "trade_date",
        "open_price",
        "highest_price",
        "lowest_price",
        "close_price",
        "turnover_vol",
        "turnover_value",
        "turnover_rate",
    ]
    paths = [
        snapshot_dir / "mkt_equd_2011.parquet",
        snapshot_dir / "mkt_equd_2012.parquet",
    ]
    raw = pd.concat(
        [
            pd.read_parquet(
                path,
                columns=source_columns,
                filters=[("security_id", "=", security_id)],
            )
            for path in paths
        ],
        ignore_index=True,
    )
    raw["trade_date"] = pd.to_datetime(raw["trade_date"]).dt.normalize()
    raw = raw[raw["trade_date"] < RAW_END_EXCLUSIVE].rename(
        columns={
            "open_price": "open",
            "highest_price": "high",
            "lowest_price": "low",
            "close_price": "close",
            "turnover_vol": "volume",
            "turnover_value": "amount",
            "turnover_rate": "turnover",
        }
    )
    actions = pd.read_parquet(
        snapshot_dir / "mkt_adjf.parquet",
        columns=["security_id", "ex_div_date"],
        filters=[("security_id", "=", security_id)],
    )
    action_dates = set(pd.to_datetime(actions["ex_div_date"]).dt.normalize())
    raw["corporate_action"] = raw["trade_date"].isin(action_dates)
    raw = raw.sort_values("trade_date", ignore_index=True)
    if raw.empty or raw.duplicated(["security_id", "trade_date"]).any():
        raise RuntimeError("selected raw quote history is empty or non-unique")
    return raw


def scalar(value: Any) -> int | float | bool | None:
    if pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        result = float(value)
        if not np.isfinite(result):
            raise ValueError("raw numeric values must be finite")
        return result
    raise TypeError(f"unsupported raw scalar: {type(value)!r}")


def snapshot_records(raw: pd.DataFrame, instrument: str) -> list[dict[str, Any]]:
    records = []
    for row in raw.itertuples(index=False):
        trade_date = pd.Timestamp(row.trade_date)
        timestamp = available_time(trade_date)
        records.append(
            {
                "raw_key": f"mkt_equd:{int(row.security_id)}:{trade_date.date()}",
                "sample_id": instrument,
                "available_time": timestamp,
                "revision_known_time": timestamp,
                "universe_known_time": timestamp,
                "payload": {column: scalar(getattr(row, column)) for column in RAW_COLUMNS},
            }
        )
    return records


def frame_from_snapshot(path: Path, security_id: int) -> pd.DataFrame:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for record in document["records"]:
        trade_date = pd.Timestamp(record["raw_key"].rsplit(":", 1)[1])
        rows.append(
            {
                "datetime": trade_date,
                "instrument": security_id,
                **record["payload"],
            }
        )
    return pd.DataFrame(rows).set_index(["datetime", "instrument"]).sort_index()


def compute_features(snapshot_path: Path, security_id: int) -> pd.DataFrame:
    panel = frame_from_snapshot(snapshot_path, security_id)
    return build_causal_daily_features(panel)


def assert_matches_training_product(
    rebuilt: pd.DataFrame,
    matrix: pd.DataFrame,
    security_id: int,
) -> dict[str, Any]:
    selected = matrix[matrix["security_id"] == security_id].copy()
    selected_index = pd.MultiIndex.from_arrays(
        [selected["datetime"], selected["security_id"]],
        names=["datetime", "instrument"],
    )
    actual = rebuilt.loc[selected_index, list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)
    expected = selected[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)
    if not np.array_equal(actual, expected, equal_nan=True):
        delta = np.nanmax(np.abs(actual - expected))
        raise RuntimeError(f"replay does not exactly match training product; max delta={delta}")
    return {
        "training_rows_compared": int(len(selected)),
        "feature_cells_compared": int(len(selected) * len(FEATURE_COLUMNS)),
        "comparison": "EXACT_NUMPY_ARRAY_EQUAL_NAN",
        "result": "PASS",
    }


def output_rows(
    features: pd.DataFrame,
    matrix: pd.DataFrame,
    security_id: int,
    instrument: str,
) -> list[list[str]]:
    selected_dates = (
        matrix.loc[matrix["security_id"] == security_id, "datetime"].drop_duplicates().sort_values()
    )
    rows: list[list[str]] = []
    for trade_date in selected_dates:
        values = features.loc[(trade_date, security_id), list(FEATURE_COLUMNS)]
        for feature_name, value in values.items():
            numeric = float(value)
            if not np.isfinite(numeric):
                raise RuntimeError("training output unexpectedly contains a non-finite feature")
            rows.append(
                [
                    instrument,
                    prediction_time(pd.Timestamp(trade_date)),
                    str(feature_name),
                    json.dumps(numeric, allow_nan=False, separators=(",", ":")),
                ]
            )
    return rows


def write_output_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["sample_id", "prediction_time", "feature_name", "feature_value_json"])
        writer.writerows(rows)


def build_code_bundle(
    destination: Path,
    feature_source: Path,
    schema_source: Path,
    builder_source: Path,
) -> dict[str, str]:
    sources = [
        ("src/qlib_peerlite/data/features.py", feature_source),
        ("src/qlib_peerlite/data/schema.py", schema_source),
        ("scripts/server/build_pit_behavior_package.py", builder_source),
    ]
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for logical_path, source in sources:
            handle.write(f"===== BEGIN {logical_path} =====\n")
            handle.write(source.read_text(encoding="utf-8"))
            handle.write(f"\n===== END {logical_path} =====\n")
    return {logical: sha256_file(source) for logical, source in sources}


def publish(
    *,
    snapshot_dir: Path,
    data_product_dir: Path,
    parent_audit_manifest: Path,
    feature_source: Path,
    schema_source: Path,
    output_dir: Path,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("output directory must be new or empty")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        source_binding = verify_source_snapshot(snapshot_dir)
        matrix, product_binding = load_training_matrix(data_product_dir)
        security_id, instrument, protected_date, mutation_date = choose_security(matrix)
        raw = load_raw_panel(snapshot_dir, security_id)
        baseline_records = snapshot_records(raw, instrument)
        mutation_key = f"mkt_equd:{security_id}:{mutation_date.date()}"
        probe_records = json.loads(json.dumps(baseline_records))
        mutated = next(
            (record for record in probe_records if record["raw_key"] == mutation_key),
            None,
        )
        if mutated is None:
            raise RuntimeError("chosen future mutation key is absent from raw snapshot")
        baseline_mutated = next(
            record for record in baseline_records if record["raw_key"] == mutation_key
        )
        original_amount = float(mutated["payload"]["amount"])
        if not np.isfinite(original_amount) or original_amount <= 0:
            raise RuntimeError("chosen mutation amount must be finite and positive")
        mutated["payload"]["amount"] = original_amount * 1_000_003.0

        baseline_snapshot = staging / "raw_before.json"
        probe_snapshot = staging / "raw_after.json"
        write_json(
            baseline_snapshot,
            {
                "snapshot_version": "pit_behavior_snapshot_v1",
                "records": baseline_records,
            },
        )
        write_json(
            probe_snapshot,
            {
                "snapshot_version": "pit_behavior_snapshot_v1",
                "records": probe_records,
            },
        )

        baseline_features = compute_features(baseline_snapshot, security_id)
        probe_features = compute_features(probe_snapshot, security_id)
        replay_check = assert_matches_training_product(baseline_features, matrix, security_id)
        baseline_rows = output_rows(baseline_features, matrix, security_id, instrument)
        probe_rows = output_rows(probe_features, matrix, security_id, instrument)
        baseline_output = staging / "baseline_output.csv"
        probe_output = staging / "probe_output.csv"
        write_output_csv(baseline_output, baseline_rows)
        write_output_csv(probe_output, probe_rows)

        protected_through = prediction_time(protected_date)
        cutoff = datetime.fromisoformat(protected_through).astimezone(UTC)
        protected_keys = {
            (row[0], canonical_utc_time(row[1]), row[2])
            for row in baseline_rows
            if datetime.fromisoformat(row[1]).astimezone(UTC) <= cutoff
        }
        if not protected_keys:
            raise RuntimeError("protected output key set is empty")

        parent_copy = staging / "parent_pit_audit_manifest.json"
        shutil.copyfile(parent_audit_manifest, parent_copy)
        parent = json.loads(parent_copy.read_text(encoding="utf-8"))
        if parent.get("status") != "PASS":
            raise RuntimeError("parent fixed PIT audit is not PASS")

        code_artifact = staging / "feature_pipeline_code.txt"
        code_hashes = build_code_bundle(
            code_artifact,
            feature_source,
            schema_source,
            Path(__file__).resolve(),
        )
        parameters_path = staging / "parameters.json"
        parameters = {
            "parameter_version": "qlib_peerlite_pit_behavior_parameters_v1",
            "feature_function": "qlib_peerlite.data.features.build_causal_daily_features",
            "feature_count": len(FEATURE_COLUMNS),
            "feature_names": list(FEATURE_COLUMNS),
            "windows": [5, 10, 20, 60],
            "mask_lookback_sessions": 60,
            "selected_security_id": security_id,
            "selected_instrument": instrument,
            "protected_training_date": str(protected_date.date()),
            "mutation_training_date": str(mutation_date.date()),
            "mutation": {
                "field": "amount",
                "operation": "MULTIPLY",
                "factor": 1_000_003.0,
                "raw_key": mutation_key,
            },
            "development_partitions_opened": [2011, 2012],
            "final_oos_market_partitions_opened": False,
            "source_binding": source_binding,
            "data_product_binding": product_binding,
            "baseline_training_product_replay": replay_check,
            "code_source_sha256": code_hashes,
        }
        write_json(parameters_path, parameters)
        environment_path = staging / "environment.json"
        write_json(
            environment_path,
            {
                "environment_version": "qlib_peerlite_pit_behavior_environment_v1",
                "python": sys.version,
                "platform": platform.platform(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "timezone": "Asia/Shanghai",
                "tzpath": [str(item) for item in __import__("zoneinfo").TZPATH],
            },
        )

        before_hash = canonical_record_sha256(baseline_mutated)
        after_hash = canonical_record_sha256(mutated)
        mutation_known_time = mutated["available_time"]
        ledger_path = staging / "perturbation_ledger.json"
        write_json(
            ledger_path,
            {
                "ledger_version": "pit_perturbation_ledger_v1",
                "baseline_snapshot_sha256": sha256_file(baseline_snapshot),
                "probe_snapshot_sha256": sha256_file(probe_snapshot),
                "entries": [
                    {
                        "raw_key": mutation_key,
                        "operation": "UPDATE",
                        "change_type": "FUTURE_POISON",
                        "known_time": mutation_known_time,
                        "baseline_record_sha256": before_hash,
                        "probe_record_sha256": after_hash,
                    }
                ],
            },
        )

        artifact_paths = {
            "baseline_raw_snapshot": baseline_snapshot,
            "probe_raw_snapshot": probe_snapshot,
            "code_or_query": code_artifact,
            "parameters": parameters_path,
            "environment": environment_path,
            "baseline_output": baseline_output,
            "probe_output": probe_output,
            "pit_audit_manifest": parent_copy,
            "perturbation_ledger": ledger_path,
        }
        bindings = {key: sha256_file(path) for key, path in artifact_paths.items()}
        request_seed = {
            "parent_audit_id": parent["audit_id"],
            "product_id": product_binding["product_id"],
            "security_id": security_id,
            "protected_through": protected_through,
            "mutation_key": mutation_key,
            "artifact_sha256": bindings,
        }
        request_digest = hashlib.sha256(canonical_json(request_seed).encode("utf-8")).hexdigest()
        request_id = f"qlib-peerlite-future-poison-{request_digest[:24]}"
        receipt_path = staging / "pipeline_receipt.json"
        write_json(
            receipt_path,
            {
                "receipt_version": "pit_behavior_receipt_v1",
                "receipt_id": f"receipt-{request_digest[:24]}",
                "request_id": request_id,
                "probe_type": "FUTURE_POISON",
                "baseline_run_id": f"baseline-{request_digest[:16]}",
                "probe_run_id": f"probe-{request_digest[:16]}",
                "artifact_sha256": bindings,
                "parent_audit": {
                    "audit_id": parent["audit_id"],
                    "content_sha256": parent["content_sha256"],
                    "status": parent["status"],
                },
                "protection": {
                    "comparison": "LE",
                    "protected_through": protected_through,
                    "expected_key_count": len(protected_keys),
                    "expected_keys_sha256": key_digest(protected_keys),
                },
                "probe": {
                    "mutation_type": "FUTURE_POISON",
                    "mutation_time_min": mutation_known_time,
                    "canary_sample_ids": [],
                },
            },
        )
        request_path = staging / "behavior_request.json"
        request_artifacts = {
            key: {"path": path.name, "sha256": bindings[key]}
            for key, path in artifact_paths.items()
        }
        request_artifacts["pipeline_receipt"] = {
            "path": receipt_path.name,
            "sha256": sha256_file(receipt_path),
        }
        write_json(
            request_path,
            {
                "request_version": "pit_behavior_request_v1",
                "request_id": request_id,
                "probe_type": "FUTURE_POISON",
                "artifacts": request_artifacts,
            },
        )
        package_manifest = {
            "manifest_version": "qlib_peerlite_pit_behavior_package_v1",
            "request_id": request_id,
            "probe_type": "FUTURE_POISON",
            "selected_security_id": security_id,
            "selected_instrument": instrument,
            "protected_through": protected_through,
            "mutation_time_min": mutation_known_time,
            "protected_key_count": len(protected_keys),
            "training_product_replay": replay_check,
            "final_oos_market_partitions_opened": False,
            "artifacts": {
                **bindings,
                "pipeline_receipt": sha256_file(receipt_path),
                "behavior_request": sha256_file(request_path),
            },
        }
        package_manifest["content_sha256"] = hashlib.sha256(
            canonical_json(package_manifest).encode("utf-8")
        ).hexdigest()
        write_json(staging / "package_manifest.json", package_manifest)

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
                    "status": "BUILT",
                    "request_id": request_id,
                    "security_id": security_id,
                    "protected_key_count": len(protected_keys),
                    "final_oos_market_partitions_opened": False,
                    "package_manifest_sha256": sha256_file(output_dir / "package_manifest.json"),
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--data-product-dir", type=Path, required=True)
    parser.add_argument("--parent-audit-manifest", type=Path, required=True)
    parser.add_argument("--feature-source", type=Path, required=True)
    parser.add_argument("--schema-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    publish(
        snapshot_dir=args.snapshot_dir,
        data_product_dir=args.data_product_dir,
        parent_audit_manifest=args.parent_audit_manifest,
        feature_source=args.feature_source,
        schema_source=args.schema_source,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
