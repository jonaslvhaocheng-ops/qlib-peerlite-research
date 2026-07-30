from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from typer.testing import CliRunner

from qlib_peerlite.cli import app
from qlib_peerlite.governance.artifacts import canonical_json_bytes, sha256_bytes, sha256_file
from qlib_peerlite.production import (
    ProductionError,
    authorize_shadow,
    build_paper_intents,
    capture_prediction,
    evaluate_schedule,
    load_calendar,
    load_shadow_policy,
    run_shadow_cycle,
    validate_signal_frame,
    verify_terminal_cycle,
)
from qlib_peerlite.production import cycle as cycle_module

SHANGHAI = ZoneInfo("Asia/Shanghai")
M9_GATE = Path("evidence/gates/M9_step_nine_terminal_gate.json")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def m10_case(tmp_path: Path) -> dict[str, object]:
    calendar_path = tmp_path / "calendar.json"
    calendar = {
        "schema_version": "qlib_peerlite_session_calendar_v1",
        "timezone": "Asia/Shanghai",
        "sessions": ["2026-07-31", "2026-08-03"],
    }
    write_json(calendar_path, calendar)
    policy_path = tmp_path / "policy.yaml"
    policy = {
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
        "max_input_bytes": 1000000,
        "max_rows": 100,
        "max_instruments": 50,
        "top_fraction": 0.4,
        "max_name_weight": 0.2,
        "max_paper_intents": 10,
        "reservation_timeout_seconds": 60,
        "m9_gate_path": str(M9_GATE),
        "m9_gate_sha256": sha256_file(M9_GATE),
        "calendar_path": str(calendar_path),
        "calendar_sha256": sha256_file(calendar_path),
        "permitted_model_ids": ["SYNTHETIC_PEERLITE"],
    }
    import yaml

    policy_path.write_text(yaml.safe_dump(policy, sort_keys=True), encoding="utf-8")
    predictions_path = tmp_path / "predictions.parquet"
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-07-31"] * 5),
            "instrument": [f"SYNTH_{letter}" for letter in "ABCDE"],
            "score": [0.9, 0.9, 0.3, -0.1, -0.5],
            "model_id": ["SYNTHETIC_PEERLITE"] * 5,
            "fold_id": ["shadow"] * 5,
        }
    )
    frame.to_parquet(predictions_path, index=False)
    manifest_path = tmp_path / "source_manifest.json"
    manifest = {
        "schema_version": "qlib_peerlite_score_source_v1",
        "score_schema_version": "qlib_peerlite_score_v1",
        "track": "SYNTHETIC",
        "predictions_sha256": sha256_file(predictions_path),
        "row_count": 5,
        "model_id": "SYNTHETIC_PEERLITE",
        "signal_date": "2026-07-31",
        "prediction_time": "2026-07-31T15:30:00+08:00",
    }
    write_json(manifest_path, manifest)
    state_root = tmp_path / "state"
    state_root.mkdir()
    return {
        "calendar_path": calendar_path,
        "policy": policy,
        "policy_path": policy_path,
        "predictions_path": predictions_path,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "frame": frame,
        "state_root": state_root,
        "as_of": datetime(2026, 7, 31, 16, 45, tzinfo=SHANGHAI),
        "cycle_id": "m10s-20260731-164500-abcdef123456",
    }


def error_code(error: pytest.ExceptionInfo[ProductionError]) -> str:
    return error.value.code


def state_digest(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        rows.append(
            (
                str(path.relative_to(root)),
                "symlink" if path.is_symlink() else "dir" if path.is_dir() else sha256_file(path),
            )
        )
    return sha256_bytes(canonical_json_bytes(rows))


def test_policy_and_authorization_are_shadow_only(m10_case: dict[str, object]) -> None:
    policy = load_shadow_policy(m10_case["policy_path"])
    assert policy.capability == "SHADOW_ONLY"
    authorization = authorize_shadow(policy, Path.cwd())
    assert authorization["capability"] == "SHADOW_ONLY"
    assert authorization["production_authorized"] is False

    for mutation, code in [
        ({"execution_mode": "live"}, "INVALID_POLICY"),
        ({"broker_endpoint": "https://invalid"}, "UNSAFE_POLICY_KEY"),
        ({"nested": {"secret_token": "x"}}, "UNSAFE_POLICY_KEY"),
    ]:
        payload = copy.deepcopy(m10_case["policy"])
        payload.update(mutation)
        path = Path(m10_case["policy_path"]).with_name(f"bad-{code}-{len(mutation)}.yaml")
        import yaml

        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        with pytest.raises(ProductionError) as error:
            load_shadow_policy(path)
        assert error_code(error) == code


def test_authorization_rejects_gate_tampering(
    m10_case: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = load_shadow_policy(m10_case["policy_path"])
    with pytest.raises(ProductionError) as error:
        authorize_shadow(policy.model_copy(update={"m9_gate_sha256": "0" * 64}), Path.cwd())
    assert error_code(error) == "M9_GATE_HASH_MISMATCH"

    gate = json.loads(M9_GATE.read_text(encoding="utf-8"))
    for field, value in [
        ("production_authorized", True),
        ("promotion_authorized", True),
        ("final_oos_opened", True),
        ("final_oos_access_count", 1),
        ("research_decision", "PROMOTE"),
    ]:
        changed = copy.deepcopy(gate)
        changed[field] = value
        path = Path(m10_case["policy_path"]).with_name(f"gate-{field}.json")
        write_json(path, changed)
        mutated = policy.model_copy(
            update={"m9_gate_path": str(path), "m9_gate_sha256": sha256_file(path)}
        )
        with pytest.raises(ProductionError) as error:
            authorize_shadow(mutated, Path.cwd())
        assert error_code(error) == "M9_NOT_SHADOW_AUTHORIZED"

    monkeypatch.chdir(Path(m10_case["state_root"]))
    with pytest.raises(ProductionError) as error:
        authorize_shadow(policy, Path.cwd())
    assert error_code(error) == "M9_GATE_MISSING"

    list_gate = Path(m10_case["policy_path"]).with_name("gate-list.json")
    write_json(list_gate, [])
    list_policy = policy.model_copy(
        update={"m9_gate_path": str(list_gate), "m9_gate_sha256": sha256_file(list_gate)}
    )
    with pytest.raises(ProductionError) as error:
        authorize_shadow(list_policy, Path.cwd())
    assert error_code(error) == "M9_GATE_INVALID"


def test_schedule_calendar_and_boundaries(m10_case: dict[str, object]) -> None:
    policy = load_shadow_policy(m10_case["policy_path"])
    calendar = load_calendar(policy)
    due = evaluate_schedule(policy, calendar, m10_case["as_of"])
    assert due.due is True
    assert due.session_date == "2026-07-31"

    before = evaluate_schedule(
        policy, calendar, datetime(2026, 7, 31, 16, 29, 59, tzinfo=SHANGHAI)
    )
    monday = evaluate_schedule(
        policy, calendar, datetime(2026, 8, 3, 17, 0, tzinfo=SHANGHAI)
    )
    absent = evaluate_schedule(
        policy, calendar, datetime(2026, 8, 4, 17, 0, tzinfo=SHANGHAI)
    )
    assert (before.reason, monday.reason, absent.reason) == (
        "BEFORE_CUTOFF",
        "NOT_REBALANCE_WEEKDAY",
        "NOT_SESSION",
    )
    with pytest.raises(ProductionError, match="timezone-aware"):
        evaluate_schedule(policy, calendar, datetime(2026, 7, 31, 17, 0))


def test_capture_and_validate_signal(m10_case: dict[str, object]) -> None:
    policy = load_shadow_policy(m10_case["policy_path"])
    snapshot = capture_prediction(Path(m10_case["predictions_path"]), policy)
    assert snapshot.sha256 == m10_case["manifest"]["predictions_sha256"]
    assert snapshot.row_count == 5
    schedule = evaluate_schedule(policy, load_calendar(policy), m10_case["as_of"])
    frame = validate_signal_frame(
        snapshot,
        m10_case["manifest"],
        policy,
        schedule,
        m10_case["as_of"],
    )
    assert list(frame.columns) == ["datetime", "instrument", "score", "model_id", "fold_id"]
    intents = build_paper_intents(frame, policy, str(m10_case["cycle_id"]))
    assert [item["instrument"] for item in intents] == ["SYNTH_A", "SYNTH_B"]
    assert [item["target_weight"] for item in intents] == [0.2, 0.2]
    assert len({item["idempotency_key"] for item in intents}) == 2


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda frame: frame.assign(score=[float("nan"), 1, 2, 3, 4]), "NONFINITE_SCORE"),
        (
            lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
            "DUPLICATE_SIGNAL_KEY",
        ),
        (
            lambda frame: frame.assign(datetime=pd.to_datetime(["2026-08-03"] * len(frame))),
            "SIGNAL_SESSION_MISMATCH",
        ),
        (
            lambda frame: frame.assign(
                datetime=pd.to_datetime(["2026-07-31"] * 4 + ["2026-08-03"])
            ),
            "MULTIPLE_SIGNAL_DATES",
        ),
        (
            lambda frame: frame.assign(instrument=["REAL_1", *frame["instrument"].iloc[1:]]),
            "NON_SYNTHETIC_INSTRUMENT",
        ),
    ],
)
def test_signal_failures(
    m10_case: dict[str, object], mutator: object, code: str
) -> None:
    policy = load_shadow_policy(m10_case["policy_path"])
    path = Path(m10_case["predictions_path"])
    frame = mutator(m10_case["frame"].copy())
    frame.to_parquet(path, index=False)
    manifest = copy.deepcopy(m10_case["manifest"])
    manifest["predictions_sha256"] = sha256_file(path)
    manifest["row_count"] = len(frame)
    snapshot = capture_prediction(path, policy)
    schedule = evaluate_schedule(policy, load_calendar(policy), m10_case["as_of"])
    with pytest.raises(ProductionError) as error:
        validate_signal_frame(snapshot, manifest, policy, schedule, m10_case["as_of"])
    assert error_code(error) == code


def test_input_and_manifest_preflight_failures(m10_case: dict[str, object]) -> None:
    policy = load_shadow_policy(m10_case["policy_path"])
    path = Path(m10_case["predictions_path"])
    symlink = path.with_name("scores-link.parquet")
    symlink.symlink_to(path)
    with pytest.raises(ProductionError) as error:
        capture_prediction(symlink, policy)
    assert error_code(error) == "UNSAFE_INPUT_PATH"
    with pytest.raises(ProductionError) as error:
        capture_prediction(path, policy.model_copy(update={"max_input_bytes": 1}))
    assert error_code(error) == "INPUT_TOO_LARGE"
    with pytest.raises(ProductionError) as error:
        capture_prediction(path, policy.model_copy(update={"max_rows": 1}))
    assert error_code(error) == "TOO_MANY_ROWS"


def test_success_replay_collision_and_crash_repair(m10_case: dict[str, object]) -> None:
    kwargs = {
        "policy_path": m10_case["policy_path"],
        "predictions_path": m10_case["predictions_path"],
        "source_manifest_path": m10_case["manifest_path"],
        "state_root": m10_case["state_root"],
        "cycle_id": m10_case["cycle_id"],
        "as_of": m10_case["as_of"],
        "project_root": Path.cwd(),
        "owner_id": "owner-a",
    }
    first = run_shadow_cycle(**kwargs)
    assert first["state"] == "COMPLETE"
    terminal = Path(m10_case["state_root"]) / "cycles" / str(m10_case["cycle_id"])
    verified = verify_terminal_cycle(terminal, str(m10_case["cycle_id"]))
    assert verified == first
    digest_before = state_digest(Path(m10_case["state_root"]))
    assert run_shadow_cycle(**kwargs) == first
    assert state_digest(Path(m10_case["state_root"])) == digest_before

    index = Path(m10_case["state_root"]) / "idempotency" / f"{m10_case['cycle_id']}.json"
    index.unlink()
    assert run_shadow_cycle(**kwargs) == first
    assert index.exists()

    changed = Path(m10_case["predictions_path"])
    altered = m10_case["frame"].copy()
    altered["score"] += 0.01
    altered.to_parquet(changed, index=False)
    changed_manifest = copy.deepcopy(m10_case["manifest"])
    changed_manifest["predictions_sha256"] = sha256_file(changed)
    write_json(Path(m10_case["manifest_path"]), changed_manifest)
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(**kwargs)
    assert error_code(error) == "IDEMPOTENCY_COLLISION"


def test_not_due_and_transactional_halt(m10_case: dict[str, object]) -> None:
    kwargs = {
        "policy_path": m10_case["policy_path"],
        "predictions_path": m10_case["predictions_path"],
        "source_manifest_path": m10_case["manifest_path"],
        "state_root": m10_case["state_root"],
        "project_root": Path.cwd(),
        "owner_id": "owner-a",
    }
    not_due = run_shadow_cycle(
        **kwargs,
        cycle_id="m10s-20260731-160000-bbbbbbbbbbbb",
        as_of=datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI),
    )
    assert not_due["state"] == "NOT_DUE"
    not_due_dir = Path(m10_case["state_root"]) / "cycles" / not_due["cycle_id"]
    assert {path.name for path in not_due_dir.iterdir()} == {"cycle_manifest.json"}

    frame = m10_case["frame"].copy()
    frame.loc[0, "score"] = float("inf")
    frame.to_parquet(m10_case["predictions_path"], index=False)
    manifest = copy.deepcopy(m10_case["manifest"])
    manifest["predictions_sha256"] = sha256_file(m10_case["predictions_path"])
    write_json(Path(m10_case["manifest_path"]), manifest)
    halted = run_shadow_cycle(
        **kwargs,
        cycle_id="m10s-20260731-164500-cccccccccccc",
        as_of=m10_case["as_of"],
    )
    assert halted["state"] == "HALTED"
    halted_dir = Path(m10_case["state_root"]) / "cycles" / halted["cycle_id"]
    assert {path.name for path in halted_dir.iterdir()} == {
        "cycle_manifest.json",
        "monitoring.json",
        "alert.json",
    }
    assert not (halted_dir / "paper_intents.json").exists()


def test_preflight_is_zero_mutation_and_paths_are_safe(m10_case: dict[str, object]) -> None:
    state_root = Path(m10_case["state_root"])
    before = state_digest(state_root)
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(
            policy_path=m10_case["policy_path"],
            predictions_path=m10_case["predictions_path"],
            source_manifest_path=m10_case["manifest_path"],
            state_root=state_root,
            cycle_id="../escape",
            as_of=m10_case["as_of"],
            project_root=Path.cwd(),
        )
    assert error_code(error) == "INVALID_CYCLE_ID"
    assert state_digest(state_root) == before

    symlink_root = state_root.with_name("state-link")
    symlink_root.symlink_to(state_root, target_is_directory=True)
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(
            policy_path=m10_case["policy_path"],
            predictions_path=m10_case["predictions_path"],
            source_manifest_path=m10_case["manifest_path"],
            state_root=symlink_root,
            cycle_id=m10_case["cycle_id"],
            as_of=m10_case["as_of"],
            project_root=Path.cwd(),
        )
    assert error_code(error) == "UNSAFE_STATE_ROOT"
    assert state_digest(state_root) == before


def test_reservation_and_index_corruption(m10_case: dict[str, object]) -> None:
    state_root = Path(m10_case["state_root"])
    kwargs = {
        "policy_path": m10_case["policy_path"],
        "predictions_path": m10_case["predictions_path"],
        "source_manifest_path": m10_case["manifest_path"],
        "state_root": state_root,
        "cycle_id": m10_case["cycle_id"],
        "as_of": m10_case["as_of"],
        "project_root": Path.cwd(),
        "owner_id": "owner-b",
    }
    policy = load_shadow_policy(m10_case["policy_path"])
    snapshot = capture_prediction(Path(m10_case["predictions_path"]), policy)
    request_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "cycle_id": m10_case["cycle_id"],
                "policy_sha256": sha256_file(m10_case["policy_path"]),
                "source_manifest_sha256": sha256_file(m10_case["manifest_path"]),
                "predictions_sha256": snapshot.sha256,
                "as_of": m10_case["as_of"].isoformat(),
            }
        )
    )
    reservations = state_root / "reservations"
    reservations.mkdir()
    reservation = reservations / f"{m10_case['cycle_id']}.json"
    write_json(
        reservation,
        {
            "schema_version": "qlib_peerlite_cycle_reservation_v1",
            "cycle_id": m10_case["cycle_id"],
            "request_digest": request_digest,
            "owner_id": "owner-a",
            "created_at": m10_case["as_of"].isoformat(),
        },
    )
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(**kwargs)
    assert error_code(error) == "CYCLE_IN_PROGRESS"

    stale = copy.deepcopy(json.loads(reservation.read_text()))
    stale["created_at"] = (m10_case["as_of"] - timedelta(seconds=61)).isoformat()
    write_json(reservation, stale)
    assert run_shadow_cycle(**kwargs)["state"] == "COMPLETE"

    fresh_case = m10_case["cycle_id"].replace("abcdef123456", "dddddddddddd")
    indexes = state_root / "idempotency"
    orphan = indexes / f"{fresh_case}.json"
    write_json(orphan, {"bad": True})
    kwargs["cycle_id"] = fresh_case
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(**kwargs)
    assert error_code(error) == "IDEMPOTENCY_INDEX_CORRUPTION"
    assert json.loads(orphan.read_text()) == {"bad": True}


def test_terminal_tampering_is_detected(m10_case: dict[str, object]) -> None:
    manifest = run_shadow_cycle(
        policy_path=m10_case["policy_path"],
        predictions_path=m10_case["predictions_path"],
        source_manifest_path=m10_case["manifest_path"],
        state_root=m10_case["state_root"],
        cycle_id=m10_case["cycle_id"],
        as_of=m10_case["as_of"],
        project_root=Path.cwd(),
        owner_id="owner-a",
    )
    terminal = Path(m10_case["state_root"]) / "cycles" / manifest["cycle_id"]
    intents = terminal / "paper_intents.json"
    original = intents.read_bytes()
    intents.write_bytes(original + b"x")
    with pytest.raises(ProductionError) as error:
        verify_terminal_cycle(terminal, manifest["cycle_id"])
    assert error_code(error) == "TERMINAL_CORRUPTION"
    intents.write_bytes(original)
    extra = terminal / "extra.json"
    extra.write_text("{}")
    with pytest.raises(ProductionError) as error:
        verify_terminal_cycle(terminal, manifest["cycle_id"])
    assert error_code(error) == "TERMINAL_CORRUPTION"


def test_terminal_cannot_self_authorize_live(m10_case: dict[str, object]) -> None:
    manifest = run_shadow_cycle(
        policy_path=m10_case["policy_path"],
        predictions_path=m10_case["predictions_path"],
        source_manifest_path=m10_case["manifest_path"],
        state_root=m10_case["state_root"],
        cycle_id=m10_case["cycle_id"],
        as_of=m10_case["as_of"],
        project_root=Path.cwd(),
    )
    terminal = Path(m10_case["state_root"]) / "cycles" / manifest["cycle_id"]
    manifest_path = terminal / "cycle_manifest.json"
    forged = json.loads(manifest_path.read_text(encoding="utf-8"))
    forged["capability"] = "LIVE"
    forged["live_execution_authorized"] = True
    forged["content_sha256"] = cycle_module._manifest_content_hash(forged)
    write_json(manifest_path, forged)
    with pytest.raises(ProductionError) as error:
        verify_terminal_cycle(terminal)
    assert error_code(error) == "TERMINAL_CORRUPTION"


def test_naive_as_of_is_rejected_without_state_mutation(
    m10_case: dict[str, object],
) -> None:
    state_root = Path(m10_case["state_root"])
    before = state_digest(state_root)
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(
            policy_path=m10_case["policy_path"],
            predictions_path=m10_case["predictions_path"],
            source_manifest_path=m10_case["manifest_path"],
            state_root=state_root,
            cycle_id=m10_case["cycle_id"],
            as_of=datetime(2026, 7, 31, 16, 45),
            project_root=Path.cwd(),
        )
    assert error_code(error) == "INVALID_AS_OF"
    assert state_digest(state_root) == before


def test_managed_directory_swap_is_fail_closed(
    m10_case: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = Path(m10_case["state_root"])
    outside = state_root.with_name("outside")
    outside.mkdir()
    (outside / "cycles").mkdir()
    original = cycle_module._StateStore.ensure_managed

    def swap_cycles(store: object) -> None:
        original(store)
        (state_root / "cycles").rename(state_root / "cycles-detached")
        (state_root / "cycles").symlink_to(outside / "cycles", target_is_directory=True)

    monkeypatch.setattr(cycle_module._StateStore, "ensure_managed", swap_cycles)
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(
            policy_path=m10_case["policy_path"],
            predictions_path=m10_case["predictions_path"],
            source_manifest_path=m10_case["manifest_path"],
            state_root=state_root,
            cycle_id=m10_case["cycle_id"],
            as_of=m10_case["as_of"],
            project_root=Path.cwd(),
        )
    assert error_code(error) == "UNSAFE_STATE_ROOT"
    assert list((outside / "cycles").iterdir()) == []
    assert list((state_root / "cycles-detached").iterdir()) == []


def test_post_check_directory_move_cannot_receive_publication(
    m10_case: dict[str, object],
) -> None:
    state_root = Path(m10_case["state_root"])
    outside = state_root.with_name("post-check-outside")
    outside.mkdir()
    store = cycle_module._StateStore.open(state_root, str(m10_case["cycle_id"]))
    try:
        store.ensure_managed()
        assert store.cycles_fd is not None
        checks = 0

        def move_then_check() -> None:
            nonlocal checks
            checks += 1
            if checks == 2:
                (state_root / "cycles").rename(outside / "cycles")
            store.assert_bound()

        with pytest.raises(ProductionError) as error:
            cycle_module._publish_terminal_fd(
                store.cycles_fd,
                str(m10_case["cycle_id"]),
                "a" * 64,
                "NOT_DUE",
                m10_case["as_of"],
                {},
                move_then_check,
            )
        assert error_code(error) == "UNSAFE_STATE_ROOT"
        assert list((outside / "cycles").iterdir()) == []
    finally:
        store.close()


def test_state_root_lock_and_no_replace_terminal(
    m10_case: dict[str, object],
) -> None:
    state_root = Path(m10_case["state_root"])
    first = cycle_module._StateStore.open(state_root, str(m10_case["cycle_id"]))
    try:
        with pytest.raises(ProductionError) as error:
            cycle_module._StateStore.open(state_root, str(m10_case["cycle_id"]))
        assert error_code(error) == "STATE_LOCKED"
    finally:
        first.close()

    cycles = state_root / "cycles"
    cycles.mkdir()
    terminal = cycles / str(m10_case["cycle_id"])
    terminal.mkdir()
    with pytest.raises(ProductionError) as error:
        cycle_module._publish_terminal(
            cycles,
            str(m10_case["cycle_id"]),
            "b" * 64,
            "NOT_DUE",
            m10_case["as_of"],
            {},
        )
    assert error_code(error) == "TERMINAL_CORRUPTION"
    assert list(terminal.iterdir()) == []


def test_source_manifest_is_parsed_and_hashed_from_one_snapshot(
    m10_case: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = Path(m10_case["manifest_path"])
    original_capture = cycle_module.capture_regular_file
    swapped = False

    def capture_then_swap(path: object, **kwargs: object) -> object:
        nonlocal swapped
        snapshot = original_capture(path, **kwargs)
        if Path(path) == source_path and not swapped:
            swapped = True
            source_path.write_text('{"replaced":true}\n', encoding="utf-8")
        return snapshot

    monkeypatch.setattr(cycle_module, "capture_regular_file", capture_then_swap)
    result = run_shadow_cycle(
        policy_path=m10_case["policy_path"],
        predictions_path=m10_case["predictions_path"],
        source_manifest_path=source_path,
        state_root=m10_case["state_root"],
        cycle_id=m10_case["cycle_id"],
        as_of=m10_case["as_of"],
        project_root=Path.cwd(),
    )
    assert swapped is True
    assert result["state"] == "COMPLETE"
    assert json.loads(source_path.read_text(encoding="utf-8")) == {"replaced": True}


def test_unsafe_existing_state_entries_are_rejected(
    m10_case: dict[str, object],
) -> None:
    common = {
        "policy_path": m10_case["policy_path"],
        "predictions_path": m10_case["predictions_path"],
        "source_manifest_path": m10_case["manifest_path"],
        "cycle_id": m10_case["cycle_id"],
        "as_of": m10_case["as_of"],
        "project_root": Path.cwd(),
    }
    index_root = Path(m10_case["state_root"]).with_name("unsafe-index-state")
    index_root.mkdir()
    (index_root / "idempotency").mkdir()
    unsafe_index = index_root / "idempotency" / f"{m10_case['cycle_id']}.json"
    unsafe_index.symlink_to(Path(m10_case["manifest_path"]))
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(**common, state_root=index_root)
    assert error_code(error) == "IDEMPOTENCY_INDEX_CORRUPTION"

    terminal_root = Path(m10_case["state_root"]).with_name("unsafe-terminal-state")
    terminal_root.mkdir()
    (terminal_root / "cycles").mkdir()
    (terminal_root / "cycles" / str(m10_case["cycle_id"])).write_text(
        "unsafe", encoding="utf-8"
    )
    with pytest.raises(ProductionError) as error:
        run_shadow_cycle(**common, state_root=terminal_root)
    assert error_code(error) == "TERMINAL_CORRUPTION"


def test_cycle_accepts_absolute_pinned_gate_path(
    m10_case: dict[str, object],
) -> None:
    import yaml

    policy = copy.deepcopy(m10_case["policy"])
    policy["m9_gate_path"] = str(M9_GATE.resolve())
    absolute_policy = Path(m10_case["policy_path"]).with_name("absolute-policy.yaml")
    absolute_policy.write_text(yaml.safe_dump(policy, sort_keys=True), encoding="utf-8")
    result = run_shadow_cycle(
        policy_path=absolute_policy,
        predictions_path=m10_case["predictions_path"],
        source_manifest_path=m10_case["manifest_path"],
        state_root=m10_case["state_root"],
        cycle_id=m10_case["cycle_id"],
        as_of=m10_case["as_of"],
        project_root=Path.cwd(),
    )
    assert result["state"] == "COMPLETE"


def test_cli_success_and_live_rejection(m10_case: dict[str, object]) -> None:
    runner = CliRunner()
    preflight = runner.invoke(
        app,
        [
            "shadow-preflight",
            "--policy",
            str(m10_case["policy_path"]),
            "--project-root",
            str(Path.cwd()),
        ],
    )
    assert preflight.exit_code == 0
    assert json.loads(preflight.stdout)["capability"] == "SHADOW_ONLY"

    cycle = runner.invoke(
        app,
        [
            "shadow-cycle",
            "--policy",
            str(m10_case["policy_path"]),
            "--predictions",
            str(m10_case["predictions_path"]),
            "--source-manifest",
            str(m10_case["manifest_path"]),
            "--state-root",
            str(m10_case["state_root"]),
            "--cycle-id",
            str(m10_case["cycle_id"]),
            "--as-of",
            m10_case["as_of"].isoformat(),
            "--project-root",
            str(Path.cwd()),
        ],
    )
    assert cycle.exit_code == 0
    assert json.loads(cycle.stdout)["state"] == "COMPLETE"

    import yaml

    unsafe = copy.deepcopy(m10_case["policy"])
    unsafe["execution_mode"] = "live"
    unsafe_path = Path(m10_case["policy_path"]).with_name("unsafe.yaml")
    unsafe_path.write_text(yaml.safe_dump(unsafe), encoding="utf-8")
    before = state_digest(Path(m10_case["state_root"]))
    rejected = runner.invoke(
        app,
        [
            "shadow-cycle",
            "--policy",
            str(unsafe_path),
            "--predictions",
            str(m10_case["predictions_path"]),
            "--source-manifest",
            str(m10_case["manifest_path"]),
            "--state-root",
            str(m10_case["state_root"]),
            "--cycle-id",
            "m10s-20260731-164500-eeeeeeeeeeee",
            "--as-of",
            m10_case["as_of"].isoformat(),
            "--project-root",
            str(Path.cwd()),
        ],
    )
    assert rejected.exit_code == 2
    assert json.loads(rejected.stderr)["code"] == "INVALID_POLICY"
    assert state_digest(Path(m10_case["state_root"])) == before


def test_production_package_has_no_forbidden_dependencies() -> None:
    root = Path("src/qlib_peerlite/production")
    forbidden = ("requests", "socket", "subprocess", "broker", "credential", "qlib_peerlite.models")
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert all(token not in source for token in forbidden)
