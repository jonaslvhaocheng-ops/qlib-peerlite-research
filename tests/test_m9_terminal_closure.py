from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _assert_prefix(path: Path, *, prefix_bytes: int, prefix_sha256: str) -> None:
    with path.open("rb") as handle:
        prefix = handle.read(prefix_bytes)
    assert len(prefix) == prefix_bytes
    assert hashlib.sha256(prefix).hexdigest() == prefix_sha256


def test_m9_failed_reauthorization_is_hash_bound_and_pre_training() -> None:
    root = ROOT / "evidence/m9/reauthorization_attempt_20260730_v1"
    receipt = json.loads((root / "validation_receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "FAIL"
    assert receipt["decision"] == "STOP_BEFORE_TRAINING"
    assert receipt["errors"] == [
        {
            "code": "FAIL_OUTCOME_INFORMED_CONTRACT",
            "path": "research.decisive_outcomes_seen",
            "message": (
                "a new frozen contract cannot be written after decisive outcomes "
                "were inspected; derive a contract and replace the final OOS"
            ),
        },
        {
            "code": "FAIL_TRIAL_BUDGET",
            "path": "method_scope.max_candidate_evaluations",
            "message": "must equal research_family.planned_new_trials",
        },
    ]
    assert receipt["side_effects"] == {
        "new_candidate_evaluations": 0,
        "new_model_fit_starts": 0,
        "final_oos_accesses": 0,
        "final_oos_opened": False,
    }
    for name in ("proposed_changes.json", "change_request.json", "planned_contract.json"):
        assert _sha256(root / name) == receipt["input_sha256"][name]
    assert _sha256(ROOT / "contracts/immutable/research_contract_m8_v1.json") == (
        receipt["input_sha256"]["parent_contract.json"]
    )
    trial_prefix = receipt["input_sha256"]["trial_ledger.jsonl"]
    _assert_prefix(
        ROOT / "contracts/trial_ledger.jsonl",
        prefix_bytes=trial_prefix["prefix_bytes"],
        prefix_sha256=trial_prefix["prefix_sha256"],
    )
    oos_prefix = receipt["input_sha256"]["oos_access_log.jsonl"]
    _assert_prefix(
        ROOT / "contracts/oos_access_log.jsonl",
        prefix_bytes=oos_prefix["prefix_bytes"],
        prefix_sha256=oos_prefix["prefix_sha256"],
    )
    parent_receipt = json.loads(
        (
            ROOT / "contracts/immutable/contract_validation_m8_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert receipt["validator"] == parent_receipt["validator"]
    assert receipt["validator_version"] == parent_receipt["validator_version"]
    assert (
        receipt["validator_bundle_sha256"]
        == parent_receipt["validator_bundle_sha256"]
    )
    child = json.loads((root / "planned_contract.json").read_text(encoding="utf-8"))
    change_request = json.loads(
        (root / "change_request.json").read_text(encoding="utf-8")
    )
    assert child["research"]["decisive_outcomes_seen"] is True
    assert change_request["outcome_reviewed"] is False
    assert change_request["final_oos_replaced"] is False
    assert receipt["lineage_observation"]["result"] == "INCONSISTENT_NOT_FREEZABLE"


def test_m9_terminal_gate_preserves_ledger_and_final_oos() -> None:
    path = ROOT / "evidence/gates/M9_step_nine_terminal_gate.json"
    gate = json.loads(path.read_text(encoding="utf-8"))
    receipt = json.loads(
        (
            ROOT
            / "evidence/m9/reauthorization_attempt_20260730_v1/validation_receipt.json"
        ).read_text(encoding="utf-8")
    )
    assert gate["status"] == "HOLD"
    assert gate["executed"] is True
    assert gate["completed"] is True
    assert gate["passed"] is False
    assert (
        gate["research_decision"]
        == "HOLD_REAUTHORIZATION_CONTRACT_INVALID"
    )
    assert gate["trial_accounting"] == {
        "candidate_evaluations": 9,
        "model_fit_starts": 64,
        "new_candidate_evaluations": 0,
        "new_model_fit_starts": 0,
    }
    assert gate["final_oos_access_count"] == 0
    assert gate["final_oos_opened"] is False
    assert gate["promotion_authorized"] is False
    assert gate["production_authorized"] is False
    assert gate["content_sha256"] == _canonical_hash(gate)
    for name in ("m8_gate", "failed_validation"):
        item = gate["evidence"][name]
        assert _sha256(ROOT / item["path"]) == item["sha256"]
    for name in ("trial_ledger", "oos_access_log"):
        item = gate["evidence"][name]
        _assert_prefix(
            ROOT / item["path"],
            prefix_bytes=item["prefix_bytes"],
            prefix_sha256=item["prefix_sha256"],
        )
    assert (
        gate["evidence"]["trial_ledger"]["prefix_sha256"]
        == receipt["input_sha256"]["trial_ledger.jsonl"]["prefix_sha256"]
    )
    assert (
        gate["evidence"]["oos_access_log"]["prefix_sha256"]
        == receipt["input_sha256"]["oos_access_log.jsonl"]["prefix_sha256"]
    )


def test_m9_oos_log_retains_initialized_untouched_prefix() -> None:
    events = [
        json.loads(line)
        for line in (ROOT / "contracts/oos_access_log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    assert events[0] == {
        "access_count": 0,
        "event": "OOS_LOG_INITIALIZED",
        "interval_end": "2026-06-30",
        "interval_start": "2025-01-01",
        "selection_uses": 0,
        "status": "UNTOUCHED",
        "timestamp": "2026-07-28T00:00:00+08:00",
    }
