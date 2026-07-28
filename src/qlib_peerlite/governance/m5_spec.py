from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import sha256_file


class M5SpecError(RuntimeError):
    """Raised when the immutable M5 baseline specification is not intact."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise M5SpecError(message)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M5SpecError(f"cannot read M5 execution spec: {exc}") from exc
    if not isinstance(value, dict):
        raise M5SpecError("M5 execution spec root must be an object")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def load_and_verify_m5_spec(project_root: Path, spec_path: Path) -> dict[str, Any]:
    """Verify the frozen M5 spec, its upstream gates and every bound code byte."""

    project_root = project_root.resolve()
    spec_path = spec_path.resolve()
    spec = _load(spec_path)
    declared_content_hash = spec.get("content_sha256")
    unsigned = dict(spec)
    unsigned.pop("content_sha256", None)
    actual_content_hash = hashlib.sha256(
        _canonical_json(unsigned).encode("utf-8")
    ).hexdigest()
    _require(declared_content_hash == actual_content_hash, "M5 spec content hash mismatch")
    _require(
        spec.get("status") == "FROZEN"
        and spec.get("stage") == "M5-STRICT_BASELINES"
        and spec.get("claim_ceiling") == "PRE_FINAL_OOS_DIAGNOSTIC",
        "M5 spec is not a frozen pre-final-OOS baseline specification",
    )

    bindings = spec.get("bindings")
    _require(isinstance(bindings, Mapping), "M5 upstream bindings are missing")
    expected_paths = {
        "contract": "contracts/immutable/research_contract_pit_v2.json",
        "candidate_registry": "contracts/candidate_registry.json",
        "model_registry": "configs/model_registry.yaml",
        "feature_spec": "contracts/feature_spec.json",
        "m3_gate": "evidence/gates/M3_pit_data_gate.json",
        "m4_gate": "evidence/gates/M4_qlib_foundation_gate.json",
        "data_product_manifest": (
            "data/manifests/pit_data_product_2012_2024_v3/data_product_manifest.json"
        ),
        "trial_ledger_start": "contracts/immutable/trial_ledger_initial_20260728.jsonl",
    }
    for name, expected_relative_path in expected_paths.items():
        item = bindings.get(name)
        _require(isinstance(item, Mapping), f"M5 binding is missing: {name}")
        _require(
            item.get("path") == expected_relative_path,
            f"M5 binding path mismatch: {name}",
        )
        path = project_root / expected_relative_path
        _require(path.is_file(), f"M5 bound artifact is missing: {expected_relative_path}")
        _require(
            item.get("sha256") == sha256_file(path),
            f"M5 bound artifact changed: {name}",
        )

    m3 = _load(project_root / expected_paths["m3_gate"])
    m4 = _load(project_root / expected_paths["m4_gate"])
    _require(
        m3.get("status") == "PASS" and m3.get("passed") is True,
        "M3 gate is not PASS",
    )
    _require(
        m4.get("status") == "PASS"
        and m4.get("passed") is True
        and m4.get("verification", {}).get("final_oos_market_partitions_opened") is False,
        "M4 gate is not a final-OOS-safe PASS",
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
        "M5 input identity or final-OOS boundary mismatch",
    )

    schedule = spec.get("schedule")
    expected_folds = [f"wf_{year}" for year in range(2018, 2025)]
    _require(
        isinstance(schedule, Mapping)
        and schedule.get("fold_ids") == expected_folds
        and schedule.get("seed") == 7
        and schedule.get("embargo_sessions") == 5
        and schedule.get("candidate_evaluations") == 2
        and schedule.get("model_fits") == 14,
        "M5 fold schedule, seed or trial budget mismatch",
    )

    candidates = spec.get("candidates")
    _require(
        isinstance(candidates, list)
        and [item.get("model_id") for item in candidates if isinstance(item, Mapping)]
        == ["B0_LIGHTGBM", "B1_MLP"],
        "M5 must contain exactly the two registered baselines",
    )
    for candidate in candidates:
        _require(isinstance(candidate, Mapping), "M5 candidate entry is malformed")
        parameters = candidate.get("parameters")
        _require(
            isinstance(parameters, Mapping)
            and parameters.get("seed") == 7
            and parameters.get("model_id") == candidate.get("model_id"),
            "M5 candidate parameters are incomplete or use the wrong seed",
        )

    outputs = spec.get("outputs")
    _require(
        isinstance(outputs, Mapping)
        and outputs.get("prediction_columns")
        == ["datetime", "instrument", "score", "model_id", "fold_id"]
        and outputs.get("checkpoint_reload_required") is True
        and outputs.get("qlib_recorder_readback_required") is True,
        "M5 output or replay contract mismatch",
    )
    safeguards = spec.get("safeguards")
    _require(
        isinstance(safeguards, Mapping)
        and safeguards.get("final_oos_market_partitions_opened") is False
        and safeguards.get("portfolio_backtests") == 0
        and safeguards.get("cost_adjusted_selection") is False,
        "M5 spec crosses a prohibited research boundary",
    )

    code_binding = spec.get("code_binding")
    _require(isinstance(code_binding, Mapping), "M5 code binding is missing")
    files = code_binding.get("files")
    _require(isinstance(files, Mapping) and bool(files), "M5 code inventory is empty")
    for relative_path, declared_hash in files.items():
        _require(
            isinstance(relative_path, str) and isinstance(declared_hash, str),
            "M5 code binding entry is malformed",
        )
        path = project_root / relative_path
        _require(path.is_file(), f"M5 bound code file is missing: {relative_path}")
        _require(
            sha256_file(path) == declared_hash,
            f"M5 bound code file changed: {relative_path}",
        )
    return spec
