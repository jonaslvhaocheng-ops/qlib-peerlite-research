from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import pandas as pd
import torch

from . import M7ContractError
from .checkpoint import (
    CHECKPOINT_V2_SCHEMA,
    M7CheckpointContext,
    validate_checkpoint_v2_header,
    validate_checkpoint_v2_metadata,
)
from .market_state import (
    DAILY_STATE_COLUMNS,
    M7_CANDIDATES,
    SyntheticFitCapability,
    SyntheticM7Dataset,
    require_synthetic_authority,
)

_FROZEN_COMMON = {
    "hidden_dim": 64,
    "num_peers": 16,
    "num_heads": 4,
    "dropout": 0.1,
    "seed": 7,
}
_FROZEN_CANDIDATES = {
    "PEERLITE_K16_CCC": {
        **_FROZEN_COMMON,
        "market_dim": 0,
        "market_gate": False,
        "loss": "ccc",
    },
    "PEERLITE_K16_MSE_GATE": {
        **_FROZEN_COMMON,
        "market_dim": 4,
        "market_gate": True,
        "loss": "mse",
    },
}


def is_m7_candidate(config: Mapping[str, Any]) -> bool:
    return config.get("model_id") in M7_CANDIDATES


def validate_candidate_config(config: Mapping[str, Any]) -> bool:
    model_id = config.get("model_id")
    if model_id not in M7_CANDIDATES:
        return False
    expected = _FROZEN_CANDIDATES[model_id]
    mismatched = [name for name, value in expected.items() if config.get(name) != value]
    if mismatched:
        raise M7ContractError(f"M7 candidate configuration mismatch: {sorted(mismatched)}")
    return True


def authorize_synthetic_fit(
    config: Mapping[str, Any],
    dataset: object,
    authority: object,
) -> tuple[object, SyntheticFitCapability | None]:
    if not validate_candidate_config(config):
        if authority is not None:
            raise M7ContractError("non-M7 models do not accept M7 authority")
        return dataset, None
    verified = require_synthetic_authority(dataset, authority, str(config["model_id"]))
    return verified, authority


def market_frame(
    config: Mapping[str, Any],
    dataset: object,
    segment: str,
) -> pd.DataFrame | None:
    if not config.get("market_gate"):
        return None
    validate_candidate_config(config)
    if type(dataset) is not SyntheticM7Dataset:
        raise M7ContractError("Gate requires an exact verified M7 dataset")
    dataset.verify_integrity()
    market = dataset.prepare(segment, col_set="market_state")
    if tuple(str(column) for column in market.columns) != DAILY_STATE_COLUMNS:
        raise M7ContractError("Gate market-state schema/order mismatch")
    return market


def validate_prediction_dataset(
    config: Mapping[str, Any],
    dataset: object,
    *,
    fixture_sha256: str | None,
    state_binding_sha256: str | None,
) -> None:
    if not validate_candidate_config(config):
        return
    if type(dataset) is not SyntheticM7Dataset:
        raise M7ContractError("M7 prediction requires the exact synthetic dataset")
    dataset.verify_integrity()
    if dataset.fixture_sha256 != fixture_sha256:
        raise M7ContractError("M7 prediction fixture mismatch")
    if config["market_gate"] and dataset.state_binding_sha256 != state_binding_sha256:
        raise M7ContractError("M7 prediction market-state binding mismatch")


def _dates_sha256(frame: pd.DataFrame) -> str:
    dates = pd.DatetimeIndex(frame.index.get_level_values("datetime")).unique().sort_values()
    return hashlib.sha256("\n".join(date.isoformat() for date in dates).encode("ascii")).hexdigest()


def build_synthetic_checkpoint_context(
    config: Mapping[str, Any],
    capability: SyntheticFitCapability,
    dataset: SyntheticM7Dataset,
    x_train: pd.DataFrame,
    x_valid: pd.DataFrame,
) -> M7CheckpointContext:
    validate_candidate_config(config)
    if capability.candidate_id != config["model_id"]:
        raise M7ContractError("synthetic checkpoint capability mismatch")
    contract_sha256 = hashlib.sha256(b"m7-synthetic-engineering-v1").hexdigest()
    return M7CheckpointContext(
        family_id="SYNTHETIC_M7_ENGINEERING_V1",
        run_id=f"synthetic-{capability.fixture_sha256[:16]}",
        fit_id=f"{config['model_id']}:synthetic:seed{config['seed']}",
        candidate_id=str(config["model_id"]),
        model_id=str(config["model_id"]),
        seed=int(config["seed"]),
        fold_id="synthetic_reserved_dates",
        purpose="SYNTHETIC_MECHANICS_ONLY",
        execution_spec_sha256=contract_sha256,
        budget_sha256=contract_sha256,
        prerequisite_bundle_sha256=contract_sha256,
        lease_event_sha256=capability.fixture_sha256,
        authoritative_ledger_sha256=hashlib.sha256(b"").hexdigest(),
        training_dates_sha256=_dates_sha256(x_train),
        validation_dates_sha256=_dates_sha256(x_valid),
        state_binding_sha256=(dataset.state_binding_sha256 if config["market_gate"] else None),
    )


def checkpoint_context_for_fit(
    config: Mapping[str, Any],
    authority: SyntheticFitCapability | None,
    dataset: object,
    x_train: pd.DataFrame,
    x_valid: pd.DataFrame,
) -> tuple[M7CheckpointContext | None, str | None, str | None]:
    if not validate_candidate_config(config):
        return None, None, None
    if type(authority) is not SyntheticFitCapability or type(dataset) is not SyntheticM7Dataset:
        raise M7ContractError("synthetic checkpoint context requires exact authority")
    context = build_synthetic_checkpoint_context(
        config,
        authority,
        dataset,
        x_train,
        x_valid,
    )
    return (
        context,
        dataset.fixture_sha256,
        dataset.state_binding_sha256 if config["market_gate"] else None,
    )


def checkpoint_config_for_load(metadata: Mapping[str, Any]) -> dict[str, Any]:
    schema = metadata.get("schema_version")
    if schema == "qlib_peerlite_checkpoint_v1":
        config = metadata.get("config")
        if not isinstance(config, dict):
            raise M7ContractError("PeerLite v1 checkpoint config is missing")
        if (
            config.get("model_id") in M7_CANDIDATES
            or config.get("loss") != "mse"
            or config.get("market_gate") is not False
        ):
            raise M7ContractError("checkpoint v1 is limited to non-M7 MSE")
        return dict(config)
    if schema == CHECKPOINT_V2_SCHEMA:
        semantic = metadata.get("semantic_payload")
        if not isinstance(semantic, dict) or not isinstance(semantic.get("config"), dict):
            raise M7ContractError("PeerLite v2 checkpoint config is missing")
        config = dict(semantic["config"])
        validate_candidate_config(config)
        validate_checkpoint_v2_header(metadata, expected_model_id=str(config["model_id"]))
        return config
    raise M7ContractError("unsupported PeerLite checkpoint")


def checkpoint_payload_for_load(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    if metadata.get("schema_version") == CHECKPOINT_V2_SCHEMA:
        semantic = metadata.get("semantic_payload")
        if not isinstance(semantic, dict):
            raise M7ContractError("PeerLite v2 checkpoint payload is missing")
        return semantic
    return metadata


def checkpoint_context_after_state_load(
    metadata: Mapping[str, Any],
    state: Mapping[str, torch.Tensor],
) -> M7CheckpointContext | None:
    if metadata.get("schema_version") != CHECKPOINT_V2_SCHEMA:
        return None
    return validate_checkpoint_v2_metadata(metadata, state)


__all__ = [
    "authorize_synthetic_fit",
    "build_synthetic_checkpoint_context",
    "checkpoint_context_after_state_load",
    "checkpoint_context_for_fit",
    "checkpoint_config_for_load",
    "checkpoint_payload_for_load",
    "is_m7_candidate",
    "market_frame",
    "validate_candidate_config",
    "validate_prediction_dataset",
]
