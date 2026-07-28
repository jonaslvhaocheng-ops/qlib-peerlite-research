#!/usr/bin/env python3
"""Build content-addressed, read-only source snapshots without exposing values."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from research_playground.db import mysql_engine
from sqlalchemy import text

SOURCE_ID_BY_TABLE = {
    "mkt_equd": "datayes-daily-raw",
    "idx_cons_core": "datayes-index-constituents",
    "md_security": "datayes-security-master",
    "md_trade_cal": "datayes-trade-calendar",
    "mkt_limit": "datayes-price-limits",
    "md_sec_halt": "datayes-security-halts",
    "equ_inst_sstate": "datayes-special-status",
    "mkt_adjf": "datayes-corporate-action-mask",
}
INDEX_IDS = (1782, 2103)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def write_query_parquet(
    conn: Any,
    *,
    sql: str,
    output_path: Path,
    chunksize: int,
) -> dict[str, Any]:
    writer: pq.ParquetWriter | None = None
    row_count = 0
    try:
        for frame in pd.read_sql(text(sql), conn, chunksize=chunksize):
            frame.columns = [str(column).lower() for column in frame.columns]
            table = pa.Table.from_pandas(frame, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(
                    output_path,
                    table.schema,
                    compression="zstd",
                    use_dictionary=True,
                )
            writer.write_table(table)
            row_count += len(frame)
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        raise RuntimeError(f"Query produced zero rows for required file {output_path.name}")
    os.chmod(output_path, 0o440)
    return {
        "path": output_path.name,
        "rows": row_count,
        "bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
    }


def source_manifest(
    output_dir: Path,
    *,
    table: str,
    files: list[dict[str, Any]],
    snapshot_time: str,
    query_bounds: dict[str, str],
) -> tuple[Path, str]:
    payload = {
        "schema_version": "qlib_peerlite_source_snapshot_v1",
        "source_id": SOURCE_ID_BY_TABLE[table],
        "table": f"datayes.{table}",
        "snapshot_time": snapshot_time,
        "query_bounds": query_bounds,
        "files": files,
        "read_only": True,
        "value_exposure": "NONE_COUNTS_AND_HASHES_ONLY",
    }
    payload["content_sha256"] = canonical_sha256(payload)
    manifest_path = output_dir / f"{table}.manifest.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(manifest_path, 0o440)
    return manifest_path, sha256_file(manifest_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-date", default="2011-09-01")
    parser.add_argument("--prediction-end", default="2026-06-30")
    parser.add_argument("--support-end", default="2026-07-10")
    parser.add_argument("--oos-start", default="2025-01-01")
    parser.add_argument("--chunksize", type=int, default=100_000)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    snapshot_time = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    bounds = {
        "start_date": args.start_date,
        "prediction_end": args.prediction_end,
        "support_end": args.support_end,
        "oos_start": args.oos_start,
    }
    file_records: dict[str, list[dict[str, Any]]] = {table: [] for table in SOURCE_ID_BY_TABLE}
    universe_join = """
        select distinct cons_id
        from datayes.idx_cons_core
        where security_id in (1782, 2103)
    """

    with mysql_engine(database="datayes").connect() as conn:
        try:
            conn.execute(text("set session max_execution_time=0"))
        except Exception:
            pass

        fixed_queries = {
            "idx_cons_core": f"""
                select
                    id, security_id, cons_id, into_pub_date, out_pub_date,
                    into_eff_date, out_eff_date, update_time
                from datayes.idx_cons_core
                where security_id in ({INDEX_IDS[0]}, {INDEX_IDS[1]})
                order by security_id, cons_id, into_eff_date, id
            """,
            "md_security": f"""
                select
                    security_id, ticker_symbol, exchange_cd, asset_class,
                    list_date, delist_date, party_id
                from datayes.md_security
                where security_id in ({universe_join})
                   or security_id in ({INDEX_IDS[0]}, {INDEX_IDS[1]})
                order by security_id
            """,
            "md_trade_cal": f"""
                select calendar_date, exchange_cd, is_open, prev_trade_date
                from datayes.md_trade_cal
                where exchange_cd in ('XSHG', 'XSHE')
                  and calendar_date between '{args.start_date}'
                                        and '{args.support_end}'
                order by calendar_date, exchange_cd
            """,
            "md_sec_halt": f"""
                select
                    id, security_id, ticker_symbol, exchange_cd,
                    halt_begin_time, resump_begin_time, update_time
                from datayes.md_sec_halt
                where security_id in ({universe_join})
                  and halt_begin_time <= '{args.support_end} 23:59:59'
                  and (
                      resump_begin_time is null
                      or resump_begin_time >= '{args.start_date} 00:00:00'
                  )
                order by security_id, halt_begin_time, id
            """,
            "equ_inst_sstate": f"""
                select
                    id, security_id, party_id, ticker_symbol, sec_short_name,
                    party_state, publish_date, eff_date, update_time
                from datayes.equ_inst_sstate
                where security_id in ({universe_join})
                  and eff_date <= '{args.support_end}'
                order by security_id, eff_date, id
            """,
            "mkt_adjf": f"""
                select id, security_id, ticker_symbol, ex_div_date
                from datayes.mkt_adjf
                where security_id in ({universe_join})
                  and ex_div_date between '{args.start_date}'
                                      and '{args.support_end}'
                order by security_id, ex_div_date, id
            """,
        }
        for table, sql in fixed_queries.items():
            output_path = args.output_dir / f"{table}.parquet"
            file_records[table].append(
                write_query_parquet(
                    conn,
                    sql=sql,
                    output_path=output_path,
                    chunksize=args.chunksize,
                )
            )
            print(f"SNAPSHOT_PROGRESS table={table} files=1")

        start_year = int(args.start_date[:4])
        end_year = int(args.support_end[:4])
        for year in range(start_year, end_year + 1):
            year_start = max(args.start_date, f"{year}-01-01")
            year_end = min(args.support_end, f"{year}-12-31")
            partition_queries = {
                "mkt_equd": f"""
                    select
                        id, security_id, ticker_symbol, exchange_cd, trade_date,
                        pre_close_price, act_pre_close_price, open_price,
                        highest_price, lowest_price, close_price, turnover_vol,
                        turnover_value, turnover_rate
                    from datayes.mkt_equd
                    where security_id in ({universe_join})
                      and trade_date between '{year_start}' and '{year_end}'
                    order by trade_date, security_id, id
                """,
                "mkt_limit": f"""
                    select
                        id, security_id, ticker_symbol, exchange_cd, trade_date,
                        limit_up_price, limit_down_price
                    from datayes.mkt_limit
                    where security_id in ({universe_join})
                      and trade_date between '{year_start}' and '{year_end}'
                    order by trade_date, security_id, id
                """,
            }
            for table, sql in partition_queries.items():
                output_path = args.output_dir / f"{table}_{year}.parquet"
                record = write_query_parquet(
                    conn,
                    sql=sql,
                    output_path=output_path,
                    chunksize=args.chunksize,
                )
                record["sealed_final_oos_partition"] = year >= int(args.oos_start[:4])
                file_records[table].append(record)
            print(f"SNAPSHOT_PROGRESS year={year} partitioned_tables=2")

    source_manifests: dict[str, dict[str, str]] = {}
    for table, files in file_records.items():
        manifest_path, digest = source_manifest(
            args.output_dir,
            table=table,
            files=files,
            snapshot_time=snapshot_time,
            query_bounds=bounds,
        )
        source_manifests[SOURCE_ID_BY_TABLE[table]] = {
            "manifest": manifest_path.name,
            "manifest_sha256": digest,
        }

    universe_payload = {
        "schema_version": "qlib_peerlite_universe_snapshot_v1",
        "definition": "CSI300 SECURITY_ID=1782 union CSI500 SECURITY_ID=2103",
        "membership_rule": (
            "announcement <= prediction_time and prediction_time in [effective_from,effective_to)"
        ),
        "source_manifest": source_manifests["datayes-index-constituents"],
    }
    universe_payload["universe_hash"] = canonical_sha256(universe_payload)
    universe_path = args.output_dir / "universe_snapshot.json"
    universe_path.write_text(
        json.dumps(universe_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(universe_path, 0o440)

    overall = {
        "schema_version": "qlib_peerlite_sealed_snapshot_bundle_v1",
        "snapshot_time": snapshot_time,
        "bounds": bounds,
        "policy": "contracts/oos_sealed_ingestion_policy.json",
        "sources": source_manifests,
        "universe": {
            "path": universe_path.name,
            "sha256": sha256_file(universe_path),
            "universe_hash": universe_payload["universe_hash"],
        },
        "value_exposure": "NONE_COUNTS_AND_HASHES_ONLY",
        "status": "SEALED_NOT_PIT_QUALIFIED",
    }
    overall["content_sha256"] = canonical_sha256(overall)
    overall_path = args.output_dir / "snapshot_bundle_manifest.json"
    overall_path.write_text(
        json.dumps(overall, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(overall_path, 0o440)
    os.chmod(args.output_dir, 0o550)
    print(
        json.dumps(
            {
                "status": overall["status"],
                "manifest": str(overall_path),
                "manifest_sha256": sha256_file(overall_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
