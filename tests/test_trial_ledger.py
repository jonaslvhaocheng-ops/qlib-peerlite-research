from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from qlib_peerlite.governance import trial_ledger
from qlib_peerlite.governance.artifacts import canonical_json_bytes
from qlib_peerlite.governance.trial_ledger import (
    LedgerPrefixBinding,
    RunIntent,
    TrialLedgerError,
    TrialLimits,
    assert_journal_starts_reconciled,
    reconcile_started_events,
    verify_ledger_prefix,
)


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _intent() -> RunIntent:
    return RunIntent(
        run_id="m7_ccc_20260728_v1",
        family_id="qlib-peerlite-a-share-daily-v0",
        execution_spec_content_sha256="a" * 64,
    )


def _event(
    intent: RunIntent,
    *,
    event: str,
    event_seq: int,
    evaluation_id: str = "m7:CCC:seed7",
    fit_id: str | None = None,
    fold_id: str | None = None,
) -> dict:
    counted_candidate = event == "CANDIDATE_EVALUATION_STARTED"
    counted_fit = event == "MODEL_FIT_STARTED"
    value: dict = {
        "schema_version": "qlib_peerlite_run_journal_event_v2",
        "run_id": intent.run_id,
        "event_seq": event_seq,
        "source_event_id": f"{intent.run_id}:{event_seq:06d}",
        "run_intent_sha256": intent.content_sha256,
        "event": event,
        "timestamp": "2026-07-28T12:00:00+08:00",
        "family_id": intent.family_id,
        "execution_spec_content_sha256": intent.execution_spec_content_sha256,
        "evaluation_id": evaluation_id,
        "model_id": "PEERLITE_K16_CCC",
        "seed": 7,
        "counts_as_candidate_evaluation": counted_candidate,
        "counts_as_model_fit": counted_fit,
    }
    if counted_fit:
        value["fit_id"] = fit_id or "m7:CCC:seed7:wf_2018"
        value["fold_id"] = fold_id or "wf_2018"
    value["event_sha256"] = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return value


def _prefix(ledger: Path) -> LedgerPrefixBinding:
    return LedgerPrefixBinding(
        sha256=_sha(ledger),
        candidate_evaluations=sum(
            json.loads(line).get("counts_as_candidate_evaluation") is True
            for line in ledger.read_text(encoding="utf-8").splitlines()
        ),
        model_fits=sum(
            json.loads(line).get("counts_as_model_fit") is True
            for line in ledger.read_text(encoding="utf-8").splitlines()
        ),
    )


def _limits() -> TrialLimits:
    return TrialLimits(candidate_evaluations=27, model_fits=60)


def test_ledger_prefix_remains_verifiable_after_later_append(tmp_path: Path) -> None:
    intent = _intent()
    ledger = tmp_path / "trial_ledger.jsonl"
    _write_jsonl(
        ledger,
        [
            _event(intent, event="CANDIDATE_EVALUATION_STARTED", event_seq=1),
            _event(intent, event="MODEL_FIT_STARTED", event_seq=2),
        ],
    )
    close_hash = _sha(ledger)
    close_bytes = ledger.stat().st_size
    with ledger.open("ab") as handle:
        handle.write(
            canonical_json_bytes(_event(intent, event="MODEL_FIT_STARTED", event_seq=3)) + b"\n"
        )

    summary = verify_ledger_prefix(
        ledger,
        expected_prefix_sha256=close_hash,
        expected_counts={"candidate_evaluations": 1, "model_fits": 1},
        expected_prefix_bytes=close_bytes,
    )

    assert summary.prefix_bytes == close_bytes
    assert summary.candidate_evaluations == 1
    assert summary.model_fits == 1
    assert ledger.stat().st_size > summary.prefix_bytes


def test_reconciliation_is_idempotent_counts_starts_and_preflights(tmp_path: Path) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "ledger_events.jsonl"
    ledger = tmp_path / "authority" / "trial_ledger.jsonl"
    _write_jsonl(
        journal,
        [
            _event(intent, event="CANDIDATE_EVALUATION_STARTED", event_seq=1),
            _event(intent, event="MODEL_FIT_STARTED", event_seq=2),
        ],
    )

    with pytest.raises(TrialLedgerError, match="not reconciled"):
        assert_journal_starts_reconciled(
            journal, ledger, run_intent=intent, journal_root=journal_root
        )

    first = reconcile_started_events(
        journal,
        ledger,
        run_intent=intent,
        journal_root=journal_root,
        expected_ledger_prefix=LedgerPrefixBinding.empty(),
        limits=_limits(),
    )
    second = reconcile_started_events(
        journal,
        ledger,
        run_intent=intent,
        journal_root=journal_root,
        expected_ledger_prefix=LedgerPrefixBinding.empty(),
        limits=_limits(),
    )
    assert_journal_starts_reconciled(journal, ledger, run_intent=intent, journal_root=journal_root)
    events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    assert first.appended_events == 2
    assert first.candidate_evaluations_after == 1
    assert first.model_fits_after == 1
    assert second.appended_events == 0
    assert len(events) == 2
    assert events[1]["outcome"] == "STARTED_OR_INTERRUPTED_RETAINED"
    assert events[0]["source_journal_relpath"] == f"{intent.run_id}/ledger_events.jsonl"
    assert not Path(events[0]["source_journal_relpath"]).is_absolute()


def test_reconciliation_rejects_prefix_mismatch_or_budget_overrun_without_writing(
    tmp_path: Path,
) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "ledger_events.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    _write_jsonl(ledger, [])
    _write_jsonl(journal, [_event(intent, event="MODEL_FIT_STARTED", event_seq=1)])
    before = ledger.read_bytes()

    with pytest.raises(TrialLedgerError, match="prefix"):
        reconcile_started_events(
            journal,
            ledger,
            run_intent=intent,
            journal_root=journal_root,
            expected_ledger_prefix=LedgerPrefixBinding("b" * 64, 0, 0),
            limits=_limits(),
        )
    assert ledger.read_bytes() == before

    with pytest.raises(TrialLedgerError, match="model-fit limit"):
        reconcile_started_events(
            journal,
            ledger,
            run_intent=intent,
            journal_root=journal_root,
            expected_ledger_prefix=LedgerPrefixBinding.empty(),
            limits=TrialLimits(candidate_evaluations=1, model_fits=0),
        )
    assert ledger.read_bytes() == before


def test_reconciliation_rejects_semantic_id_collision_and_mutated_idempotent_payload(
    tmp_path: Path,
) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal_one = journal_root / intent.run_id / "one.jsonl"
    journal_two = journal_root / intent.run_id / "two.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    candidate = _event(intent, event="CANDIDATE_EVALUATION_STARTED", event_seq=1)
    _write_jsonl(journal_one, [candidate])
    reconcile_started_events(
        journal_one,
        ledger,
        run_intent=intent,
        journal_root=journal_root,
        expected_ledger_prefix=LedgerPrefixBinding.empty(),
        limits=_limits(),
    )
    before = ledger.read_bytes()

    collision = _event(intent, event="CANDIDATE_EVALUATION_STARTED", event_seq=2)
    _write_jsonl(journal_two, [collision])
    with pytest.raises(TrialLedgerError, match="evaluation_id"):
        reconcile_started_events(
            journal_two,
            ledger,
            run_intent=intent,
            journal_root=journal_root,
            expected_ledger_prefix=_prefix(ledger),
            limits=_limits(),
        )
    assert ledger.read_bytes() == before

    mutated = dict(candidate)
    mutated["model_id"] = "PEERLITE_K16_GATE"
    mutated["event_sha256"] = hashlib.sha256(
        canonical_json_bytes(
            {key: value for key, value in mutated.items() if key != "event_sha256"}
        )
    ).hexdigest()
    _write_jsonl(journal_two, [mutated])
    with pytest.raises(TrialLedgerError, match="source_event_id"):
        reconcile_started_events(
            journal_two,
            ledger,
            run_intent=intent,
            journal_root=journal_root,
            expected_ledger_prefix=_prefix(ledger),
            limits=_limits(),
        )
    assert ledger.read_bytes() == before


def test_reconciliation_is_atomic_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "journal.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    _write_jsonl(ledger, [{"event": "LEDGER_INITIALIZED"}])
    _write_jsonl(journal, [_event(intent, event="CANDIDATE_EVALUATION_STARTED", event_seq=1)])
    before = ledger.read_bytes()

    def fail_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(trial_ledger, "_atomic_replace_bytes", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        reconcile_started_events(
            journal,
            ledger,
            run_intent=intent,
            journal_root=journal_root,
            expected_ledger_prefix=_prefix(ledger),
            limits=_limits(),
        )
    assert ledger.read_bytes() == before


def test_reconciliation_rejects_bad_journal_before_creating_or_changing_ledger(
    tmp_path: Path,
) -> None:
    intent = _intent()
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "journal.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b'{"not":"complete"}')

    with pytest.raises(TrialLedgerError, match="invalid JSONL"):
        reconcile_started_events(
            journal,
            ledger,
            run_intent=intent,
            journal_root=journal_root,
            expected_ledger_prefix=LedgerPrefixBinding.empty(),
            limits=_limits(),
        )
    assert not ledger.exists()
