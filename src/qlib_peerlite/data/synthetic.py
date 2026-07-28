from __future__ import annotations

import numpy as np
import pandas as pd

from .dataset import PanelDataset


def make_synthetic_dataset(
    *,
    n_dates: int = 90,
    n_instruments: int = 48,
    n_features: int = 12,
    seed: int = 7,
) -> PanelDataset:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_dates)
    instruments = [f"S{i:04d}" for i in range(n_instruments)]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])

    feature_names = [f"f{i:02d}" for i in range(n_features)]
    x = rng.normal(size=(n_dates, n_instruments, n_features))
    peer_group = np.arange(n_instruments) % 4
    group_state = rng.normal(scale=0.7, size=(n_dates, 4))
    market = rng.normal(scale=0.5, size=(n_dates, 3))

    for date_idx in range(n_dates):
        x[date_idx, :, 0] += group_state[date_idx, peer_group]
        x[date_idx, :, 1] += market[date_idx, 0]

    peer_mean = np.zeros((n_dates, n_instruments))
    for group_id in range(4):
        mask = peer_group == group_id
        peer_mean[:, mask] = x[:, mask, 0].mean(axis=1, keepdims=True)

    label = (
        0.35 * x[:, :, 0]
        - 0.20 * x[:, :, 1]
        + 0.30 * (x[:, :, 0] - peer_mean)
        + 0.10 * market[:, 1, None]
        + rng.normal(scale=0.35, size=(n_dates, n_instruments))
    )

    frame = pd.DataFrame(x.reshape(-1, n_features), index=index, columns=feature_names)
    frame["label"] = label.reshape(-1)
    for position, name in enumerate(("market_ret", "market_vol", "market_turnover")):
        frame[name] = np.repeat(market[:, position], n_instruments)

    train_end = dates[int(n_dates * 0.60) - 1]
    valid_end = dates[int(n_dates * 0.80) - 1]
    segments = {
        "train": (dates[0], train_end),
        "valid": (dates[int(n_dates * 0.60)], valid_end),
        "test": (dates[int(n_dates * 0.80)], dates[-1]),
    }
    return PanelDataset(
        frame=frame,
        segments=segments,
        feature_columns=feature_names,
        label_column="label",
        market_columns=["market_ret", "market_vol", "market_turnover"],
    )
