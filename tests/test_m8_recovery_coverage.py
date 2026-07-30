from __future__ import annotations

import json
from pathlib import Path

import pytest

from qlib_peerlite.governance.trial_ledger import RunIntent
from qlib_peerlite.m8_closure.recovery import (
    _read_jsonl,
    canonicalize_interrupted_m8_journal,
    write_canonical_jsonl,
)

ROOT = Path(__file__).parents[1]
SOURCE = (
    ROOT / "evidence/m8/failures/m8_confirmation_20260730_v1/trial_journal.jsonl"
)


def _intent() -> RunIntent:
    return RunIntent(
        run_id="m8_confirmation_20260730_v1_recovery",
        family_id="QLIB_PEERLITE_M8_CONFIRMATION_V1",
        execution_spec_content_sha256="1" * 64,
    )


def _events() -> list[dict[str, object]]:
    return [json.loads(line) for line in SOURCE.read_text().splitlines()]


def _write(path: Path, events: list[object]) -> None:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def test_recovery_happy_path_and_create_once(tmp_path: Path) -> None:
    events = canonicalize_interrupted_m8_journal(SOURCE, run_intent=_intent())
    assert len(events) == 4
    target = tmp_path / "recovery/trial_journal_v2.jsonl"
    write_canonical_jsonl(target, events)
    assert len(_read_jsonl(target)) == 4
    with pytest.raises(FileExistsError):
        write_canonical_jsonl(target, events)


def test_read_jsonl_rejects_blank_and_non_object(tmp_path: Path) -> None:
    blank = tmp_path / "blank.jsonl"
    blank.write_text("{}\n\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="blank legacy"):
        _read_jsonl(blank)
    scalar = tmp_path / "scalar.jsonl"
    scalar.write_text("1\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not an object"):
        _read_jsonl(scalar)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda rows: rows.pop(), "event sequence mismatch"),
        (
            lambda rows: rows[1].__setitem__("model_id", "OTHER"),
            "candidate identity mismatch",
        ),
        (
            lambda rows: rows[2].__setitem__("fold_id", "wf_2021"),
            "fit identity mismatch",
        ),
        (
            lambda rows: rows[3].__setitem__("status", "FAIL"),
            "completion event mismatch",
        ),
    ],
)
def test_recovery_rejects_incident_shape_changes(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    rows = _events()
    mutation(rows)
    path = tmp_path / "changed.jsonl"
    _write(path, rows)
    with pytest.raises(RuntimeError, match=message):
        canonicalize_interrupted_m8_journal(path, run_intent=_intent())
