#!/usr/bin/env python3
"""Build the label-free M7 market-state product from the sealed raw snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from qlib_peerlite.data.features import build_causal_daily_features
from qlib_peerlite.data.market_state import (
    STATE_INPUT_COLUMNS,
    aggregate_daily_state,
    select_state_population,
)
from qlib_peerlite.data.qlib_dataset import load_bound_product_frame
from qlib_peerlite.governance.artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)
from scripts.server import build_pit_data_product as pit_builder

TZ = ZoneInfo("Asia/Shanghai")
RowTransform = Callable[[pd.DataFrame], pd.DataFrame]


def _content_sha256(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _dates_sha256(dates: pd.DatetimeIndex) -> str:
    return hashlib.sha256(
        "\n".join(pd.Timestamp(date).date().isoformat() for date in dates).encode("ascii")
    ).hexdigest()


def build_state_frames(
    *,
    snapshot_dir: Path,
    required_product_dir: Path,
    diagnostic_transform: RowTransform | None = None,
    verify_source: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    source_bindings = pit_builder.verify_snapshot(snapshot_dir) if verify_source else {}
    calendar = pit_builder.eligible_calendar(snapshot_dir)
    intervals, security_ids = pit_builder.build_membership_lookup(snapshot_dir)
    master = pit_builder.security_master(snapshot_dir, security_ids)
    security_ids &= set(master["security_id"].astype(int))
    raw = pit_builder.read_year_partitions(
        snapshot_dir,
        "mkt_equd",
        [
            "security_id",
            "ticker_symbol",
            "exchange_cd",
            "trade_date",
            "open_price",
            "highest_price",
            "lowest_price",
            "close_price",
            "turnover_vol",
            "turnover_value",
            "turnover_rate",
        ],
    )
    raw = raw[
        raw["security_id"].isin(security_ids)
        & raw["exchange_cd"].isin(["XSHG", "XSHE"])
    ].copy()
    raw["trade_date"] = pit_builder.parse_date(raw["trade_date"])
    raw = raw[raw["trade_date"] < pit_builder.PREDICTION_END_EXCLUSIVE]
    raw = raw.rename(
        columns={
            "open_price": "open",
            "highest_price": "high",
            "lowest_price": "low",
            "close_price": "close",
            "turnover_vol": "volume",
            "turnover_value": "amount",
            "turnover_rate": "turnover",
        }
    ).sort_values(["security_id", "trade_date"], ignore_index=True)
    if raw.duplicated(["security_id", "trade_date"]).any():
        raise RuntimeError("market-state raw quotes have duplicate permanent-ID/date keys")
    raw = pit_builder.attach_membership(raw, intervals)
    raw = raw.merge(
        master[["security_id", "list_date", "delist_date"]],
        how="left",
        on="security_id",
        validate="m:1",
    )
    eligible_dates = {
        int(row.security_id): pit_builder.listing_eligibility_date(row.list_date, calendar)
        for row in master.itertuples(index=False)
    }
    raw["listing_eligible_date"] = raw["security_id"].map(eligible_dates)
    raw["listing_age_eligible"] = raw["trade_date"] >= raw["listing_eligible_date"]
    raw["is_active"] = (raw["trade_date"] >= raw["list_date"]) & (
        raw["delist_date"].isna() | (raw["trade_date"] < raw["delist_date"])
    )
    raw = pit_builder.attach_special_status(snapshot_dir, raw)
    raw = pit_builder.attach_corporate_action(
        raw,
        pit_builder.corporate_action_dates(snapshot_dir, security_ids),
    )
    if diagnostic_transform is not None:
        transformed = diagnostic_transform(raw.copy())
        if not isinstance(transformed, pd.DataFrame) or len(transformed) != len(raw):
            raise RuntimeError("diagnostic transform must preserve the source row count")
        raw = transformed
    raw = raw.sort_values(["trade_date", "security_id"], ignore_index=True)
    panel = raw.set_index(["trade_date", "security_id"]).rename_axis(
        ["datetime", "instrument"]
    )
    features = build_causal_daily_features(panel)
    raw = raw.join(features.reset_index(drop=True))
    raw["price_domain_valid"] = (
        (raw[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (raw["volume"] >= 0)
        & (raw["amount"] >= 0)
    )
    state_input = raw[
        [
            "trade_date",
            "security_id",
            "universe_member",
            "listing_age_eligible",
            "is_active",
            "special_status_forbidden",
            "special_status_unknown",
            "price_domain_valid",
            "feature_eligible",
            "ret_mean_20",
            "ret_std_20",
            "ret_1d",
            "turnover_mean_20",
        ]
    ].copy()
    state_input = state_input.rename(
        columns={"trade_date": "datetime", "security_id": "instrument"}
    )
    state_input["instrument"] = state_input["instrument"].astype(str)
    state_input = state_input.set_index(["datetime", "instrument"])
    state_input = state_input.loc[:, list(STATE_INPUT_COLUMNS)].sort_index()
    population = select_state_population(state_input)

    required_product = load_bound_product_frame(
        required_product_dir,
        verify_all_files=verify_source,
    )
    required_dates = pd.DatetimeIndex(
        required_product.frame.index.get_level_values("datetime").unique()
    ).sort_values()
    population = population.loc[
        population.index.get_level_values("datetime").isin(required_dates)
    ]
    state = aggregate_daily_state(population, required_dates=required_dates)
    bindings = {
        "source_bindings": source_bindings,
        "source_snapshot_bundle_sha256": sha256_file(
            snapshot_dir / "snapshot_bundle_manifest.json"
        ),
        "required_product_manifest_sha256": required_product.product_manifest_sha256,
        "required_dates_sha256": _dates_sha256(required_dates),
    }
    return state, population, bindings


def publish(
    *,
    snapshot_dir: Path,
    required_product_dir: Path,
    output_dir: Path,
) -> None:
    if output_dir.exists():
        raise RuntimeError("market-state output directory must not already exist")
    state, population, bindings = build_state_frames(
        snapshot_dir=snapshot_dir,
        required_product_dir=required_product_dir,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        state_path = temporary / "market_state.parquet"
        population_path = temporary / "selected_population.parquet"
        state.reset_index().to_parquet(state_path, index=False, compression="zstd")
        population.reset_index().to_parquet(population_path, index=False, compression="zstd")
        code_paths = [
            Path(__file__).resolve(),
            Path(pit_builder.__file__).resolve(),
            Path(build_causal_daily_features.__code__.co_filename).resolve(),
            Path(select_state_population.__code__.co_filename).resolve(),
        ]
        manifest: dict[str, Any] = {
            "schema_version": "qlib_peerlite_market_state_product_v1",
            "semantic_version": "m7_market_state_product_v1",
            "status": "BUILT_NOT_PIT_QUALIFIED",
            "product_id": output_dir.name,
            "created_at": datetime.now(TZ).isoformat(),
            "source_snapshot": {
                "path": str(snapshot_dir),
                "bundle_sha256": bindings["source_snapshot_bundle_sha256"],
                "source_bindings": bindings["source_bindings"],
            },
            "required_model_date_axis": {
                "product_manifest_sha256": bindings["required_product_manifest_sha256"],
                "dates_sha256": bindings["required_dates_sha256"],
            },
            "policy": {
                "population": (
                    "PIT CSI800 member AND 60-session listing age AND active AND "
                    "non-ST/non-unknown AND valid RAW price domain AND "
                    "causal-feature eligible"
                ),
                "state_sources": [
                    "ret_mean_20",
                    "ret_std_20",
                    "ret_1d",
                    "turnover_mean_20",
                ],
                "state_outputs": [
                    "mkt_trend_20",
                    "mkt_vol_20",
                    "mkt_breadth_1d",
                    "mkt_turnover_20",
                ],
                "labels_or_execution_fields_consumed": False,
            },
            "builder": [
                {"path": str(path), "sha256": sha256_file(path)} for path in code_paths
            ],
            "state": {
                "path": state_path.name,
                "sha256": sha256_file(state_path),
                "rows": len(state),
                "date_min": str(state.index.min().date()),
                "date_max": str(state.index.max().date()),
            },
            "population": {
                "path": population_path.name,
                "sha256": sha256_file(population_path),
                "rows": len(population),
            },
            "oos_seal": {
                "final_oos_start": "2025-01-01",
                "final_oos_market_partitions_opened": False,
                "performance_metrics_computed": False,
            },
        }
        manifest["content_sha256"] = _content_sha256(manifest)
        atomic_write_json(temporary / "market_state_manifest.json", manifest)
        for path in temporary.iterdir():
            path.chmod(0o440)
        temporary.chmod(0o550)
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--required-product-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    publish(
        snapshot_dir=args.snapshot_dir.resolve(),
        required_product_dir=args.required_product_dir.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(
        json.dumps(
            {
                "status": "BUILT_NOT_PIT_QUALIFIED",
                "output_dir": str(args.output_dir.resolve()),
                "final_oos_market_partitions_opened": False,
            }
        )
    )


if __name__ == "__main__":
    main()
