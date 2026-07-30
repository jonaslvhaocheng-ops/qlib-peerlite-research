from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qlib_peerlite.governance.artifacts import canonical_json_bytes, sha256_file
from qlib_peerlite.governance.trial_ledger import verify_ledger_prefix

ROOT = Path(__file__).parents[1]


def test_m8_hold_gate_is_hash_bound_and_does_not_claim_completion() -> None:
    path = ROOT / "evidence/gates/M8_institutional_evaluation_gate.json"
    gate = json.loads(path.read_text(encoding="utf-8"))
    supplied = gate.pop("content_sha256")
    assert supplied == hashlib.sha256(canonical_json_bytes(gate)).hexdigest()
    assert gate["status"] == "HOLD"
    assert gate["passed"] is False
    assert gate["executed"] is True
    assert gate["completed"] is False
    assert gate["research_decision"] == "HOLD_OPERATIONAL_CONFIRMATION_INCOMPLETE"
    assert gate["final_oos_access_count"] == 0
    assert gate["final_oos_opened"] is False
    assert gate["promotion_authorized"] is False


def test_m8_hold_evidence_and_authoritative_counts_match() -> None:
    gate = json.loads(
        (ROOT / "evidence/gates/M8_institutional_evaluation_gate.json").read_text(
            encoding="utf-8"
        )
    )
    for item in gate["evidence"].values():
        path = ROOT / item["path"]
        assert sha256_file(path) == item["sha256"]

    ledger = gate["evidence"]["trial_ledger"]
    summary = verify_ledger_prefix(
        ROOT / ledger["path"],
        expected_prefix_sha256=ledger["sha256"],
        expected_counts={
            "candidate_evaluations": ledger["candidate_evaluations"],
            "model_fits": ledger["model_fits"],
        },
    )
    assert summary.candidate_evaluations == 9
    assert summary.model_fits == 64


def test_m8_final_oos_access_log_remains_at_frozen_prefix() -> None:
    expected = "6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190"
    assert sha256_file(ROOT / "contracts/oos_access_log.jsonl") == expected
