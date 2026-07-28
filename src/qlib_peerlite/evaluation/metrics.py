from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def daily_rank_ic(scores: pd.Series, labels: pd.Series) -> pd.Series:
    joined = pd.concat([scores.rename("score"), labels.rename("label")], axis=1).dropna()

    def calculate(group: pd.DataFrame) -> float:
        if len(group) < 3 or group["score"].nunique() < 2 or group["label"].nunique() < 2:
            return float("nan")
        return float(spearmanr(group["score"], group["label"]).statistic)

    return joined.groupby(level="datetime", sort=True).apply(calculate).rename("rank_ic")


def information_ratio(returns: pd.Series, periods_per_year: int = 52) -> float:
    values = returns.dropna().astype(float)
    if len(values) < 2:
        return float("nan")
    volatility = values.std(ddof=1)
    if volatility <= 0:
        return float("nan")
    return float(values.mean() / volatility * math.sqrt(periods_per_year))


def max_drawdown(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min()) if len(drawdown) else float("nan")


def decile_monotonicity(scores: pd.Series, labels: pd.Series, groups: int = 10) -> dict[str, float]:
    joined = pd.concat([scores.rename("score"), labels.rename("label")], axis=1).dropna()
    rows: list[pd.DataFrame] = []
    for _, frame in joined.groupby(level="datetime", sort=True):
        if len(frame) < groups:
            continue
        ranked = frame["score"].rank(method="first", pct=True)
        bucket = np.minimum((ranked * groups).apply(np.ceil).astype(int), groups)
        temp = frame.copy()
        temp["bucket"] = bucket
        rows.append(temp)
    if not rows:
        return {"decile_slope": float("nan"), "top_minus_bottom": float("nan")}
    panel = pd.concat(rows)
    means = panel.groupby("bucket")["label"].mean()
    if len(means) < 2:
        return {"decile_slope": float("nan"), "top_minus_bottom": float("nan")}
    slope = np.polyfit(means.index.to_numpy(float), means.to_numpy(float), 1)[0]
    return {
        "decile_slope": float(slope),
        "top_minus_bottom": float(means.iloc[-1] - means.iloc[0]),
    }


def evaluate_predictions(scores: pd.Series, labels: pd.Series) -> dict[str, float]:
    ic = daily_rank_ic(scores, labels)
    ic_std = ic.std(ddof=1)
    output = {
        "rank_ic_mean": float(ic.mean()),
        "rank_ic_std": float(ic_std),
        "rank_icir": (
            float(ic.mean() / ic_std)
            if np.isfinite(ic_std) and ic_std > 0
            else float("nan")
        ),
        "rank_ic_positive_fraction": float((ic > 0).mean()),
        "observations": float(len(pd.concat([scores, labels], axis=1).dropna())),
        "dates": float(ic.notna().sum()),
    }
    output.update(decile_monotonicity(scores, labels))
    return output
