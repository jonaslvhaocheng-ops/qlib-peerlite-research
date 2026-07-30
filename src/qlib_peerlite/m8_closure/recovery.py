"""Fail-closed recovery helpers for the interrupted M8 confirmation run."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from qlib_peerlite.governance.artifacts import canonical_json_bytes
from qlib_peerlite.governance.trial_ledger import RunIntent

MODEL_ID = "PEERLITE_K16_MSE"
SEED = 19
EXPECTED_FOLDS = ("wf_2018", "wf_2019", "wf_2020")
COUNTED_EVENTS = ("CANDIDATE_EVALUATION_STARTED", "MODEL_FIT_STARTED")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise RuntimeError(f"blank legacy journal line {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"legacy journal line {line_number} is not an object")
        events.append(value)
    return events


def _event_hash(event: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(event)).hexdigest()


def canonicalize_interrupted_m8_journal(
    legacy_journal: Path,
    *,
    run_intent: RunIntent,
) -> list[dict[str, Any]]:
    """Convert the exact retained v1 incident into counted v2 start events.

    The accepted shape is intentionally narrow. Any additional, missing or
    reordered event fails closed so recovery cannot reinterpret a later run.
    """

    events = _read_jsonl(legacy_journal)
    expected_types = [
        "M8_CONFIRMATION_STARTED",
        "CANDIDATE_EVALUATION_STARTED",
        "MODEL_FIT_STARTED",
        "MODEL_FIT_COMPLETED",
        "MODEL_FIT_STARTED",
        "MODEL_FIT_COMPLETED",
        "MODEL_FIT_STARTED",
    ]
    actual_types = [event.get("event") for event in events]
    if actual_types != expected_types:
        raise RuntimeError("legacy M8 journal event sequence mismatch")

    candidate = events[1]
    evaluation_id = candidate.get("evaluation_id")
    if (
        candidate.get("model_id") != MODEL_ID
        or candidate.get("seed") != SEED
        or candidate.get("counts_as_candidate_evaluation") is not True
        or not isinstance(evaluation_id, str)
        or not evaluation_id
    ):
        raise RuntimeError("legacy M8 candidate identity mismatch")

    fit_starts = [events[index] for index in (2, 4, 6)]
    for fold_id, event in zip(EXPECTED_FOLDS, fit_starts, strict=True):
        expected_fit_id = f"{evaluation_id}:{fold_id}"
        if (
            event.get("evaluation_id") != evaluation_id
            or event.get("fit_id") != expected_fit_id
            or event.get("model_id") != MODEL_ID
            or event.get("seed") != SEED
            or event.get("fold_id") != fold_id
            or event.get("counts_as_model_fit") is not True
        ):
            raise RuntimeError(f"legacy M8 fit identity mismatch: {fold_id}")
    for completed, started in zip((events[3], events[5]), fit_starts[:2], strict=True):
        if (
            completed.get("fit_id") != started["fit_id"]
            or completed.get("status") != "PASS"
            or completed.get("counts_as_model_fit") is not False
        ):
            raise RuntimeError("legacy M8 completion event mismatch")

    counted = [candidate, *fit_starts]
    canonical: list[dict[str, Any]] = []
    for sequence, source in enumerate(counted, 1):
        event_type = source["event"]
        event: dict[str, Any] = {
            "schema_version": "qlib_peerlite_run_journal_event_v2",
            "run_id": run_intent.run_id,
            "event_seq": sequence,
            "source_event_id": f"{run_intent.run_id}:{sequence:06d}",
            "run_intent_sha256": run_intent.content_sha256,
            "event": event_type,
            "timestamp": source["timestamp"],
            "family_id": run_intent.family_id,
            "execution_spec_content_sha256": (
                run_intent.execution_spec_content_sha256
            ),
            "evaluation_id": evaluation_id,
            "model_id": MODEL_ID,
            "seed": SEED,
            "purpose": "M8_CONFIRMATION_RETAINED_FAILURE",
            "counts_as_candidate_evaluation": (
                event_type == "CANDIDATE_EVALUATION_STARTED"
            ),
            "counts_as_model_fit": event_type == "MODEL_FIT_STARTED",
        }
        if event_type == "MODEL_FIT_STARTED":
            event["fit_id"] = source["fit_id"]
            event["fold_id"] = source["fold_id"]
        event["event_sha256"] = _event_hash(event)
        canonical.append(event)
    return canonical


def write_canonical_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    """Create the recovery journal once; never overwrite retained evidence."""

    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(canonical_json_bytes(event) + b"\n" for event in events)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
