from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import sha256_file


class M6SpecError(RuntimeError):
    """Raised when the immutable M6 PeerLite specification is not intact."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise M6SpecError(message)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M6SpecError(f"cannot read M6 execution spec: {exc}") from exc
    if not isinstance(value, dict):
        raise M6SpecError("M6 execution spec root must be an object")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def load_and_verify_m6_spec(project_root: Path, spec_path: Path) -> dict[str, Any]:
    """Verify the frozen M6 spec, upstream gates, budget and bound code."""

    project_root = project_root.resolve()
    spec_path = spec_path.resolve()
    spec = _load(spec_path)
    declared_content_hash = spec.get("content_sha256")
    unsigned = dict(spec)
    unsigned.pop("content_sha256", None)
    actual_content_hash = hashlib.sha256(
        _canonical_json(unsigned).encode("utf-8")
    ).hexdigest()
    _require(declared_content_hash == actual_content_hash, "M6 spec content hash mismatch")
    _require(
        spec.get("status") == "FROZEN"
        and spec.get("stage") == "M6-PEERLITE-MSE"
        and spec.get("claim_ceiling") == "PRE_FINAL_OOS_DIAGNOSTIC",
        "M6 spec is not a frozen pre-final-OOS PeerLite specification",
    )

    expected_paths = {
        "contract": "contracts/immutable/research_contract_pit_v2.json",
        "candidate_registry": "contracts/candidate_registry.json",
        "model_registry": "configs/model_registry.yaml",
        "feature_spec": "contracts/feature_spec.json",
        "m3_gate": "evidence/gates/M3_pit_data_gate.json",
        "m4_gate": "evidence/gates/M4_qlib_foundation_gate.json",
        "m5_gate": "evidence/gates/M5_baseline_gate.json",
        "data_product_manifest": (
            "data/manifests/pit_data_product_2012_2024_v3/data_product_manifest.json"
        ),
        "mechanics_receipt": (
            "evidence/peerlite/mechanics_20260728_v2/mechanics_receipt.json"
        ),
        "trial_budget_start": "contracts/immutable/m6_trial_budget_start.json",
    }
    bindings = spec.get("bindings")
    _require(isinstance(bindings, Mapping), "M6 upstream bindings are missing")
    for name, expected_relative_path in expected_paths.items():
        item = bindings.get(name)
        _require(isinstance(item, Mapping), f"M6 binding is missing: {name}")
        _require(
            item.get("path") == expected_relative_path,
            f"M6 binding path mismatch: {name}",
        )
        path = project_root / expected_relative_path
        _require(path.is_file(), f"M6 bound artifact is missing: {expected_relative_path}")
        _require(
            item.get("sha256") == sha256_file(path),
            f"M6 bound artifact changed: {name}",
        )

    m3_gate = _load(project_root / expected_paths["m3_gate"])
    _require(
        m3_gate.get("status") == "PASS"
        and m3_gate.get("passed") is True
        and m3_gate.get("scope") == "EXACT_PRE_FINAL_OOS_DEVELOPMENT_INPUT_ONLY"
        and any(
            "No 2025+ final-OOS market partition was opened" in finding
            for finding in m3_gate.get("findings", [])
            if isinstance(finding, str)
        )
        and "2025+ final-OOS access before the M8 one-time opening procedure"
        in m3_gate.get("still_forbidden", []),
        "m3_gate is not a final-OOS-safe PASS",
    )
    for gate_name in ("m4_gate", "m5_gate"):
        gate = _load(project_root / expected_paths[gate_name])
        _require(
            gate.get("status") == "PASS"
            and gate.get("passed") is True
            and gate.get("verification", {}).get(
                "final_oos_market_partitions_opened"
            )
            is False,
            f"{gate_name} is not a final-OOS-safe PASS",
        )
    mechanics = _load(project_root / expected_paths["mechanics_receipt"])
    _require(
        mechanics.get("status") == "PASS"
        and mechanics.get("track") == "SYNTHETIC_ONLY"
        and mechanics.get("real_data_accessed") is False
        and mechanics.get("counts_as_model_fit") is False,
        "M6 mechanics receipt is not a synthetic-only PASS",
    )

    budget = _load(project_root / expected_paths["trial_budget_start"])
    budget_unsigned = dict(budget)
    budget_declared_hash = budget_unsigned.pop("content_sha256", None)
    budget_actual_hash = hashlib.sha256(
        _canonical_json(budget_unsigned).encode("utf-8")
    ).hexdigest()
    ledger_binding = budget.get("trial_ledger")
    _require(
        budget_declared_hash == budget_actual_hash
        and budget.get("status") == "FROZEN"
        and budget.get("stage") == "M6-PEERLITE-MSE"
        and isinstance(ledger_binding, Mapping)
        and ledger_binding.get("path") == "contracts/trial_ledger.jsonl"
        and ledger_binding.get("sha256_at_freeze")
        == sha256_file(project_root / "contracts/trial_ledger.jsonl")
        and budget.get("consumed_before_m6")
        == {"candidate_evaluations": 4, "model_fits": 29}
        and budget.get("declared_m6_increment")
        == {"candidate_evaluations": 2, "model_fits": 15}
        and budget.get("declared_after_m6_success")
        == {"candidate_evaluations": 6, "model_fits": 44}
        and budget.get("limits")
        == {"candidate_evaluations": 27, "model_fits": 60},
        "M6 trial budget or frozen pre-run ledger identity mismatch",
    )

    input_data = spec.get("input_data")
    _require(
        isinstance(input_data, Mapping)
        and input_data.get("product_id") == "pit_data_product_2012_2024_v3"
        and input_data.get("rows") == 1_658_525
        and input_data.get("feature_count") == 50
        and input_data.get("date_max") == "2024-12-17"
        and str(input_data.get("date_max")) < "2025-01-01"
        and input_data.get("final_oos_market_partitions_opened") is False,
        "M6 input identity or final-OOS boundary mismatch",
    )

    schedule = spec.get("schedule")
    expected_folds = [f"wf_{year}" for year in range(2018, 2025)]
    _require(
        isinstance(schedule, Mapping)
        and schedule.get("fold_ids") == expected_folds
        and schedule.get("seed") == 7
        and schedule.get("embargo_sessions") == 5
        and schedule.get("candidate_evaluations") == 2
        and schedule.get("model_fits") == 15,
        "M6 fold schedule, seed or trial increment mismatch",
    )
    cumulative = schedule.get("cumulative_trials_after_success")
    _require(
        isinstance(cumulative, Mapping)
        and cumulative.get("candidate_evaluations") == 6
        and cumulative.get("model_fits") == 44
        and cumulative.get("candidate_evaluation_limit") == 27
        and cumulative.get("model_fit_limit") == 60,
        "M6 cumulative trial accounting is incomplete",
    )

    candidates = spec.get("candidates")
    _require(
        isinstance(candidates, list)
        and [item.get("model_id") for item in candidates if isinstance(item, Mapping)]
        == ["PEERLITE_K16_MSE", "PEERLITE_K32_MSE"],
        "M6 must contain exactly the two registered MSE PeerLite candidates",
    )
    for expected_peers, candidate in zip((16, 32), candidates, strict=True):
        _require(isinstance(candidate, Mapping), "M6 candidate entry is malformed")
        parameters = candidate.get("parameters")
        _require(
            isinstance(parameters, Mapping)
            and parameters.get("model_id") == candidate.get("model_id")
            and parameters.get("input_dim") == 50
            and parameters.get("hidden_dim") == 64
            and parameters.get("num_peers") == expected_peers
            and parameters.get("num_heads") == 4
            and parameters.get("loss") == "mse"
            and parameters.get("market_gate") is False
            and parameters.get("seed") == 7
            and parameters.get("cross_section_batch_size") == 16,
            "M6 PeerLite candidate parameters are incomplete",
        )

    deterministic_refit = spec.get("deterministic_refit")
    _require(
        isinstance(deterministic_refit, Mapping)
        and deterministic_refit.get("model_id") == "PEERLITE_K16_MSE"
        and deterministic_refit.get("fold_id") == "wf_2018"
        and deterministic_refit.get("seed") == 7
        and deterministic_refit.get("exact_score_equality") is True
        and deterministic_refit.get("counts_as_model_fit") is True,
        "M6 deterministic refit contract is incomplete",
    )

    safeguards = spec.get("safeguards")
    _require(
        isinstance(safeguards, Mapping)
        and safeguards.get("final_oos_market_partitions_opened") is False
        and safeguards.get("portfolio_backtests") == 0
        and safeguards.get("cost_adjusted_selection") is False
        and safeguards.get("ccc_allowed") is False
        and safeguards.get("market_gate_allowed") is False
        and safeguards.get("model_selection_performed") is False,
        "M6 spec crosses a prohibited research boundary",
    )
    determinism = spec.get("determinism")
    _require(
        isinstance(determinism, Mapping)
        and determinism.get("cublas_workspace_config") == ":4096:8"
        and determinism.get("torch_deterministic_algorithms") == "STRICT",
        "M6 strict determinism contract is incomplete",
    )
    outputs = spec.get("outputs")
    _require(
        isinstance(outputs, Mapping)
        and outputs.get("prediction_columns")
        == ["datetime", "instrument", "score", "model_id", "fold_id"]
        and outputs.get("checkpoint_reload_required") is True
        and outputs.get("qlib_recorder_readback_required") is True,
        "M6 output or replay contract mismatch",
    )

    code_binding = spec.get("code_binding")
    _require(isinstance(code_binding, Mapping), "M6 code binding is missing")
    files = code_binding.get("files")
    _require(isinstance(files, Mapping) and bool(files), "M6 code inventory is empty")
    for relative_path, declared_hash in files.items():
        _require(
            isinstance(relative_path, str) and isinstance(declared_hash, str),
            "M6 code binding entry is malformed",
        )
        path = project_root / relative_path
        _require(path.is_file(), f"M6 bound code file is missing: {relative_path}")
        _require(
            sha256_file(path) == declared_hash,
            f"M6 bound code file changed: {relative_path}",
        )
    return spec
