from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import sha256_file


class EmpiricalGateError(RuntimeError):
    """Raised when strict empirical work lacks immutable upstream evidence."""


@dataclass(frozen=True)
class EmpiricalEvidence:
    contract_path: Path
    contract_receipt_path: Path
    pit_manifest_path: Path
    behavior_manifest_path: Path
    m3_gate_path: Path
    data_product_manifest_path: Path
    data_product_verification_path: Path


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EmpiricalGateError(message)


def _evidence_item(gate: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    evidence = gate.get("evidence")
    if not isinstance(evidence, Mapping):
        raise EmpiricalGateError("M3 gate has no evidence registry")
    item = evidence.get(name)
    if not isinstance(item, Mapping):
        raise EmpiricalGateError(f"M3 gate lacks evidence item: {name}")
    return item


def _all_checks_pass(manifest: Mapping[str, Any], expected: int) -> bool:
    checks = manifest.get("checks")
    return (
        isinstance(checks, list)
        and len(checks) == expected
        and all(isinstance(item, Mapping) and item.get("status") == "PASS" for item in checks)
    )


def assert_empirical_ready(evidence: EmpiricalEvidence) -> None:
    if os.environ.get("QLIB_PEERLITE_ALLOW_EMPIRICAL", "").lower() != "true":
        raise EmpiricalGateError("QLIB_PEERLITE_ALLOW_EMPIRICAL=true is required")

    for path in (
        evidence.contract_path,
        evidence.contract_receipt_path,
        evidence.pit_manifest_path,
        evidence.behavior_manifest_path,
        evidence.m3_gate_path,
        evidence.data_product_manifest_path,
        evidence.data_product_verification_path,
    ):
        if not path.is_file():
            raise EmpiricalGateError(f"missing evidence artifact: {path}")

    contract = _load(evidence.contract_path)
    receipt = _load(evidence.contract_receipt_path)
    pit = _load(evidence.pit_manifest_path)
    behavior = _load(evidence.behavior_manifest_path)
    m3_gate = _load(evidence.m3_gate_path)
    product = _load(evidence.data_product_manifest_path)
    product_verification = _load(evidence.data_product_verification_path)

    contract_meta = contract.get("contract")
    _require(isinstance(contract_meta, Mapping), "research contract metadata is missing")
    _require(contract_meta.get("status") == "FROZEN", "research contract is not FROZEN")
    _require(
        receipt.get("status") == "PASS" and receipt.get("strict") is True,
        "strict contract validation receipt is not PASS",
    )
    contract_file_sha = sha256_file(evidence.contract_path)
    _require(
        receipt.get("contract_file_sha256") == contract_file_sha,
        "contract validation receipt does not bind contract bytes",
    )
    for field in ("contract_id", "canonical_hash"):
        _require(
            receipt.get(field) == contract_meta.get(field),
            f"contract validation receipt {field} mismatch",
        )

    binding = pit.get("contract_binding", {})
    _require(
        pit.get("status") == "PASS"
        and pit.get("pit_qualification") == "QUALIFIED"
        and pit.get("evidence_ceiling") == "PASS"
        and binding.get("execution_boundary") == "PRODUCTION_CLI"
        and binding.get("test_only_adapter") is False
        and _all_checks_pass(pit, 17),
        "PIT manifest is not a production 17/17 PASS/QUALIFIED result",
    )
    _require(
        binding.get("contract_id") == contract_meta.get("contract_id")
        and binding.get("canonical_hash") == contract_meta.get("canonical_hash")
        and binding.get("file_sha256") == contract_file_sha,
        "PIT manifest does not bind the active frozen contract",
    )
    coverage = pit.get("coverage_matrix")
    _require(
        isinstance(coverage, Mapping)
        and coverage.get("scope") == "FULL_TRAINING_INPUT"
        and coverage.get("expected_rows") == coverage.get("parsed_rows")
        and coverage.get("expected_security_time_keys")
        == coverage.get("observed_security_time_keys")
        and coverage.get("expected_matrix_cells") == coverage.get("observed_matrix_cells"),
        "PIT manifest does not cover the complete declared training input",
    )

    _require(
        behavior.get("status") == "PASS"
        and behavior.get("certification_status") == "NOVEL_CANDIDATE"
        and _all_checks_pass(behavior, 4),
        "derived-feature behavior audit is not a 4/4 PASS",
    )
    parent = behavior.get("parent_audit")
    _require(
        isinstance(parent, Mapping)
        and parent.get("audit_id") == pit.get("audit_id")
        and parent.get("content_sha256") == pit.get("content_sha256")
        and parent.get("status") == "PASS",
        "behavior audit does not bind the fixed PIT parent",
    )
    protection = behavior.get("protection")
    _require(
        isinstance(protection, Mapping)
        and protection.get("baseline_key_count", 0) > 0
        and protection.get("baseline_key_count") == protection.get("probe_key_count")
        and protection.get("baseline_keys_sha256") == protection.get("probe_keys_sha256"),
        "behavior audit protected key population is empty or inconsistent",
    )

    _require(
        m3_gate.get("gate_id") == "M3-STRICT"
        and m3_gate.get("status") == "PASS"
        and m3_gate.get("executed") is True
        and m3_gate.get("completed") is True
        and m3_gate.get("passed") is True,
        "M3 project gate is not a completed PASS",
    )
    declared_contract = _evidence_item(m3_gate, "active_descendant_contract")
    declared_receipt = _evidence_item(m3_gate, "strict_contract_validation")
    declared_pit = _evidence_item(m3_gate, "fixed_pit_audit")
    declared_behavior = _evidence_item(m3_gate, "behavior_pit_audit")
    declared_product = _evidence_item(m3_gate, "data_product")
    declared_product_verification = _evidence_item(m3_gate, "data_product_verification")
    _require(
        declared_contract.get("sha256") == contract_file_sha
        and declared_contract.get("contract_id") == contract_meta.get("contract_id")
        and declared_contract.get("canonical_hash") == contract_meta.get("canonical_hash"),
        "M3 gate active-contract binding mismatch",
    )
    _require(
        declared_receipt.get("sha256") == sha256_file(evidence.contract_receipt_path),
        "M3 gate validation-receipt binding mismatch",
    )
    _require(
        declared_pit.get("sha256") == sha256_file(evidence.pit_manifest_path)
        and declared_pit.get("audit_id") == pit.get("audit_id")
        and declared_pit.get("content_sha256") == pit.get("content_sha256"),
        "M3 gate fixed-PIT binding mismatch",
    )
    _require(
        declared_behavior.get("sha256") == sha256_file(evidence.behavior_manifest_path)
        and declared_behavior.get("behavior_id") == behavior.get("behavior_id")
        and declared_behavior.get("content_sha256") == behavior.get("content_sha256"),
        "M3 gate behavior-PIT binding mismatch",
    )

    product_sha = sha256_file(evidence.data_product_manifest_path)
    _require(
        declared_product.get("sha256") == product_sha
        and declared_product.get("product_id") == product.get("product_id"),
        "M3 gate data-product binding mismatch",
    )
    oos_seal = product.get("oos_seal")
    matrix = product.get("matrix")
    _require(
        isinstance(oos_seal, Mapping)
        and oos_seal.get("final_oos_market_partitions_opened") is False
        and oos_seal.get("performance_metrics_computed") is False,
        "data product opened final OOS or computed performance metrics",
    )
    _require(
        isinstance(matrix, Mapping)
        and matrix.get("rows") == declared_product.get("samples")
        and matrix.get("feature_count") == declared_product.get("features")
        and str(matrix.get("date_max", "")) < "2025-01-01"
        and all(int(item.get("year", 9999)) < 2025 for item in matrix.get("files", [])),
        "data product population, feature count or final-OOS boundary mismatch",
    )
    _require(
        product.get("contract_id") == contract_meta.get("parent_contract_id"),
        "data product does not bind the active contract's direct parent",
    )

    _require(
        declared_product_verification.get("sha256")
        == sha256_file(evidence.data_product_verification_path)
        and product_verification.get("status") == "PASS"
        and product_verification.get("passed") is True
        and product_verification.get("product_id") == product.get("product_id")
        and product_verification.get("product_manifest_sha256") == product_sha,
        "independent data-product verification is missing or mismatched",
    )
    verification_checks = product_verification.get("checks")
    _require(
        isinstance(verification_checks, Mapping)
        and verification_checks.get("final_oos_partition_opened") is False
        and verification_checks.get("performance_metrics_computed") is False
        and verification_checks.get("matrix_rows") == matrix.get("rows")
        and verification_checks.get("matrix_feature_count") == matrix.get("feature_count"),
        "data-product verification checks are inconsistent",
    )

    consumed = _evidence_item(m3_gate, "consumed_value_view")
    derived_sources = [
        item
        for item in contract.get("data", {}).get("sources", [])
        if item.get("source_id") == "qlib-peerlite-derived-features"
    ]
    _require(
        len(derived_sources) == 1
        and derived_sources[0].get("snapshot_hash") == consumed.get("training_evidence_sha256"),
        "active contract does not bind the qualified consumed-value snapshot",
    )
