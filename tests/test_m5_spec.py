from __future__ import annotations

import json
from pathlib import Path

import pytest

from qlib_peerlite.governance.m5_spec import M5SpecError, load_and_verify_m5_spec

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "contracts/immutable/m5_baseline_execution_spec_v1.json"


def test_frozen_m5_baseline_spec_is_fully_bound() -> None:
    spec = load_and_verify_m5_spec(PROJECT_ROOT, SPEC_PATH)

    assert [candidate["model_id"] for candidate in spec["candidates"]] == [
        "B0_LIGHTGBM",
        "B1_MLP",
    ]
    assert spec["schedule"]["model_fits"] == 14
    assert spec["diagnostics"]["selection_allowed"] is False
    assert spec["safeguards"]["final_oos_market_partitions_opened"] is False


def test_m5_spec_drift_is_rejected(tmp_path: Path) -> None:
    changed_path = tmp_path / "changed.json"
    changed = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    changed["schedule"]["seed"] = 19
    changed_path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(M5SpecError, match="content hash mismatch"):
        load_and_verify_m5_spec(PROJECT_ROOT, changed_path)
