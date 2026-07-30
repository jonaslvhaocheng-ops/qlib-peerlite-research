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
        if item["path"] == "contracts/trial_ledger.jsonl":
            continue
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
        expected_prefix_bytes=ledger["prefix_bytes"],
    )
    assert summary.candidate_evaluations == 9
    assert summary.model_fits == 64


def test_m8_final_oos_access_log_retains_frozen_prefix() -> None:
    expected = "6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190"
    prefix = (ROOT / "contracts/oos_access_log.jsonl").read_bytes()[:187]
    assert len(prefix) == 187
    assert hashlib.sha256(prefix).hexdigest() == expected


def test_m8_post_incident_closure_binds_forensic_and_closed_states() -> None:
    root = ROOT / "evidence/m8/forensics/m8_confirmation_20260730_v1"
    package = json.loads(
        (root / "closure_package_manifest.json").read_text(encoding="utf-8")
    )
    for name in ("execution_binding_closure", "contract_authorization_closure"):
        item = package[name]
        assert sha256_file(ROOT / item["path"]) == item["sha256"]
    assert sha256_file(ROOT / package["hold_gate"]["path"]) == package["hold_gate"][
        "sha256"
    ]

    execution = json.loads(
        (root / "execution_binding_closure.json").read_text(encoding="utf-8")
    )
    assert (
        sha256_file(ROOT / execution["executed_runner_forensic_path"])
        == execution["executed_runner_forensic_sha256"]
        == execution["executed_runner_frozen_sha256"]
    )
    assert (
        sha256_file(ROOT / execution["closed_entrypoint_path"])
        == execution["closed_entrypoint_sha256"]
    )
    for name in ("frozen_evaluator", "frozen_complete_verifier"):
        item = execution[name]
        assert sha256_file(ROOT / item["forensic_path"]) == item["frozen_sha256"]
        assert sha256_file(ROOT / item["closed_path"]) == item["closed_sha256"]

    authorization = json.loads(
        (root / "contract_authorization_closure.json").read_text(encoding="utf-8")
    )
    assert authorization["status"] == "FAIL_RETAINED_NOT_RETROACTIVELY_RATIFIABLE"
    assert authorization["retry_authorized"] is False
    assert authorization["promotion_authorized"] is False
