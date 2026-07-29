from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("journey", "status"),
    [("ccc", "PASS"), ("gate", "PASS"), ("preflight", "NOT_RUN")],
)
def test_m7_acceptance_journeys_in_clean_process(journey: str, status: str) -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/run_m7_acceptance.py", journey],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["journey"] == journey
    assert result["status"] == status
    assert result["persistent_effects"] == 0
    assert result["persistent_effect_paths"] == []
    if journey == "preflight":
        assert result["claim_ceiling"] == "PRECHECK_ONLY_NOT_FIT_AUTHORITY"
        assert "cost_spec" in result["reason"]
        assert "benchmark_spec" in result["reason"]
    else:
        assert result["claim_ceiling"] == "SYNTHETIC_MECHANICS_ONLY"
        assert result["checkpoint_replay_exact"] is True
        assert result["score_rows"] > 0
