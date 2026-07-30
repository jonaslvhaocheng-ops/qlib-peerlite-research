from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import torch

from qlib_peerlite.governance.artifacts import canonical_json_bytes

from . import M7ContractError
from .ccc import ccc_contract_payload

CHECKPOINT_V2_SCHEMA = "qlib_peerlite_checkpoint_v2"


@dataclass(frozen=True)
class M7CheckpointContext:
    family_id: str
    run_id: str
    fit_id: str
    candidate_id: str
    model_id: str
    seed: int
    fold_id: str
    purpose: str
    execution_spec_sha256: str
    budget_sha256: str
    prerequisite_bundle_sha256: str
    lease_event_sha256: str
    authoritative_ledger_sha256: str
    training_dates_sha256: str
    validation_dates_sha256: str
    state_binding_sha256: str | None


def _state_dict_sha256(state: Mapping[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tensor.dtype).encode("ascii"))
        digest.update(canonical_json_bytes({"shape": list(tensor.shape)}))
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(payload))).hexdigest()


def _require_sha256(value: object, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise M7ContractError(f"M7 checkpoint {name} is not a SHA256")


def validate_checkpoint_v2_header(
    metadata: Mapping[str, Any],
    *,
    expected_model_id: str,
) -> M7CheckpointContext:
    if metadata.get("schema_version") != CHECKPOINT_V2_SCHEMA:
        raise M7ContractError("unsupported M7 checkpoint schema")
    semantic = metadata.get("semantic_payload")
    execution = metadata.get("execution_context")
    if not isinstance(semantic, dict) or not isinstance(execution, dict):
        raise M7ContractError("M7 checkpoint payload is incomplete")
    try:
        context = M7CheckpointContext(**execution)
    except TypeError as exc:
        raise M7ContractError("M7 checkpoint execution context is invalid") from exc
    synthetic = context.family_id == "SYNTHETIC_M7_ENGINEERING_V1"
    empirical = context.family_id == "QLIB_PEERLITE_M7_INITIAL_SCREEN_V1"
    if synthetic:
        if (
            context.purpose != "SYNTHETIC_MECHANICS_ONLY"
            or context.fold_id != "synthetic_reserved_dates"
        ):
            raise M7ContractError("M7 checkpoint is not synthetic engineering evidence")
    elif empirical:
        if context.purpose not in {"ROLLING_SCREEN_FIT", "DETERMINISTIC_REFIT"}:
            raise M7ContractError("M7 empirical checkpoint purpose mismatch")
        if context.fold_id not in {f"wf_{year}" for year in range(2018, 2025)}:
            raise M7ContractError("M7 empirical checkpoint fold mismatch")
    else:
        raise M7ContractError(
            "M7 checkpoint is not synthetic engineering or authorized empirical evidence"
        )
    config = semantic.get("config")
    if not isinstance(config, dict):
        raise M7ContractError("M7 checkpoint candidate config is missing")
    if (
        context.model_id != expected_model_id
        or context.candidate_id != expected_model_id
        or semantic.get("model_id") != expected_model_id
        or semantic.get("candidate_id") != expected_model_id
    ):
        raise M7ContractError("M7 checkpoint candidate/model mismatch")
    for name in (
        "execution_spec_sha256",
        "budget_sha256",
        "prerequisite_bundle_sha256",
        "lease_event_sha256",
        "authoritative_ledger_sha256",
        "training_dates_sha256",
        "validation_dates_sha256",
    ):
        _require_sha256(getattr(context, name), name)
    if context.state_binding_sha256 is not None:
        _require_sha256(context.state_binding_sha256, "state_binding_sha256")
    if context.seed != config.get("seed"):
        raise M7ContractError("M7 checkpoint execution context/config mismatch")
    if synthetic:
        expected_contract_sha256 = hashlib.sha256(b"m7-synthetic-engineering-v1").hexdigest()
        expected_empty_ledger_sha256 = hashlib.sha256(b"").hexdigest()
        if (
            context.fit_id != f"{expected_model_id}:synthetic:seed{config.get('seed')}"
            or context.run_id != f"synthetic-{context.lease_event_sha256[:16]}"
            or context.execution_spec_sha256 != expected_contract_sha256
            or context.budget_sha256 != expected_contract_sha256
            or context.prerequisite_bundle_sha256 != expected_contract_sha256
            or context.authoritative_ledger_sha256 != expected_empty_ledger_sha256
        ):
            raise M7ContractError("M7 checkpoint execution context/config mismatch")
    expected_state_binding = (
        semantic.get("state_binding_sha256") if config.get("market_gate") is True else None
    )
    if context.state_binding_sha256 != expected_state_binding:
        raise M7ContractError("M7 checkpoint market-state binding mismatch")
    _require_sha256(metadata.get("semantic_state_sha256"), "semantic_state_sha256")
    _require_sha256(metadata.get("execution_binding_sha256"), "execution_binding_sha256")
    if metadata["semantic_state_sha256"] != _hash_payload(semantic):
        raise M7ContractError("M7 checkpoint semantic hash mismatch")
    expected_execution = _hash_payload(
        {**asdict(context), "semantic_state_sha256": metadata["semantic_state_sha256"]}
    )
    if metadata["execution_binding_sha256"] != expected_execution:
        raise M7ContractError("M7 checkpoint execution binding mismatch")
    return context


def build_checkpoint_v2_metadata(
    *,
    config: Mapping[str, Any],
    feature_names: list[str],
    standardizer: Mapping[str, Any],
    market_standardizer: Mapping[str, Any] | None,
    training_summary: Mapping[str, Any],
    training_history: list[dict[str, float]],
    state_dict: Mapping[str, torch.Tensor],
    context: M7CheckpointContext,
) -> dict[str, Any]:
    semantic_payload = {
        "candidate_id": context.candidate_id,
        "model_id": context.model_id,
        "config": dict(config),
        "feature_names": feature_names,
        "standardizer": dict(standardizer),
        "market_standardizer": (None if market_standardizer is None else dict(market_standardizer)),
        "objective_contract": (
            ccc_contract_payload()
            if context.candidate_id == "PEERLITE_K16_CCC"
            else {"name": "mse"}
        ),
        "validation_contract": {
            "metric": "mse",
            "improvement_delta": 1e-10,
            "best_epoch": training_summary["best_epoch"],
        },
        "state_dict_sha256": _state_dict_sha256(state_dict),
        "state_binding_sha256": context.state_binding_sha256,
    }
    semantic_sha256 = _hash_payload(semantic_payload)
    execution_payload = {**asdict(context), "semantic_state_sha256": semantic_sha256}
    execution_sha256 = _hash_payload(execution_payload)
    return {
        "schema_version": CHECKPOINT_V2_SCHEMA,
        "semantic_payload": semantic_payload,
        "semantic_state_sha256": semantic_sha256,
        "execution_context": asdict(context),
        "execution_binding_sha256": execution_sha256,
        "training_summary": dict(training_summary),
        "training_history": training_history,
    }


def validate_checkpoint_v2_metadata(
    metadata: Mapping[str, Any],
    state_dict: Mapping[str, torch.Tensor],
) -> M7CheckpointContext:
    if metadata.get("schema_version") != CHECKPOINT_V2_SCHEMA:
        raise M7ContractError("unsupported M7 checkpoint schema")
    semantic = metadata.get("semantic_payload")
    if not isinstance(semantic, dict):
        raise M7ContractError("M7 checkpoint payload is incomplete")
    context = validate_checkpoint_v2_header(
        metadata,
        expected_model_id=str(semantic.get("model_id")),
    )
    if semantic.get("state_dict_sha256") != _state_dict_sha256(state_dict):
        raise M7ContractError("M7 checkpoint state hash mismatch")
    return context


__all__ = [
    "CHECKPOINT_V2_SCHEMA",
    "M7CheckpointContext",
    "build_checkpoint_v2_metadata",
    "validate_checkpoint_v2_header",
    "validate_checkpoint_v2_metadata",
]
