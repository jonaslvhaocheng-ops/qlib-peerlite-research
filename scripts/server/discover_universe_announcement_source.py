#!/usr/bin/env python3
"""Discover live metadata candidates for CSI membership announcement time."""

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


def query(conn: Any, sql: str) -> pd.DataFrame:
    frame = pd.read_sql(text(sql), conn)
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
        table_candidates = query(
            conn,
            """
            select table_schema, table_name, table_rows, table_comment
            from information_schema.tables
            where table_schema in ('datayes', 'abmdata')
              and (
                lower(table_name) regexp '(idx|index).*(cons|const|change|adjust)'
                or lower(table_name) regexp '(cons|const).*(idx|index|change)'
              )
            order by table_schema, table_name
            """,
        )
        clock_candidates = query(
            conn,
            """
            select
                c.table_schema,
                c.table_name,
                c.column_name,
                c.column_type,
                c.column_comment,
                t.table_comment
            from information_schema.columns c
            join information_schema.tables t
              on t.table_schema = c.table_schema
             and t.table_name = c.table_name
            where c.table_schema in ('datayes', 'abmdata')
              and (
                lower(c.column_name) regexp
                  '(announ|publish|declare|release|notice|effective|entry|update)'
                or lower(c.column_comment) regexp
                  '(公告|发布|披露|生效|入库|更新时间)'
              )
              and (
                lower(c.table_name) regexp '(idx|index|cons|const)'
                or lower(t.table_comment) regexp '(指数|成分)'
              )
            order by c.table_schema, c.table_name, c.ordinal_position
            """,
        )

    result = {
        "schema_version": "qlib_peerlite_universe_clock_discovery_v1",
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "mode": "VERIFY",
        "target_claim": "MARKET_RECONSTRUCTIBLE",
        "positive_ceiling": "CANDIDATE_DISCOVERY_ONLY_NEVER_PIT_PASS",
        "table_candidates": records(table_candidates),
        "clock_candidates": records(clock_candidates),
        "status": ("CANDIDATES_FOUND" if not clock_candidates.empty else "NO_LIVE_CLOCK_CANDIDATE"),
        "interpretation_rule": (
            "A name or comment match is not availability evidence. Each candidate "
            "requires an authoritative dictionary, revision semantics and sampled "
            "historical proof before selection."
        ),
    }
    output_path = args.output_dir / "universe_clock_discovery.json"
    output_path.write_text(
        json.dumps(json_safe(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "qlib_peerlite_evidence_manifest_v1",
        "files": {output_path.name: hashlib.sha256(output_path.read_bytes()).hexdigest()},
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(args.output_dir), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
