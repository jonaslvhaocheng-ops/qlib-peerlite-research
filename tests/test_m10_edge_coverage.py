from __future__ import annotations

import errno
import json
import os
import stat
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
import yaml

from qlib_peerlite.governance.artifacts import sha256_file
from qlib_peerlite.production import ProductionError
from qlib_peerlite.production import cycle as cycle_module
from qlib_peerlite.production import policy as policy_module
from qlib_peerlite.production import schedule as schedule_module
from qlib_peerlite.production import signals as signals_module

SHANGHAI = ZoneInfo("Asia/Shanghai")


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def base_policy(tmp_path: Path) -> tuple[dict[str, object], Path]:
    calendar_path = tmp_path / "calendar.json"
    dump(
        calendar_path,
        {
            "schema_version": "qlib_peerlite_session_calendar_v1",
            "timezone": "Asia/Shanghai",
            "sessions": ["2026-07-31"],
        },
    )
    gate_path = tmp_path / "gate.json"
    dump(
        gate_path,
        {
            "gate_id": "M9-STEP-NINE-TERMINAL-CLOSURE",
            "status": "HOLD",
            "research_decision": "HOLD_REAUTHORIZATION_CONTRACT_INVALID",
            "promotion_authorized": False,
            "production_authorized": False,
            "final_oos_opened": False,
            "final_oos_access_count": 0,
            "active_candidate": "PEERLITE_K16_MSE",
        },
    )
    payload: dict[str, object] = {
        "schema_version": "qlib_peerlite_shadow_policy_v1",
        "capability": "SHADOW_ONLY",
        "input_track": "SYNTHETIC",
        "execution_mode": "paper",
        "timezone": "Asia/Shanghai",
        "session_close": "15:00",
        "run_after": "16:30",
        "rebalance_weekday": 4,
        "max_signal_age_minutes": 180,
        "future_skew_seconds": 30,
        "max_input_bytes": 100000,
        "max_rows": 100,
        "max_instruments": 10,
        "top_fraction": 0.5,
        "max_name_weight": 0.5,
        "max_paper_intents": 10,
        "reservation_timeout_seconds": 60,
        "m9_gate_path": str(gate_path),
        "m9_gate_sha256": sha256_file(gate_path),
        "calendar_path": str(calendar_path),
        "calendar_sha256": sha256_file(calendar_path),
        "permitted_model_ids": ["SYNTHETIC_PEERLITE"],
    }
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return payload, path


def valid_snapshot(tmp_path: Path, policy: object) -> tuple[Path, object, dict[str, object]]:
    path = tmp_path / "scores.parquet"
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-07-31", "2026-07-31"]),
            "instrument": ["SYNTH_A", "SYNTH_B"],
            "score": [1.0, 0.0],
            "model_id": ["SYNTHETIC_PEERLITE", "SYNTHETIC_PEERLITE"],
            "fold_id": ["shadow", "shadow"],
        }
    )
    frame.to_parquet(path, index=False)
    snapshot = signals_module.capture_prediction(path, policy)
    manifest: dict[str, object] = {
        "schema_version": "qlib_peerlite_score_source_v1",
        "score_schema_version": "qlib_peerlite_score_v1",
        "track": "SYNTHETIC",
        "predictions_sha256": snapshot.sha256,
        "row_count": 2,
        "model_id": "SYNTHETIC_PEERLITE",
        "signal_date": "2026-07-31",
        "prediction_time": "2026-07-31T15:30:00+08:00",
    }
    return path, snapshot, manifest


def assert_code(code: str, callback: object) -> None:
    with pytest.raises(ProductionError) as error:
        callback()
    assert error.value.code == code


@pytest.mark.parametrize(
    "mutation",
    [
        {"m9_gate_sha256": "x" * 64},
        {"permitted_model_ids": ["SYNTHETIC_PEERLITE", "SYNTHETIC_PEERLITE"]},
        {"permitted_model_ids": [" "]},
        {"session_close": "bad"},
        {"session_close": "24:00"},
    ],
)
def test_policy_validation_edges(tmp_path: Path, mutation: dict[str, object]) -> None:
    payload, path = base_policy(tmp_path)
    payload.update(mutation)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    assert_code("INVALID_POLICY", lambda: policy_module.load_shadow_policy(path))


def test_policy_input_and_gate_parse_edges(tmp_path: Path) -> None:
    payload, path = base_policy(tmp_path)
    missing = tmp_path / "missing.yaml"
    assert_code("INVALID_POLICY", lambda: policy_module.load_shadow_policy(missing))
    link = tmp_path / "policy-link"
    link.symlink_to(path)
    assert_code("INVALID_POLICY", lambda: policy_module.load_shadow_policy(link))
    path.write_bytes(b"\xff")
    assert_code("INVALID_POLICY", lambda: policy_module.load_shadow_policy(path))
    path.write_text("- item", encoding="utf-8")
    assert_code("INVALID_POLICY", lambda: policy_module.load_shadow_policy(path))
    payload, path = base_policy(tmp_path)
    payload["items"] = [{"safe": 1}, {"password_hint": 2}]
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    assert_code("UNSAFE_POLICY_KEY", lambda: policy_module.load_shadow_policy(path))

    payload, path = base_policy(tmp_path)
    policy = policy_module.load_shadow_policy(path)
    gate = Path(policy.m9_gate_path)
    gate.write_text("{", encoding="utf-8")
    changed = policy.model_copy(update={"m9_gate_sha256": sha256_file(gate)})
    assert_code("M9_GATE_INVALID", lambda: policy_module.authorize_shadow(changed, tmp_path))


@pytest.mark.parametrize(
    "calendar",
    [
        None,
        {"schema_version": "bad", "timezone": "Asia/Shanghai", "sessions": []},
        {
            "schema_version": "qlib_peerlite_session_calendar_v1",
            "timezone": "Asia/Shanghai",
            "sessions": [],
        },
        {
            "schema_version": "qlib_peerlite_session_calendar_v1",
            "timezone": "Asia/Shanghai",
            "sessions": [1],
        },
        {
            "schema_version": "qlib_peerlite_session_calendar_v1",
            "timezone": "Asia/Shanghai",
            "sessions": ["bad"],
        },
        {
            "schema_version": "qlib_peerlite_session_calendar_v1",
            "timezone": "Asia/Shanghai",
            "sessions": ["2026-07-31", "2026-07-31"],
        },
    ],
)
def test_calendar_invalid_content(tmp_path: Path, calendar: object) -> None:
    _, path = base_policy(tmp_path)
    policy = policy_module.load_shadow_policy(path)
    calendar_path = Path(policy.calendar_path)
    if calendar is None:
        calendar_path.write_text("{", encoding="utf-8")
    else:
        dump(calendar_path, calendar)
    policy = policy.model_copy(update={"calendar_sha256": sha256_file(calendar_path)})
    assert_code("CALENDAR_INVALID", lambda: schedule_module.load_calendar(policy))


def test_calendar_missing_hash_and_symlink(tmp_path: Path) -> None:
    _, path = base_policy(tmp_path)
    policy = policy_module.load_shadow_policy(path)
    assert_code(
        "CALENDAR_HASH_MISMATCH",
        lambda: schedule_module.load_calendar(
            policy.model_copy(update={"calendar_sha256": "0" * 64})
        ),
    )
    calendar = Path(policy.calendar_path)
    link = tmp_path / "calendar-link"
    link.symlink_to(calendar)
    linked = policy.model_copy(update={"calendar_path": str(link)})
    assert_code("CALENDAR_MISSING", lambda: schedule_module.load_calendar(linked))


def test_capture_prediction_error_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, policy_path = base_policy(tmp_path)
    policy = policy_module.load_shadow_policy(policy_path)
    assert_code(
        "UNSAFE_INPUT_PATH",
        lambda: signals_module.capture_prediction(tmp_path / "missing.parquet", policy),
    )
    assert_code("UNSAFE_INPUT_PATH", lambda: signals_module.capture_prediction(tmp_path, policy))
    invalid = tmp_path / "invalid.parquet"
    invalid.write_bytes(b"no")
    assert_code("INVALID_PARQUET", lambda: signals_module.capture_prediction(invalid, policy))
    wrong = tmp_path / "wrong.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(wrong, index=False)
    assert_code("SCORE_SCHEMA_MISMATCH", lambda: signals_module.capture_prediction(wrong, policy))

    _, path, = base_policy(tmp_path / "growth")
    grow_policy = policy_module.load_shadow_policy(path).model_copy(update={"max_input_bytes": 1})
    one = tmp_path / "one"
    one.write_bytes(b"12")
    real_fstat = signals_module.os.fstat
    monkeypatch.setattr(
        signals_module.os,
        "fstat",
        lambda descriptor: SimpleNamespace(st_mode=stat.S_IFREG, st_size=0),
    )
    assert_code("INPUT_TOO_LARGE", lambda: signals_module.capture_prediction(one, grow_policy))
    monkeypatch.setattr(signals_module.os, "fstat", real_fstat)


def test_manifest_and_signal_time_edges(tmp_path: Path) -> None:
    _, policy_path = base_policy(tmp_path)
    policy = policy_module.load_shadow_policy(policy_path)
    _, snapshot, manifest = valid_snapshot(tmp_path, policy)
    bad = dict(manifest)
    bad["extra"] = 1
    assert_code(
        "SOURCE_MANIFEST_INVALID",
        lambda: signals_module.validate_source_manifest(bad, snapshot, policy),
    )
    bad = dict(manifest)
    bad["track"] = "STRICT"
    assert_code(
        "SOURCE_MANIFEST_MISMATCH",
        lambda: signals_module.validate_source_manifest(bad, snapshot, policy),
    )
    schedule = schedule_module.ScheduleDecision(True, "DUE", "2026-07-31")
    as_of = datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI)
    cases = [
        ("PREDICTION_TIME_INVALID", {"prediction_time": 1}, policy, snapshot),
        ("PREDICTION_TIME_INVALID", {"prediction_time": "bad"}, policy, snapshot),
        (
            "PREDICTION_TIME_INVALID",
            {"prediction_time": "2026-07-31T15:30:00"},
            policy,
            snapshot,
        ),
        (
            "PREDICTION_TIME_INVALID",
            {"prediction_time": "2026-07-31T14:59:00+08:00"},
            policy,
            snapshot,
        ),
        (
            "FUTURE_SIGNAL",
            {"prediction_time": "2026-07-31T16:46:00+08:00"},
            policy,
            snapshot,
        ),
        (
            "STALE_SIGNAL",
            {"prediction_time": "2026-07-31T15:01:00+08:00"},
            policy.model_copy(update={"max_signal_age_minutes": 10}),
            snapshot,
        ),
        (
            "TOO_MANY_INSTRUMENTS",
            {},
            policy.model_copy(update={"max_instruments": 1}),
            snapshot,
        ),
        ("MODEL_ID_MISMATCH", {"model_id": "OTHER"}, policy, snapshot),
    ]
    for code, changes, candidate_policy, candidate_snapshot in cases:
        candidate = dict(manifest)
        candidate.update(changes)
        assert_code(
            code,
            lambda c=candidate, p=candidate_policy, s=candidate_snapshot: (
                signals_module.validate_signal_frame(s, c, p, schedule, as_of)
            ),
        )

    bad_frame = pd.DataFrame(
        {
            "datetime": ["bad"],
            "instrument": ["SYNTH_A"],
            "score": [1.0],
            "model_id": ["SYNTHETIC_PEERLITE"],
            "fold_id": ["shadow"],
        }
    )
    bad_path = tmp_path / "bad-date.parquet"
    bad_frame.to_parquet(bad_path, index=False)
    bad_snapshot = signals_module.capture_prediction(bad_path, policy)
    bad_manifest = dict(manifest)
    bad_manifest["predictions_sha256"] = bad_snapshot.sha256
    bad_manifest["row_count"] = 1
    assert_code(
        "SIGNAL_DATE_INVALID",
        lambda: signals_module.validate_signal_frame(
            bad_snapshot, bad_manifest, policy, schedule, as_of
        ),
    )
    invalid_snapshot = signals_module.PredictionSnapshot(b"bad", "0" * 64, 1)
    assert_code(
        "INVALID_PARQUET",
        lambda: signals_module.validate_signal_frame(
            invalid_snapshot, manifest, policy, schedule, as_of
        ),
    )


def make_terminal(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    cycles = tmp_path / "cycles"
    cycles.mkdir()
    return cycle_module._publish_terminal(
        cycles,
        "m10s-20260731-164500-aaaaaaaaaaaa",
        "d" * 64,
        "COMPLETE",
        datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
        {
            "signal_manifest.json": {"ok": True},
            "monitoring.json": {"ok": True},
            "paper_intents.json": {"items": []},
        },
    )


def test_terminal_verifier_edges(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert_code(
        "TERMINAL_CORRUPTION",
        lambda: cycle_module.verify_terminal_cycle(missing),
    )
    terminal, manifest = make_terminal(tmp_path)
    assert_code(
        "TERMINAL_CORRUPTION",
        lambda: cycle_module.verify_terminal_cycle(terminal, "wrong"),
    )
    assert_code(
        "IDEMPOTENCY_COLLISION",
        lambda: cycle_module.verify_terminal_cycle(
            terminal, manifest["cycle_id"], "e" * 64
        ),
    )
    child = terminal / "paper_intents.json"
    payload = child.read_bytes()
    child.unlink()
    child.symlink_to(terminal / "monitoring.json")
    assert_code(
        "TERMINAL_CORRUPTION",
        lambda: cycle_module.verify_terminal_cycle(terminal),
    )
    child.unlink()
    child.write_bytes(payload)
    manifest_path = terminal / "cycle_manifest.json"
    changed = json.loads(manifest_path.read_text())
    changed["content_sha256"] = "0" * 64
    dump(manifest_path, changed)
    assert_code(
        "TERMINAL_CORRUPTION",
        lambda: cycle_module.verify_terminal_cycle(terminal),
    )


def test_index_reservation_and_cleanup_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal, manifest = make_terminal(tmp_path)
    state_root = tmp_path
    indexes = state_root / "idempotency"
    indexes.mkdir()
    index_path = indexes / f"{manifest['cycle_id']}.json"
    index = cycle_module._index_value(
        manifest["cycle_id"],
        manifest["request_digest"],
        terminal,
        manifest,
        datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
    )
    index["terminal_state"] = "HALTED"
    dump(index_path, index)
    assert_code(
        "IDEMPOTENCY_INDEX_CORRUPTION",
        lambda: cycle_module._validate_index(
            index_path, state_root, manifest["cycle_id"], manifest["request_digest"]
        ),
    )
    index["terminal_state"] = manifest["state"]
    index["committed_at"] = "bad"
    dump(index_path, index)
    assert_code(
        "IDEMPOTENCY_INDEX_CORRUPTION",
        lambda: cycle_module._validate_index(
            index_path, state_root, manifest["cycle_id"], manifest["request_digest"]
        ),
    )

    reservation = tmp_path / "reservation.json"
    dump(reservation, {"bad": True})
    assert_code(
        "RESERVATION_CORRUPTION",
        lambda: cycle_module._acquire_reservation(
            reservation,
            manifest["cycle_id"],
            manifest["request_digest"],
            "owner",
            datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
            60,
        ),
    )
    reservation_value = {
        "schema_version": "qlib_peerlite_cycle_reservation_v1",
        "cycle_id": manifest["cycle_id"],
        "request_digest": "x",
        "owner_id": "owner",
        "created_at": "2026-07-31T16:00:00+08:00",
    }
    dump(reservation, reservation_value)
    assert_code(
        "IDEMPOTENCY_COLLISION",
        lambda: cycle_module._acquire_reservation(
            reservation,
            manifest["cycle_id"],
            manifest["request_digest"],
            "owner",
            datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
            60,
        ),
    )
    reservation_value["request_digest"] = manifest["request_digest"]
    reservation_value["created_at"] = "bad"
    dump(reservation, reservation_value)
    assert_code(
        "RESERVATION_CORRUPTION",
        lambda: cycle_module._acquire_reservation(
            reservation,
            manifest["cycle_id"],
            manifest["request_digest"],
            "owner",
            datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
            60,
        ),
    )
    reservation_value["created_at"] = "2026-07-31T16:00:00+08:00"
    dump(reservation, reservation_value)
    real_rename = cycle_module.os.rename
    monkeypatch.setattr(
        cycle_module.os,
        "rename",
        lambda source, target: (_ for _ in ()).throw(OSError()),
    )
    assert_code(
        "CYCLE_IN_PROGRESS",
        lambda: cycle_module._acquire_reservation(
            reservation,
            manifest["cycle_id"],
            manifest["request_digest"],
            "owner",
            datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
            60,
        ),
    )
    monkeypatch.setattr(cycle_module.os, "rename", real_rename)

    missing_reservation = tmp_path / "none"
    cycle_module._remove_owned_reservation(
        missing_reservation, "owner", manifest["request_digest"]
    )
    dump(reservation, reservation_value)
    cycle_module._remove_owned_reservation(reservation, "other", manifest["request_digest"])
    assert reservation.exists()


def test_publish_collision_failure_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cycles = tmp_path / "cycles"
    cycles.mkdir()
    cycle_id = "m10s-20260731-164500-ffffffffffff"
    terminal, manifest = cycle_module._publish_terminal(
        cycles,
        cycle_id,
        "a" * 64,
        "NOT_DUE",
        datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI),
        {},
    )
    again_terminal, again = cycle_module._publish_terminal(
        cycles,
        cycle_id,
        "a" * 64,
        "NOT_DUE",
        datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI),
        {},
    )
    assert (again_terminal, again) == (terminal, manifest)

    real_rename = cycle_module._rename_directory_noreplace
    monkeypatch.setattr(
        cycle_module,
        "_rename_directory_noreplace",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ProductionError("TERMINAL_PUBLISH_FAILED", "forced")
        ),
    )
    assert_code(
        "TERMINAL_PUBLISH_FAILED",
        lambda: cycle_module._publish_terminal(
            cycles,
            "m10s-20260731-164500-eeeeeeeeeeee",
            "b" * 64,
            "NOT_DUE",
            datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI),
            {},
        ),
    )
    monkeypatch.setattr(cycle_module, "_rename_directory_noreplace", real_rename)

    real_write = cycle_module._write_exclusive_fd
    monkeypatch.setattr(
        cycle_module,
        "_write_exclusive_fd",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("forced")),
    )
    with pytest.raises(OSError, match="forced"):
        cycle_module._publish_terminal(
            cycles,
            "m10s-20260731-164500-dddddddddddd",
            "c" * 64,
            "COMPLETE",
            datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI),
            {"monitoring.json": {}},
        )
    monkeypatch.setattr(cycle_module, "_write_exclusive_fd", real_write)


def test_cycle_low_level_file_and_index_edges(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert_code("SAFE_JSON", lambda: cycle_module._safe_json_file(missing, "SAFE_JSON"))
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    assert_code("SAFE_JSON", lambda: cycle_module._safe_json_file(malformed, "SAFE_JSON"))
    sequence = tmp_path / "sequence.json"
    sequence.write_text("[]", encoding="utf-8")
    assert_code("SAFE_JSON", lambda: cycle_module._safe_json_file(sequence, "SAFE_JSON"))

    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "cycles").write_text("unsafe", encoding="utf-8")
    assert_code(
        "UNSAFE_STATE_ROOT",
        lambda: cycle_module._validate_state_root(
            state_root, "m10s-20260731-164500-aaaaaaaaaaaa"
        ),
    )

    exclusive = tmp_path / "exclusive.json"
    cycle_module._exclusive_json(exclusive, {"ok": True}, "EXISTS")
    assert_code(
        "EXISTS",
        lambda: cycle_module._exclusive_json(exclusive, {"ok": True}, "EXISTS"),
    )

    index_root = tmp_path / "index-root"
    index_root.mkdir()
    terminal, manifest = make_terminal(index_root)
    index_dir = index_root / "idempotency"
    index_dir.mkdir()
    index_path = index_dir / f"{manifest['cycle_id']}.json"
    committed = datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI)
    cycle_module._write_or_validate_index(
        index_path,
        index_root,
        manifest["cycle_id"],
        manifest["request_digest"],
        terminal,
        manifest,
        committed,
    )
    cycle_module._write_or_validate_index(
        index_path,
        index_root,
        manifest["cycle_id"],
        manifest["request_digest"],
        terminal,
        manifest,
        committed,
    )


def test_secure_descriptor_defensive_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "state"
    root.mkdir()
    root_fd = os.open(root, os.O_RDONLY)
    try:
        (root / "child").mkdir()
        assert_code(
            "SAFE_READ",
            lambda: cycle_module._read_fd_file(root_fd, "child", "SAFE_READ"),
        )
        assert_code(
            "SAFE_DIR",
            lambda: cycle_module._open_child_directory(root_fd, "missing", "SAFE_DIR"),
        )
        (root / "target").write_text("x", encoding="utf-8")
        (root / "link").symlink_to(root / "target")
        assert cycle_module._entry_kind(root_fd, "link") == "unsafe"
    finally:
        os.close(root_fd)

    assert_code(
        "INVALID_CYCLE_ID",
        lambda: cycle_module._StateStore.open(root, "../bad"),
    )
    cycle_module._validate_state_root(
        root, "m10s-20260731-164500-aaaaaaaaaaaa"
    )

    store = cycle_module._StateStore.open(
        root, "m10s-20260731-164500-aaaaaaaaaaaa"
    )
    store.assert_bound()
    store.ensure_managed()
    (root / "cycles").rename(root / "cycles-gone")
    assert_code("UNSAFE_STATE_ROOT", store.assert_bound)
    store.close()

    race_root = tmp_path / "race-state"
    race_root.mkdir()
    raced = cycle_module._StateStore.open(
        race_root, "m10s-20260731-164500-bbbbbbbbbbbb"
    )
    real_mkdir = cycle_module.os.mkdir

    def create_then_report_exists(name: str, mode: int, *, dir_fd: int) -> None:
        real_mkdir(name, mode, dir_fd=dir_fd)
        raise FileExistsError

    monkeypatch.setattr(cycle_module.os, "mkdir", create_then_report_exists)
    raced.ensure_managed()
    monkeypatch.setattr(cycle_module.os, "mkdir", real_mkdir)
    raced.close()

    directory_fd = os.open(tmp_path, os.O_RDONLY)
    real_open = cycle_module.os.open
    try:
        def deny_create(*args: object, **kwargs: object) -> int:
            raise PermissionError

        monkeypatch.setattr(cycle_module.os, "open", deny_create)
        assert_code(
            "WRITE_DENIED",
            lambda: cycle_module._write_exclusive_fd(
                directory_fd, "denied", b"x", "WRITE_DENIED"
            ),
        )
    finally:
        monkeypatch.setattr(cycle_module.os, "open", real_open)
        os.close(directory_fd)


def test_secure_reservation_and_cleanup_edges(tmp_path: Path) -> None:
    reservations = tmp_path / "reservations"
    reservations.mkdir()
    descriptor = os.open(reservations, os.O_RDONLY)
    cycle_id = "m10s-20260731-164500-aaaaaaaaaaaa"
    digest = "d" * 64
    as_of = datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI)
    name = f"{cycle_id}.json"
    try:
        dump(reservations / name, {"bad": True})
        assert_code(
            "RESERVATION_CORRUPTION",
            lambda: cycle_module._acquire_reservation_fd(
                descriptor, cycle_id, digest, "owner", as_of, 60
            ),
        )
        dump(
            reservations / name,
            cycle_module._reservation_value(cycle_id, "x", "owner", as_of),
        )
        assert_code(
            "IDEMPOTENCY_COLLISION",
            lambda: cycle_module._acquire_reservation_fd(
                descriptor, cycle_id, digest, "owner", as_of, 60
            ),
        )
        invalid = cycle_module._reservation_value(cycle_id, digest, "owner", as_of)
        invalid["created_at"] = "bad"
        dump(reservations / name, invalid)
        assert_code(
            "RESERVATION_CORRUPTION",
            lambda: cycle_module._acquire_reservation_fd(
                descriptor, cycle_id, digest, "owner", as_of, 60
            ),
        )
        fresh = cycle_module._reservation_value(cycle_id, digest, "owner", as_of)
        dump(reservations / name, fresh)
        assert_code(
            "CYCLE_IN_PROGRESS",
            lambda: cycle_module._acquire_reservation_fd(
                descriptor, cycle_id, digest, "owner", as_of, 60
            ),
        )
        cycle_module._remove_owned_reservation_fd(
            descriptor, "m10s-20260731-164500-bbbbbbbbbbbb", "owner", digest
        )
        cycle_module._remove_owned_reservation_fd(
            descriptor, cycle_id, "other", digest
        )
        assert (reservations / name).exists()
        cycle_module._remove_owned_reservation_fd(
            descriptor, cycle_id, "owner", digest
        )
        assert not (reservations / name).exists()
    finally:
        os.close(descriptor)

    legacy = tmp_path / "legacy.json"
    dump(legacy, {"owner_id": "owner", "request_digest": digest})
    cycle_module._remove_owned_reservation(legacy, "owner", digest)
    assert not legacy.exists()


def test_policy_snapshot_bounds(tmp_path: Path) -> None:
    assert_code(
        "SNAPSHOT",
        lambda: policy_module.capture_regular_file(tmp_path, code="SNAPSHOT"),
    )
    oversized = tmp_path / "oversized"
    oversized.write_bytes(b"12")
    assert_code(
        "SNAPSHOT",
        lambda: policy_module.capture_regular_file(
            oversized, code="SNAPSHOT", max_bytes=1
        ),
    )
    real_fstat = policy_module.os.fstat
    try:
        policy_module.os.fstat = lambda descriptor: SimpleNamespace(
            st_mode=stat.S_IFREG, st_size=0
        )
        assert_code(
            "SNAPSHOT",
            lambda: policy_module.capture_regular_file(
                oversized, code="SNAPSHOT", max_bytes=1
            ),
        )
    finally:
        policy_module.os.fstat = real_fstat


def test_remaining_secure_failure_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal_root = tmp_path / "terminal-root"
    terminal_root.mkdir()
    terminal, manifest = make_terminal(terminal_root)
    manifest_path = terminal / "cycle_manifest.json"
    invalid_time = json.loads(manifest_path.read_text(encoding="utf-8"))
    invalid_time["created_at"] = "bad"
    invalid_time["content_sha256"] = cycle_module._manifest_content_hash(invalid_time)
    dump(manifest_path, invalid_time)
    assert_code(
        "TERMINAL_CORRUPTION",
        lambda: cycle_module.verify_terminal_cycle(terminal),
    )

    index_root = tmp_path / "index-root"
    index_root.mkdir()
    terminal, manifest = make_terminal(index_root)
    index_dir = terminal.parent.parent / "idempotency"
    index_dir.mkdir()
    index_path = index_dir / f"{manifest['cycle_id']}.json"
    value = cycle_module._index_value(
        manifest["cycle_id"],
        manifest["request_digest"],
        terminal,
        manifest,
        datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
    )
    value["committed_at"] = "2026-07-31T16:45:00"
    dump(index_path, value)
    assert_code(
        "IDEMPOTENCY_INDEX_CORRUPTION",
        lambda: cycle_module._validate_index(
            index_path,
            terminal.parent.parent,
            manifest["cycle_id"],
            manifest["request_digest"],
        ),
    )

    index_fd = os.open(index_dir, os.O_RDONLY)
    cycles_fd = os.open(terminal.parent, os.O_RDONLY)
    real_write = cycle_module._write_exclusive_fd
    try:
        def fail_other(*args: object, **kwargs: object) -> None:
            raise ProductionError("OTHER", "forced")

        monkeypatch.setattr(cycle_module, "_write_exclusive_fd", fail_other)
        assert_code(
            "OTHER",
            lambda: cycle_module._write_or_validate_index_fd(
                index_fd,
                cycles_fd,
                manifest["cycle_id"],
                manifest["request_digest"],
                manifest,
                manifest_path.read_bytes(),
                datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
            ),
        )
    finally:
        monkeypatch.setattr(cycle_module, "_write_exclusive_fd", real_write)
        os.close(index_fd)
        os.close(cycles_fd)

    reservations = tmp_path / "secure-reservations"
    reservations.mkdir()
    reservation_fd = os.open(reservations, os.O_RDONLY)
    cycle_id = "m10s-20260731-164500-cccccccccccc"
    digest = "c" * 64
    as_of = datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI)
    try:
        naive = cycle_module._reservation_value(cycle_id, digest, "owner", as_of)
        naive["created_at"] = "2026-07-31T16:00:00"
        dump(reservations / f"{cycle_id}.json", naive)
        assert_code(
            "RESERVATION_CORRUPTION",
            lambda: cycle_module._acquire_reservation_fd(
                reservation_fd, cycle_id, digest, "owner", as_of, 60
            ),
        )
        stale = cycle_module._reservation_value(
            cycle_id,
            digest,
            "owner",
            datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI),
        )
        dump(reservations / f"{cycle_id}.json", stale)
        real_rename = cycle_module.os.rename
        monkeypatch.setattr(
            cycle_module.os,
            "rename",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("forced")),
        )
        assert_code(
            "CYCLE_IN_PROGRESS",
            lambda: cycle_module._acquire_reservation_fd(
                reservation_fd, cycle_id, digest, "owner", as_of, 60
            ),
        )
        monkeypatch.setattr(cycle_module.os, "rename", real_rename)
    finally:
        os.close(reservation_fd)

    legacy = tmp_path / "legacy-reservation.json"
    naive = cycle_module._reservation_value(cycle_id, digest, "owner", as_of)
    naive["created_at"] = "2026-07-31T16:00:00"
    dump(legacy, naive)
    assert_code(
        "RESERVATION_CORRUPTION",
        lambda: cycle_module._acquire_reservation(
            legacy, cycle_id, digest, "owner", as_of, 60
        ),
    )
    dump(legacy, cycle_module._reservation_value(cycle_id, digest, "owner", as_of))
    assert_code(
        "CYCLE_IN_PROGRESS",
        lambda: cycle_module._acquire_reservation(
            legacy, cycle_id, digest, "owner", as_of, 60
        ),
    )
    legacy.unlink()
    cycle_module._acquire_reservation(
        legacy, cycle_id, digest, "owner", as_of, 60
    )

    cycles = tmp_path / "publish-cycles"
    cycles.mkdir()
    cycles_fd = os.open(cycles, os.O_RDONLY)
    real_mkdir = cycle_module.os.mkdir
    try:
        monkeypatch.setattr(
            cycle_module.os,
            "mkdir",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("forced")),
        )
        assert_code(
            "TERMINAL_PUBLISH_FAILED",
            lambda: cycle_module._publish_terminal_fd(
                cycles_fd,
                "m10s-20260731-164500-dddddddddddd",
                "d" * 64,
                "NOT_DUE",
                as_of,
                {},
            ),
        )
    finally:
        monkeypatch.setattr(cycle_module.os, "mkdir", real_mkdir)
        os.close(cycles_fd)


def test_state_root_trust_and_root_binding_edges(tmp_path: Path) -> None:
    unsafe = tmp_path / "unsafe-mode"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o777)
    assert_code(
        "UNSAFE_STATE_ROOT",
        lambda: cycle_module._StateStore.open(
            unsafe, "m10s-20260731-164500-aaaaaaaaaaaa"
        ),
    )

    root = tmp_path / "root"
    root.mkdir()
    store = cycle_module._StateStore.open(
        root, "m10s-20260731-164500-bbbbbbbbbbbb"
    )
    moved = tmp_path / "root-moved"
    root.rename(moved)
    try:
        assert_code("UNSAFE_STATE_ROOT", store.assert_bound)
        root.mkdir()
        assert_code("UNSAFE_STATE_ROOT", store.assert_bound)
    finally:
        store.close()


def test_atomic_noreplace_platform_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Operation:
        def __init__(self, result: int) -> None:
            self.result = result
            self.argtypes: object = None

        def __call__(self, *args: object) -> int:
            return self.result

    class Library:
        def __init__(self, *, linux: bool, result: int) -> None:
            if linux:
                self.renameat2 = Operation(result)
            else:
                self.renameatx_np = Operation(result)

    monkeypatch.setattr(cycle_module.sys, "platform", "linux")
    monkeypatch.setattr(
        cycle_module.ctypes, "CDLL", lambda *args, **kwargs: Library(linux=True, result=0)
    )
    cycle_module._rename_directory_noreplace(1, "a", 2, "b")

    class MissingLibrary:
        pass

    monkeypatch.setattr(
        cycle_module.ctypes, "CDLL", lambda *args, **kwargs: MissingLibrary()
    )
    assert_code(
        "ATOMIC_NOREPLACE_UNAVAILABLE",
        lambda: cycle_module._rename_directory_noreplace(1, "a", 2, "b"),
    )

    monkeypatch.setattr(cycle_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        cycle_module.ctypes, "CDLL", lambda *args, **kwargs: Library(linux=False, result=-1)
    )
    monkeypatch.setattr(cycle_module.ctypes, "get_errno", lambda: errno.EIO)
    assert_code(
        "TERMINAL_PUBLISH_FAILED",
        lambda: cycle_module._rename_directory_noreplace(1, "a", 2, "b"),
    )
