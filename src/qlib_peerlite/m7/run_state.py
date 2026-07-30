from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

from qlib_peerlite.governance.artifacts import canonical_json_bytes
from qlib_peerlite.governance.trial_ledger import (
    RunIntent,
    TrialLedgerError,
    assert_journal_starts_reconciled,
)

from . import M7StateError
from .market_state import M7_CANDIDATES

M7_FAMILY_ID = "QLIB_PEERLITE_M7_INITIAL_SCREEN_V1"
M7_FITS = (
    ("wf_2018", "ROLLING_SCREEN_FIT"),
    ("wf_2019", "ROLLING_SCREEN_FIT"),
    ("wf_2020", "ROLLING_SCREEN_FIT"),
    ("wf_2021", "ROLLING_SCREEN_FIT"),
    ("wf_2022", "ROLLING_SCREEN_FIT"),
    ("wf_2023", "ROLLING_SCREEN_FIT"),
    ("wf_2024", "ROLLING_SCREEN_FIT"),
    ("wf_2018", "DETERMINISTIC_REFIT"),
)


def _strict_canonical_receipt(path: str | Path) -> dict[str, object]:
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise M7StateError("terminal fit receipt is not canonical UTF-8 JSON")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in pairs:
            if key in output:
                raise M7StateError("terminal fit receipt contains duplicate keys")
            output[key] = value
        return output

    try:
        receipt = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(
                M7StateError("terminal fit receipt contains non-finite JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M7StateError("terminal fit receipt is not strict UTF-8 JSON") from exc
    if not isinstance(receipt, dict):
        raise M7StateError("terminal fit receipt schema mismatch")
    if raw != canonical_json_bytes(receipt) + b"\n":
        raise M7StateError("terminal fit receipt is not canonical JSON")
    return receipt


@dataclass(frozen=True)
class M7RunState:
    status: str = "NOT_AUTHORIZED"
    candidate_index: int = 0
    fit_index: int = 0
    candidate_starts: int = 6
    fit_starts: int = 44
    active_event_sha256: str | None = None


def authorize_run(prerequisite_bundle_sha256: str) -> M7RunState:
    if len(prerequisite_bundle_sha256) != 64:
        raise M7StateError("prerequisite bundle SHA256 is invalid")
    return M7RunState(status="PREREQUISITES_VERIFIED")


def start_next_candidate(state: M7RunState) -> M7RunState:
    if state.status not in {"PREREQUISITES_VERIFIED", "CANDIDATE_COMPLETE"}:
        raise M7StateError("candidate start is out of order")
    if state.candidate_index >= len(M7_CANDIDATES) or state.candidate_starts >= 8:
        raise M7StateError("candidate start exceeds M7 scope or cap")
    return replace(
        state,
        status="CANDIDATE_INTENT",
        candidate_starts=state.candidate_starts + 1,
        fit_index=0,
    )


def acknowledge_candidate(state: M7RunState, event_sha256: str) -> M7RunState:
    if state.status != "CANDIDATE_INTENT" or len(event_sha256) != 64:
        raise M7StateError("candidate acknowledgement is invalid")
    return replace(state, status="CANDIDATE_RECONCILED", active_event_sha256=event_sha256)


def start_next_fit(state: M7RunState) -> M7RunState:
    if state.status not in {"CANDIDATE_RECONCILED", "FIT_SUCCESS"}:
        raise M7StateError("fit start is out of order")
    if state.fit_index >= len(M7_FITS) or state.fit_starts >= 60:
        raise M7StateError("fit start exceeds M7 scope or cap")
    return replace(state, status="FIT_INTENT", fit_starts=state.fit_starts + 1)


def acknowledge_fit(state: M7RunState, event_sha256: str) -> M7RunState:
    if state.status != "FIT_INTENT" or len(event_sha256) != 64:
        raise M7StateError("fit acknowledgement is invalid")
    return replace(state, status="FIT_AUTHORIZED", active_event_sha256=event_sha256)


def finish_active_fit(state: M7RunState, outcome: str) -> M7RunState:
    if state.status != "FIT_AUTHORIZED" or outcome not in {"SUCCESS", "FAILED", "INTERRUPTED"}:
        raise M7StateError("fit completion is invalid")
    if outcome != "SUCCESS":
        return replace(state, status=f"FIT_{outcome}")
    return replace(state, status="FIT_SUCCESS", fit_index=state.fit_index + 1)


def finish_candidate(state: M7RunState) -> M7RunState:
    if state.status != "FIT_SUCCESS" or state.fit_index != len(M7_FITS):
        raise M7StateError("candidate cannot finish before all fixed fits succeed")
    next_index = state.candidate_index + 1
    terminal = "RUN_SCREEN_COMPLETE" if next_index == len(M7_CANDIDATES) else "CANDIDATE_COMPLETE"
    return replace(
        state,
        status=terminal,
        candidate_index=next_index,
        active_event_sha256=None,
    )


def recover_from_persisted_evidence(
    state: M7RunState,
    *,
    journal_path: str | Path,
    ledger_path: str | Path,
    run_intent: RunIntent,
    journal_root: str | Path,
    source_event_id: str,
    terminal_receipt_path: str | Path | None = None,
) -> M7RunState:
    if state.status == "RUN_SCREEN_COMPLETE":
        return state
    if state.status != "FIT_INTENT":
        raise M7StateError("recovery is only valid for a pending fit intent")
    try:
        assert_journal_starts_reconciled(
            journal_path,
            ledger_path,
            run_intent=run_intent,
            journal_root=journal_root,
        )
    except TrialLedgerError:
        return state
    events = [
        json.loads(line)
        for line in Path(journal_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [event for event in events if event.get("source_event_id") == source_event_id]
    if len(matches) != 1:
        raise M7StateError("recovery source event is missing or duplicated")
    event = matches[0]
    candidate_id = M7_CANDIDATES[state.candidate_index]
    fold_id, purpose = M7_FITS[state.fit_index]
    expected = {
        "event": "MODEL_FIT_STARTED",
        "model_id": candidate_id,
        "seed": 7,
        "fold_id": fold_id,
        "purpose": purpose,
    }
    if any(event.get(key) != value for key, value in expected.items()):
        raise M7StateError("recovery source event identity mismatch")
    event_sha256 = str(event.get("event_sha256"))
    if terminal_receipt_path is None:
        return replace(
            state,
            status="FIT_INTERRUPTED",
            active_event_sha256=event_sha256,
        )
    receipt = _strict_canonical_receipt(terminal_receipt_path)
    required = {
        "schema_version",
        "run_id",
        "source_event_id",
        "model_id",
        "seed",
        "fold_id",
        "purpose",
        "outcome",
        "checkpoint_sha256",
        "output_sha256",
        "receipt_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise M7StateError("terminal fit receipt schema mismatch")
    if receipt.get("schema_version") != "qlib_peerlite_fit_terminal_v1":
        raise M7StateError("terminal fit receipt schema version mismatch")
    claimed = receipt.pop("receipt_sha256")
    expected_receipt = hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
    if claimed != expected_receipt:
        raise M7StateError("terminal fit receipt hash mismatch")
    identity = {
        "run_id": run_intent.run_id,
        "source_event_id": source_event_id,
        "model_id": candidate_id,
        "seed": 7,
        "fold_id": fold_id,
        "purpose": purpose,
        "outcome": "SUCCESS",
    }
    if any(receipt.get(key) != value for key, value in identity.items()):
        raise M7StateError("terminal fit receipt identity mismatch")
    for name in ("checkpoint_sha256", "output_sha256"):
        value = receipt.get(name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise M7StateError(f"terminal fit receipt {name} is invalid")
    return replace(state, status="FIT_SUCCESS", fit_index=state.fit_index + 1)


__all__ = [
    "M7_FAMILY_ID",
    "M7_FITS",
    "M7RunState",
    "acknowledge_candidate",
    "acknowledge_fit",
    "authorize_run",
    "finish_active_fit",
    "finish_candidate",
    "recover_from_persisted_evidence",
    "start_next_candidate",
    "start_next_fit",
]
