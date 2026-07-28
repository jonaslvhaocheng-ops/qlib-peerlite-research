#!/usr/bin/env python3
"""Materialize the long-form consumed-value view required by the PIT auditor."""

from __future__ import annotations

import argparse
import concurrent.futures
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

from qlib_peerlite.data.features import FEATURE_COLUMNS

TZ = ZoneInfo("Asia/Shanghai")
INGESTED_TIME = "2026-07-28T15:56:25+08:00"
PARSE_READY_TIME = "2026-07-28T15:57:00+08:00"
FIELD_ORDER = [
    "row_id",
    "security_id",
    "feature_name",
    "feature_value",
    "prediction_time",
    "event_time",
    "published_time",
    "vendor_available_time",
    "ingested_time",
    "parse_ready_time",
    "ingestion_batch_id",
    "ingested_object_sha256",
    "tradable_time",
    "label_start_time",
    "label_end_time",
    "split",
    "universe_member",
    "universe_announced_time",
    "universe_effective_from",
    "universe_effective_to",
    "security_status",
    "revision_id",
    "revision_known_time",
    "adjustment_mode",
    "adjustment_known_time",
    "adjustment_invariance_pass",
    "halt_time",
    "quote_resume_time",
    "trade_resume_time",
    "calendar_session_id",
    "identifier_valid_from",
    "identifier_valid_to",
]


def sha256_file(path: Path, *, chunk_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def feature_definition(name: str) -> dict[str, Any]:
    daily = {
        "ret_1d": ("close(T)/close(T-1)-1", "RETURN", "ratio"),
        "gap_return": ("open(T)/close(T-1)-1", "RETURN", "ratio"),
        "intraday_return": ("close(T)/open(T)-1", "RETURN", "ratio"),
        "high_low_range": ("high(T)/low(T)-1", "RETURN", "ratio"),
        "close_location": ("(close(T)-low(T))/(high(T)-low(T))", "OTHER", "ratio"),
        "upper_shadow": (
            "(high(T)-max(open(T),close(T)))/open(T)",
            "RETURN",
            "ratio",
        ),
        "lower_shadow": (
            "(min(open(T),close(T))-low(T))/open(T)",
            "RETURN",
            "ratio",
        ),
        "log_volume": ("log1p(max(raw_volume(T),0))", "VOLUME", "log shares"),
        "log_amount": ("log1p(max(raw_turnover_value(T),0))", "OTHER", "log CNY"),
        "turnover_raw": ("raw_turnover_rate(T)", "OTHER", "vendor rate"),
    }
    if name in daily:
        formula, use, unit = daily[name]
    else:
        family, window_text = name.rsplit("_", 1)
        window = int(window_text)
        formulas = {
            "ret_mean": f"mean(ret_1d, trailing {window} sessions including T)",
            "ret_std": f"population_std(ret_1d, trailing {window} sessions including T)",
            "downside_vol": (
                f"population_std(min(ret_1d,0), trailing {window} sessions including T)"
            ),
            "range_mean": (f"mean(high_low_range, trailing {window} sessions including T)"),
            "turnover_mean": (f"mean(turnover_raw, trailing {window} sessions including T)"),
            "turnover_std": (
                f"population_std(turnover_raw, trailing {window} sessions including T)"
            ),
            "log_volume_mean": (f"mean(log_volume, trailing {window} sessions including T)"),
            "log_amount_mean": (f"mean(log_amount, trailing {window} sessions including T)"),
            "amihud_mean": (
                f"mean(abs(ret_1d)/abs(raw_turnover_value), trailing {window} sessions including T)"
            ),
            "price_volume_corr": (
                f"Pearson_corr(ret_1d,log_volume, trailing {window} sessions including T)"
            ),
        }
        if family not in formulas:
            raise ValueError(f"unknown frozen feature: {name}")
        formula = formulas[family]
        use = "OTHER"
        unit = "derived ratio"
    return {
        "feature_name": name,
        "formula": formula,
        "implementation": "src/qlib_peerlite/data/features.py",
        "use": use,
        "unit": unit,
        "basis": "RAW unadjusted OHLCV and turnover",
        "grain": "permanent security ID and eligible trading session",
        "event_time_policy": "OBSERVED_BY_PREDICTION",
        "null_policy": "not nullable after frozen eligibility filters",
        "adjustment_policy": {
            "basis": "RAW",
            "convention": "no price adjustment; event-crossing windows are masked",
            "allowed_modes": ["RAW"],
        },
    }


def semantics_document(product_manifest_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "qlib_peerlite_derived_feature_semantics_v1",
        "semantics_id": "qlib-peerlite-daily-raw-50-v1",
        "version": "1",
        "source_product_manifest_sha256": product_manifest_sha256,
        "prediction_clock": "16:00:00 Asia/Shanghai after 15:15 vendor publication",
        "availability_rule": (
            "Each feature is a deterministic function of current/past RAW observations "
            "whose declared DataYes availability is no later than prediction_time."
        ),
        "revision_rule": (
            "Every materialization is immutable. A changed source snapshot or feature "
            "implementation produces a new snapshot rather than rewriting this one."
        ),
        "features": [feature_definition(name) for name in FEATURE_COLUMNS],
    }


def timestamp_text(values: pd.Series) -> pd.Series:
    return values.map(lambda value: "" if pd.isna(value) else value.isoformat())


def materialize_chunk(frame: pd.DataFrame, product_id: str) -> pd.DataFrame:
    id_columns = [
        "security_id",
        "datetime",
        "split",
        "prediction_time",
        "event_time",
        "published_time",
        "vendor_available_time",
        "tradable_time",
        "label_start_time",
        "label_end_time",
        "universe_announced_time",
        "universe_effective_from",
        "universe_effective_to",
        "identifier_valid_from",
        "identifier_valid_to",
    ]
    long = frame[id_columns + list(FEATURE_COLUMNS)].melt(
        id_vars=id_columns,
        value_vars=list(FEATURE_COLUMNS),
        var_name="feature_name",
        value_name="feature_value",
    )
    long = long.sort_values(["datetime", "security_id", "feature_name"], ignore_index=True)
    date_key = long["datetime"].dt.strftime("%Y%m%d")
    long["row_id"] = long["security_id"].astype(str) + ":" + date_key + ":" + long["feature_name"]
    long["security_id"] = long["security_id"].astype(str)
    for column in (
        "prediction_time",
        "event_time",
        "published_time",
        "vendor_available_time",
        "tradable_time",
        "label_start_time",
        "label_end_time",
        "universe_announced_time",
        "universe_effective_from",
        "universe_effective_to",
        "identifier_valid_from",
        "identifier_valid_to",
    ):
        long[column] = timestamp_text(long[column])
    long["ingested_time"] = INGESTED_TIME
    long["parse_ready_time"] = PARSE_READY_TIME
    long["ingestion_batch_id"] = ""
    long["ingested_object_sha256"] = ""
    long["universe_member"] = "true"
    long["security_status"] = "ACTIVE"
    long["revision_id"] = product_id + ":" + long["security_id"] + ":" + date_key
    long["revision_known_time"] = long["vendor_available_time"]
    long["adjustment_mode"] = "RAW"
    long["adjustment_known_time"] = ""
    long["adjustment_invariance_pass"] = ""
    long["halt_time"] = ""
    long["quote_resume_time"] = ""
    long["trade_resume_time"] = ""
    long["calendar_session_id"] = "XSHG_XSHE-" + long["label_start_time"].str.slice(0, 10)
    if not np.isfinite(long["feature_value"].to_numpy(dtype=np.float64)).all():
        raise RuntimeError("non-finite consumed feature value")
    return long[FIELD_ORDER]


def materialize_partition(
    matrix_path: str,
    part_path: str,
    product_id: str,
    sample_start: str | None,
    sample_end: str | None,
    chunk_samples: int,
) -> dict[str, Any]:
    frame = pd.read_parquet(matrix_path)
    if sample_start is not None:
        frame = frame[frame["datetime"] >= pd.Timestamp(sample_start)]
    if sample_end is not None:
        frame = frame[frame["datetime"] <= pd.Timestamp(sample_end)]
    if frame.empty:
        return {"path": part_path, "sample_rows": 0, "evidence_rows": 0}
    header = True
    evidence_rows = 0
    target = Path(part_path)
    for start in range(0, len(frame), chunk_samples):
        chunk = frame.iloc[start : start + chunk_samples].copy()
        long = materialize_chunk(chunk, product_id)
        long.to_csv(
            target,
            mode="w" if header else "a",
            header=header,
            index=False,
            lineterminator="\n",
        )
        header = False
        evidence_rows += len(long)
    return {
        "path": part_path,
        "sample_rows": int(len(frame)),
        "evidence_rows": evidence_rows,
    }


def materialize(
    product_dir: Path,
    output_dir: Path,
    *,
    sample_start: str | None,
    sample_end: str | None,
    chunk_samples: int,
    workers: int,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("output directory must be new or empty")
    product_manifest_path = product_dir / "data_product_manifest.json"
    product_manifest_hash = sha256_file(product_manifest_path)
    product_manifest = json.loads(product_manifest_path.read_text(encoding="utf-8"))
    if product_manifest.get("status") != "BUILT_NOT_PIT_QUALIFIED":
        raise RuntimeError("unexpected source data-product status")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        semantics = semantics_document(product_manifest_hash)
        semantics_path = temporary / "derived_feature_semantics.json"
        write_json(semantics_path, semantics)
        evidence_path = temporary / "training_evidence.csv"
        parts_dir = temporary / "parts"
        parts_dir.mkdir()
        tasks: list[tuple[str, str]] = []
        for position, item in enumerate(product_manifest["matrix"]["files"]):
            tasks.append(
                (
                    str(product_dir / item["path"]),
                    str(parts_dir / f"part_{position:03d}_{int(item['year'])}.csv"),
                )
            )
        results: list[dict[str, Any]] = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    materialize_partition,
                    matrix_path,
                    part_path,
                    product_manifest["product_id"],
                    sample_start,
                    sample_end,
                    chunk_samples,
                )
                for matrix_path, part_path in tasks
            ]
            for future in futures:
                results.append(future.result())
        populated = [item for item in results if item["sample_rows"] > 0]
        if not populated:
            raise RuntimeError("selected evidence population is empty")
        with evidence_path.open("wb") as output:
            for position, item in enumerate(populated):
                with Path(item["path"]).open("rb") as source:
                    if position:
                        source.readline()
                    shutil.copyfileobj(source, output, length=16 * 1024 * 1024)
        sample_rows = sum(int(item["sample_rows"]) for item in populated)
        evidence_rows = sum(int(item["evidence_rows"]) for item in populated)
        shutil.rmtree(parts_dir)
        if evidence_rows != sample_rows * len(FEATURE_COLUMNS):
            raise RuntimeError("consumed-value rectangularity failure")

        scope = (
            "FULL_TRAINING_INPUT" if sample_start is None and sample_end is None else "SAMPLE_ONLY"
        )
        parameters = {
            "product_id": product_manifest["product_id"],
            "sample_start": sample_start,
            "sample_end": sample_end,
            "chunk_samples": chunk_samples,
            "workers": workers,
            "feature_count": len(FEATURE_COLUMNS),
            "field_order": FIELD_ORDER,
        }
        manifest = {
            "schema_version": "qlib_peerlite_consumed_value_manifest_v1",
            "evidence_id": output_dir.name,
            "created_at": datetime.now(TZ).isoformat(),
            "status": "MATERIALIZED_NOT_PIT_QUALIFIED",
            "scope": scope,
            "source_product_manifest": {
                "path": str(product_manifest_path),
                "sha256": product_manifest_hash,
            },
            "feature_semantics": {
                "path": semantics_path.name,
                "sha256": sha256_file(semantics_path),
                "version": semantics["version"],
            },
            "training_evidence": {
                "path": evidence_path.name,
                "sha256": sha256_file(evidence_path),
                "bytes": evidence_path.stat().st_size,
                "sample_rows": sample_rows,
                "feature_count": len(FEATURE_COLUMNS),
                "evidence_rows": evidence_rows,
            },
            "materializer": {
                "path": "scripts/server/materialize_pit_consumed_values.py",
                "sha256": sha256_file(Path(__file__).resolve()),
                "parameters": parameters,
                "parameters_sha256": canonical_json_sha256(parameters),
            },
            "oos_seal": {
                "final_oos_start": "2025-01-01",
                "final_oos_rows_included": False,
                "performance_metrics_computed": False,
            },
        }
        manifest["content_sha256"] = canonical_json_sha256(manifest)
        manifest_path = temporary / "consumed_value_manifest.json"
        write_json(manifest_path, manifest)
        for path in temporary.iterdir():
            path.chmod(0o440)
        temporary.chmod(0o550)
        if output_dir.exists():
            output_dir.rmdir()
        os.replace(temporary, output_dir)
        return manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-start")
    parser.add_argument("--sample-end")
    parser.add_argument("--chunk-samples", type=int, default=20_000)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()
    if (args.sample_start is None) != (args.sample_end is None):
        raise ValueError("sample-start and sample-end must be supplied together")
    manifest = materialize(
        args.product_dir,
        args.output_dir,
        sample_start=args.sample_start,
        sample_end=args.sample_end,
        chunk_samples=args.chunk_samples,
        workers=args.workers,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "scope": manifest["scope"],
                "sample_rows": manifest["training_evidence"]["sample_rows"],
                "evidence_rows": manifest["training_evidence"]["evidence_rows"],
                "bytes": manifest["training_evidence"]["bytes"],
                "evidence_sha256": manifest["training_evidence"]["sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
