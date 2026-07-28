#!/usr/bin/env python3
"""Targeted VERIFY probe for live CSI300/CSI500 constituent sources."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from research_playground.db import mysql_engine
from sqlalchemy import text


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        return json_safe(value.item())
    return value


def query(conn: Any, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    frame = pd.read_sql(text(sql), conn, params=params or {})
    frame.columns = [str(column).lower() for column in frame.columns]
    return frame


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json_safe(frame.astype(object).where(pd.notna, None).to_dict("records"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    with mysql_engine(database="datayes").connect() as conn:
        try:
            conn.execute(text("set session max_execution_time=30000"))
        except Exception:
            pass

        candidate_tables = query(
            conn,
            """
            select table_schema, table_name, table_rows, table_comment
            from information_schema.tables
            where table_schema = 'datayes'
              and table_name in (
                  'idx_cons', 'idx_cons_csi', 'md_index', 'mkt_idxd', 'md_security'
              )
            order by table_name
            """,
        )
        candidate_columns = query(
            conn,
            """
            select table_name, column_name, column_type, is_nullable, column_comment
            from information_schema.columns
            where table_schema = 'datayes'
              and table_name in (
                  'idx_cons', 'idx_cons_csi', 'md_index', 'mkt_idxd', 'md_security'
              )
            order by table_name, ordinal_position
            """,
        )
        index_identity = query(
            conn,
            """
            select
                security_id,
                ticker_symbol,
                exchange_cd,
                sec_full_name,
                sec_short_name,
                asset_class,
                list_status_cd,
                list_date,
                delist_date,
                update_time
            from datayes.md_security
            where ticker_symbol in ('000300', '000905')
            order by ticker_symbol, exchange_cd, security_id
            """,
        )
        interval_summary = query(
            conn,
            """
            select
                idx_security.ticker_symbol as index_ticker,
                idx_security.exchange_cd as index_exchange,
                idx_security.asset_class as index_asset_class,
                count(*) as row_count,
                min(membership.into_date) as first_into_date,
                max(membership.into_date) as last_into_date,
                min(membership.out_date) as first_out_date,
                max(membership.out_date) as last_out_date,
                sum(case when membership.out_date is null then 1 else 0 end)
                    as open_memberships,
                count(distinct membership.cons_id) as distinct_constituents
            from datayes.idx_cons membership
            join datayes.md_security idx_security
              on idx_security.security_id = membership.security_id
            where idx_security.ticker_symbol in ('000300', '000905')
            group by
                idx_security.ticker_symbol,
                idx_security.exchange_cd,
                idx_security.asset_class
            order by index_ticker, index_exchange
            """,
        )
        membership_sample = query(
            conn,
            """
            select
                idx_security.security_id as index_security_id,
                idx_security.ticker_symbol as index_ticker,
                idx_security.exchange_cd as index_exchange,
                membership.cons_id,
                constituent.ticker_symbol as constituent_ticker,
                constituent.exchange_cd as constituent_exchange,
                constituent.list_date,
                constituent.delist_date,
                membership.into_date,
                membership.out_date,
                membership.is_new,
                membership.update_time
            from datayes.idx_cons membership
            join datayes.md_security idx_security
              on idx_security.security_id = membership.security_id
            left join datayes.md_security constituent
              on constituent.security_id = membership.cons_id
            where idx_security.ticker_symbol in ('000300', '000905')
            order by membership.into_date desc, membership.id desc
            limit 200
            """,
        )

    summary_tickers = set(interval_summary["index_ticker"].astype(str))
    interval_supported = {"000300", "000905"}.issubset(summary_tickers)
    required_announcement_names = {
        "announce_date",
        "announcement_date",
        "publish_time",
        "effective_announce_date",
    }
    idx_columns = set(
        candidate_columns.loc[
            candidate_columns["table_name"].isin(["idx_cons", "idx_cons_csi"]),
            "column_name",
        ].str.lower()
    )
    announcement_field_present = bool(required_announcement_names & idx_columns)

    result = {
        "schema_version": "qlib_peerlite_universe_verify_v1",
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "mode": "VERIFY",
        "target_path": "datayes.idx_cons / idx_cons_csi -> CSI300+CSI500 PIT membership",
        "target_claim": "MARKET_RECONSTRUCTIBLE",
        "status": (
            "SUPPORTED_EFFECTIVE_INTERVAL_ONLY"
            if interval_supported
            else "NEEDS_EVIDENCE"
        ),
        "positive_ceiling": "SOURCE_DECISION_ONLY_NEVER_PIT_PASS",
        "checks": {
            "both_index_identities_observed": interval_supported,
            "effective_interval_fields_observed": {"into_date", "out_date"}.issubset(
                idx_columns
            ),
            "announcement_or_publication_field_observed": announcement_field_present,
            "historical_inactive_rows_observed": bool(
                (membership_sample["out_date"].notna()).any()
            ),
        },
        "candidate_tables": records(candidate_tables),
        "candidate_columns": records(candidate_columns),
        "index_identity": records(index_identity),
        "interval_summary": records(interval_summary),
        "membership_sample": records(membership_sample),
        "decision": (
            "datayes.idx_cons is a viable effective-interval candidate for both indices; "
            "it cannot yet satisfy PIT announcement-time eligibility."
            if interval_supported
            else "the live candidate does not establish both required indices"
        ),
        "blocker": (
            "No authoritative announcement/publication clock is established by the "
            "observed constituent tables; UPDATE_TIME cannot be reinterpreted as historical "
            "market availability."
        ),
        "next_action": (
            "Locate a versioned DataYes/CSI source dictionary or announcement-change table "
            "that binds each membership interval to a publication timestamp."
        ),
    }
    safe = json_safe(result)
    content = json.dumps(
        safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    safe["content_sha256"] = hashlib.sha256(content).hexdigest()
    json_path = args.output_dir / "universe_verify.json"
    json_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "schema_version": "qlib_peerlite_verify_manifest_v1",
        "files": {
            "universe_verify.json": hashlib.sha256(json_path.read_bytes()).hexdigest()
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"status": safe["status"], "output": str(args.output_dir)}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
