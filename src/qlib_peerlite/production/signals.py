from __future__ import annotations

import io
import math
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq

from qlib_peerlite.governance.artifacts import sha256_bytes

from .errors import ProductionError
from .policy import ShadowPolicy
from .schedule import ScheduleDecision

SHANGHAI = ZoneInfo("Asia/Shanghai")
SCORE_COLUMNS = ["datetime", "instrument", "score", "model_id", "fold_id"]
SYNTHETIC_ID = re.compile(r"^SYNTH_[A-Z0-9]{1,24}$")


@dataclass(frozen=True)
class PredictionSnapshot:
    payload: bytes
    sha256: str
    row_count: int


def capture_prediction(path: str | Path, policy: ShadowPolicy) -> PredictionSnapshot:
    source = Path(path)
    if source.is_symlink():
        raise ProductionError("UNSAFE_INPUT_PATH", "prediction input cannot be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise ProductionError("UNSAFE_INPUT_PATH", "prediction input cannot be opened") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ProductionError("UNSAFE_INPUT_PATH", "prediction input must be regular")
        if info.st_size > policy.max_input_bytes:
            raise ProductionError("INPUT_TOO_LARGE", "prediction input exceeds byte limit")
        payload = b""
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, policy.max_input_bytes + 1))
            if not chunk:
                break
            payload += chunk
            if len(payload) > policy.max_input_bytes:
                raise ProductionError("INPUT_TOO_LARGE", "prediction input exceeds byte limit")
    finally:
        os.close(descriptor)
    try:
        parquet = pq.ParquetFile(io.BytesIO(payload))
    except Exception as exc:
        raise ProductionError("INVALID_PARQUET", "prediction input is not valid Parquet") from exc
    row_count = parquet.metadata.num_rows
    if row_count > policy.max_rows:
        raise ProductionError("TOO_MANY_ROWS", "prediction input exceeds row limit")
    if parquet.schema_arrow.names != SCORE_COLUMNS:
        raise ProductionError("SCORE_SCHEMA_MISMATCH", "prediction columns/order differ")
    return PredictionSnapshot(payload, sha256_bytes(payload), row_count)


def validate_source_manifest(
    manifest: dict[str, Any],
    snapshot: PredictionSnapshot,
    policy: ShadowPolicy,
) -> None:
    required = {
        "schema_version",
        "score_schema_version",
        "track",
        "predictions_sha256",
        "row_count",
        "model_id",
        "signal_date",
        "prediction_time",
    }
    if set(manifest) != required:
        raise ProductionError("SOURCE_MANIFEST_INVALID", "source manifest schema differs")
    valid = (
        manifest["schema_version"] == "qlib_peerlite_score_source_v1"
        and manifest["score_schema_version"] == "qlib_peerlite_score_v1"
        and manifest["track"] == policy.input_track
        and manifest["predictions_sha256"] == snapshot.sha256
        and manifest["row_count"] == snapshot.row_count
        and manifest["model_id"] in policy.permitted_model_ids
    )
    if not valid:
        raise ProductionError("SOURCE_MANIFEST_MISMATCH", "source manifest does not bind input")


def _parse_prediction_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ProductionError("PREDICTION_TIME_INVALID", "prediction_time must be text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProductionError("PREDICTION_TIME_INVALID", "prediction_time is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductionError("PREDICTION_TIME_INVALID", "prediction_time must be timezone-aware")
    return parsed.astimezone(SHANGHAI)


def validate_signal_frame(
    snapshot: PredictionSnapshot,
    manifest: dict[str, Any],
    policy: ShadowPolicy,
    schedule: ScheduleDecision,
    as_of: datetime,
) -> pd.DataFrame:
    try:
        frame = pd.read_parquet(io.BytesIO(snapshot.payload))
    except Exception as exc:
        raise ProductionError("INVALID_PARQUET", "prediction table cannot be materialized") from exc
    dates = pd.to_datetime(frame["datetime"], errors="coerce")
    if dates.isna().any():
        raise ProductionError("SIGNAL_DATE_INVALID", "signal datetime contains invalid values")
    unique_dates = sorted({value.date().isoformat() for value in dates})
    if len(unique_dates) != 1:
        raise ProductionError("MULTIPLE_SIGNAL_DATES", "one cycle requires one cross-section")
    if unique_dates[0] != schedule.session_date or manifest["signal_date"] != schedule.session_date:
        raise ProductionError("SIGNAL_SESSION_MISMATCH", "signal date differs from due session")
    prediction_time = _parse_prediction_time(manifest["prediction_time"])
    close_hour, close_minute = (int(piece) for piece in policy.session_close.split(":"))
    session_close = datetime.combine(
        prediction_time.date(),
        datetime.min.time().replace(hour=close_hour, minute=close_minute),
        SHANGHAI,
    )
    local_as_of = as_of.astimezone(SHANGHAI)
    if (
        prediction_time.date().isoformat() != schedule.session_date
        or prediction_time < session_close
    ):
        raise ProductionError("PREDICTION_TIME_INVALID", "prediction time precedes session close")
    if prediction_time > local_as_of + timedelta(seconds=policy.future_skew_seconds):
        raise ProductionError("FUTURE_SIGNAL", "prediction time is beyond allowed future skew")
    if local_as_of - prediction_time > timedelta(minutes=policy.max_signal_age_minutes):
        raise ProductionError("STALE_SIGNAL", "prediction time exceeds freshness limit")
    if frame.duplicated(["datetime", "instrument"]).any():
        raise ProductionError("DUPLICATE_SIGNAL_KEY", "signal keys must be unique")
    if any(not SYNTHETIC_ID.fullmatch(str(value)) for value in frame["instrument"]):
        raise ProductionError(
            "NON_SYNTHETIC_INSTRUMENT",
            "instrument is outside synthetic namespace",
        )
    if frame["instrument"].nunique() > policy.max_instruments:
        raise ProductionError("TOO_MANY_INSTRUMENTS", "instrument count exceeds limit")
    scores = pd.to_numeric(frame["score"], errors="coerce")
    if any(not math.isfinite(float(value)) for value in scores):
        raise ProductionError("NONFINITE_SCORE", "scores must be finite")
    model_ids = set(frame["model_id"].astype(str))
    if model_ids != {manifest["model_id"]}:
        raise ProductionError("MODEL_ID_MISMATCH", "row model IDs differ from manifest")
    return frame.loc[:, SCORE_COLUMNS].copy()
