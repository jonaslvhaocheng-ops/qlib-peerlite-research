from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataConfig(StrictModel):
    feature_columns: list[str] = Field(default_factory=list)
    label_column: str = "label"
    market_columns: list[str] = Field(default_factory=list)
    min_listing_sessions: int = 60
    embargo_sessions: int = 5
    raw_prices_only: bool = True


class ModelConfig(StrictModel):
    family: Literal["lightgbm", "mlp", "peerlite"] = "peerlite"
    input_dim: int
    hidden_dim: int = 64
    num_peers: Literal[16, 32] = 16
    num_heads: int = 4
    dropout: float = 0.1
    loss: Literal["mse", "ccc"] = "mse"
    market_gate: bool = False
    market_dim: int = 0

    @model_validator(mode="after")
    def validate_dimensions(self) -> ModelConfig:
        if self.hidden_dim % self.num_heads:
            raise ValueError("hidden_dim must be divisible by num_heads")
        if self.market_gate and self.market_dim <= 0:
            raise ValueError("market_dim must be positive when market_gate is enabled")
        return self


class TrainingConfig(StrictModel):
    seed: int = 7
    epochs: int = 100
    patience: int = 12
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    gradient_clip_norm: float = 1.0


class PortfolioConfig(StrictModel):
    rebalance_weekday: int = 4
    top_fraction: float = 0.10
    max_name_weight: float = 0.02
    adv_participation_limit: float = 0.05
    base_cost_bps_per_side: float = 10.0
    stress_cost_bps_per_side: float = 20.0

    @model_validator(mode="after")
    def validate_portfolio(self) -> PortfolioConfig:
        if not 0 < self.top_fraction <= 1:
            raise ValueError("top_fraction must be in (0, 1]")
        if not 0 < self.max_name_weight <= 1:
            raise ValueError("max_name_weight must be in (0, 1]")
        if not 0 < self.adv_participation_limit <= 1:
            raise ValueError("adv_participation_limit must be in (0, 1]")
        return self


class ExperimentConfig(StrictModel):
    experiment_id: str
    track: Literal["SYNTHETIC", "STRICT"] = "SYNTHETIC"
    data: DataConfig
    model: ModelConfig
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)


def load_config(path: str | Path) -> ExperimentConfig:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ExperimentConfig.model_validate(payload)
