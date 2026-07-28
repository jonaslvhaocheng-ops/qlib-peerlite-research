#!/usr/bin/env python3
"""Build the pre-final-OOS Qlib PeerLite data product from a sealed snapshot.

This command is deliberately restricted to the TRAIN and MODEL_SELECTION
periods.  It never opens the 2025/2026 market-data partitions and it emits no
performance metric.  The result remains unqualified until the fixed and
behavior PIT audits pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from qlib_peerlite.data.features import FEATURE_COLUMNS, build_causal_daily_features

TZ = ZoneInfo("Asia/Shanghai")
SOURCE_BUNDLE_SHA256 = "2575e52c7375fe28c06ccc6305da34e3328f025e7397ae735264f06cf62dc040"
UNIVERSE_HASH = "4c4fde609a8ee6cf21fdc40114f368fdbb5a102d661d6c630e223a785b7dee97"
CSI300_ID = 1782
CSI500_ID = 2103
PREDICTION_END_EXCLUSIVE = pd.Timestamp("2025-01-01")
RESEARCH_START = pd.Timestamp("2012-01-01")
SELECTION_START = pd.Timestamp("2024-01-01")
EMBARGO_SESSIONS = 5
RAW_START_YEAR = 2011
RAW_END_YEAR = 2024


def sha256_file(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def local_timestamp(date: pd.Series | pd.DatetimeIndex, clock: str) -> pd.Series:
    series = date if isinstance(date, pd.Series) else pd.Series(date)
    values = pd.to_datetime(series).dt.strftime("%Y-%m-%d") + f" {clock}"
    return pd.to_datetime(values).dt.tz_localize(TZ)


def verify_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    bundle_path = snapshot_dir / "snapshot_bundle_manifest.json"
    if sha256_file(bundle_path) != SOURCE_BUNDLE_SHA256:
        raise RuntimeError("source snapshot bundle hash does not match frozen contract")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if bundle.get("universe", {}).get("universe_hash") != UNIVERSE_HASH:
        raise RuntimeError("source snapshot universe hash does not match frozen contract")
    if bundle.get("status") != "SEALED_NOT_PIT_QUALIFIED":
        raise RuntimeError("unexpected source snapshot status")

    verified: dict[str, Any] = {}
    for source_id, binding in bundle["sources"].items():
        manifest_path = snapshot_dir / binding["manifest"]
        actual_manifest_hash = sha256_file(manifest_path)
        if actual_manifest_hash != binding["manifest_sha256"]:
            raise RuntimeError(f"manifest hash mismatch: {manifest_path.name}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            path = snapshot_dir / item["path"]
            if not path.is_file():
                raise RuntimeError(f"missing source file: {path.name}")
            if sha256_file(path) != item["sha256"]:
                raise RuntimeError(f"source file hash mismatch: {path.name}")
        verified[source_id] = {
            "manifest": binding["manifest"],
            "manifest_sha256": actual_manifest_hash,
        }
    return verified


def read_year_partitions(
    snapshot_dir: Path,
    stem: str,
    columns: list[str],
    *,
    start_year: int = RAW_START_YEAR,
    end_year: int = RAW_END_YEAR,
) -> pd.DataFrame:
    paths = [snapshot_dir / f"{stem}_{year}.parquet" for year in range(start_year, end_year + 1)]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing pre-OOS partitions: {missing}")
    # The explicit path list is the OOS seal: 2025/2026 files are never opened.
    return pd.concat(
        [pd.read_parquet(path, columns=columns) for path in paths],
        ignore_index=True,
        copy=False,
    )


def eligible_calendar(snapshot_dir: Path) -> pd.DatetimeIndex:
    calendar = pd.read_parquet(
        snapshot_dir / "md_trade_cal.parquet",
        columns=["calendar_date", "exchange_cd", "is_open"],
        filters=[("calendar_date", "<", date(2025, 1, 1))],
    )
    calendar["calendar_date"] = parse_date(calendar["calendar_date"])
    selected = calendar[
        calendar["exchange_cd"].isin(["XSHG", "XSHE"])
        & (calendar["is_open"] == 1)
        & (calendar["calendar_date"] < PREDICTION_END_EXCLUSIVE)
    ]
    by_exchange = {
        exchange: set(group["calendar_date"]) for exchange, group in selected.groupby("exchange_cd")
    }
    if by_exchange.get("XSHG") != by_exchange.get("XSHE"):
        raise RuntimeError("XSHG and XSHE eligible calendars differ")
    return pd.DatetimeIndex(sorted(by_exchange["XSHG"]))


def filter_asof_rows(
    path: Path,
    *,
    columns: list[str],
    date_column: str,
) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=columns)
    frame[date_column] = parse_date(frame[date_column])
    return frame[frame[date_column] < PREDICTION_END_EXCLUSIVE].copy()


def build_membership_lookup(
    snapshot_dir: Path,
) -> tuple[dict[int, list[tuple[np.datetime64, np.datetime64, np.datetime64]]], set[int]]:
    frame = pd.read_parquet(
        snapshot_dir / "idx_cons_core.parquet",
        columns=[
            "security_id",
            "cons_id",
            "into_pub_date",
            "into_eff_date",
            "out_pub_date",
            "out_eff_date",
        ],
    )
    frame = frame[frame["security_id"].isin([CSI300_ID, CSI500_ID])].copy()
    for column in ("into_pub_date", "into_eff_date", "out_pub_date", "out_eff_date"):
        frame[column] = parse_date(frame[column])
    frame = frame[
        frame["into_pub_date"].notna()
        & frame["into_eff_date"].notna()
        & (frame["into_pub_date"] < PREDICTION_END_EXCLUSIVE)
        & (frame["into_eff_date"] < PREDICTION_END_EXCLUSIVE)
    ]
    intervals: dict[int, list[tuple[np.datetime64, np.datetime64, np.datetime64]]] = defaultdict(
        list
    )
    for row in frame.itertuples(index=False):
        end = row.out_eff_date
        # A removal announced in the final OOS is not eligible in development.
        if pd.isna(row.out_pub_date) or row.out_pub_date >= PREDICTION_END_EXCLUSIVE:
            end = pd.NaT
        end_value = np.datetime64("2262-04-11") if pd.isna(end) else np.datetime64(end)
        intervals[int(row.cons_id)].append(
            (
                np.datetime64(row.into_pub_date),
                np.datetime64(row.into_eff_date),
                end_value,
            )
        )
    for security_id in intervals:
        intervals[security_id].sort(key=lambda item: (item[1], item[0]))
    return dict(intervals), set(intervals)


def attach_membership(
    raw: pd.DataFrame,
    intervals: dict[int, list[tuple[np.datetime64, np.datetime64, np.datetime64]]],
) -> pd.DataFrame:
    eligible = np.zeros(len(raw), dtype=bool)
    announced = np.full(len(raw), np.datetime64("NaT"), dtype="datetime64[ns]")
    effective_from = np.full(len(raw), np.datetime64("NaT"), dtype="datetime64[ns]")
    effective_to = np.full(len(raw), np.datetime64("NaT"), dtype="datetime64[ns]")

    for security_id, positions in raw.groupby("security_id", sort=False).indices.items():
        candidates = intervals.get(int(security_id), [])
        if not candidates:
            continue
        index = np.asarray(positions, dtype=np.int64)
        dates = raw.loc[index, "trade_date"].to_numpy(dtype="datetime64[ns]")
        chosen_start = np.full(len(index), np.datetime64("NaT"), dtype="datetime64[ns]")
        for pub, start, end in candidates:
            mask = (dates >= pub) & (dates >= start) & (dates < end)
            replace = mask & (np.isnat(chosen_start) | (start >= chosen_start))
            if not replace.any():
                continue
            chosen_start[replace] = start
            eligible[index[replace]] = True
            announced[index[replace]] = pub
            effective_from[index[replace]] = start
            if end < np.datetime64("2262-04-11"):
                effective_to[index[replace]] = end

    raw["universe_member"] = eligible
    raw["universe_announced_date"] = announced
    raw["universe_effective_from_date"] = effective_from
    raw["universe_effective_to_date"] = effective_to
    return raw


def security_master(snapshot_dir: Path, security_ids: set[int]) -> pd.DataFrame:
    frame = pd.read_parquet(
        snapshot_dir / "md_security.parquet",
        columns=[
            "security_id",
            "ticker_symbol",
            "exchange_cd",
            "asset_class",
            "list_date",
            "delist_date",
        ],
    )
    frame = frame[
        frame["security_id"].isin(security_ids)
        & frame["exchange_cd"].isin(["XSHG", "XSHE"])
        & (frame["asset_class"] == "E")
    ].copy()
    frame["list_date"] = parse_date(frame["list_date"])
    frame["delist_date"] = parse_date(frame["delist_date"])
    if frame["security_id"].duplicated().any():
        raise RuntimeError("security master has duplicate permanent IDs")
    return frame


def listing_eligibility_date(
    list_date: pd.Timestamp, calendar: pd.DatetimeIndex, minimum_sessions: int = 60
) -> pd.Timestamp:
    start = int(calendar.searchsorted(list_date, side="left"))
    target = start + minimum_sessions - 1
    if target >= len(calendar):
        return pd.NaT
    return pd.Timestamp(calendar[target])


def attach_special_status(snapshot_dir: Path, raw: pd.DataFrame) -> pd.DataFrame:
    status = pd.read_parquet(
        snapshot_dir / "equ_inst_sstate.parquet",
        columns=[
            "security_id",
            "sec_short_name",
            "party_state",
            "publish_date",
            "eff_date",
        ],
    )
    status["publish_date"] = parse_date(status["publish_date"])
    status["eff_date"] = parse_date(status["eff_date"])
    status = status[
        status["eff_date"].notna() & (status["eff_date"] < PREDICTION_END_EXCLUSIVE)
    ].copy()
    status["known_date"] = status[["publish_date", "eff_date"]].max(axis=1)
    status.loc[status["publish_date"].isna(), "known_date"] = pd.NaT
    status["is_forbidden"] = (
        status["sec_short_name"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.contains(r"(?:^|\*)ST|PT|退", regex=True)
    )

    forbidden = np.zeros(len(raw), dtype=bool)
    unknown = np.zeros(len(raw), dtype=bool)
    for security_id, positions in raw.groupby("security_id", sort=False).indices.items():
        events = status[status["security_id"] == security_id].sort_values(
            ["known_date", "eff_date"], na_position="last"
        )
        if events.empty:
            continue
        index = np.asarray(positions, dtype=np.int64)
        dates = raw.loc[index, "trade_date"].to_numpy(dtype="datetime64[ns]")
        valid = events[events["known_date"].notna()]
        if not valid.empty:
            known = valid["known_date"].to_numpy(dtype="datetime64[ns]")
            loc = np.searchsorted(known, dates, side="right") - 1
            has = loc >= 0
            values = valid["is_forbidden"].to_numpy(dtype=bool)
            forbidden[index[has]] = values[loc[has]]
        missing = events[events["known_date"].isna()]
        for event in missing.itertuples(index=False):
            unknown[index[dates >= np.datetime64(event.eff_date)]] = True
    raw["special_status_forbidden"] = forbidden
    raw["special_status_unknown"] = unknown
    return raw


def corporate_action_dates(snapshot_dir: Path, security_ids: set[int]) -> pd.DataFrame:
    actions = filter_asof_rows(
        snapshot_dir / "mkt_adjf.parquet",
        columns=["security_id", "ex_div_date"],
        date_column="ex_div_date",
    )
    actions = actions[actions["security_id"].isin(security_ids)].drop_duplicates()
    return actions


def attach_corporate_action(raw: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    keys = pd.MultiIndex.from_frame(actions[["security_id", "ex_div_date"]])
    raw_keys = pd.MultiIndex.from_frame(
        raw[["security_id", "trade_date"]].rename(columns={"trade_date": "ex_div_date"})
    )
    raw["corporate_action"] = raw_keys.isin(keys)
    return raw


def add_label_schedule(raw: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    positions = calendar.searchsorted(raw["trade_date"].to_numpy(dtype="datetime64[ns]"))
    exact = (positions < len(calendar)) & (
        calendar.to_numpy(dtype="datetime64[ns]")[np.minimum(positions, len(calendar) - 1)]
        == raw["trade_date"].to_numpy(dtype="datetime64[ns]")
    )
    next_one = positions + 1
    next_five = positions + 5
    valid = exact & (next_five < len(calendar))
    raw["label_start_date"] = pd.NaT
    raw["label_end_date"] = pd.NaT
    raw.loc[valid, "label_start_date"] = calendar[next_one[valid]].to_numpy()
    raw.loc[valid, "label_end_date"] = calendar[next_five[valid]].to_numpy()
    return raw


def attach_labels(raw: pd.DataFrame) -> pd.DataFrame:
    prices = raw[["security_id", "trade_date", "open", "close"]].copy()
    start = prices.rename(
        columns={
            "trade_date": "label_start_date",
            "open": "label_open",
            "close": "_unused_start_close",
        }
    )[["security_id", "label_start_date", "label_open"]]
    end = prices.rename(
        columns={
            "trade_date": "label_end_date",
            "close": "label_close",
            "open": "_unused_end_open",
        }
    )[["security_id", "label_end_date", "label_close"]]
    raw = raw.merge(start, how="left", on=["security_id", "label_start_date"], validate="m:1")
    raw = raw.merge(end, how="left", on=["security_id", "label_end_date"], validate="m:1")
    raw["label"] = raw["label_close"] / raw["label_open"] - 1.0
    return raw


def attach_open_limit_state(snapshot_dir: Path, raw: pd.DataFrame) -> pd.DataFrame:
    limits = read_year_partitions(
        snapshot_dir,
        "mkt_limit",
        ["security_id", "trade_date", "limit_up_price", "limit_down_price"],
    )
    limits["trade_date"] = parse_date(limits["trade_date"])
    wanted = set(raw["security_id"].unique())
    limits = limits[limits["security_id"].isin(wanted)].rename(
        columns={"trade_date": "label_start_date"}
    )
    raw = raw.merge(
        limits,
        how="left",
        on=["security_id", "label_start_date"],
        validate="m:1",
    )
    tolerance = 1e-8
    raw["execution_at_limit"] = np.isclose(
        raw["label_open"], raw["limit_up_price"], rtol=0, atol=tolerance
    ) | np.isclose(raw["label_open"], raw["limit_down_price"], rtol=0, atol=tolerance)
    return raw


def halt_intervals(snapshot_dir: Path, security_ids: set[int]) -> dict[int, list[tuple[int, int]]]:
    halts = pd.read_parquet(
        snapshot_dir / "md_sec_halt.parquet",
        columns=["security_id", "halt_begin_time", "resump_begin_time"],
    )
    halts = halts[halts["security_id"].isin(security_ids)].copy()
    cutoff = pd.Timestamp("2025-01-01", tz=TZ)
    for column in ("halt_begin_time", "resump_begin_time"):
        values = pd.to_datetime(halts[column], errors="coerce")
        if values.dt.tz is None:
            values = values.dt.tz_localize(TZ)
        else:
            values = values.dt.tz_convert(TZ)
        halts[column] = values
    halts = halts[halts["halt_begin_time"].notna() & (halts["halt_begin_time"] < cutoff)]
    result: dict[int, list[tuple[int, int]]] = defaultdict(list)
    maximum = pd.Timestamp.max.tz_localize("UTC").value
    for row in halts.itertuples(index=False):
        end = (
            maximum
            if pd.isna(row.resump_begin_time)
            else row.resump_begin_time.tz_convert("UTC").value
        )
        result[int(row.security_id)].append((row.halt_begin_time.tz_convert("UTC").value, end))
    return dict(result)


def attach_execution_halt(
    raw: pd.DataFrame, intervals: dict[int, list[tuple[int, int]]]
) -> pd.DataFrame:
    execution = local_timestamp(raw["label_start_date"], "09:30:00")
    execution_ns = execution.dt.tz_convert("UTC").astype("int64").to_numpy()
    blocked = np.zeros(len(raw), dtype=bool)
    halt_time = np.full(len(raw), np.datetime64("NaT"), dtype="datetime64[ns]")
    resume_time = np.full(len(raw), np.datetime64("NaT"), dtype="datetime64[ns]")
    for security_id, positions in raw.groupby("security_id", sort=False).indices.items():
        candidates = intervals.get(int(security_id), [])
        if not candidates:
            continue
        index = np.asarray(positions, dtype=np.int64)
        stamps = execution_ns[index]
        for start, end in candidates:
            mask = (stamps >= start) & (stamps < end)
            if mask.any():
                blocked[index[mask]] = True
                halt_time[index[mask]] = np.datetime64(start, "ns")
                if end < pd.Timestamp.max.tz_localize("UTC").value:
                    resume_time[index[mask]] = np.datetime64(end, "ns")
    raw["execution_halted"] = blocked
    raw["halt_time_utc"] = halt_time
    raw["resume_time_utc"] = resume_time
    return raw


def action_crosses_labels(raw: pd.DataFrame, actions: pd.DataFrame) -> np.ndarray:
    by_security = {
        int(security_id): group["ex_div_date"].sort_values().to_numpy(dtype="datetime64[ns]")
        for security_id, group in actions.groupby("security_id", sort=False)
    }
    crosses = np.zeros(len(raw), dtype=bool)
    for security_id, positions in raw.groupby("security_id", sort=False).indices.items():
        dates = by_security.get(int(security_id))
        if dates is None or len(dates) == 0:
            continue
        index = np.asarray(positions, dtype=np.int64)
        starts = raw.loc[index, "label_start_date"].to_numpy(dtype="datetime64[ns]")
        ends = raw.loc[index, "label_end_date"].to_numpy(dtype="datetime64[ns]")
        left = np.searchsorted(dates, starts, side="left")
        right = np.searchsorted(dates, ends, side="right")
        crosses[index] = right > left
    return crosses


def build_matrix(snapshot_dir: Path) -> tuple[pd.DataFrame, dict[str, int], pd.DatetimeIndex]:
    calendar = eligible_calendar(snapshot_dir)
    intervals, security_ids = build_membership_lookup(snapshot_dir)
    master = security_master(snapshot_dir, security_ids)
    security_ids &= set(master["security_id"].astype(int))

    raw = read_year_partitions(
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
        raw["security_id"].isin(security_ids) & raw["exchange_cd"].isin(["XSHG", "XSHE"])
    ].copy()
    raw["trade_date"] = parse_date(raw["trade_date"])
    raw = raw[raw["trade_date"] < PREDICTION_END_EXCLUSIVE]
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
        raise RuntimeError("raw quotes have duplicate permanent-ID/date keys")

    raw = attach_membership(raw, intervals)
    raw = raw.merge(
        master[["security_id", "list_date", "delist_date"]],
        how="left",
        on="security_id",
        validate="m:1",
    )
    eligible_dates = {
        int(row.security_id): listing_eligibility_date(row.list_date, calendar)
        for row in master.itertuples(index=False)
    }
    raw["listing_eligible_date"] = raw["security_id"].map(eligible_dates)
    raw["listing_age_eligible"] = raw["trade_date"] >= raw["listing_eligible_date"]
    raw = attach_special_status(snapshot_dir, raw)
    actions = corporate_action_dates(snapshot_dir, security_ids)
    raw = attach_corporate_action(raw, actions)
    raw = add_label_schedule(raw, calendar)
    raw = attach_labels(raw)
    raw = attach_open_limit_state(snapshot_dir, raw)
    raw = attach_execution_halt(raw, halt_intervals(snapshot_dir, security_ids))
    raw["label_crosses_action"] = action_crosses_labels(raw, actions)

    # The feature builder sorts the panel index.  Align the source frame to the
    # same canonical order before joining by position.
    raw = raw.sort_values(["trade_date", "security_id"], ignore_index=True)
    panel = raw.set_index(["trade_date", "security_id"]).rename_axis(["datetime", "instrument"])
    features = build_causal_daily_features(panel)
    raw = raw.join(features.reset_index(drop=True))

    selection_sessions = calendar[
        (calendar >= SELECTION_START) & (calendar < PREDICTION_END_EXCLUSIVE)
    ]
    if len(selection_sessions) <= EMBARGO_SESSIONS * 2:
        raise RuntimeError("selection calendar is incomplete")
    selection_effective_start = selection_sessions[EMBARGO_SESSIONS]
    selection_latest_label_end = selection_sessions[-(EMBARGO_SESSIONS + 1)]
    raw["split"] = np.where(
        raw["trade_date"] < SELECTION_START,
        "TRAIN",
        np.where(raw["trade_date"] >= selection_effective_start, "MODEL_SELECTION", "UNASSIGNED"),
    )

    finite_features = np.isfinite(raw[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)).all(axis=1)
    raw["finite_features"] = finite_features
    raw["finite_label"] = np.isfinite(raw["label"].to_numpy(dtype=np.float64))
    raw["price_domain_valid"] = (
        (raw[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (raw["volume"] >= 0)
        & (raw["amount"] >= 0)
    )
    raw["label_interval_in_split"] = np.where(
        raw["split"] == "TRAIN",
        raw["label_end_date"] < SELECTION_START,
        np.where(
            raw["split"] == "MODEL_SELECTION",
            raw["label_end_date"] <= selection_latest_label_end,
            False,
        ),
    )

    reason_masks = {
        "before_research_start": raw["trade_date"] < RESEARCH_START,
        "outside_pit_universe": ~raw["universe_member"],
        "listing_age_lt_60_sessions": ~raw["listing_age_eligible"],
        "special_status_forbidden": raw["special_status_forbidden"],
        "special_status_unknown": raw["special_status_unknown"],
        "feature_action_mask": ~raw["feature_eligible"],
        "missing_or_nonfinite_features": ~raw["finite_features"],
        "missing_or_nonfinite_label": ~raw["finite_label"],
        "invalid_raw_price_domain": ~raw["price_domain_valid"],
        "execution_at_price_limit": raw["execution_at_limit"],
        "execution_halted": raw["execution_halted"],
        "label_crosses_corporate_action": raw["label_crosses_action"],
        "purge_or_embargo": ~raw["label_interval_in_split"],
        "unassigned_split": raw["split"] == "UNASSIGNED",
    }
    include = np.ones(len(raw), dtype=bool)
    exclusion_counts: Counter[str] = Counter()
    for reason, mask in reason_masks.items():
        newly_excluded = include & mask.to_numpy(dtype=bool)
        exclusion_counts[reason] = int(newly_excluded.sum())
        include &= ~mask.to_numpy(dtype=bool)

    selected = raw.loc[include].copy()
    selected["datetime"] = selected["trade_date"]
    selected["instrument"] = selected["security_id"].astype(str)
    selected["prediction_time"] = local_timestamp(selected["trade_date"], "16:00:00")
    selected["event_time"] = local_timestamp(selected["trade_date"], "15:00:00")
    selected["published_time"] = local_timestamp(selected["trade_date"], "15:15:00")
    selected["vendor_available_time"] = selected["published_time"]
    selected["tradable_time"] = local_timestamp(selected["label_start_date"], "09:30:00")
    selected["label_start_time"] = selected["tradable_time"]
    selected["label_end_time"] = local_timestamp(selected["label_end_date"], "15:00:00")
    selected["universe_announced_time"] = local_timestamp(
        selected["universe_announced_date"], "23:59:59"
    )
    selected["universe_effective_from"] = local_timestamp(
        selected["universe_effective_from_date"], "00:00:00"
    )
    selected["universe_effective_to"] = pd.Series(
        pd.NaT,
        index=selected.index,
        dtype="datetime64[ns, Asia/Shanghai]",
    )
    has_end = selected["universe_effective_to_date"].notna()
    selected.loc[has_end, "universe_effective_to"] = local_timestamp(
        selected.loc[has_end, "universe_effective_to_date"], "00:00:00"
    )
    selected["identifier_valid_from"] = local_timestamp(selected["list_date"], "00:00:00")
    selected["identifier_valid_to"] = pd.Series(
        pd.NaT,
        index=selected.index,
        dtype="datetime64[ns, Asia/Shanghai]",
    )
    delisted_before_prediction = selected["delist_date"].notna() & (
        selected["delist_date"] <= selected["trade_date"]
    )
    if delisted_before_prediction.any():
        raise RuntimeError("eligible matrix unexpectedly contains already-delisted rows")

    metadata_columns = [
        "datetime",
        "instrument",
        "security_id",
        "ticker_symbol",
        "exchange_cd",
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
        "label",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover",
        "label_open",
        "label_close",
        "limit_up_price",
        "limit_down_price",
    ]
    selected = selected[metadata_columns + list(FEATURE_COLUMNS)].sort_values(
        ["datetime", "instrument"], ignore_index=True
    )
    if selected.duplicated(["datetime", "instrument"]).any():
        raise RuntimeError("final matrix key is not unique")
    if len(FEATURE_COLUMNS) != 50:
        raise RuntimeError("frozen feature count is not 50")
    return selected, dict(exclusion_counts), calendar


def calendar_rows(calendar: pd.DatetimeIndex) -> pd.DataFrame:
    frame = pd.DataFrame({"session_id": "XSHG_XSHE-" + calendar.strftime("%Y-%m-%d")})
    frame["open_time"] = local_timestamp(pd.Series(calendar), "09:30:00")
    frame["close_time"] = local_timestamp(pd.Series(calendar), "15:00:00")
    frame["break_start"] = local_timestamp(pd.Series(calendar), "11:30:00")
    frame["break_end"] = local_timestamp(pd.Series(calendar), "13:00:00")
    return frame


def publish_product(
    output_dir: Path,
    matrix: pd.DataFrame,
    exclusions: dict[str, int],
    calendar: pd.DatetimeIndex,
    source_bindings: dict[str, Any],
    snapshot_dir: Path,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("output directory must be new or empty")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        matrix_dir = temporary / "matrix"
        matrix_dir.mkdir()
        files: list[dict[str, Any]] = []
        for year, group in matrix.groupby(matrix["datetime"].dt.year, sort=True):
            path = matrix_dir / f"matrix_{int(year)}.parquet"
            group.to_parquet(path, index=False, compression="zstd")
            files.append(
                {
                    "path": str(path.relative_to(temporary)),
                    "year": int(year),
                    "rows": int(len(group)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

        population = matrix[
            [
                "security_id",
                "prediction_time",
                "split",
                "universe_announced_time",
                "universe_effective_from",
                "universe_effective_to",
                "identifier_valid_from",
                "identifier_valid_to",
                "label_start_time",
                "label_end_time",
            ]
        ].copy()
        population_path = temporary / "population.parquet"
        population.to_parquet(population_path, index=False, compression="zstd")

        calendar_path = temporary / "calendar.csv"
        calendar_rows(calendar).to_csv(calendar_path, index=False, lineterminator="\n")

        exclusions_path = temporary / "exclusion_counts.json"
        write_json(
            exclusions_path,
            {
                "schema_version": "qlib_peerlite_exclusion_counts_v1",
                "ordering_rule": "first failing reason in frozen order",
                "counts": exclusions,
                "included_rows": int(len(matrix)),
            },
        )

        code_path = Path(__file__).resolve()
        parameters = {
            "research_start": str(RESEARCH_START.date()),
            "selection_nominal_boundary": str(SELECTION_START.date()),
            "selection_effective_start": str(
                matrix.loc[matrix["split"] == "MODEL_SELECTION", "datetime"].min().date()
            ),
            "train_effective_end": str(
                matrix.loc[matrix["split"] == "TRAIN", "datetime"].max().date()
            ),
            "selection_effective_end": str(
                matrix.loc[matrix["split"] == "MODEL_SELECTION", "datetime"].max().date()
            ),
            "selection_latest_label_end": str(
                matrix.loc[matrix["split"] == "MODEL_SELECTION", "label_end_time"].max().date()
            ),
            "embargo_sessions": EMBARGO_SESSIONS,
            "development_end_exclusive": str(PREDICTION_END_EXCLUSIVE.date()),
            "raw_partition_years": [RAW_START_YEAR, RAW_END_YEAR],
            "minimum_listing_sessions": 60,
            "prediction_clock": "16:00:00 Asia/Shanghai",
            "vendor_available_clock": "15:15:00 Asia/Shanghai",
            "feature_windows": [5, 10, 20, 60],
            "feature_count": len(FEATURE_COLUMNS),
            "source_snapshot": snapshot_dir.name,
        }
        manifest = {
            "schema_version": "qlib_peerlite_pit_data_product_v1",
            "product_id": output_dir.name,
            "created_at": datetime.now(TZ).isoformat(),
            "status": "BUILT_NOT_PIT_QUALIFIED",
            "contract_id": "qrc-v2-0e4027198e7c052673bc12c0b10e67e5",
            "parent_contract_file_sha256": (
                "dc6a34e7fa03891a9767d9c39ef2307398e91666a9049fa7809a20e3b6692fa2"
            ),
            "source_snapshot": {
                "snapshot_id": snapshot_dir.name,
                "bundle_sha256": SOURCE_BUNDLE_SHA256,
                "universe_hash": UNIVERSE_HASH,
                "sources": source_bindings,
            },
            "oos_seal": {
                "final_oos_start": "2025-01-01",
                "opened_market_partitions": [RAW_START_YEAR, RAW_END_YEAR],
                "final_oos_market_partitions_opened": False,
                "performance_metrics_computed": False,
            },
            "builder": {
                "path": "scripts/server/build_pit_data_product.py",
                "sha256": sha256_file(code_path),
                "parameters": parameters,
                "parameters_sha256": canonical_json_sha256(parameters),
            },
            "matrix": {
                "key": ["datetime", "instrument"],
                "features": list(FEATURE_COLUMNS),
                "feature_count": len(FEATURE_COLUMNS),
                "label": "label",
                "rows": int(len(matrix)),
                "date_min": str(matrix["datetime"].min().date()),
                "date_max": str(matrix["datetime"].max().date()),
                "instrument_count": int(matrix["instrument"].nunique()),
                "split_counts": {
                    key: int(value)
                    for key, value in matrix["split"].value_counts().sort_index().items()
                },
                "files": files,
            },
            "population": {
                "path": population_path.name,
                "rows": int(len(population)),
                "bytes": population_path.stat().st_size,
                "sha256": sha256_file(population_path),
            },
            "calendar": {
                "path": calendar_path.name,
                "rows": int(len(calendar)),
                "sha256": sha256_file(calendar_path),
            },
            "exclusions": {
                "path": exclusions_path.name,
                "sha256": sha256_file(exclusions_path),
            },
            "value_exposure": "COUNTS_HASHES_AND_BOUNDS_ONLY",
        }
        manifest["content_sha256"] = canonical_json_sha256(manifest)
        write_json(temporary / "data_product_manifest.json", manifest)
        for path in temporary.rglob("*"):
            if path.is_file():
                path.chmod(0o440)
        temporary.chmod(0o550)
        if output_dir.exists():
            output_dir.rmdir()
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source_bindings = verify_snapshot(args.snapshot_dir)
    matrix, exclusions, calendar = build_matrix(args.snapshot_dir)
    if matrix.empty:
        raise RuntimeError("eligible data product is empty")
    publish_product(
        args.output_dir,
        matrix,
        exclusions,
        calendar,
        source_bindings,
        args.snapshot_dir,
    )
    manifest = json.loads(
        (args.output_dir / "data_product_manifest.json").read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "product_id": manifest["product_id"],
                "rows": manifest["matrix"]["rows"],
                "date_min": manifest["matrix"]["date_min"],
                "date_max": manifest["matrix"]["date_max"],
                "final_oos_market_partitions_opened": False,
                "manifest_sha256": sha256_file(args.output_dir / "data_product_manifest.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
