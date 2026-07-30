from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


def _load_script(name: str):
    path = Path(__file__).parents[1] / "scripts" / "server" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m8_confirmation_schedule_and_model_are_frozen() -> None:
    runner = _load_script("run_m8_confirmation.py")
    assert runner.SEEDS == (19, 42, 73, 101)
    assert runner.FOLDS == tuple(f"wf_{year}" for year in range(2018, 2025))
    parameters = runner.model_parameters(42)
    assert parameters["model_id"] == "PEERLITE_K16_MSE"
    assert parameters["num_peers"] == 16
    assert parameters["loss"] == "mse"
    assert parameters["market_gate"] is False
    assert parameters["seed"] == 42


def test_m8_score_loader_rejects_duplicate_keys(tmp_path: Path) -> None:
    evaluator = _load_script("evaluate_m8_confirmation.py")
    path = tmp_path / "scores.parquet"
    pd.DataFrame(
        {
            "datetime": ["2024-01-02", "2024-01-02"],
            "instrument": ["1", "1"],
            "score": [0.1, 0.2],
            "fold_id": ["wf_2024", "wf_2024"],
        }
    ).to_parquet(path, index=False)
    with pytest.raises(RuntimeError, match="duplicate predictions"):
        evaluator.load_scores(path)


def test_m8_content_hash_excludes_only_its_own_field() -> None:
    runner = _load_script("run_m8_confirmation.py")
    first = runner.canonical_hash({"value": 1, "content_sha256": "old"})
    second = runner.canonical_hash({"content_sha256": "new", "value": 1})
    changed = runner.canonical_hash({"value": 2})
    assert first == second
    assert changed != first


def test_m8_verifier_hash_uses_canonical_payload() -> None:
    verifier = _load_script("verify_m8_confirmation.py")
    assert verifier.canonical_hash({"b": 2, "a": 1}) == verifier.canonical_hash(
        {"a": 1, "b": 2, "content_sha256": "ignored"}
    )
