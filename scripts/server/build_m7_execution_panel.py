#!/usr/bin/env python3
"""Build the hash-bound pre-final-OOS portfolio execution panel for M7."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from qlib_peerlite.governance.artifacts import atomic_write_json, sha256_file


def _halted_at_open(halts: pd.DataFrame, keys: pd.DataFrame) -> np.ndarray:
    halted = np.zeros(len(keys), dtype=bool)
    by_security = {
        int(security): frame
        for security, frame in halts.groupby("security_id", sort=False)
    }
    for security, positions in keys.groupby("security_id", sort=False).indices.items():
        events = by_security.get(int(security))
        if events is None:
            continue
        execution_times = keys.iloc[positions]["execution_time"].to_numpy(
            dtype="datetime64[ns]"
        )
        begins = events["halt_begin_time"].to_numpy(dtype="datetime64[ns]")
        resumes = events["resump_begin_time"].fillna(pd.Timestamp.max).to_numpy(
            dtype="datetime64[ns]"
        )
        active = (begins[:, None] <= execution_times[None, :]) & (
            resumes[:, None] > execution_times[None, :]
        )
        halted[np.asarray(positions, dtype=int)] = active.any(axis=0)
    return halted


def run(
    *,
    product_dir: Path,
    snapshot_dir: Path,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    product_manifest = json.loads(
        (product_dir / "data_product_manifest.json").read_text(encoding="utf-8")
    )
    if product_manifest["matrix"]["date_max"] >= "2025-01-01":
        raise RuntimeError("execution product crosses final OOS")
    matrix_parts: list[pd.DataFrame] = []
    market_parts: list[pd.DataFrame] = []
    limit_parts: list[pd.DataFrame] = []
    source_files: list[dict[str, object]] = []
    matrix_columns = [
        "datetime",
        "instrument",
        "security_id",
        "label_start_time",
        "label_end_time",
        "label",
    ]
    for year in range(2017, 2025):
        market_path = snapshot_dir / f"mkt_equd_{year}.parquet"
        market_parts.append(
            pd.read_parquet(
                market_path,
                columns=[
                    "security_id",
                    "trade_date",
                    "open_price",
                    "close_price",
                    "turnover_value",
                ],
            )
        )
        source_files.append(
            {
                "path": str(market_path),
                "sha256": sha256_file(market_path),
                "bytes": market_path.stat().st_size,
            }
        )
        if year < 2018:
            continue
        matrix_path = product_dir / "matrix" / f"matrix_{year}.parquet"
        limit_path = snapshot_dir / f"mkt_limit_{year}.parquet"
        matrix_parts.append(pd.read_parquet(matrix_path, columns=matrix_columns))
        limit_parts.append(
            pd.read_parquet(
                limit_path,
                columns=[
                    "security_id",
                    "trade_date",
                    "limit_up_price",
                    "limit_down_price",
                ],
            )
        )
        for path in (matrix_path, limit_path):
            source_files.append(
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    matrix = pd.concat(matrix_parts, ignore_index=True)
    matrix["datetime"] = pd.to_datetime(matrix["datetime"])
    date_map = (
        matrix[["datetime", "label_start_time", "label_end_time"]]
        .drop_duplicates()
        .sort_values("datetime")
    )
    per_date_counts = date_map.groupby("datetime").size()
    if not per_date_counts.eq(1).all():
        raise RuntimeError("label-start date mapping is not unique")
    date_map = date_map.drop_duplicates("datetime")
    date_map["execution_date"] = pd.to_datetime(date_map["label_start_time"]).dt.date
    date_map["exit_date"] = pd.to_datetime(date_map["label_end_time"]).dt.date
    market = pd.concat(market_parts, ignore_index=True)
    limits = pd.concat(limit_parts, ignore_index=True)
    market["trade_date"] = pd.to_datetime(market["trade_date"]).dt.date
    market["trade_datetime"] = pd.to_datetime(market["trade_date"])
    market = market.sort_values(["security_id", "trade_date"])
    market["adv20"] = (
        market.groupby("security_id", sort=False)["turnover_value"]
        .rolling(20, min_periods=20)
        .mean()
        .reset_index(level=0, drop=True)
    )
    limits["trade_date"] = pd.to_datetime(limits["trade_date"]).dt.date
    union_ids = np.sort(matrix["security_id"].drop_duplicates().to_numpy())
    prediction_axis = pd.DatetimeIndex(date_map["datetime"].sort_values())
    base = pd.DataFrame(
        {
            "security_id": np.repeat(union_ids, len(prediction_axis)),
            "datetime": np.tile(prediction_axis.to_numpy(), len(union_ids)),
        }
    )
    asof_market = market.loc[
        market["security_id"].isin(union_ids),
        ["security_id", "trade_datetime", "close_price", "adv20"],
    ].sort_values(["trade_datetime", "security_id"])
    base = pd.merge_asof(
        base.sort_values(["datetime", "security_id"]),
        asof_market,
        left_on="datetime",
        right_on="trade_datetime",
        by="security_id",
        direction="backward",
        allow_exact_matches=True,
    ).rename(columns={"close_price": "prediction_close_price"})
    base = base.drop(columns=["trade_datetime"]).merge(
        date_map[["datetime", "execution_date", "exit_date"]],
        on="datetime",
        how="inner",
        validate="many_to_one",
    )
    execution_market = market[
        ["security_id", "trade_date", "open_price"]
    ].rename(columns={"trade_date": "execution_date"})
    exit_lookup = base[["security_id", "exit_date"]].copy()
    exit_lookup["exit_datetime"] = pd.to_datetime(exit_lookup["exit_date"])
    exit_lookup["_row"] = np.arange(len(exit_lookup))
    exit_market = market[
        ["security_id", "trade_datetime", "close_price"]
    ].sort_values(["trade_datetime", "security_id"])
    exit_values = pd.merge_asof(
        exit_lookup.sort_values(["exit_datetime", "security_id"]),
        exit_market,
        left_on="exit_datetime",
        right_on="trade_datetime",
        by="security_id",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("_row")
    base["exit_close_price"] = exit_values["close_price"].to_numpy()
    execution = base.merge(
        execution_market,
        on=["security_id", "execution_date"],
        how="left",
        validate="many_to_one",
    )
    execution["execution_time"] = (
        pd.to_datetime(execution["execution_date"].astype(str))
        + pd.Timedelta(hours=9, minutes=30)
    )
    execution = execution.merge(
        limits,
        left_on=["security_id", "execution_date"],
        right_on=["security_id", "trade_date"],
        how="left",
        validate="many_to_one",
    ).drop(columns=["trade_date"])
    halt_path = snapshot_dir / "md_sec_halt.parquet"
    halts = pd.read_parquet(
        halt_path,
        columns=["security_id", "halt_begin_time", "resump_begin_time"],
    )
    source_files.append(
        {
            "path": str(halt_path),
            "sha256": sha256_file(halt_path),
            "bytes": halt_path.stat().st_size,
        }
    )
    execution["halted_at_open"] = _halted_at_open(halts, execution)
    open_values = execution["open_price"].to_numpy(dtype=float)
    finite_open = np.isfinite(open_values) & (open_values > 0)
    finite_limits = np.isfinite(
        execution[["limit_up_price", "limit_down_price"]].to_numpy(dtype=float)
    ).all(axis=1)
    execution["can_buy"] = (
        finite_open
        & finite_limits
        & ~execution["halted_at_open"]
        & (execution["open_price"] < execution["limit_up_price"] - 1e-12)
    )
    execution["can_sell"] = (
        finite_open
        & finite_limits
        & ~execution["halted_at_open"]
        & (execution["open_price"] > execution["limit_down_price"] + 1e-12)
    )
    execution["forward_return"] = (
        execution["exit_close_price"] / execution["open_price"] - 1.0
    )
    execution["overnight_return"] = (
        execution["open_price"] / execution["prediction_close_price"] - 1.0
    )
    execution["carry_return"] = (
        execution["exit_close_price"] / execution["prediction_close_price"] - 1.0
    )
    execution.loc[~finite_open, ["forward_return", "overnight_return"]] = np.nan
    eligible_keys = pd.MultiIndex.from_frame(
        matrix[["datetime", "security_id"]].drop_duplicates()
    )
    execution_keys = pd.MultiIndex.from_frame(execution[["datetime", "security_id"]])
    execution["eligible"] = execution_keys.isin(eligible_keys)
    eligible_labels = matrix.set_index(["datetime", "security_id"])["label"]
    comparable = execution.loc[execution["eligible"]].set_index(
        ["datetime", "security_id"]
    )
    difference = (
        comparable["forward_return"] - eligible_labels.loc[comparable.index]
    ).abs()
    if difference.max() > 1e-10:
        raise RuntimeError("raw execution return differs from the audited eligible label")
    output = pd.DataFrame(
        {
            "datetime": pd.to_datetime(execution["datetime"]),
            "instrument": execution["security_id"].astype(str),
            "forward_return": execution["forward_return"].astype(float),
            "carry_return": execution["carry_return"].astype(float),
            "overnight_return": execution["overnight_return"].astype(float),
            "eligible": execution["eligible"].astype(bool),
            "can_buy": execution["can_buy"].astype(bool),
            "can_sell": execution["can_sell"].astype(bool),
            "adv20": execution["adv20"].astype(float),
            "execution_date": pd.to_datetime(execution["execution_date"]),
        }
    )
    carry_finite = np.isfinite(output["carry_return"].to_numpy(dtype=float))
    overnight_finite = np.isfinite(output["overnight_return"].to_numpy(dtype=float))
    adv_finite = np.isfinite(output["adv20"].to_numpy(dtype=float))
    finite_mask = adv_finite & (carry_finite | overnight_finite)
    excluded_nonfinite_rows = int((~finite_mask).sum())
    output = output.loc[finite_mask]
    output = output.sort_values(["datetime", "instrument"], ignore_index=True)
    duplicate_count = int(output.duplicated(["datetime", "instrument"]).sum())
    nonfinite_count = int(
        (
            ~np.isfinite(
                output[["carry_return", "adv20"]].to_numpy(dtype=float)
            ).all(axis=1)
            & ~np.isfinite(
                output[["overnight_return", "adv20"]].to_numpy(dtype=float)
            ).all(axis=1)
        ).sum()
    )
    if duplicate_count:
        raise RuntimeError(f"execution panel contains {duplicate_count} duplicate keys")
    if output["datetime"].max() >= pd.Timestamp("2025-01-01"):
        raise RuntimeError("execution panel crosses final OOS")
    if nonfinite_count:
        raise RuntimeError(f"execution panel contains {nonfinite_count} non-finite values")
    panel_path = output_dir / "execution_panel.parquet"
    output.to_parquet(panel_path, index=False)
    manifest = {
        "schema_version": "qlib_peerlite_m7_execution_panel_v1",
        "semantic_version": "m7_execution_panel_v1",
        "status": "PASS",
        "rows": len(output),
        "date_min": output["datetime"].min().date().isoformat(),
        "date_max": output["datetime"].max().date().isoformat(),
        "columns": list(output.columns),
        "panel_sha256": sha256_file(panel_path),
        "product_manifest_sha256": sha256_file(product_dir / "data_product_manifest.json"),
        "source_files": source_files,
        "rules": {
            "buy": "T+1 open exists, not halted, and open strictly below limit-up",
            "sell": "T+1 open exists, not halted, and open strictly above limit-down",
            "adv20": "exp(T-known log_amount_mean_20)",
            "missing": "fail closed",
        },
        "excluded_nonfinite_rows": excluded_nonfinite_rows,
        "final_oos_market_partitions_opened": False,
    }
    unsigned = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    manifest["content_sha256"] = hashlib.sha256(unsigned).hexdigest()
    atomic_write_json(output_dir / "execution_panel_manifest.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(
        product_dir=args.product_dir.resolve(),
        snapshot_dir=args.snapshot_dir.resolve(),
        output_dir=args.output_dir.resolve(),
    )


if __name__ == "__main__":
    main()
