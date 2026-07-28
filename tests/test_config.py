from __future__ import annotations

from pathlib import Path

import pytest

from qlib_peerlite.config import ExperimentConfig, load_config


def test_synthetic_config_is_strict_and_loadable() -> None:
    config = load_config(Path("configs/synthetic_demo.yaml"))
    assert config.track == "SYNTHETIC"
    assert config.model.input_dim == 12
    assert config.model.num_peers == 16


def test_market_gate_requires_market_dimension() -> None:
    payload = load_config(Path("configs/synthetic_demo.yaml")).model_dump()
    payload["model"]["market_gate"] = True
    with pytest.raises(ValueError, match="market_dim"):
        ExperimentConfig.model_validate(payload)
