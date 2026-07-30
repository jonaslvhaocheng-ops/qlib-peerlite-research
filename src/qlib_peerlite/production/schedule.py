from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .errors import ProductionError
from .policy import FileSnapshot, ShadowPolicy, capture_regular_file

SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class SessionCalendar:
    sessions: frozenset[str]
    sha256: str


@dataclass(frozen=True)
class ScheduleDecision:
    due: bool
    reason: str
    session_date: str


def load_calendar(
    policy: ShadowPolicy,
    *,
    snapshot: FileSnapshot | None = None,
) -> SessionCalendar:
    path = Path(policy.calendar_path)
    captured = snapshot or capture_regular_file(path, code="CALENDAR_MISSING")
    if captured.sha256 != policy.calendar_sha256:
        raise ProductionError("CALENDAR_HASH_MISMATCH", "calendar hash differs")
    try:
        payload: Any = json.loads(captured.payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionError("CALENDAR_INVALID", "calendar cannot be parsed") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "qlib_peerlite_session_calendar_v1"
        or payload.get("timezone") != "Asia/Shanghai"
        or not isinstance(payload.get("sessions"), list)
    ):
        raise ProductionError("CALENDAR_INVALID", "calendar schema is invalid")
    sessions = payload["sessions"]
    if not sessions or any(not isinstance(value, str) for value in sessions):
        raise ProductionError("CALENDAR_INVALID", "calendar sessions are invalid")
    try:
        parsed = [datetime.strptime(value, "%Y-%m-%d").date().isoformat() for value in sessions]
    except ValueError as exc:
        raise ProductionError("CALENDAR_INVALID", "calendar session date is invalid") from exc
    if parsed != sorted(set(parsed)):
        raise ProductionError("CALENDAR_INVALID", "calendar sessions must be unique and sorted")
    return SessionCalendar(frozenset(parsed), captured.sha256)


def _clock(value: str) -> time:
    hour, minute = (int(piece) for piece in value.split(":"))
    return time(hour, minute)


def evaluate_schedule(
    policy: ShadowPolicy,
    calendar: SessionCalendar,
    as_of: datetime,
) -> ScheduleDecision:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ProductionError("INVALID_AS_OF", "as_of must be timezone-aware")
    local = as_of.astimezone(SHANGHAI)
    session = local.date().isoformat()
    if session not in calendar.sessions:
        return ScheduleDecision(False, "NOT_SESSION", session)
    if local.weekday() != policy.rebalance_weekday:
        return ScheduleDecision(False, "NOT_REBALANCE_WEEKDAY", session)
    if local.timetz().replace(tzinfo=None) < _clock(policy.run_after):
        return ScheduleDecision(False, "BEFORE_CUTOFF", session)
    return ScheduleDecision(True, "DUE", session)
