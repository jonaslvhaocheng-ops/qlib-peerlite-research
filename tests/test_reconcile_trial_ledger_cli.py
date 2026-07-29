from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from qlib_peerlite.governance.artifacts import canonical_json_bytes
from qlib_peerlite.governance.trial_ledger import RunIntent

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/reconcile_trial_ledger.py"


def _intent() -> RunIntent:
    return RunIntent(
        run_id="m7_gate_20260728_v1",
        family_id="qlib-peerlite-a-share-daily-v0",
        execution_spec_content_sha256="b" * 64,
    )


def _event(intent: RunIntent, *, event: str, seq: int) -> dict:
    value: dict = {
        "schema_version": "qlib_peerlite_run_journal_event_v2",
        "run_id": intent.run_id,
        "event_seq": seq,
        "source_event_id": f"{intent.run_id}:{seq:06d}",
        "run_intent_sha256": intent.content_sha256,
        "event": event,
        "timestamp": "2026-07-28T12:00:00+08:00",
        "family_id": intent.family_id,
        "execution_spec_content_sha256": intent.execution_spec_content_sha256,
        "evaluation_id": "m7:gate:seed7",
        "model_id": "PEERLITE_K16_MSE_GATE",
        "seed": 7,
        "counts_as_candidate_evaluation": event == "CANDIDATE_EVALUATION_STARTED",
        "counts_as_model_fit": event == "MODEL_FIT_STARTED",
    }
    if event == "MODEL_FIT_STARTED":
        value["fit_id"] = "m7:gate:seed7:wf_2018"
        value["fold_id"] = "wf_2018"
    value["event_sha256"] = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return value


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))


def _command(
    *,
    journal: Path,
    ledger: Path,
    receipt: Path,
    journal_root: Path,
    intent: RunIntent,
    prefix_sha256: str | None = None,
) -> list[str]:
    return [
        sys.executable,
        str(SCRIPT),
        "--journal",
        str(journal),
        "--journal-root",
        str(journal_root),
        "--ledger",
        str(ledger),
        "--receipt",
        str(receipt),
        "--run-id",
        intent.run_id,
        "--family-id",
        intent.family_id,
        "--execution-spec-content-sha256",
        intent.execution_spec_content_sha256,
        "--expected-prefix-sha256",
        prefix_sha256 or hashlib.sha256(b"").hexdigest(),
        "--expected-prefix-candidates",
        "0",
        "--expected-prefix-fits",
        "0",
        "--expected-prefix-bytes",
        "0",
        "--candidate-limit",
        "27",
        "--model-fit-limit",
        "60",
    ]


def test_reconciliation_cli_is_idempotent_and_emits_receipt(tmp_path: Path) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "ledger_events.jsonl"
    ledger = tmp_path / "authority" / "ledger.jsonl"
    receipt_one = tmp_path / "receipt_one.json"
    receipt_two = tmp_path / "receipt_two.json"
    _write_jsonl(
        journal,
        [
            _event(intent, event="CANDIDATE_EVALUATION_STARTED", seq=1),
            _event(intent, event="MODEL_FIT_STARTED", seq=2),
        ],
    )

    first = subprocess.run(
        _command(
            journal=journal,
            ledger=ledger,
            receipt=receipt_one,
            journal_root=journal_root,
            intent=intent,
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    second = subprocess.run(
        _command(
            journal=journal,
            ledger=ledger,
            receipt=receipt_two,
            journal_root=journal_root,
            intent=intent,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(receipt_one.read_text(encoding="utf-8"))["appended_events"] == 2
    assert json.loads(receipt_two.read_text(encoding="utf-8"))["appended_events"] == 0
    assert json.loads(receipt_one.read_text(encoding="utf-8"))["candidate_evaluations_after"] == 1
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2


def test_reconciliation_cli_fails_without_partial_receipt_for_bad_event(tmp_path: Path) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "ledger_events.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    receipt = tmp_path / "receipt.json"
    journal.parent.mkdir(parents=True)
    journal.write_text('{"event":"MODEL_FIT_STARTED"}', encoding="utf-8")

    completed = subprocess.run(
        _command(
            journal=journal,
            ledger=ledger,
            receipt=receipt,
            journal_root=journal_root,
            intent=intent,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not receipt.exists()
    assert not ledger.exists()


def test_reconciliation_cli_rejects_wrong_prefix_without_receipt(tmp_path: Path) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "ledger_events.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    receipt = tmp_path / "receipt.json"
    _write_jsonl(journal, [_event(intent, event="MODEL_FIT_STARTED", seq=1)])

    completed = subprocess.run(
        _command(
            journal=journal,
            ledger=ledger,
            receipt=receipt,
            journal_root=journal_root,
            intent=intent,
            prefix_sha256="c" * 64,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not receipt.exists()
    assert not ledger.exists()
