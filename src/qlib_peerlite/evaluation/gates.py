from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class PromotionDecision:
    decision: str
    reasons: tuple[str, ...]
    seed_positive_fraction: float
    fold_positive_fraction: float
    bootstrap_ci_low: float
    best_year_contribution: float
    stress_net_ir: float

    def to_dict(self) -> dict:
        return asdict(self)


def promotion_decision(
    comparisons: pd.DataFrame,
    *,
    bootstrap_ci_low: float,
    best_year_contribution: float,
    stress_net_ir: float,
    hard_gate_failures: list[str] | None = None,
) -> PromotionDecision:
    """Apply frozen v0 research-candidate gates.

    comparisons requires seed, fold_id and ``net_ir_delta`` columns.
    """

    hard_gate_failures = list(hard_gate_failures or [])
    required = {"seed", "fold_id", "net_ir_delta"}
    if not required.issubset(comparisons.columns):
        raise ValueError(f"comparison table missing {sorted(required - set(comparisons.columns))}")

    seed_delta = comparisons.groupby("seed")["net_ir_delta"].mean()
    fold_delta = comparisons.groupby("fold_id")["net_ir_delta"].mean()
    seed_positive = float((seed_delta > 0).mean())
    fold_positive = float((fold_delta > 0).mean())

    reasons = list(hard_gate_failures)
    if seed_positive < 0.8:
        reasons.append("positive relative result in fewer than 4/5 seeds")
    if fold_positive < 0.6:
        reasons.append("positive relative result in fewer than 60% of rolling folds")
    if bootstrap_ci_low <= 0:
        reasons.append("block-bootstrap 95% lower bound is not positive")
    if best_year_contribution > 0.5:
        reasons.append("best year contributes more than 50% of cumulative excess")
    if stress_net_ir <= 0:
        reasons.append("stress-cost net information ratio is not positive")

    if hard_gate_failures:
        decision = "REJECT"
    elif not reasons:
        decision = "PROMOTE"
    elif seed_positive < 0.5 or fold_positive < 0.5 or stress_net_ir <= 0:
        decision = "REJECT"
    else:
        decision = "HOLD"

    return PromotionDecision(
        decision=decision,
        reasons=tuple(reasons),
        seed_positive_fraction=seed_positive,
        fold_positive_fraction=fold_positive,
        bootstrap_ci_low=float(bootstrap_ci_low),
        best_year_contribution=float(best_year_contribution),
        stress_net_ir=float(stress_net_ir),
    )
