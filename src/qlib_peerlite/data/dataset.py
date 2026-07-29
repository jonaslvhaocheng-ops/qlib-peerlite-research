from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from .schema import ensure_panel_index


@dataclass
class PanelDataset:
    """Small Qlib-like dataset used by local models and deterministic tests."""

    frame: pd.DataFrame
    segments: dict[str, tuple[pd.Timestamp, pd.Timestamp]]
    feature_columns: list[str]
    label_column: str = "label"
    market_columns: list[str] | None = None
    market_state_columns: list[str] | None = None

    def __post_init__(self) -> None:
        self.frame = self.frame.sort_index()
        ensure_panel_index(self.frame)
        self.market_columns = list(self.market_columns or [])
        self.market_state_columns = list(self.market_state_columns or [])

    def prepare(
        self,
        segment: str,
        col_set: Literal["feature", "label", "market", "market_state", "all"] | list[str] = "all",
        data_key: str | None = None,
    ) -> pd.DataFrame:
        del data_key
        start, end = self.segments[segment]
        dates = self.frame.index.get_level_values("datetime")
        selected = self.frame.loc[(dates >= start) & (dates <= end)]
        if col_set == "feature":
            return selected[self.feature_columns].copy()
        if col_set == "label":
            return selected[[self.label_column]].copy()
        if col_set == "market":
            return selected[self.market_columns].copy()
        if col_set == "market_state":
            return selected[self.market_state_columns].copy()
        if col_set == "all":
            return selected.copy()
        if isinstance(col_set, str):
            raise ValueError(f"unsupported col_set: {col_set}")
        return selected[list(col_set)].copy()
