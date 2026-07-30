from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import torch

from qlib_peerlite.data.dataset import PanelDataset
from qlib_peerlite.data.market_state import aggregate_daily_state
from qlib_peerlite.m7 import M7ContractError
from qlib_peerlite.m7.adapter import (
    build_synthetic_checkpoint_context,
    checkpoint_context_for_fit,
)
from qlib_peerlite.m7.checkpoint import (
    M7CheckpointContext,
    build_checkpoint_v2_metadata,
    validate_checkpoint_v2_header,
)
from qlib_peerlite.m7.empirical import (
    EmpiricalFitCapability,
    EmpiricalM7Dataset,
    _state_binding_sha256,
    build_empirical_m7_fit,
    require_empirical_authority,
)
from qlib_peerlite.models.peerlite import PeerLiteModel


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _delegate_and_state() -> tuple[PanelDataset, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=12)
    instruments = ["A", "B", "C"]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(rng.normal(size=(len(index), 4)), index=index, columns=list("abcd"))
    frame["label"] = 0.2 * frame["a"] - 0.1 * frame["b"]
    delegate = PanelDataset(
        frame=frame,
        segments={
            "train": (dates[0], dates[5]),
            "valid": (dates[6], dates[8]),
            "test": (dates[9], dates[-1]),
        },
        feature_columns=list("abcd"),
        label_column="label",
    )
    population = pd.DataFrame(
        {
            "ret_mean_20": frame["a"],
            "ret_std_20": frame["b"].abs() + 0.01,
            "ret_1d": frame["c"],
            "turnover_mean_20": frame["d"].abs() + 0.01,
        },
        index=index,
    )
    return delegate, aggregate_daily_state(population)


def _date_hash(frame: pd.DataFrame) -> str:
    dates = pd.DatetimeIndex(frame.index.get_level_values("datetime")).unique().sort_values()
    return hashlib.sha256(
        "\n".join(date.isoformat() for date in dates).encode("ascii")
    ).hexdigest()


def _context(
    delegate: PanelDataset,
    state: pd.DataFrame,
    *,
    candidate: str,
) -> M7CheckpointContext:
    return M7CheckpointContext(
        family_id="QLIB_PEERLITE_M7_INITIAL_SCREEN_V1",
        run_id="m7-test",
        fit_id=f"{candidate}:screen:seed7:wf_2024",
        candidate_id=candidate,
        model_id=candidate,
        seed=7,
        fold_id="wf_2024",
        purpose="ROLLING_SCREEN_FIT",
        execution_spec_sha256=_sha("execution"),
        budget_sha256=_sha("budget"),
        prerequisite_bundle_sha256=_sha("prerequisites"),
        lease_event_sha256=_sha("lease"),
        authoritative_ledger_sha256=_sha("ledger"),
        training_dates_sha256=_date_hash(delegate.prepare("train", col_set="feature")),
        validation_dates_sha256=_date_hash(delegate.prepare("valid", col_set="feature")),
        state_binding_sha256=(
            _state_binding_sha256(state) if candidate == "PEERLITE_K16_MSE_GATE" else None
        ),
    )


def _config(candidate: str) -> dict[str, object]:
    gate = candidate == "PEERLITE_K16_MSE_GATE"
    return {
        "input_dim": 4,
        "hidden_dim": 64,
        "num_peers": 16,
        "num_heads": 4,
        "dropout": 0.1,
        "market_dim": 4 if gate else 0,
        "market_gate": gate,
        "loss": "mse" if gate else "ccc",
        "seed": 7,
        "epochs": 2,
        "patience": 1,
        "learning_rate": 0.001,
        "weight_decay": 0.0001,
        "gradient_clip_norm": 1.0,
        "cross_section_batch_size": 2,
        "device": "cpu",
        "model_id": candidate,
    }


@pytest.mark.parametrize(
    ("candidate", "loss", "gate"),
    [
        ("PEERLITE_K16_CCC", "ccc", False),
        ("PEERLITE_K16_MSE_GATE", "mse", True),
    ],
)
def test_empirical_fit_requires_factory_capability_and_replays(
    tmp_path, candidate: str, loss: str, gate: bool
) -> None:
    delegate, state = _delegate_and_state()
    context = _context(delegate, state, candidate=candidate)
    dataset, capability = build_empirical_m7_fit(
        delegate=delegate,
        state=state,
        candidate_id=candidate,
        context=context,
        dataset_binding_sha256=_sha("dataset"),
    )
    model = PeerLiteModel(
        input_dim=4,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.1,
        market_dim=4 if gate else 0,
        market_gate=gate,
        loss=loss,
        seed=7,
        epochs=2,
        patience=1,
        cross_section_batch_size=2,
        device="cpu",
        model_id=candidate,
    )
    with pytest.raises(M7ContractError):
        model.fit(dataset)
    model.fit(dataset, m7_authority=capability)
    expected = model.predict(dataset)
    checkpoint = tmp_path / candidate
    model.save_checkpoint(checkpoint)
    replay = PeerLiteModel.load_checkpoint(checkpoint, device="cpu").predict(dataset)
    np.testing.assert_array_equal(expected.to_numpy(), replay.to_numpy())


def test_empirical_factory_rejects_wrong_candidate_or_state_binding() -> None:
    delegate, state = _delegate_and_state()
    context = _context(delegate, state, candidate="PEERLITE_K16_MSE_GATE")
    bad = M7CheckpointContext(
        **{**context.__dict__, "state_binding_sha256": _sha("wrong")}
    )
    with pytest.raises(M7ContractError, match="state binding"):
        build_empirical_m7_fit(
            delegate=delegate,
            state=state,
            candidate_id="PEERLITE_K16_MSE_GATE",
            context=bad,
            dataset_binding_sha256=_sha("dataset"),
        )


def test_empirical_wrapper_omits_none_data_key_for_qlib_compatibility() -> None:
    delegate, state = _delegate_and_state()
    missing = object()

    class StrictQlibDelegate:
        def prepare(
            self,
            segment: str,
            *,
            col_set: str | list[str],
            data_key: object = missing,
        ) -> pd.DataFrame:
            if data_key is None:
                raise KeyError(None)
            return delegate.prepare(segment, col_set=col_set)

    context = _context(delegate, state, candidate="PEERLITE_K16_MSE_GATE")
    dataset, _ = build_empirical_m7_fit(
        delegate=StrictQlibDelegate(),
        state=state,
        candidate_id="PEERLITE_K16_MSE_GATE",
        context=context,
        dataset_binding_sha256=_sha("dataset"),
    )
    assert dataset.prepare("train", col_set="feature").shape[1] == 4
    assert dataset.prepare("train", col_set="market_state").shape[1] == 4


def test_empirical_private_constructors_finality_integrity_and_data_key() -> None:
    delegate, state = _delegate_and_state()
    context = _context(delegate, state, candidate="PEERLITE_K16_MSE_GATE")
    with pytest.raises(M7ContractError, match="factory"):
        EmpiricalFitCapability(
            "PEERLITE_K16_MSE_GATE",
            context,
            _sha("dataset"),
            _token=object(),
        )
    with pytest.raises(M7ContractError, match="factory"):
        EmpiricalM7Dataset(
            delegate,
            state,
            _sha("dataset"),
            _sha("lease"),
            _token=object(),
        )
    with pytest.raises(TypeError, match="final"):
        type("ForbiddenEmpiricalDataset", (EmpiricalM7Dataset,), {})

    dataset, _ = build_empirical_m7_fit(
        delegate=delegate,
        state=state,
        candidate_id="PEERLITE_K16_MSE_GATE",
        context=context,
        dataset_binding_sha256=_sha("dataset"),
    )
    calls: list[str | None] = []

    class DataKeyDelegate:
        def prepare(
            self,
            segment: str,
            *,
            col_set: str | list[str],
            data_key: str | None = None,
        ) -> pd.DataFrame:
            calls.append(data_key)
            return delegate.prepare(segment, col_set=col_set)

    keyed, _ = build_empirical_m7_fit(
        delegate=DataKeyDelegate(),
        state=state,
        candidate_id="PEERLITE_K16_MSE_GATE",
        context=context,
        dataset_binding_sha256=_sha("dataset"),
    )
    keyed.prepare("train", col_set="feature", data_key="infer")
    assert calls[-1] == "infer"
    dataset.state_binding_sha256 = _sha("tampered")
    with pytest.raises(M7ContractError, match="binding mismatch"):
        dataset.verify_integrity()


@pytest.mark.parametrize(
    ("candidate", "context_change", "binding", "message"),
    [
        ("OTHER", {}, _sha("dataset"), "outside"),
        (
            "PEERLITE_K16_CCC",
            {"family_id": "OTHER"},
            _sha("dataset"),
            "outside frozen",
        ),
        ("PEERLITE_K16_CCC", {}, "bad", "not a SHA256"),
        (
            "PEERLITE_K16_CCC",
            {"training_dates_sha256": _sha("wrong")},
            _sha("dataset"),
            "dates",
        ),
    ],
)
def test_empirical_factory_rejects_invalid_scope_dates_or_binding(
    candidate: str,
    context_change: dict[str, object],
    binding: str,
    message: str,
) -> None:
    delegate, state = _delegate_and_state()
    base_candidate = "PEERLITE_K16_CCC"
    context = replace(
        _context(delegate, state, candidate=base_candidate),
        **context_change,
    )
    with pytest.raises(M7ContractError, match=message):
        build_empirical_m7_fit(
            delegate=delegate,
            state=state,
            candidate_id=candidate,
            context=context,
            dataset_binding_sha256=binding,
        )


def test_empirical_authority_and_checkpoint_context_fail_closed() -> None:
    delegate, state = _delegate_and_state()
    candidate = "PEERLITE_K16_MSE_GATE"
    context = _context(delegate, state, candidate=candidate)
    dataset, capability = build_empirical_m7_fit(
        delegate=delegate,
        state=state,
        candidate_id=candidate,
        context=context,
        dataset_binding_sha256=_sha("dataset"),
    )
    assert require_empirical_authority(dataset, capability, candidate) is dataset
    with pytest.raises(M7ContractError, match="exact generated"):
        require_empirical_authority(object(), capability, candidate)
    with pytest.raises(M7ContractError, match="candidate mismatch"):
        require_empirical_authority(dataset, capability, "PEERLITE_K16_CCC")

    original_context = capability.context
    object.__setattr__(
        capability,
        "context",
        replace(original_context, lease_event_sha256=_sha("wrong-lease")),
    )
    with pytest.raises(M7ContractError, match="lease mismatch"):
        require_empirical_authority(dataset, capability, candidate)
    object.__setattr__(capability, "context", original_context)
    object.__setattr__(capability, "dataset_binding_sha256", _sha("wrong-dataset"))
    with pytest.raises(M7ContractError, match="dataset mismatch"):
        require_empirical_authority(dataset, capability, candidate)
    object.__setattr__(capability, "dataset_binding_sha256", _sha("dataset"))

    train = delegate.prepare("train", col_set="feature")
    valid = delegate.prepare("valid", col_set="feature")
    config = _config(candidate)
    assert (
        build_synthetic_checkpoint_context(config, capability, dataset, train, valid)
        == context
    )
    object.__setattr__(
        capability,
        "context",
        replace(original_context, candidate_id="PEERLITE_K16_CCC"),
    )
    with pytest.raises(M7ContractError, match="capability mismatch"):
        build_synthetic_checkpoint_context(config, capability, dataset, train, valid)
    object.__setattr__(capability, "context", original_context)
    shorter_train = train.loc[
        train.index.get_level_values("datetime")
        > train.index.get_level_values("datetime").min()
    ]
    with pytest.raises(M7ContractError, match="training-date"):
        build_synthetic_checkpoint_context(
            config,
            capability,
            dataset,
            shorter_train,
            valid,
        )
    shorter_valid = valid.loc[
        valid.index.get_level_values("datetime")
        > valid.index.get_level_values("datetime").min()
    ]
    with pytest.raises(M7ContractError, match="validation-date"):
        build_synthetic_checkpoint_context(
            config,
            capability,
            dataset,
            train,
            shorter_valid,
        )
    with pytest.raises(M7ContractError, match="exact dataset"):
        checkpoint_context_for_fit(config, capability, object(), train, valid)


def test_empirical_checkpoint_header_rejects_bad_purpose_and_fold() -> None:
    delegate, state = _delegate_and_state()
    candidate = "PEERLITE_K16_CCC"
    context = _context(delegate, state, candidate=candidate)
    config = _config(candidate)
    metadata = build_checkpoint_v2_metadata(
        config=config,
        feature_names=list("abcd"),
        standardizer={"mean": [0.0] * 4, "scale": [1.0] * 4},
        market_standardizer=None,
        training_summary={"best_epoch": 1},
        training_history=[],
        state_dict={"weight": torch.tensor([1.0])},
        context=context,
    )
    bad_purpose = dict(metadata)
    bad_purpose["execution_context"] = {
        **metadata["execution_context"],
        "purpose": "OTHER",
    }
    with pytest.raises(M7ContractError, match="purpose"):
        validate_checkpoint_v2_header(bad_purpose, expected_model_id=candidate)
    bad_fold = dict(metadata)
    bad_fold["execution_context"] = {
        **metadata["execution_context"],
        "fold_id": "wf_2025",
    }
    with pytest.raises(M7ContractError, match="fold"):
        validate_checkpoint_v2_header(bad_fold, expected_model_id=candidate)

    synthetic_candidate = "PEERLITE_K16_CCC"
    synthetic_config = _config(synthetic_candidate)
    synthetic_contract = hashlib.sha256(b"m7-synthetic-engineering-v1").hexdigest()
    synthetic_context = M7CheckpointContext(
        family_id="SYNTHETIC_M7_ENGINEERING_V1",
        run_id="wrong-run-id",
        fit_id=f"{synthetic_candidate}:synthetic:seed7",
        candidate_id=synthetic_candidate,
        model_id=synthetic_candidate,
        seed=7,
        fold_id="synthetic_reserved_dates",
        purpose="SYNTHETIC_MECHANICS_ONLY",
        execution_spec_sha256=synthetic_contract,
        budget_sha256=synthetic_contract,
        prerequisite_bundle_sha256=synthetic_contract,
        lease_event_sha256=_sha("lease"),
        authoritative_ledger_sha256=hashlib.sha256(b"").hexdigest(),
        training_dates_sha256=_sha("train"),
        validation_dates_sha256=_sha("valid"),
        state_binding_sha256=None,
    )
    bad_synthetic = build_checkpoint_v2_metadata(
        config=synthetic_config,
        feature_names=list("abcd"),
        standardizer={"mean": [0.0] * 4, "scale": [1.0] * 4},
        market_standardizer=None,
        training_summary={"best_epoch": 1},
        training_history=[],
        state_dict={"weight": torch.tensor([1.0])},
        context=synthetic_context,
    )
    with pytest.raises(M7ContractError, match="context/config mismatch"):
        validate_checkpoint_v2_header(
            bad_synthetic,
            expected_model_id=synthetic_candidate,
        )
