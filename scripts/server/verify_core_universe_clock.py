#!/usr/bin/env python3
"""VERIFY announcement/effective clocks in datayes.idx_cons_core."""

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

INDEX_IDS = (1782, 2103)


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
        columns = query(
            conn,
            """
            select
                column_name, column_type, is_nullable, column_default,
                column_comment
            from information_schema.columns
            where table_schema = 'datayes'
              and table_name = 'idx_cons_core'
            order by ordinal_position
            """,
        )
        summary = query(
            conn,
            """
            select
                c.security_id,
                i.ticker_symbol as index_ticker,
                i.exchange_cd as index_exchange,
                i.asset_class as index_asset_class,
                count(*) as row_count,
                count(distinct c.cons_id) as distinct_constituents,
                min(c.into_eff_date) as first_into_eff_date,
                max(c.into_eff_date) as last_into_eff_date,
                min(c.into_pub_date) as first_into_pub_date,
                max(c.into_pub_date) as last_into_pub_date,
                sum(case when c.out_eff_date is null then 1 else 0 end)
                    as open_memberships,
                sum(case when c.into_pub_date is null then 1 else 0 end)
                    as missing_into_pub,
                sum(
                    case
                        when c.out_eff_date is not null and c.out_pub_date is null
                        then 1 else 0
                    end
                ) as missing_out_pub,
                sum(
                    case
                        when c.into_pub_date > c.into_eff_date then 1 else 0
                    end
                ) as late_into_pub,
                sum(
                    case
                        when c.out_pub_date > c.out_eff_date then 1 else 0
                    end
                ) as late_out_pub,
                min(datediff(c.into_eff_date, c.into_pub_date))
                    as min_into_lead_days,
                max(datediff(c.into_eff_date, c.into_pub_date))
                    as max_into_lead_days
            from datayes.idx_cons_core c
            join datayes.md_security i
              on i.security_id = c.security_id
            where c.security_id in (1782, 2103)
            group by
                c.security_id, i.ticker_symbol, i.exchange_cd, i.asset_class
            order by c.security_id
            """,
        )
        yearly_coverage = query(
            conn,
            """
            select
                c.security_id,
                year(c.into_eff_date) as into_year,
                count(*) as additions,
                sum(case when c.into_pub_date is null then 1 else 0 end)
                    as missing_into_pub,
                sum(
                    case
                        when c.into_pub_date > c.into_eff_date then 1 else 0
                    end
                ) as late_into_pub
            from datayes.idx_cons_core c
            where c.security_id in (1782, 2103)
            group by c.security_id, year(c.into_eff_date)
            order by c.security_id, into_year
            """,
        )
        duplicate_keys = query(
            conn,
            """
            select
                security_id, cons_id, into_eff_date, count(*) as duplicate_count
            from datayes.idx_cons_core
            where security_id in (1782, 2103)
            group by security_id, cons_id, into_eff_date
            having count(*) > 1
            order by duplicate_count desc, security_id, cons_id
            limit 200
            """,
        )
        interval_comparison = query(
            conn,
            """
            select
                core.security_id,
                count(*) as core_rows,
                sum(
                    case
                        when generic.id is not null then 1 else 0
                    end
                ) as exact_interval_matches,
                sum(
                    case
                        when generic.id is null then 1 else 0
                    end
                ) as missing_from_generic
            from datayes.idx_cons_core core
            left join datayes.idx_cons generic
              on generic.security_id = core.security_id
             and generic.cons_id = core.cons_id
             and generic.into_date = core.into_eff_date
             and (
                  generic.out_date = core.out_eff_date
                  or (
                      generic.out_date is null
                      and core.out_eff_date is null
                  )
             )
            where core.security_id in (1782, 2103)
            group by core.security_id
            order by core.security_id
            """,
        )
        samples = query(
            conn,
            """
            select
                c.id,
                c.security_id,
                i.ticker_symbol as index_ticker,
                c.cons_id,
                s.ticker_symbol as constituent_ticker,
                s.exchange_cd as constituent_exchange,
                c.into_pub_date,
                c.into_eff_date,
                c.out_pub_date,
                c.out_eff_date,
                c.update_time
            from datayes.idx_cons_core c
            join datayes.md_security i
              on i.security_id = c.security_id
            left join datayes.md_security s
              on s.security_id = c.cons_id
            where c.security_id in (1782, 2103)
            order by c.into_eff_date desc, c.id desc
            limit 200
            """,
        )

    observed_ids = set(summary["security_id"].astype(int)) if not summary.empty else set()
    both_indices = set(INDEX_IDS).issubset(observed_ids)
    required_columns = {
        "security_id",
        "cons_id",
        "into_pub_date",
        "into_eff_date",
        "out_pub_date",
        "out_eff_date",
    }
    observed_columns = set(columns["column_name"].str.lower())
    announcement_schema = required_columns.issubset(observed_columns)
    no_into_clock_failures = bool(
        not summary.empty
        and (summary["missing_into_pub"].fillna(0).astype(int) == 0).all()
        and (summary["late_into_pub"].fillna(0).astype(int) == 0).all()
    )
    coverage_starts_by_2012 = bool(
        not summary.empty
        and (
            pd.to_datetime(summary["first_into_eff_date"], errors="coerce")
            <= pd.Timestamp("2012-01-01")
        ).all()
    )
    no_duplicate_keys = duplicate_keys.empty

    status = (
        "CLOCK_CANDIDATE_SUPPORTED"
        if all(
            [
                both_indices,
                announcement_schema,
                no_into_clock_failures,
                coverage_starts_by_2012,
                no_duplicate_keys,
            ]
        )
        else "NEEDS_EVIDENCE"
    )
    result = {
        "schema_version": "qlib_peerlite_core_universe_clock_verify_v1",
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "mode": "VERIFY",
        "target_path": "datayes.idx_cons_core -> CSI300+CSI500 announcement/effective membership",
        "target_claim": "MARKET_RECONSTRUCTIBLE",
        "status": status,
        "positive_ceiling": "SOURCE_CLOCK_CANDIDATE_ONLY_NEVER_PIT_PASS",
        "checks": {
            "both_exact_index_ids_observed": both_indices,
            "announcement_effective_schema_observed": announcement_schema,
            "no_missing_or_late_into_publication_dates": no_into_clock_failures,
            "coverage_starts_by_2012": coverage_starts_by_2012,
            "no_duplicate_membership_keys": no_duplicate_keys,
        },
        "columns": records(columns),
        "summary": records(summary),
        "yearly_coverage": records(yearly_coverage),
        "duplicate_keys": records(duplicate_keys),
        "interval_comparison_to_idx_cons": records(interval_comparison),
        "samples": records(samples),
        "interpretation": (
            "Database field comments support announcement/effective semantics, but "
            "a versioned vendor dictionary, source snapshot and independent behavior "
            "audit remain mandatory before PIT qualification."
        ),
    }
    output_path = args.output_dir / "core_universe_clock_verify.json"
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
    return 0 if status == "CLOCK_CANDIDATE_SUPPORTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
