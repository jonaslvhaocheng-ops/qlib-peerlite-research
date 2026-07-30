from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path

import pytest

from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.m7 import M7ContractError
from qlib_peerlite.m7.adapter import (
    authorize_synthetic_fit,
    build_synthetic_checkpoint_context,
    checkpoint_config_for_load,
    checkpoint_context_after_state_load,
    checkpoint_context_for_fit,
    checkpoint_payload_for_load,
    is_m7_candidate,
    market_frame,
    validate_candidate_config,
    validate_prediction_dataset,
)
from qlib_peerlite.m7.market_state import (
    SyntheticFixtureSpec,
    build_synthetic_m7_fixture,
)
from qlib_peerlite.models.peerlite import PeerLiteModel


def test_m7_review_repairs_remove_empirical_authority_and_protect_adapter() -> None:
    run_state = importlib.import_module("qlib_peerlite.m7.run_state")
    adapter = importlib.import_module("qlib_peerlite.m7.adapter")

    assert not hasattr(run_state, "EmpiricalFitLease")
    assert not hasattr(run_state, "verify_reconciled_empirical_fit_lease")
    assert hasattr(run_state, "recover_from_persisted_evidence")
    assert hasattr(adapter, "validate_candidate_config")
    assert hasattr(adapter, "authorize_synthetic_fit")


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
        "epochs": 1,
        "patience": 1,
        "learning_rate": 1e-3,
        "weight_decay": 1e-4,
        "gradient_clip_norm": 1.0,
        "cross_section_batch_size": 2,
        "model_id": candidate,
    }


def _fixture() -> tuple[object, object]:
    return build_synthetic_m7_fixture(
        SyntheticFixtureSpec("m7-synthetic-v1", 7, "2000-01-03", 12, 4, 4)
    )


def test_adapter_freezes_candidate_semantics_and_keeps_ordinary_models_ordinary() -> None:
    ordinary = {"model_id": "PEERLITE_K16_MSE"}
    dataset = make_synthetic_dataset(n_dates=12, n_instruments=4, n_features=4)
    assert is_m7_candidate(_config("PEERLITE_K16_CCC"))
    assert not is_m7_candidate(ordinary)
    assert validate_candidate_config(ordinary) is False
    assert authorize_synthetic_fit(ordinary, dataset, None) == (dataset, None)
    assert checkpoint_context_for_fit(
        ordinary,
        None,
        dataset,
        dataset.prepare("train", col_set="feature"),
        dataset.prepare("valid", col_set="feature"),
    ) == (None, None, None)
    assert market_frame(ordinary, dataset, "train") is None
    validate_prediction_dataset(
        ordinary,
        dataset,
        fixture_sha256=None,
        state_binding_sha256=None,
    )
    with pytest.raises(M7ContractError, match="do not accept"):
        authorize_synthetic_fit(ordinary, dataset, object())

    for field, value in (
        ("hidden_dim", 32),
        ("num_peers", 32),
        ("num_heads", 2),
        ("dropout", 0.0),
        ("seed", 19),
        ("market_dim", 9),
        ("market_gate", True),
        ("loss", "mse"),
    ):
        broken = _config("PEERLITE_K16_CCC")
        broken[field] = value
        with pytest.raises(M7ContractError, match="configuration mismatch"):
            validate_candidate_config(broken)


def test_adapter_exact_authority_context_and_prediction_bindings() -> None:
    dataset, base = _fixture()
    ccc = _config("PEERLITE_K16_CCC")
    gate = _config("PEERLITE_K16_MSE_GATE")
    ccc_capability = base.for_candidate("PEERLITE_K16_CCC")
    gate_capability = base.for_candidate("PEERLITE_K16_MSE_GATE")
    train = dataset.prepare("train", col_set="feature")
    valid = dataset.prepare("valid", col_set="feature")

    with pytest.raises(M7ContractError, match="capability mismatch"):
        build_synthetic_checkpoint_context(
            ccc,
            gate_capability,
            dataset,
            train,
            valid,
        )
    with pytest.raises(M7ContractError, match="exact authority"):
        checkpoint_context_for_fit(ccc, None, dataset, train, valid)

    context = build_synthetic_checkpoint_context(
        ccc,
        ccc_capability,
        dataset,
        train,
        valid,
    )
    assert context.state_binding_sha256 is None
    gate_context = build_synthetic_checkpoint_context(
        gate,
        gate_capability,
        dataset,
        train,
        valid,
    )
    assert gate_context.state_binding_sha256 == dataset.state_binding_sha256
    validate_prediction_dataset(
        gate,
        dataset,
        fixture_sha256=dataset.fixture_sha256,
        state_binding_sha256=dataset.state_binding_sha256,
    )
    with pytest.raises(M7ContractError, match="market-state binding"):
        validate_prediction_dataset(
            gate,
            dataset,
            fixture_sha256=dataset.fixture_sha256,
            state_binding_sha256="0" * 64,
        )

    original_columns = dataset._delegate.market_state_columns
    dataset._delegate.market_state_columns = list(reversed(original_columns))
    with pytest.raises(M7ContractError, match="schema/order"):
        market_frame(gate, dataset, "train")


def test_adapter_checkpoint_dispatch_rejects_schema_smuggling(tmp_path: Path) -> None:
    ordinary = PeerLiteModel(
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
    ordinary.fit(make_synthetic_dataset(n_dates=12, n_instruments=4, n_features=4))
    checkpoint = tmp_path / "ordinary"
    ordinary.save_checkpoint(checkpoint)
    v1 = json.loads((checkpoint / "metadata.json").read_text(encoding="utf-8"))
    assert checkpoint_config_for_load(v1)["model_id"] == "PEERLITE_K16_MSE"
    assert checkpoint_payload_for_load(v1) is v1
    assert checkpoint_context_after_state_load(v1, ordinary.network.state_dict()) is None

    with pytest.raises(M7ContractError, match="config is missing"):
        checkpoint_config_for_load({"schema_version": "qlib_peerlite_checkpoint_v1"})
    for mutation in (
        {"model_id": "PEERLITE_K16_CCC", "loss": "mse", "market_gate": False},
        {"model_id": "OTHER", "loss": "ccc", "market_gate": False},
        {"model_id": "OTHER", "loss": "mse", "market_gate": True},
    ):
        broken = copy.deepcopy(v1)
        broken["config"].update(mutation)
        with pytest.raises(M7ContractError, match="limited to non-M7 MSE"):
            checkpoint_config_for_load(broken)
    with pytest.raises(M7ContractError, match="unsupported"):
        checkpoint_config_for_load({"schema_version": "unknown"})
    with pytest.raises(M7ContractError, match="config is missing"):
        checkpoint_config_for_load(
            {
                "schema_version": "qlib_peerlite_checkpoint_v2",
                "semantic_payload": {},
            }
        )
    with pytest.raises(M7ContractError, match="payload is missing"):
        checkpoint_payload_for_load({"schema_version": "qlib_peerlite_checkpoint_v2"})
