from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from .schema import ensure_panel_index

RAW_COLUMNS = ("open", "high", "low", "close", "volume", "amount", "turnover")
WINDOWS = (5, 10, 20, 60)
DAILY_FEATURES = (
    "ret_1d",
    "gap_return",
    "intraday_return",
    "high_low_range",
    "close_location",
    "upper_shadow",
    "lower_shadow",
    "log_volume",
    "log_amount",
    "turnover_raw",
)
ROLLING_FAMILIES = (
    "ret_mean",
    "ret_std",
    "downside_vol",
    "range_mean",
    "turnover_mean",
    "turnover_std",
    "log_volume_mean",
    "log_amount_mean",
    "amihud_mean",
    "price_volume_corr",
)
FEATURE_COLUMNS = tuple(DAILY_FEATURES) + tuple(
    f"{family}_{window}" for window in WINDOWS for family in ROLLING_FAMILIES
)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, np.nan)
    return numerator / denominator


def build_causal_daily_features(
    raw: pd.DataFrame,
    *,
    windows: Iterable[int] = WINDOWS,
    corporate_action_column: str = "corporate_action",
    mask_lookback_sessions: int = 60,
) -> pd.DataFrame:
    """Build exactly 50 trailing features from RAW daily observations.

    All operations are per instrument and use only current/past rows. If a
    corporate-action marker is present, rows whose lookback crosses that event
    are excluded through an explicit ``feature_eligible`` flag.
    """

    ensure_panel_index(raw)
    missing = sorted(set(RAW_COLUMNS) - set(raw.columns))
    if missing:
        raise ValueError(f"raw panel is missing columns: {missing}")

    frame = raw.sort_index().copy()
    inst = frame.groupby(level="instrument", sort=False, group_keys=False)
    previous_close = inst["close"].shift(1)

    output = pd.DataFrame(index=frame.index)
    output["ret_1d"] = _safe_divide(frame["close"], previous_close) - 1.0
    output["gap_return"] = _safe_divide(frame["open"], previous_close) - 1.0
    output["intraday_return"] = _safe_divide(frame["close"], frame["open"]) - 1.0
    output["high_low_range"] = _safe_divide(frame["high"], frame["low"]) - 1.0
    output["close_location"] = _safe_divide(
        frame["close"] - frame["low"], frame["high"] - frame["low"]
    )
    output["upper_shadow"] = _safe_divide(
        frame["high"] - frame[["open", "close"]].max(axis=1), frame["open"]
    )
    output["lower_shadow"] = _safe_divide(
        frame[["open", "close"]].min(axis=1) - frame["low"], frame["open"]
    )
    output["log_volume"] = np.log1p(frame["volume"].clip(lower=0))
    output["log_amount"] = np.log1p(frame["amount"].clip(lower=0))
    output["turnover_raw"] = frame["turnover"]
    output["amihud_raw"] = _safe_divide(output["ret_1d"].abs(), frame["amount"].abs())

    grouped = output.groupby(level="instrument", sort=False, group_keys=False)
    for window in windows:
        min_periods = int(window)
        output[f"ret_mean_{window}"] = grouped["ret_1d"].rolling(
            window, min_periods=min_periods
        ).mean().droplevel(0)
        output[f"ret_std_{window}"] = grouped["ret_1d"].rolling(
            window, min_periods=min_periods
        ).std(ddof=0).droplevel(0)
        negative = output["ret_1d"].clip(upper=0)
        output[f"downside_vol_{window}"] = negative.groupby(
            level="instrument", sort=False
        ).rolling(window, min_periods=min_periods).std(ddof=0).droplevel(0)
        for source, name in (
            ("high_low_range", "range_mean"),
            ("turnover_raw", "turnover_mean"),
            ("log_volume", "log_volume_mean"),
            ("log_amount", "log_amount_mean"),
            ("amihud_raw", "amihud_mean"),
        ):
            output[f"{name}_{window}"] = grouped[source].rolling(
                window, min_periods=min_periods
            ).mean().droplevel(0)
        output[f"turnover_std_{window}"] = grouped["turnover_raw"].rolling(
            window, min_periods=min_periods
        ).std(ddof=0).droplevel(0)
        rolling_correlation = pd.Series(np.nan, index=output.index, dtype=float)
        for _, cross_history in output.groupby(
            level="instrument", sort=False, group_keys=False
        ):
            values = (
                cross_history["ret_1d"]
                .rolling(window, min_periods=min_periods)
                .corr(cross_history["log_volume"])
            )
            rolling_correlation.loc[cross_history.index] = values.to_numpy()
        output[f"price_volume_corr_{window}"] = rolling_correlation

    if corporate_action_column in frame:
        action = frame[corporate_action_column].fillna(False).astype(bool)
        contaminated = (
            action.groupby(level="instrument", sort=False)
            .rolling(mask_lookback_sessions, min_periods=1)
            .max()
            .droplevel(0)
            .astype(bool)
        )
    else:
        contaminated = pd.Series(False, index=frame.index)

    result = output.loc[:, list(FEATURE_COLUMNS)].replace([np.inf, -np.inf], np.nan)
    result["feature_eligible"] = ~contaminated
    result.loc[contaminated, list(FEATURE_COLUMNS)] = np.nan
    return result
