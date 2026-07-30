from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import test_m7_review_repairs_red as repair_tests
import torch

from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.governance.artifacts import canonical_json_bytes
from qlib_peerlite.governance.trial_ledger import (
    LedgerPrefixBinding,
    RunIntent,
    TrialLimits,
    reconcile_started_events,
)
from qlib_peerlite.m7 import M7ContractError, M7StateError
from qlib_peerlite.m7.ccc import (
    CCC_CONTRACT_VERSION,
    CCC_EPSILON,
    ConcordanceCorrelationLoss,
    ccc_contract_payload,
)
from qlib_peerlite.m7.checkpoint import (
    CHECKPOINT_V2_SCHEMA,
    M7CheckpointContext,
    build_checkpoint_v2_metadata,
    validate_checkpoint_v2_header,
    validate_checkpoint_v2_metadata,
)
from qlib_peerlite.m7.market_state import (
    M7_CANDIDATES,
    SYNTHETIC_CLAIM_CEILING,
    SyntheticFitCapability,
    SyntheticFixtureSpec,
    SyntheticM7Dataset,
    build_synthetic_m7_fixture,
    require_synthetic_authority,
)
from qlib_peerlite.m7.prerequisites import (
    M7_PREREQUISITE_REGISTRY_V1,
    validate_screening_prerequisites,
)
from qlib_peerlite.m7.run_state import (
    M7_FAMILY_ID,
    M7_FITS,
    M7RunState,
    acknowledge_candidate,
    acknowledge_fit,
    authorize_run,
    finish_active_fit,
    finish_candidate,
    recover_from_persisted_evidence,
    start_next_candidate,
    start_next_fit,
)
from qlib_peerlite.models.peerlite import PeerLiteModel


def _spec(**overrides: object) -> SyntheticFixtureSpec:
    values: dict[str, object] = {
        "fixture_version": "m7-synthetic-v1",
        "seed": 7,
        "start_date": "2000-01-03",
        "trading_days": 12,
        "instruments": 4,
        "feature_count": 4,
    }
    values.update(overrides)
    return SyntheticFixtureSpec(**values)


def _model(candidate: str, *, epochs: int = 1) -> PeerLiteModel:
    gate = candidate == "PEERLITE_K16_MSE_GATE"
    return PeerLiteModel(
        4,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.1,
        market_dim=4 if gate else 0,
        market_gate=gate,
        loss="mse" if gate else "ccc",
        seed=7,
        epochs=epochs,
        patience=1,
        cross_section_batch_size=2,
        device="cpu",
        model_id=candidate,
    )


def _write_prerequisites(root: Path) -> None:
    for rule in M7_PREREQUISITE_REGISTRY_V1:
        path = root / rule.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": rule.expected_schema or f"{rule.name}_v1",
                    "semantic_version": "1.0.0",
                    "status": rule.required_status,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )


def _event(intent: RunIntent, *, source_event_id: str | None = None) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": "qlib_peerlite_run_journal_event_v2",
        "run_id": intent.run_id,
        "event_seq": 1,
        "source_event_id": source_event_id or f"{intent.run_id}:000001",
        "run_intent_sha256": intent.content_sha256,
        "event": "MODEL_FIT_STARTED",
        "timestamp": "2026-07-30T02:00:00+08:00",
        "family_id": intent.family_id,
        "execution_spec_content_sha256": intent.execution_spec_content_sha256,
        "evaluation_id": "PEERLITE_K16_CCC:screen:seed7",
        "model_id": "PEERLITE_K16_CCC",
        "seed": 7,
        "counts_as_candidate_evaluation": False,
        "counts_as_model_fit": True,
        "fit_id": "PEERLITE_K16_CCC:screen:seed7:wf_2018",
        "fold_id": "wf_2018",
        "purpose": "ROLLING_SCREEN_FIT",
    }
    event["event_sha256"] = hashlib.sha256(canonical_json_bytes(event)).hexdigest()
    return event


def test_ccc_public_contract_and_degenerate_cases() -> None:
    assert CCC_CONTRACT_VERSION == "qlib_peerlite_ccc_numerical_contract_v1"
    assert CCC_EPSILON == 1e-8
    assert ccc_contract_payload()["singleton"] == "mse"
    constant = ConcordanceCorrelationLoss()(
        torch.ones(4, dtype=torch.float32),
        torch.ones(4, dtype=torch.float32),
    )
    assert constant.dtype == torch.float64
    assert torch.isfinite(constant)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("fixture_version", "bad", "version"),
        ("seed", True, "seed"),
        ("seed", 8, "seed"),
        ("start_date", "2000-01-04", "reserved"),
        ("trading_days", 7, "trading_days"),
        ("trading_days", 65, "trading_days"),
        ("instruments", 1, "instruments"),
        ("instruments", 17, "instruments"),
        ("feature_count", 0, "feature_count"),
        ("feature_count", 17, "feature_count"),
    ],
)
def test_synthetic_spec_rejects_every_invalid_class(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(M7ContractError, match=message):
        _spec(**{field: value})


def test_synthetic_fixture_is_deterministic_owned_final_and_candidate_bound() -> None:
    first, base_capability = build_synthetic_m7_fixture(_spec())
    second, second_capability = build_synthetic_m7_fixture(_spec())
    assert first.claim_ceiling == SYNTHETIC_CLAIM_CEILING
    assert first.segments == second.segments
    assert first.fixture_sha256 == second.fixture_sha256
    assert base_capability.fixture_sha256 == second_capability.fixture_sha256
    pd.testing.assert_frame_equal(first.prepare("train"), second.prepare("train"))
    with pytest.raises(TypeError, match="final"):
        type("Forbidden", (SyntheticM7Dataset,), {})
    with pytest.raises(M7ContractError, match="candidate"):
        base_capability.for_candidate("OTHER")
    capability = base_capability.for_candidate(M7_CANDIDATES[0])
    assert require_synthetic_authority(first, capability, M7_CANDIDATES[0]) is first
    with pytest.raises(M7ContractError, match="exact generated"):
        require_synthetic_authority(make_synthetic_dataset(), capability, M7_CANDIDATES[0])
    with pytest.raises(M7ContractError, match="candidate mismatch"):
        require_synthetic_authority(first, capability, M7_CANDIDATES[1])
    _, different_capability = build_synthetic_m7_fixture(_spec(trading_days=13))
    with pytest.raises(M7ContractError, match="fixture mismatch"):
        require_synthetic_authority(
            first,
            different_capability.for_candidate(M7_CANDIDATES[0]),
            M7_CANDIDATES[0],
        )


def test_synthetic_private_constructors_and_integrity_fail_closed() -> None:
    dataset, capability = build_synthetic_m7_fixture(_spec())
    with pytest.raises(M7ContractError, match="fixture factory"):
        SyntheticFitCapability("0" * 64, None, _token=object())
    with pytest.raises(M7ContractError, match="fixture factory"):
        SyntheticM7Dataset(
            make_synthetic_dataset(n_dates=12, n_instruments=4, n_features=4),
            "0" * 64,
            "0" * 64,
            _token=object(),
        )
    with pytest.raises(M7ContractError, match="exact specification"):
        build_synthetic_m7_fixture(object())  # type: ignore[arg-type]
    dataset._delegate.frame.iloc[0, 0] += 1.0
    with pytest.raises(M7ContractError, match="integrity"):
        dataset.verify_integrity()
    assert capability.claim_ceiling == SYNTHETIC_CLAIM_CEILING


def test_current_repository_prerequisites_are_frozen_and_complete() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = validate_screening_prerequisites(root)
    assert len(bundle.artifact_sha256) == 18
    assert bundle.claim_ceiling == "PRECHECK_ONLY_NOT_FIT_AUTHORITY"


def test_prerequisite_registry_passes_and_hashes_exact_fixed_files(tmp_path: Path) -> None:
    _write_prerequisites(tmp_path)
    first = validate_screening_prerequisites(tmp_path)
    second = validate_screening_prerequisites(tmp_path)
    assert len(first.artifact_sha256) == 18
    assert first == second
    assert len(first.bundle_sha256) == 64
    assert first.claim_ceiling == "PRECHECK_ONLY_NOT_FIT_AUTHORITY"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "bom",
        "duplicate",
        "nonfinite",
        "invalid_json",
        "invalid_utf8",
        "array",
        "schema",
        "status",
        "version",
    ],
)
def test_prerequisite_parser_fails_closed(tmp_path: Path, mutation: str) -> None:
    _write_prerequisites(tmp_path)
    rule = M7_PREREQUISITE_REGISTRY_V1[1]
    path = tmp_path / rule.path
    if mutation == "missing":
        path.unlink()
    elif mutation == "bom":
        path.write_bytes(b"\xef\xbb\xbf{}")
    elif mutation == "duplicate":
        path.write_text('{"status":"FROZEN","status":"PASS"}', encoding="utf-8")
    elif mutation == "nonfinite":
        path.write_text('{"status":"FROZEN","x":NaN}', encoding="utf-8")
    elif mutation == "invalid_json":
        path.write_text("{", encoding="utf-8")
    elif mutation == "invalid_utf8":
        path.write_bytes(b"\xff")
    elif mutation == "array":
        path.write_text("[]", encoding="utf-8")
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "schema":
            payload["schema_version"] = "wrong"
        elif mutation == "status":
            payload["status"] = "PLANNED"
        elif mutation == "version":
            payload["semantic_version"] = ""
        path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(M7ContractError, match="prerequisites"):
        validate_screening_prerequisites(tmp_path)


def test_prerequisite_symlink_is_rejected(tmp_path: Path) -> None:
    _write_prerequisites(tmp_path)
    rule = M7_PREREQUISITE_REGISTRY_V1[0]
    path = tmp_path / rule.path
    target = path.with_name("target.json")
    path.replace(target)
    path.symlink_to(target)
    with pytest.raises(M7ContractError, match="unsafe path"):
        validate_screening_prerequisites(tmp_path)


def _persisted_recovery_evidence(
    tmp_path: Path,
) -> tuple[RunIntent, Path, Path, Path, dict[str, object]]:
    _write_prerequisites(tmp_path)
    intent = RunIntent(
        "m7-test-run",
        M7_FAMILY_ID,
        "a" * 64,
        budget_limit_binding={"version": 1},
        market_state_authority_binding={"version": 1},
    )
    journal_root = tmp_path / "runs"
    journal = journal_root / intent.run_id / "events.jsonl"
    journal.parent.mkdir(parents=True)
    event = _event(intent)
    journal.write_bytes(canonical_json_bytes(event) + b"\n")
    ledger = tmp_path / "ledger.jsonl"
    reconcile_started_events(
        journal,
        ledger,
        run_intent=intent,
        journal_root=journal_root,
        expected_ledger_prefix=LedgerPrefixBinding.empty(),
        limits=TrialLimits(8, 60),
    )
    return intent, journal_root, journal, ledger, event


def test_recovery_uses_persisted_evidence_not_caller_digests(tmp_path: Path) -> None:
    intent, journal_root, journal, ledger, event = _persisted_recovery_evidence(tmp_path)
    pending = M7RunState(status="FIT_INTENT")
    ledger_bytes = ledger.read_bytes()
    ledger.unlink()
    assert (
        recover_from_persisted_evidence(
            pending,
            journal_path=journal,
            ledger_path=ledger,
            run_intent=intent,
            journal_root=journal_root,
            source_event_id=str(event["source_event_id"]),
        )
        is pending
    )
    ledger.write_bytes(ledger_bytes)
    recovered = recover_from_persisted_evidence(
        pending,
        journal_path=journal,
        ledger_path=ledger,
        run_intent=intent,
        journal_root=journal_root,
        source_event_id=str(event["source_event_id"]),
    )
    assert recovered.status == "FIT_INTERRUPTED"

    receipt = {
        "schema_version": "qlib_peerlite_fit_terminal_v1",
        "run_id": intent.run_id,
        "source_event_id": event["source_event_id"],
        "model_id": "PEERLITE_K16_CCC",
        "seed": 7,
        "fold_id": "wf_2018",
        "purpose": "ROLLING_SCREEN_FIT",
        "outcome": "SUCCESS",
        "checkpoint_sha256": "a" * 64,
        "output_sha256": "b" * 64,
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
    receipt_path = tmp_path / "terminal.json"
    receipt_path.write_bytes(canonical_json_bytes(receipt) + b"\n")
    succeeded = recover_from_persisted_evidence(
        pending,
        journal_path=journal,
        ledger_path=ledger,
        run_intent=intent,
        journal_root=journal_root,
        source_event_id=str(event["source_event_id"]),
        terminal_receipt_path=receipt_path,
    )
    assert succeeded.status == "FIT_SUCCESS"
    assert succeeded.fit_index == 1

    with pytest.raises(M7StateError, match="pending fit intent"):
        recover_from_persisted_evidence(
            M7RunState(),
            journal_path=journal,
            ledger_path=ledger,
            run_intent=intent,
            journal_root=journal_root,
            source_event_id=str(event["source_event_id"]),
        )
    with pytest.raises(M7StateError, match="missing or duplicated"):
        recover_from_persisted_evidence(
            pending,
            journal_path=journal,
            ledger_path=ledger,
            run_intent=intent,
            journal_root=journal_root,
            source_event_id="missing",
        )
    with pytest.raises(M7StateError, match="identity mismatch"):
        recover_from_persisted_evidence(
            M7RunState(status="FIT_INTENT", candidate_index=1),
            journal_path=journal,
            ledger_path=ledger,
            run_intent=intent,
            journal_root=journal_root,
            source_event_id=str(event["source_event_id"]),
        )

    for field, value, message in (
        ("extra", True, "schema mismatch"),
        ("receipt_sha256", "0" * 64, "hash mismatch"),
        ("schema_version", "WRONG_SCHEMA", "schema version mismatch"),
        ("outcome", "FAILED", "identity mismatch"),
        ("checkpoint_sha256", "BAD", "checkpoint_sha256 is invalid"),
        ("output_sha256", "BAD", "output_sha256 is invalid"),
    ):
        broken = dict(receipt)
        broken[field] = value
        if field not in {"extra", "receipt_sha256"}:
            unsigned = {key: item for key, item in broken.items() if key != "receipt_sha256"}
            broken["receipt_sha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
        receipt_path.write_bytes(canonical_json_bytes(broken) + b"\n")
        with pytest.raises(M7StateError, match=message):
            recover_from_persisted_evidence(
                pending,
                journal_path=journal,
                ledger_path=ledger,
                run_intent=intent,
                journal_root=journal_root,
                source_event_id=str(event["source_event_id"]),
                terminal_receipt_path=receipt_path,
            )
    malformed_receipts = (
        (b"\xef\xbb\xbf{}\n", "canonical UTF-8"),
        (b'{"x":1,"x":2}\n', "duplicate"),
        (b'{"x":NaN}\n', "non-finite"),
        (b"\xff", "strict UTF-8"),
        (b"{", "strict UTF-8"),
        (b"[]\n", "schema mismatch"),
        (json.dumps(receipt).encode("utf-8") + b"\n", "not canonical JSON"),
    )
    for raw, message in malformed_receipts:
        receipt_path.write_bytes(raw)
        with pytest.raises(M7StateError, match=message):
            recover_from_persisted_evidence(
                pending,
                journal_path=journal,
                ledger_path=ledger,
                run_intent=intent,
                journal_root=journal_root,
                source_event_id=str(event["source_event_id"]),
                terminal_receipt_path=receipt_path,
            )


def test_run_state_legal_sequence_caps_and_terminal_replay() -> None:
    state = authorize_run("a" * 64)
    state = start_next_candidate(state)
    state = acknowledge_candidate(state, "b" * 64)
    for _ in M7_FITS:
        state = start_next_fit(state)
        state = acknowledge_fit(state, "c" * 64)
        state = finish_active_fit(state, "SUCCESS")
    state = finish_candidate(state)
    assert state.status == "CANDIDATE_COMPLETE"
    state = start_next_candidate(state)
    state = acknowledge_candidate(state, "d" * 64)
    for _ in M7_FITS:
        state = finish_active_fit(
            acknowledge_fit(start_next_fit(state), "e" * 64),
            "SUCCESS",
        )
    state = finish_candidate(state)
    assert state.status == "RUN_SCREEN_COMPLETE"
    assert (
        recover_from_persisted_evidence(
            state,
            journal_path="unused",
            ledger_path="unused",
            run_intent=RunIntent(
                "unused",
                M7_FAMILY_ID,
                "a" * 64,
                budget_limit_binding={"version": 1},
                market_state_authority_binding={"version": 1},
            ),
            journal_root="unused",
            source_event_id="unused",
        )
        is state
    )


@pytest.mark.parametrize(
    "action",
    [
        lambda: authorize_run("short"),
        lambda: start_next_candidate(M7RunState()),
        lambda: acknowledge_candidate(M7RunState(status="CANDIDATE_INTENT"), "short"),
        lambda: start_next_fit(M7RunState(status="NOT_AUTHORIZED")),
        lambda: acknowledge_fit(M7RunState(status="FIT_INTENT"), "short"),
        lambda: finish_active_fit(M7RunState(status="FIT_AUTHORIZED"), "BAD"),
        lambda: finish_candidate(M7RunState(status="FIT_SUCCESS", fit_index=1)),
    ],
)
def test_run_state_rejects_illegal_transitions(action: object) -> None:
    with pytest.raises(M7StateError):
        action()  # type: ignore[operator]


def test_run_state_failure_interruption_and_caps() -> None:
    failed = finish_active_fit(M7RunState(status="FIT_AUTHORIZED"), "FAILED")
    interrupted = finish_active_fit(M7RunState(status="FIT_AUTHORIZED"), "INTERRUPTED")
    assert failed.status == "FIT_FAILED"
    assert interrupted.status == "FIT_INTERRUPTED"
    with pytest.raises(M7StateError, match="cap"):
        start_next_candidate(M7RunState(status="PREREQUISITES_VERIFIED", candidate_starts=8))
    with pytest.raises(M7StateError, match="cap"):
        start_next_fit(M7RunState(status="CANDIDATE_RECONCILED", fit_starts=60))


def _checkpoint_context(candidate: str) -> M7CheckpointContext:
    gate = candidate == "PEERLITE_K16_MSE_GATE"
    contract_hash = hashlib.sha256(b"m7-synthetic-engineering-v1").hexdigest()
    lease_hash = "d" * 64
    return M7CheckpointContext(
        family_id="SYNTHETIC_M7_ENGINEERING_V1",
        run_id=f"synthetic-{lease_hash[:16]}",
        fit_id=f"{candidate}:synthetic:seed7",
        candidate_id=candidate,
        model_id=candidate,
        seed=7,
        fold_id="synthetic_reserved_dates",
        purpose="SYNTHETIC_MECHANICS_ONLY",
        execution_spec_sha256=contract_hash,
        budget_sha256=contract_hash,
        prerequisite_bundle_sha256=contract_hash,
        lease_event_sha256=lease_hash,
        authoritative_ledger_sha256=hashlib.sha256(b"").hexdigest(),
        training_dates_sha256="f" * 64,
        validation_dates_sha256="0" * 64,
        state_binding_sha256="1" * 64 if gate else None,
    )


def test_checkpoint_v2_semantic_and_execution_mutations_fail() -> None:
    state = {"weight": torch.tensor([1.0], dtype=torch.float32)}
    context = _checkpoint_context("PEERLITE_K16_CCC")
    metadata = build_checkpoint_v2_metadata(
        config=_model(context.model_id).config,
        feature_names=["f00"],
        standardizer={"columns": ["f00"], "mean": [0.0], "scale": [1.0]},
        market_standardizer=None,
        training_summary={"best_epoch": 0},
        training_history=[{"epoch": 0.0}],
        state_dict=state,
        context=context,
    )
    assert metadata["schema_version"] == CHECKPOINT_V2_SCHEMA
    assert validate_checkpoint_v2_metadata(metadata, state) == context
    with pytest.raises(M7ContractError, match="state hash"):
        validate_checkpoint_v2_metadata(metadata, {"weight": torch.tensor([2.0])})
    broken = copy.deepcopy(metadata)
    broken["semantic_state_sha256"] = "0" * 64
    with pytest.raises(M7ContractError, match="semantic hash"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_binding_sha256"] = "0" * 64
    with pytest.raises(M7ContractError, match="execution binding"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["semantic_payload"]["candidate_id"] = "OTHER"
    broken["semantic_state_sha256"] = hashlib.sha256(
        canonical_json_bytes(broken["semantic_payload"])
    ).hexdigest()
    broken["execution_binding_sha256"] = hashlib.sha256(
        canonical_json_bytes(
            {
                **broken["execution_context"],
                "semantic_state_sha256": broken["semantic_state_sha256"],
            }
        )
    ).hexdigest()
    with pytest.raises(M7ContractError, match="candidate/model"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_context"]["family_id"] = "EMPIRICAL"
    with pytest.raises(M7ContractError, match="not synthetic"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_context"].pop("run_id")
    with pytest.raises(M7ContractError, match="context is invalid"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_context"]["budget_sha256"] = "BAD"
    with pytest.raises(M7ContractError, match="not a SHA256"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_context"]["state_binding_sha256"] = "BAD"
    with pytest.raises(M7ContractError, match="state_binding_sha256"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["semantic_payload"].pop("config")
    with pytest.raises(M7ContractError, match="candidate config is missing"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_context"]["fold_id"] = "wf_2018"
    with pytest.raises(M7ContractError, match="not synthetic"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_context"]["seed"] = 999
    with pytest.raises(M7ContractError, match="context/config mismatch"):
        validate_checkpoint_v2_metadata(broken, state)
    broken = copy.deepcopy(metadata)
    broken["execution_context"]["state_binding_sha256"] = "1" * 64
    with pytest.raises(M7ContractError, match="market-state binding mismatch"):
        validate_checkpoint_v2_metadata(broken, state)
    with pytest.raises(M7ContractError, match="schema"):
        validate_checkpoint_v2_metadata({"schema_version": "bad"}, state)
    with pytest.raises(M7ContractError, match="incomplete"):
        validate_checkpoint_v2_metadata({"schema_version": CHECKPOINT_V2_SCHEMA}, state)
    with pytest.raises(M7ContractError, match="schema"):
        validate_checkpoint_v2_header({"schema_version": "bad"}, expected_model_id="x")
    with pytest.raises(M7ContractError, match="incomplete"):
        validate_checkpoint_v2_header(
            {"schema_version": CHECKPOINT_V2_SCHEMA},
            expected_model_id="x",
        )


@pytest.mark.parametrize("candidate", M7_CANDIDATES)
def test_public_synthetic_fit_checkpoint_reload_and_score_replay(
    tmp_path: Path, candidate: str
) -> None:
    dataset, base_capability = build_synthetic_m7_fixture(_spec())
    capability = base_capability.for_candidate(candidate)
    first = _model(candidate)
    first.fit(dataset, m7_authority=capability)
    score = first.predict(dataset, "test")
    assert score.name == "score"
    assert score.index.names == ["datetime", "instrument"]
    assert score.index.is_unique and score.index.is_monotonic_increasing
    assert np.isfinite(score.to_numpy()).all()
    checkpoint = tmp_path / candidate
    first.save_checkpoint(checkpoint)
    metadata = json.loads((checkpoint / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["schema_version"] == CHECKPOINT_V2_SCHEMA
    loaded = PeerLiteModel.load_checkpoint(checkpoint, device="cpu")
    np.testing.assert_array_equal(
        loaded.predict(dataset, "test").to_numpy(),
        score.to_numpy(),
    )
    if candidate == "PEERLITE_K16_MSE_GATE":
        train_market = dataset.prepare("train", col_set="market_state")
        expected = train_market.groupby(level="datetime").first().mean()
        pd.testing.assert_series_equal(
            loaded.market_standardizer.mean_,
            expected.astype(float),
            check_names=False,
        )


def test_m7_model_authority_and_prediction_rejections() -> None:
    dataset, base = build_synthetic_m7_fixture(_spec())
    ccc = _model("PEERLITE_K16_CCC")
    with pytest.raises(M7ContractError, match="requires"):
        ccc.fit(dataset)
    with pytest.raises(M7ContractError, match="candidate mismatch"):
        ccc.fit(
            dataset,
            m7_authority=base.for_candidate("PEERLITE_K16_MSE_GATE"),
        )
    ccc.fit(dataset, m7_authority=base.for_candidate("PEERLITE_K16_CCC"))
    with pytest.raises(M7ContractError, match="exact synthetic"):
        ccc.predict(make_synthetic_dataset(n_dates=12, n_instruments=4, n_features=4))
    other, _ = build_synthetic_m7_fixture(_spec(trading_days=13))
    with pytest.raises(M7ContractError, match="fixture mismatch"):
        ccc.predict(other)
    base_model = PeerLiteModel(
        4,
        hidden_dim=8,
        num_peers=16,
        num_heads=2,
        dropout=0.0,
        epochs=1,
        patience=1,
        device="cpu",
        model_id="PEERLITE_K16_MSE",
    )
    with pytest.raises(M7ContractError, match="do not accept"):
        base_model.fit(dataset, m7_authority=base)
    with pytest.raises(TypeError, match="unexpected"):
        ccc.fit(dataset, unexpected=True)


def test_protected_adapter_review_suite_is_in_core_denominator(tmp_path: Path) -> None:
    repair_tests.test_m7_review_repairs_remove_empirical_authority_and_protect_adapter()
    repair_tests.test_adapter_freezes_candidate_semantics_and_keeps_ordinary_models_ordinary()
    repair_tests.test_adapter_exact_authority_context_and_prediction_bindings()
    repair_tests.test_adapter_checkpoint_dispatch_rejects_schema_smuggling(tmp_path)
