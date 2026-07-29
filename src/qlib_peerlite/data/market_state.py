"""Pure, label-free market-state population and daily aggregation primitives.

This module deliberately accepts only a narrow T-known input schema.  It has
no file I/O, Qlib dependency or access to the M3 supervised matrix, preventing
future label/execution predicates from entering ``U_state(T)`` by accident.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterable

import numpy as np
import pandas as pd

from .schema import ensure_panel_index


class MarketStateError(ValueError):
    """Raised when a market-state product is not a complete T-known product."""


ELIGIBILITY_COLUMNS = (
    "universe_member",
    "listing_age_eligible",
    "is_active",
    "special_status_forbidden",
    "special_status_unknown",
    "price_domain_valid",
    "feature_eligible",
)
STATE_SOURCE_COLUMNS = (
    "ret_mean_20",
    "ret_std_20",
    "ret_1d",
    "turnover_mean_20",
)
STATE_INPUT_COLUMNS = (*ELIGIBILITY_COLUMNS, *STATE_SOURCE_COLUMNS)
DAILY_STATE_COLUMNS = (
    "mkt_trend_20",
    "mkt_vol_20",
    "mkt_breadth_1d",
    "mkt_turnover_20",
)
DAILY_PRODUCT_COLUMNS = (
    *DAILY_STATE_COLUMNS,
    "population_count",
    "population_keyset_sha256",
    "state_sha256",
)
_FORBIDDEN_EXACT_COLUMNS = {
    "label",
    "label_open",
    "label_close",
    "label_start",
    "label_end",
    "execution_at_price_limit",
    "execution_halted",
    "limit_up_price",
    "limit_down_price",
    "halt",
    "resume",
    "label_crosses_corporate_action",
    "purge_or_embargo",
    "split",
}
_FORBIDDEN_PREFIXES = ("label_", "execution_", "limit_", "halt_", "purge_", "split_")


def _is_forbidden_column(column: str) -> bool:
    return column in _FORBIDDEN_EXACT_COLUMNS or column.startswith(_FORBIDDEN_PREFIXES)


def _require_exact_input_columns(frame: pd.DataFrame) -> None:
    columns = set(frame.columns)
    forbidden = sorted(column for column in columns if _is_forbidden_column(str(column)))
    if forbidden:
        raise MarketStateError(f"market-state input contains forbidden fields: {forbidden}")
    missing = sorted(set(STATE_INPUT_COLUMNS).difference(columns))
    extra = sorted(columns.difference(STATE_INPUT_COLUMNS))
    if missing or extra:
        raise MarketStateError(
            f"market-state input schema mismatch; missing={missing}, unexpected={extra}"
        )


def _require_boolean_columns(frame: pd.DataFrame) -> None:
    for column in ELIGIBILITY_COLUMNS:
        values = frame[column]
        if not values.map(lambda value: isinstance(value, (bool, np.bool_))).all():
            raise MarketStateError(f"market-state eligibility column is not boolean: {column}")


def _keyset_sha256(instruments: Iterable[object]) -> str:
    digest = hashlib.sha256()
    for instrument in sorted(instruments):
        if not isinstance(instrument, str) or not instrument:
            raise MarketStateError("market-state instrument key must be a non-empty string")
        digest.update(instrument.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _state_sha256(
    date: pd.Timestamp,
    *,
    population_count: int,
    population_keyset_sha256: str,
    values: Iterable[float],
) -> str:
    if not isinstance(population_count, int) or population_count <= 0:
        raise MarketStateError("market-state population_count must be a positive integer")
    if (
        not isinstance(population_keyset_sha256, str)
        or len(population_keyset_sha256) != 64
        or any(character not in "0123456789abcdef" for character in population_keyset_sha256)
    ):
        raise MarketStateError("market-state keyset digest is not a lowercase SHA256")
    digest = hashlib.sha256()
    digest.update(pd.Timestamp(date).date().isoformat().encode("ascii"))
    digest.update(b"\0")
    digest.update(struct.pack(">Q", population_count))
    digest.update(bytes.fromhex(population_keyset_sha256))
    for value in values:
        numeric = float(value)
        if not np.isfinite(numeric):
            raise MarketStateError("market-state digest received a non-finite value")
        digest.update(struct.pack(">d", numeric))
    return digest.hexdigest()


def _normalized_required_dates(required_dates: Iterable[object] | None) -> pd.DatetimeIndex | None:
    if required_dates is None:
        return None
    dates = pd.DatetimeIndex(pd.to_datetime(list(required_dates))).normalize()
    if dates.tz is not None:
        raise MarketStateError("required market-state dates must be timezone-naive")
    if dates.empty or not dates.is_unique:
        raise MarketStateError("required market-state dates must be non-empty and unique")
    return dates.sort_values()


def select_state_population(frame: pd.DataFrame) -> pd.DataFrame:
    """Select the independent, T-known ``U_state(T)`` from an allowlisted input.

    The result intentionally retains only the four causal state-source features.
    Labels, execution eligibility and split/purge rules are physically rejected
    before any filtering or aggregation occurs.
    """

    ensure_panel_index(frame)
    _require_exact_input_columns(frame)
    _require_boolean_columns(frame)
    numeric = frame.loc[:, list(STATE_SOURCE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    finite_sources = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1)
    eligible = (
        frame["universe_member"].to_numpy(dtype=bool)
        & frame["listing_age_eligible"].to_numpy(dtype=bool)
        & frame["is_active"].to_numpy(dtype=bool)
        & ~frame["special_status_forbidden"].to_numpy(dtype=bool)
        & ~frame["special_status_unknown"].to_numpy(dtype=bool)
        & frame["price_domain_valid"].to_numpy(dtype=bool)
        & frame["feature_eligible"].to_numpy(dtype=bool)
        & finite_sources
    )
    selected = numeric.loc[eligible].astype("float64")
    return selected


def aggregate_daily_state(
    population: pd.DataFrame,
    *,
    required_dates: Iterable[object] | None = None,
) -> pd.DataFrame:
    """Aggregate the frozen four-dimensional state from a label-free population."""

    ensure_panel_index(population)
    if set(population.columns) != set(STATE_SOURCE_COLUMNS):
        raise MarketStateError(
            "market-state population must contain exactly the four state sources"
        )
    if population.empty:
        raise MarketStateError("market-state population is empty")
    values = population.loc[:, list(STATE_SOURCE_COLUMNS)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise MarketStateError("market-state population contains non-finite source values")

    rows: list[dict[str, object]] = []
    for date, section in population.groupby(level="datetime", sort=True):
        date_values = section.loc[:, list(STATE_SOURCE_COLUMNS)].to_numpy(dtype="float64")
        if len(section) == 0 or not np.isfinite(date_values).all():
            raise MarketStateError(f"market-state population is empty or non-finite on {date}")
        instruments = section.index.get_level_values("instrument")
        keyset_digest = _keyset_sha256(instruments)
        state_values = (
            float(section["ret_mean_20"].mean()),
            float(section["ret_std_20"].median()),
            float((section["ret_1d"] > 0.0).mean()),
            float(section["turnover_mean_20"].median()),
        )
        if not np.isfinite(np.asarray(state_values, dtype=float)).all():
            raise MarketStateError(f"daily market state is non-finite on {date}")
        timestamp = pd.Timestamp(date).normalize()
        row: dict[str, object] = {
            "datetime": timestamp,
            **dict(zip(DAILY_STATE_COLUMNS, state_values, strict=True)),
            "population_count": int(len(section)),
            "population_keyset_sha256": keyset_digest,
        }
        row["state_sha256"] = _state_sha256(
            timestamp,
            population_count=row["population_count"],
            population_keyset_sha256=keyset_digest,
            values=state_values,
        )
        rows.append(row)
    state = pd.DataFrame(rows).set_index("datetime").loc[:, list(DAILY_PRODUCT_COLUMNS)]
    state.index = pd.DatetimeIndex(state.index, name="datetime")
    validate_state_product(state, expected_dates=required_dates)
    return state


def validate_state_product(
    state: pd.DataFrame,
    *,
    expected_dates: Iterable[object] | None = None,
) -> None:
    """Validate daily state values, semantic digests and required coverage."""

    if not isinstance(state.index, pd.DatetimeIndex) or state.index.name != "datetime":
        raise MarketStateError("market-state product must use a DatetimeIndex named datetime")
    if (
        state.index.tz is not None
        or not state.index.is_monotonic_increasing
        or not state.index.is_unique
    ):
        raise MarketStateError(
            "market-state product index must be unique, sorted and timezone-naive"
        )
    if state.empty:
        raise MarketStateError("market-state product is empty")
    if tuple(state.columns) != DAILY_PRODUCT_COLUMNS:
        raise MarketStateError("market-state product schema/order mismatch")
    numeric = state.loc[:, list(DAILY_STATE_COLUMNS)].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise MarketStateError("market-state product contains non-finite state values")
    required = _normalized_required_dates(expected_dates)
    if required is not None and not state.index.equals(required):
        missing = required.difference(state.index)
        unexpected = state.index.difference(required)
        raise MarketStateError(
            f"market-state product has empty/mismatched dates; missing={list(missing)}, "
            f"unexpected={list(unexpected)}"
        )
    for date, row in state.iterrows():
        count = row["population_count"]
        if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or int(count) <= 0:
            raise MarketStateError(f"market-state population_count is invalid on {date}")
        keyset_digest = row["population_keyset_sha256"]
        expected_digest = _state_sha256(
            pd.Timestamp(date),
            population_count=int(count),
            population_keyset_sha256=keyset_digest,
            values=[float(row[column]) for column in DAILY_STATE_COLUMNS],
        )
        if row["state_sha256"] != expected_digest:
            raise MarketStateError(f"market-state semantic digest mismatch on {date}")


def join_market_state(model_rows: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    """Exact-date broadcast of one validated state vector to supervised model rows."""

    ensure_panel_index(model_rows)
    validate_state_product(state)
    dates = pd.DatetimeIndex(model_rows.index.get_level_values("datetime"))
    state_for_rows = state.reindex(dates)
    if state_for_rows.loc[:, list(DAILY_STATE_COLUMNS)].isna().any().any():
        missing = sorted(set(dates[state_for_rows["mkt_trend_20"].isna()].strftime("%Y-%m-%d")))
        raise MarketStateError(f"market-state product is missing model dates: {missing}")
    output = state_for_rows.loc[:, list(DAILY_STATE_COLUMNS)].copy()
    output.index = model_rows.index
    if output.isna().any().any() or not np.isfinite(output.to_numpy(dtype=float)).all():
        raise MarketStateError("market-state date broadcast is non-finite")
    return output
