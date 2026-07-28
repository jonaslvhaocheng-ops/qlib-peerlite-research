from __future__ import annotations

import math

import pandas as pd

from .metrics import information_ratio, max_drawdown


def _capped_equal_weights(
    frame: pd.DataFrame,
    *,
    top_fraction: float,
    max_name_weight: float,
    portfolio_notional: float,
    adv_participation_limit: float,
) -> pd.Series:
    tradable = frame.loc[frame["tradable"].astype(bool)].dropna(subset=["score", "forward_return"])
    if tradable.empty:
        return pd.Series(dtype=float)
    count = max(1, int(math.ceil(len(tradable) * top_fraction)))
    selected = tradable.nlargest(count, "score")
    base_weight = min(1.0 / count, max_name_weight)
    weights = pd.Series(base_weight, index=selected.index, dtype=float)
    if "adv20" in selected and portfolio_notional > 0:
        capacity_weight = (
            selected["adv20"].clip(lower=0) * adv_participation_limit / portfolio_notional
        )
        weights = pd.concat([weights, capacity_weight], axis=1).min(axis=1)
    return weights.clip(lower=0, upper=max_name_weight)


def backtest_weekly_top_fraction(
    panel: pd.DataFrame,
    *,
    top_fraction: float = 0.10,
    max_name_weight: float = 0.02,
    adv_participation_limit: float = 0.05,
    cost_bps_per_side: float = 10.0,
    portfolio_notional: float = 100_000_000.0,
    rebalance_weekday: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Backtest a transparent weekly long-only score portfolio.

    Input uses a ``(datetime, instrument)`` MultiIndex and must contain score,
    forward_return, tradable and optionally adv20. Unallocated weight remains
    cash; weights are never silently re-normalized above hard caps.
    """

    if not isinstance(panel.index, pd.MultiIndex) or tuple(panel.index.names) != (
        "datetime",
        "instrument",
    ):
        raise ValueError("portfolio panel must use (datetime, instrument) index")
    required = {"score", "forward_return", "tradable"}
    if not required.issubset(panel.columns):
        raise ValueError(f"portfolio panel missing {sorted(required - set(panel.columns))}")

    dates = pd.DatetimeIndex(sorted(panel.index.get_level_values("datetime").unique()))
    selected_dates: list[pd.Timestamp] = []
    for _, weekly_dates in pd.Series(dates, index=dates).groupby(dates.to_period("W-FRI")):
        exact = [date for date in weekly_dates if date.weekday() == rebalance_weekday]
        selected_dates.append(pd.Timestamp(exact[-1] if exact else weekly_dates.iloc[-1]))

    prior = pd.Series(dtype=float)
    return_rows: list[dict[str, float | pd.Timestamp]] = []
    holding_rows: list[pd.DataFrame] = []
    for date in selected_dates:
        cross_section = panel.xs(date, level="datetime", drop_level=False)
        weights = _capped_equal_weights(
            cross_section,
            top_fraction=top_fraction,
            max_name_weight=max_name_weight,
            portfolio_notional=portfolio_notional,
            adv_participation_limit=adv_participation_limit,
        )
        instruments = weights.index.get_level_values("instrument")
        current = pd.Series(weights.to_numpy(), index=instruments)
        union = prior.index.union(current.index)
        turnover = float(
            current.reindex(union, fill_value=0.0)
            .sub(prior.reindex(union, fill_value=0.0))
            .abs()
            .sum()
        )
        cost = turnover * cost_bps_per_side / 10_000.0
        selected_returns = cross_section.loc[weights.index, "forward_return"].astype(float)
        gross = float((weights * selected_returns).sum())
        net = gross - cost
        return_rows.append(
            {
                "datetime": date,
                "gross_return": gross,
                "transaction_cost": cost,
                "net_return": net,
                "turnover": turnover,
                "invested_weight": float(weights.sum()),
                "names": float(len(weights)),
            }
        )
        if len(weights):
            holding = pd.DataFrame(
                {
                    "datetime": date,
                    "instrument": instruments,
                    "weight": weights.to_numpy(),
                    "score": cross_section.loc[weights.index, "score"].to_numpy(),
                }
            )
            holding_rows.append(holding)
        prior = current

    returns = pd.DataFrame(return_rows).set_index("datetime")
    holdings = (
        pd.concat(holding_rows, ignore_index=True)
        if holding_rows
        else pd.DataFrame(columns=["datetime", "instrument", "weight", "score"])
    )
    return returns, holdings


def portfolio_metrics(returns: pd.DataFrame) -> dict[str, float]:
    net = returns["net_return"]
    return {
        "net_information_ratio": information_ratio(net),
        "gross_information_ratio": information_ratio(returns["gross_return"]),
        "annualized_net_return": float((1.0 + net).prod() ** (52 / max(len(net), 1)) - 1.0),
        "max_drawdown": max_drawdown(net),
        "average_turnover": float(returns["turnover"].mean()),
        "average_invested_weight": float(returns["invested_weight"].mean()),
        "total_cost": float(returns["transaction_cost"].sum()),
    }
