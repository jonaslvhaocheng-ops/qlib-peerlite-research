#!/usr/bin/env python3
"""Read-only source certificate for Qlib PeerLite.

Run on the ABM research server where ``research_playground.db.mysql_engine`` is
available. The output is DISCOVER evidence: it can reject an unsuitable path
but never certifies PIT availability or authorizes training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from research_playground.db import mysql_engine
from sqlalchemy import text

SHANGHAI = ZoneInfo("Asia/Shanghai")
TARGETS = [
    ("datayes", "mkt_equd", "raw_daily_market", "TRADE_DATE"),
    ("datayes", "md_security", "security_master", "LIST_DATE"),
    ("datayes", "md_trade_cal", "trade_calendar", "CALENDAR_DATE"),
    ("datayes", "mkt_equd_eval_new", "valuation_liquidity_candidate", "TRADE_DATE"),
    ("datayes", "mkt_equd_ind", "daily_trade_state_candidate", "TRADE_DATE"),
    ("datayes", "mkt_limit", "price_limit_state", "TRADE_DATE"),
    ("datayes", "abm_stock_pool", "daily_stock_pool_candidate", "TRADE_DATE"),
    ("datayes", "abm_is_ST", "daily_st_state_candidate", "TRADE_DATE"),
    ("datayes", "idx_cons", "historical_index_membership_candidate", "INTO_DATE"),
    ("abmdata", "qt_idx_constituents", "historical_index_membership_candidate", "into_date"),
]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        return json_safe(value.item())
    return value


def query_frame(conn: Any, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    frame = pd.read_sql(text(sql), conn, params=params or {})
    frame.columns = [str(column).lower() for column in frame.columns]
    return frame


def table_certificate(conn: Any, schema: str, table: str, role: str, date_field: str) -> dict:
    columns = query_frame(
        conn,
        """
        select
            column_name,
            ordinal_position,
            column_type,
            is_nullable,
            column_default,
            column_comment
        from information_schema.columns
        where table_schema = :schema and table_name = :table
        order by ordinal_position
        """,
        {"schema": schema, "table": table},
    )
    table_meta = query_frame(
        conn,
        """
        select
            engine,
            table_rows,
            create_time,
            update_time,
            table_collation,
            table_comment
        from information_schema.tables
        where table_schema = :schema and table_name = :table
        """,
        {"schema": schema, "table": table},
    )
    indexes = query_frame(
        conn,
        """
        select index_name, non_unique, seq_in_index, column_name, index_type
        from information_schema.statistics
        where table_schema = :schema and table_name = :table
        order by index_name, seq_in_index
        """,
        {"schema": schema, "table": table},
    )
    exists = not columns.empty
    date_min = None
    date_max = None
    sample: list[dict[str, Any]] = []
    if exists and date_field.lower() in set(columns["column_name"].str.lower()):
        safe_name = f"`{schema}`.`{table}`"
        safe_field = f"`{date_field}`"
        try:
            date_min = query_frame(
                conn,
                f"select {safe_field} as boundary_value from {safe_name} "
                f"where {safe_field} is not null order by {safe_field} asc limit 1",
            ).iloc[0, 0]
            date_max = query_frame(
                conn,
                f"select {safe_field} as boundary_value from {safe_name} "
                f"where {safe_field} is not null order by {safe_field} desc limit 1",
            ).iloc[0, 0]
            sample = query_frame(conn, f"select * from {safe_name} limit 3").astype(
                object
            ).where(pd.notna, None).to_dict("records")
        except Exception as exc:
            sample = [{"diagnostic_error": type(exc).__name__, "message": str(exc)}]

    return {
        "schema": schema,
        "table": table,
        "role": role,
        "exists": exists,
        "date_field": date_field,
        "date_min": json_safe(date_min),
        "date_max": json_safe(date_max),
        "table_metadata": (
            table_meta.astype(object).where(pd.notna, None).to_dict("records")[0]
            if not table_meta.empty
            else None
        ),
        "columns": columns.astype(object).where(pd.notna, None).to_dict("records"),
        "indexes": indexes.astype(object).where(pd.notna, None).to_dict("records"),
        "sample_rows": sample,
    }


def universe_probe(conn: Any) -> dict[str, Any]:
    candidates = query_frame(
        conn,
        """
        select table_schema, table_name, table_rows, table_comment
        from information_schema.tables
        where table_schema in ('datayes', 'abmdata')
          and (
              lower(table_name) like '%idx%cons%'
              or lower(table_name) like '%index%cons%'
              or lower(table_name) like '%constituent%'
          )
        order by table_schema, table_name
        """,
    ).astype(object).where(pd.notna, None).to_dict("records")
    exact_available = any(
        row.get("table_schema") == "abmdata"
        and row.get("table_name") == "qt_idx_constituents"
        for row in candidates
    )
    if not exact_available:
        return {
            "status": "EXACT_TABLE_MISSING",
            "exact_table": "abmdata.qt_idx_constituents",
            "candidate_tables": candidates,
            "rows": [],
        }
    frame = query_frame(
        conn,
        """
        select
            index_code,
            index_name,
            stock_code,
            stock_name,
            into_date,
            out_date,
            first_entrydate,
            out_declaredate,
            is_valid,
            entrytime,
            updatetime
        from abmdata.qt_idx_constituents
        where index_code in ('000300', '000300.SH', '000905', '000905.SH')
           or index_name like '%沪深300%'
           or index_name like '%中证500%'
        order by index_code, into_date desc
        limit 200
        """,
    )
    return {
        "status": "SAMPLE_ONLY",
        "exact_table": "abmdata.qt_idx_constituents",
        "candidate_tables": candidates,
        "rows": frame.astype(object).where(pd.notna, None).to_dict("records"),
    }


def write_markdown(path: Path, payload: dict) -> None:
    lines = [
        "# Qlib PeerLite 数据源证书",
        "",
        f"- 生成时间：`{payload['generated_at']}`",
        f"- 模式：`{payload['mode']}`",
        f"- 正面证据上限：`{payload['positive_ceiling']}`",
        f"- 状态：`{payload['status']}`",
        "",
        "当前物理字段、样本和数据库可读性不能证明历史市场可得时间、修订保留、",
        "公告时点、公司行动或完整 PIT 股票池。",
        "",
        "## 表级摘要",
        "",
        "| 来源 | 角色 | 存在 | 日期范围 | 列数 |",
        "| --- | --- | ---: | --- | ---: |",
    ]
    for item in payload["tables"]:
        lines.append(
            f"| `{item['schema']}.{item['table']}` | {item['role']} | "
            f"{item['exists']} | {item['date_min']} ~ {item['date_max']} | "
            f"{len(item['columns'])} |"
        )
    lines.extend(
        [
            "",
            "## 当前阻塞",
            "",
            *[f"- {gap}" for gap in payload["evidence_gaps"]],
            "",
            "## 下一项唯一高信息动作",
            "",
            payload["next_action"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    generated_at = datetime.now(SHANGHAI).isoformat()
    with mysql_engine(database="datayes").connect() as conn:
        try:
            conn.execute(text("set session max_execution_time=30000"))
        except Exception:
            pass
        tables = [
            table_certificate(conn, schema, table, role, date_field)
            for schema, table, role, date_field in TARGETS
        ]
        universe = universe_probe(conn)

    payload = {
        "schema_version": "qlib_peerlite_source_certificate_v1",
        "generated_at": generated_at,
        "mode": "DISCOVER",
        "target_claim": "MARKET_RECONSTRUCTIBLE",
        "positive_ceiling": "CANDIDATE_PATH_ONLY",
        "status": "NEEDS_EVIDENCE",
        "runtime": {
            "hostname": platform.node(),
            "python": sys.version,
            "platform": platform.platform(),
        },
        "tables": tables,
        "universe_probe": universe,
        "evidence_gaps": [
            "version-matched authoritative field dictionary and source locators",
            "historical vendor_available_time or equivalent market-availability evidence",
            "revision-retention policy for every consumed raw field",
            (
                "independent CSI300/CSI500 announcement/effective-date authority "
                "including exits and delistings"
            ),
            "immutable full extraction snapshot and receipt",
            "current statutory/broker fee receipt"
        ],
        "next_action": (
            "Review qt_idx_constituents index-code coverage and the DataYes raw-field dictionary; "
            "then decide whether the candidate universe and daily RAW path are "
            "eligible to enter VERIFY."
        ),
    }
    payload = json_safe(payload)
    payload["content_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    json_path = args.output_dir / "source_certificate.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(args.output_dir / "source_certificate.md", payload)
    manifest = {
        "schema_version": "qlib_peerlite_source_certificate_manifest_v1",
        "generated_at": generated_at,
        "files": {
            name: hashlib.sha256((args.output_dir / name).read_bytes()).hexdigest()
            for name in ("source_certificate.json", "source_certificate.md")
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"status": payload["status"], "output": str(args.output_dir)}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
