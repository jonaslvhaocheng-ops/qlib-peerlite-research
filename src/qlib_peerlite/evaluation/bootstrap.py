from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import information_ratio


def _moving_block_indices(
    length: int,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if length <= 0:
        return np.array([], dtype=int)
    starts = rng.integers(0, length, size=int(np.ceil(length / block_length)))
    blocks = [np.mod(np.arange(start, start + block_length), length) for start in starts]
    return np.concatenate(blocks)[:length]


def bootstrap_ir_difference(
    candidate_returns: pd.Series,
    benchmark_returns: pd.Series,
    *,
    block_length: int = 4,
    draws: int = 2_000,
    seed: int = 7,
    periods_per_year: int = 52,
) -> dict[str, float]:
    aligned = pd.concat(
        [candidate_returns.rename("candidate"), benchmark_returns.rename("benchmark")],
        axis=1,
    ).dropna()
    if len(aligned) < max(8, block_length * 2):
        raise ValueError("insufficient aligned returns for block bootstrap")
    rng = np.random.default_rng(seed)
    deltas = np.empty(draws, dtype=float)
    for draw in range(draws):
        idx = _moving_block_indices(len(aligned), block_length, rng)
        sampled = aligned.iloc[idx]
        deltas[draw] = information_ratio(
            sampled["candidate"], periods_per_year
        ) - information_ratio(sampled["benchmark"], periods_per_year)
    return {
        "ir_delta_point": information_ratio(
            aligned["candidate"], periods_per_year
        ) - information_ratio(aligned["benchmark"], periods_per_year),
        "ir_delta_ci_2_5": float(np.quantile(deltas, 0.025)),
        "ir_delta_ci_97_5": float(np.quantile(deltas, 0.975)),
        "bootstrap_draws": float(draws),
        "block_length": float(block_length),
    }
