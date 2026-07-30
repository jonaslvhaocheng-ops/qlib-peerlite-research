from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AShareCostSchedule:
    """Frozen A-share research costs in basis points of traded notional."""

    broker_commission_bps_per_side: float = 3.0
    base_impact_bps_per_side: float = 10.0
    stress_impact_bps_per_side: float = 20.0

    @staticmethod
    def stamp_duty_bps(date: pd.Timestamp) -> float:
        return 5.0 if pd.Timestamp(date) >= pd.Timestamp("2023-08-28") else 10.0

    @staticmethod
    def transfer_fee_bps(date: pd.Timestamp) -> float:
        return 0.1 if pd.Timestamp(date) >= pd.Timestamp("2022-04-29") else 0.2

    def side_cost_bps(
        self,
        date: pd.Timestamp,
        *,
        side: str,
        stress: bool = False,
    ) -> float:
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        impact = self.stress_impact_bps_per_side if stress else self.base_impact_bps_per_side
        statutory = self.transfer_fee_bps(date)
        if side == "sell":
            statutory += self.stamp_duty_bps(date)
        return self.broker_commission_bps_per_side + impact + statutory


def _rebalance_dates(index: pd.MultiIndex, weekday: int) -> list[pd.Timestamp]:
    dates = pd.DatetimeIndex(sorted(index.get_level_values("datetime").unique()))
    selected: list[pd.Timestamp] = []
    for _, weekly_dates in pd.Series(dates, index=dates).groupby(dates.to_period("W-FRI")):
        exact = [date for date in weekly_dates if date.weekday() == weekday]
        selected.append(pd.Timestamp(exact[-1] if exact else weekly_dates.iloc[-1]))
    return selected


def _desired_weights(
    section: pd.DataFrame,
    *,
    mode: str,
    top_fraction: float,
    max_name_weight: float,
) -> pd.Series:
    eligible = section.loc[section["eligible"].astype(bool)].dropna(
        subset=["score", "forward_return"]
    )
    if eligible.empty:
        return pd.Series(dtype=float)
    if mode == "top_fraction":
        count = max(1, int(math.ceil(len(eligible) * top_fraction)))
        selected = eligible.nlargest(count, "score")
    elif mode == "equal_weight_universe":
        selected = eligible
    else:
        raise ValueError("unsupported portfolio mode")
    weight = min(1.0 / len(selected), max_name_weight)
    return pd.Series(
        weight,
        index=selected.index.get_level_values("instrument"),
        dtype=float,
    )


def backtest_weekly_executable(
    panel: pd.DataFrame,
    *,
    mode: str = "top_fraction",
    top_fraction: float = 0.10,
    max_name_weight: float = 0.02,
    adv_participation_limit: float = 0.05,
    portfolio_notional: float = 100_000_000.0,
    rebalance_weekday: int = 4,
    costs: AShareCostSchedule | None = None,
    stress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Weekly long-only simulation with side-aware costs and failed-fill retention."""

    if not isinstance(panel.index, pd.MultiIndex) or tuple(panel.index.names) != (
        "datetime",
        "instrument",
    ):
        raise ValueError("portfolio panel must use (datetime, instrument) index")
    required = {
        "score",
        "forward_return",
        "carry_return",
        "overnight_return",
        "eligible",
        "can_buy",
        "can_sell",
        "adv20",
    }
    if not required.issubset(panel.columns):
        raise ValueError(f"portfolio panel missing {sorted(required - set(panel.columns))}")
    if not np.isfinite(panel[["score", "adv20"]].to_numpy(dtype=float)).all():
        raise ValueError("portfolio panel contains non-finite required numeric inputs")
    carry_finite = np.isfinite(panel["carry_return"].to_numpy(dtype=float))
    overnight_finite = np.isfinite(panel["overnight_return"].to_numpy(dtype=float))
    eligible_forward = panel["eligible"].to_numpy(dtype=bool) & ~np.isfinite(
        panel["forward_return"].to_numpy(dtype=float)
    )
    if (~(carry_finite | overnight_finite)).any() or eligible_forward.any():
        raise ValueError("portfolio panel return availability invariant failed")
    costs = costs or AShareCostSchedule()
    prior = pd.Series(dtype=float)
    return_rows: list[dict[str, float | pd.Timestamp]] = []
    holding_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []

    for date in _rebalance_dates(panel.index, rebalance_weekday):
        section = panel.xs(date, level="datetime", drop_level=False)
        by_instrument = section.droplevel("datetime")
        desired = _desired_weights(
            section,
            mode=mode,
            top_fraction=top_fraction,
            max_name_weight=max_name_weight,
        )
        union = prior.index.union(desired.index)
        prior_aligned = prior.reindex(union, fill_value=0.0)
        current = prior_aligned.copy()
        desired = desired.reindex(union, fill_value=0.0)
        buy_turnover = 0.0
        sell_turnover = 0.0
        requested_by_name = desired - prior_aligned
        filled_by_name = pd.Series(0.0, index=union, dtype=float)

        # Execute reductions first. A blocked or capacity-limited sell remains in
        # inventory and therefore consumes cash that cannot be spent on replacements.
        for instrument in union:
            old = float(current[instrument])
            target = float(desired[instrument])
            row = by_instrument.loc[instrument] if instrument in by_instrument.index else None
            can_sell = bool(row["can_sell"]) if row is not None else False
            requested = target - old
            if requested >= 0:
                continue
            filled = requested if can_sell else 0.0
            if row is not None and filled < 0:
                capacity_weight = (
                    max(float(row["adv20"]), 0.0)
                    * adv_participation_limit
                    / portfolio_notional
                )
                filled = max(filled, -capacity_weight)
            current[instrument] = old + filled
            sell_turnover += max(-filled, 0.0)
            filled_by_name[instrument] += filled

        # Capacity-limit each desired increase, then allocate the available cash
        # pro rata. This never scales retained positions upward and cannot create
        # leverage when a sell is blocked.
        proposed_buys = pd.Series(0.0, index=union, dtype=float)
        for instrument in union:
            target = float(desired[instrument])
            old = float(current[instrument])
            requested = target - old
            if requested <= 0:
                continue
            row = by_instrument.loc[instrument] if instrument in by_instrument.index else None
            can_buy = bool(row["can_buy"]) if row is not None else False
            if not can_buy:
                continue
            capacity_weight = (
                max(float(row["adv20"]), 0.0)
                * adv_participation_limit
                / portfolio_notional
            )
            proposed_buys[instrument] = min(requested, capacity_weight)
        available_cash = max(0.0, 1.0 - float(current.sum()))
        proposed_total = float(proposed_buys.sum())
        buy_scale = min(1.0, available_cash / proposed_total) if proposed_total > 0 else 0.0
        filled_buys = proposed_buys * buy_scale
        current = current + filled_buys
        filled_by_name = filled_by_name + filled_buys
        buy_turnover = float(filled_buys.sum())

        if float(current.sum()) > 1.0 + 1e-12:
            raise AssertionError("cash constraint violated: invested weight exceeds one")
        if (current < -1e-12).any() or (current > max_name_weight + 1e-12).any():
            raise AssertionError("long-only or single-name weight constraint violated")

        unfilled = 0
        for instrument in union:
            requested = float(requested_by_name[instrument])
            filled = float(filled_by_name[instrument])
            if not np.isclose(filled, requested):
                unfilled += 1
            if filled or requested:
                trade_rows.append(
                    {
                        "datetime": date,
                        "instrument": instrument,
                        "prior_weight": float(prior_aligned[instrument]),
                        "target_weight": float(desired[instrument]),
                        "filled_weight": filled,
                        "unfilled_weight": requested - filled,
                    }
                )
        old = prior_aligned
        rows = by_instrument.reindex(union)
        carry = rows["carry_return"].astype(float)
        forward = rows["forward_return"].astype(float)
        overnight = rows["overnight_return"].astype(float)
        gross = 0.0
        for instrument in union:
            old_weight = float(old[instrument])
            current_weight = float(current[instrument])
            overnight_value = float(overnight[instrument])
            forward_value = float(forward[instrument])
            carry_value = float(carry[instrument])
            if old_weight > 0 and not np.isfinite(overnight_value):
                if (
                    not np.isclose(current_weight, old_weight)
                    or not np.isfinite(carry_value)
                ):
                    raise ValueError(
                        f"unpriced retained holding changed on {date.date()}: {instrument}; "
                        f"old={old_weight}, current={current_weight}, carry={carry_value}"
                    )
                gross += current_weight * carry_value
                continue
            if old_weight > 0:
                gross += old_weight * overnight_value
            if current_weight > 0:
                if not np.isfinite(forward_value):
                    raise ValueError(
                        f"post-open holding lacks a forward return on {date.date()}: "
                        f"{instrument}"
                    )
                gross += current_weight * forward_value
        current = current[current > 1e-15]
        buy_cost = buy_turnover * costs.side_cost_bps(date, side="buy", stress=stress) / 10_000
        sell_cost = (
            sell_turnover * costs.side_cost_bps(date, side="sell", stress=stress) / 10_000
        )
        transaction_cost = buy_cost + sell_cost
        return_rows.append(
            {
                "datetime": date,
                "gross_return": gross,
                "transaction_cost": transaction_cost,
                "net_return": gross - transaction_cost,
                "turnover": buy_turnover + sell_turnover,
                "buy_turnover": buy_turnover,
                "sell_turnover": sell_turnover,
                "invested_weight": float(current.sum()),
                "cash_weight": 1.0 - float(current.sum()),
                "names": float(len(current)),
                "unfilled_orders": float(unfilled),
            }
        )
        for instrument, weight in current.items():
            holding_rows.append(
                {
                    "datetime": date,
                    "instrument": instrument,
                    "weight": float(weight),
                    "score": float(by_instrument.loc[instrument, "score"]),
                }
            )
        prior = current

    returns = pd.DataFrame(return_rows).set_index("datetime")
    holdings = pd.DataFrame(
        holding_rows,
        columns=["datetime", "instrument", "weight", "score"],
    )
    trades = pd.DataFrame(
        trade_rows,
        columns=[
            "datetime",
            "instrument",
            "prior_weight",
            "target_weight",
            "filled_weight",
            "unfilled_weight",
        ],
    )
    return returns, holdings, trades


__all__ = ["AShareCostSchedule", "backtest_weekly_executable"]
