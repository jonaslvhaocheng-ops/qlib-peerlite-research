#!/usr/bin/env python3
"""VERIFY auxiliary A-share calendar, status, execution and event sources."""

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

TABLES = (
    "md_security",
    "md_trade_cal",
    "mkt_limit",
    "md_sec_halt",
    "equ_inst_sstate",
    "mkt_adjf",
)


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

    quoted_tables = ", ".join(f"'{name}'" for name in TABLES)
    with mysql_engine(database="datayes").connect() as conn:
        try:
            conn.execute(text("set session max_execution_time=60000"))
        except Exception:
            pass
        columns = query(
            conn,
            f"""
            select
                table_name, ordinal_position, column_name, column_type,
                is_nullable, column_comment
            from information_schema.columns
            where table_schema = 'datayes'
              and table_name in ({quoted_tables})
            order by table_name, ordinal_position
            """,
        )
        security_summary = query(
            conn,
            """
            select
                count(*) as a_share_rows,
                count(distinct security_id) as distinct_security_ids,
                count(distinct concat(exchange_cd, ':', ticker_symbol))
                    as distinct_exchange_tickers,
                min(list_date) as first_list_date,
                max(list_date) as last_list_date,
                sum(case when delist_date is not null then 1 else 0 end)
                    as delisted_rows
            from datayes.md_security
            where asset_class = 'E'
              and exchange_cd in ('XSHG', 'XSHE')
            """,
        )
        security_duplicate_keys = query(
            conn,
            """
            select
                exchange_cd, ticker_symbol, count(*) as duplicate_count
            from datayes.md_security
            where asset_class = 'E'
              and exchange_cd in ('XSHG', 'XSHE')
            group by exchange_cd, ticker_symbol
            having count(*) > 1
            order by duplicate_count desc, exchange_cd, ticker_symbol
            limit 200
            """,
        )
        calendar_summary = query(
            conn,
            """
            select
                exchange_cd,
                min(calendar_date) as first_date,
                max(calendar_date) as last_date,
                sum(case when is_open = 1 then 1 else 0 end) as open_days,
                count(*) as rows_total
            from datayes.md_trade_cal
            where exchange_cd in ('XSHG', 'XSHE')
            group by exchange_cd
            order by exchange_cd
            """,
        )
        calendar_mismatches = query(
            conn,
            """
            select
                sh.calendar_date,
                sh.is_open as xshg_is_open,
                sz.is_open as xshe_is_open
            from datayes.md_trade_cal sh
            join datayes.md_trade_cal sz
              on sz.calendar_date = sh.calendar_date
             and sz.exchange_cd = 'XSHE'
            where sh.exchange_cd = 'XSHG'
              and sh.calendar_date between '2012-01-01' and '2026-06-30'
              and sh.is_open <> sz.is_open
            order by sh.calendar_date
            limit 200
            """,
        )
        limit_summary = query(
            conn,
            """
            select
                min(trade_date) as first_date,
                max(trade_date) as last_date,
                count(*) as row_count,
                count(distinct security_id) as distinct_security_ids,
                sum(
                    case
                        when limit_up_price is null or limit_down_price is null
                        then 1 else 0
                    end
                ) as missing_limit_prices
            from datayes.mkt_limit
            where exchange_cd in ('XSHG', 'XSHE')
            """,
        )
        limit_duplicate_keys = query(
            conn,
            """
            select security_id, trade_date, count(*) as duplicate_count
            from datayes.mkt_limit
            where exchange_cd in ('XSHG', 'XSHE')
            group by security_id, trade_date
            having count(*) > 1
            order by duplicate_count desc, trade_date desc
            limit 200
            """,
        )
        halt_summary = query(
            conn,
            """
            select
                min(halt_begin_time) as first_halt_time,
                max(halt_begin_time) as last_halt_time,
                max(resump_begin_time) as last_resumption_time,
                count(*) as row_count,
                count(distinct security_id) as distinct_security_ids,
                sum(case when halt_begin_time is null then 1 else 0 end)
                    as missing_halt_begin,
                sum(case when resump_begin_time is null then 1 else 0 end)
                    as open_ended_halts
            from datayes.md_sec_halt
            where exchange_cd in ('XSHG', 'XSHE')
            """,
        )
        special_state_summary = query(
            conn,
            """
            select
                min(publish_date) as first_publish_date,
                max(publish_date) as last_publish_date,
                min(eff_date) as first_effective_date,
                max(eff_date) as last_effective_date,
                count(*) as row_count,
                count(distinct security_id) as distinct_security_ids,
                sum(case when publish_date is null then 1 else 0 end)
                    as missing_publish_date,
                sum(case when eff_date is null then 1 else 0 end)
                    as missing_effective_date,
                sum(
                    case when publish_date > eff_date then 1 else 0 end
                ) as publish_after_effective,
                sum(
                    case
                        when eff_date >= '2012-01-01' and publish_date is null
                        then 1 else 0
                    end
                ) as research_period_missing_publish,
                sum(
                    case
                        when eff_date >= '2012-01-01'
                         and publish_date > eff_date
                        then 1 else 0
                    end
                ) as research_period_publish_after_effective
            from datayes.equ_inst_sstate
            """,
        )
        special_state_clock_anomalies = query(
            conn,
            """
            select
                id, security_id, ticker_symbol, sec_short_name, party_state,
                publish_date, eff_date, reason, update_time
            from datayes.equ_inst_sstate
            where publish_date is null or publish_date > eff_date
            order by eff_date, id
            """,
        )
        special_state_values = query(
            conn,
            """
            select party_state, count(*) as row_count
            from datayes.equ_inst_sstate
            group by party_state
            order by row_count desc, party_state
            """,
        )
        special_state_samples = query(
            conn,
            """
            select
                id, security_id, ticker_symbol, sec_short_name, party_state,
                publish_date, eff_date, reason, update_time
            from datayes.equ_inst_sstate
            order by coalesce(publish_date, eff_date) desc, id desc
            limit 200
            """,
        )
        corporate_action_summary = query(
            conn,
            """
            select
                min(ex_div_date) as first_ex_div_date,
                max(ex_div_date) as last_ex_div_date,
                count(*) as row_count,
                count(distinct security_id) as distinct_security_ids,
                sum(case when ex_div_date is null then 1 else 0 end)
                    as missing_ex_div_date
            from datayes.mkt_adjf
            """,
        )
        corporate_action_duplicate_keys = query(
            conn,
            """
            select security_id, ex_div_date, count(*) as duplicate_count
            from datayes.mkt_adjf
            group by security_id, ex_div_date
            having count(*) > 1
            order by duplicate_count desc, ex_div_date desc
            limit 200
            """,
        )

    observed_tables = set(columns["table_name"])
    required_tables_present = set(TABLES).issubset(observed_tables)
    state_row = special_state_summary.iloc[0]
    conservative_state_clock_supported = bool(
        int(state_row["missing_effective_date"]) == 0
        and int(state_row["research_period_missing_publish"]) == 0
    )
    current_coverage = {
        "mkt_limit": str(limit_summary.iloc[0]["last_date"]) >= "2026-06-30",
        "md_sec_halt": (
            pd.Timestamp(halt_summary.iloc[0]["last_halt_time"]) >= pd.Timestamp("2026-06-30")
        ),
        "equ_inst_sstate": str(state_row["last_effective_date"]) >= "2026-06-30",
        "mkt_adjf": (str(corporate_action_summary.iloc[0]["last_ex_div_date"]) >= "2026-06-30"),
    }
    unique_operational_keys = bool(
        security_duplicate_keys.empty
        and limit_duplicate_keys.empty
        and corporate_action_duplicate_keys.empty
    )
    status = (
        "AUXILIARY_SOURCE_CANDIDATES_SUPPORTED"
        if (
            required_tables_present
            and conservative_state_clock_supported
            and all(current_coverage.values())
            and unique_operational_keys
        )
        else "NEEDS_EVIDENCE"
    )
    result = {
        "schema_version": "qlib_peerlite_auxiliary_source_verify_v2",
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "mode": "VERIFY",
        "target_claim": "MARKET_RECONSTRUCTIBLE",
        "status": status,
        "positive_ceiling": "SOURCE_CANDIDATES_ONLY_NEVER_PIT_PASS",
        "checks": {
            "all_required_tables_present": required_tables_present,
            "special_state_conservative_availability_supported": (
                conservative_state_clock_supported
            ),
            "coverage_through_final_oos": current_coverage,
            "unique_operational_keys": unique_operational_keys,
            "xshg_xshe_calendar_mismatch_count_capped": len(calendar_mismatches),
        },
        "columns": records(columns),
        "security_summary": records(security_summary),
        "security_duplicate_keys": records(security_duplicate_keys),
        "calendar_summary": records(calendar_summary),
        "calendar_mismatches_capped": records(calendar_mismatches),
        "limit_summary": records(limit_summary),
        "limit_duplicate_keys": records(limit_duplicate_keys),
        "halt_summary": records(halt_summary),
        "special_state_summary": records(special_state_summary),
        "special_state_clock_anomalies": records(special_state_clock_anomalies),
        "special_state_values": records(special_state_values),
        "special_state_samples": records(special_state_samples),
        "corporate_action_summary": records(corporate_action_summary),
        "corporate_action_duplicate_keys": records(corporate_action_duplicate_keys),
        "interpretation_limits": [
            "The result selects source candidates and checks clocks/coverage only.",
            "Portfolio execution may use realized halt and limit state at "
            "execution time; signal construction may not read future execution state.",
            "Special status becomes eligible at max(PUBLISH_DATE, EFF_DATE); "
            "a research-period row missing PUBLISH_DATE is unknown and excluded.",
            "mkt_adjf is permitted only to locate ex-dividend event dates for "
            "masking; cumulative adjustment factors are forbidden model inputs.",
            "A fixed source snapshot and full PIT plus behavior audits remain mandatory.",
        ],
    }
    output_path = args.output_dir / "auxiliary_source_verify.json"
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
    return 0 if status == "AUXILIARY_SOURCE_CANDIDATES_SUPPORTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
