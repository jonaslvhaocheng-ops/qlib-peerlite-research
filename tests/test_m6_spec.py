from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from qlib_peerlite.governance.m6_spec import M6SpecError, load_and_verify_m6_spec

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "contracts/immutable/m6_peerlite_execution_spec_v1.json"
GATE_PATH = PROJECT_ROOT / "evidence/gates/M6_peerlite_gate.json"


def content_hash(value: dict) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    payload = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_frozen_m6_peerlite_spec_is_fully_bound() -> None:
    if GATE_PATH.is_file():
        gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
        assert gate["status"] == "PASS"
        spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        assert spec["content_sha256"] == content_hash(spec)
        assert gate["evidence"]["execution_spec"]["sha256"] == hashlib.sha256(
            SPEC_PATH.read_bytes()
        ).hexdigest()
        assert (
            gate["evidence"]["execution_spec"]["content_sha256"]
            == spec["content_sha256"]
        )
    else:
        spec = load_and_verify_m6_spec(PROJECT_ROOT, SPEC_PATH)

    assert [candidate["model_id"] for candidate in spec["candidates"]] == [
        "PEERLITE_K16_MSE",
        "PEERLITE_K32_MSE",
    ]
    assert spec["schedule"]["model_fits"] == 15
    assert spec["schedule"]["cumulative_trials_after_success"]["model_fits"] == 44
    assert spec["deterministic_refit"]["exact_score_equality"] is True
    assert spec["safeguards"]["ccc_allowed"] is False
    assert spec["safeguards"]["market_gate_allowed"] is False


def test_m6_spec_drift_is_rejected(tmp_path: Path) -> None:
    changed_path = tmp_path / "changed.json"
    changed = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    changed["candidates"][0]["parameters"]["num_peers"] = 32
    changed_path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(M6SpecError, match="content hash mismatch"):
        load_and_verify_m6_spec(PROJECT_ROOT, changed_path)
