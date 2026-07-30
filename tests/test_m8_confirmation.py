from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from qlib_peerlite.governance.trial_ledger import RunIntent
from qlib_peerlite.m8_closure.recovery import (
    canonicalize_interrupted_m8_journal,
)


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


def test_m8_confirmation_entrypoint_is_permanently_closed(tmp_path: Path) -> None:
    runner = _load_script("run_m8_confirmation.py")
    with pytest.raises(RuntimeError, match="permanently closed"):
        runner.run(tmp_path, tmp_path, tmp_path / "forbidden-retry")
    assert not (tmp_path / "forbidden-retry").exists()


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


def test_m8_complete_path_evaluator_is_permanently_closed(tmp_path: Path) -> None:
    evaluator = _load_script("evaluate_m8_confirmation.py")
    with pytest.raises(RuntimeError, match="permanently closed"):
        evaluator.run(tmp_path, tmp_path, tmp_path, tmp_path, tmp_path)


def test_m8_complete_path_verifier_is_permanently_closed(tmp_path: Path) -> None:
    verifier = _load_script("verify_m8_confirmation.py")
    with pytest.raises(RuntimeError, match="permanently closed"):
        verifier.run(tmp_path, tmp_path, tmp_path, tmp_path)


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


def test_m8_interruption_recovery_counts_exact_starts(tmp_path: Path) -> None:
    source = (
        Path(__file__).parents[1]
        / "evidence/m8/failures/m8_confirmation_20260730_v1/trial_journal.jsonl"
    )
    intent = RunIntent(
        run_id="m8_confirmation_20260730_v1_recovery",
        family_id="QLIB_PEERLITE_M8_CONFIRMATION_V1",
        execution_spec_content_sha256="1" * 64,
    )
    events = canonicalize_interrupted_m8_journal(source, run_intent=intent)
    assert len(events) == 4
    assert sum(event["counts_as_candidate_evaluation"] for event in events) == 1
    assert sum(event["counts_as_model_fit"] for event in events) == 3
    assert [event.get("fold_id") for event in events[1:]] == [
        "wf_2018",
        "wf_2019",
        "wf_2020",
    ]

    modified = [json.loads(line) for line in source.read_text().splitlines()]
    modified[-1]["fold_id"] = "wf_2021"
    tampered = tmp_path / "tampered.jsonl"
    tampered.write_text(
        "".join(json.dumps(event) + "\n" for event in modified),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="fit identity mismatch"):
        canonicalize_interrupted_m8_journal(tampered, run_intent=intent)
