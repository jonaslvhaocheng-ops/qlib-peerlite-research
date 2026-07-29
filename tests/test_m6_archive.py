from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from qlib_peerlite.governance.m6_archive import M6ArchiveError, verify_archived_m6_evidence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_REPLAY_RECEIPT = PROJECT_ROOT / "evidence/m6_5_pre_m7/m6_archival_replay_server_receipt.json"


def test_archival_verifier_accepts_m6_close_time_prefix_and_history() -> None:
    summary = verify_archived_m6_evidence(PROJECT_ROOT)

    assert summary.status == "PASS"
    assert summary.ledger_candidate_evaluations == 6
    assert summary.ledger_model_fits == 44
    assert (
        summary.ledger_prefix_bytes
        < (PROJECT_ROOT / "contracts/trial_ledger.jsonl").stat().st_size + 1
    )
    assert summary.pre_run_code_commit == "0af4572"


def test_archival_verifier_rejects_tampered_gate_copy(tmp_path: Path) -> None:
    gate_source = PROJECT_ROOT / "evidence/gates/M6_peerlite_gate.json"
    gate = json.loads(gate_source.read_text(encoding="utf-8"))
    gate["evidence"]["execution_spec"]["content_sha256"] = "0" * 64
    tampered = tmp_path / "m6_gate_tampered.json"
    tampered.write_text(json.dumps(gate), encoding="utf-8")

    with pytest.raises(M6ArchiveError, match="content hash"):
        verify_archived_m6_evidence(PROJECT_ROOT, gate_path=tampered)


def test_server_archival_replay_is_complete_read_only_and_exact() -> None:
    raw = SERVER_REPLAY_RECEIPT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "e2cacbf23cb4a4431bc2fadd9659fae8d7a7d75f607010ec18af68c3cc91a5ea"
    )
    receipt = json.loads(raw)
    unsigned = dict(receipt)
    unsigned.pop("content_sha256")
    canonical = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    assert receipt["content_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert receipt["status"] == "PASS"
    assert receipt["checkpoint_replays"] == 14
    assert receipt["model_fit_calls"] == 0
    assert receipt["trial_ledger_mutated"] is False
    assert receipt["ledger"]["sha256_before"] == receipt["ledger"]["sha256_after"]
    assert receipt["final_oos_market_partitions_opened"] is False
    assert receipt["product"]["date_max"] == "2024-12-17"
    assert receipt["frozen_source"]["git_commit"] == "0af45727d7f51af1c5a597d4a06fa5f95e34f758"
    assert sum(len(candidate["folds"]) for candidate in receipt["candidates"]) == 14
    assert all(
        fold["exact_match"] is True
        for candidate in receipt["candidates"]
        for fold in candidate["folds"]
    )
