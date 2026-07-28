from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from qlib_peerlite.governance.gates import (
    EmpiricalEvidence,
    EmpiricalGateError,
    assert_empirical_ready,
)


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ready_evidence(tmp_path: Path) -> EmpiricalEvidence:
    contract_path = tmp_path / "contract.json"
    receipt_path = tmp_path / "receipt.json"
    pit_path = tmp_path / "pit.json"
    behavior_path = tmp_path / "behavior.json"
    gate_path = tmp_path / "m3.json"
    product_path = tmp_path / "product.json"
    verification_path = tmp_path / "verification.json"

    contract_id = "qrc-v2-child"
    canonical_hash = "a" * 64
    _write(
        contract_path,
        {
            "contract": {
                "status": "FROZEN",
                "contract_id": contract_id,
                "canonical_hash": canonical_hash,
                "parent_contract_id": "qrc-v2-parent",
            },
            "data": {
                "sources": [
                    {
                        "source_id": "qlib-peerlite-derived-features",
                        "snapshot_hash": "b" * 64,
                    }
                ]
            },
        },
    )
    _write(
        receipt_path,
        {
            "status": "PASS",
            "strict": True,
            "contract_file_sha256": _sha(contract_path),
            "contract_id": contract_id,
            "canonical_hash": canonical_hash,
        },
    )
    _write(
        pit_path,
        {
            "audit_id": "pit-audit-test",
            "content_sha256": "c" * 64,
            "status": "PASS",
            "pit_qualification": "QUALIFIED",
            "evidence_ceiling": "PASS",
            "contract_binding": {
                "contract_id": contract_id,
                "canonical_hash": canonical_hash,
                "file_sha256": _sha(contract_path),
                "execution_boundary": "PRODUCTION_CLI",
                "test_only_adapter": False,
            },
            "coverage_matrix": {
                "scope": "FULL_TRAINING_INPUT",
                "expected_rows": 100,
                "parsed_rows": 100,
                "expected_security_time_keys": 2,
                "observed_security_time_keys": 2,
                "expected_matrix_cells": 100,
                "observed_matrix_cells": 100,
            },
            "checks": [{"check_id": f"C{i}", "status": "PASS"} for i in range(17)],
        },
    )
    _write(
        behavior_path,
        {
            "behavior_id": "pit-behavior-test",
            "content_sha256": "d" * 64,
            "status": "PASS",
            "certification_status": "NOVEL_CANDIDATE",
            "parent_audit": {
                "audit_id": "pit-audit-test",
                "content_sha256": "c" * 64,
                "status": "PASS",
            },
            "protection": {
                "baseline_key_count": 5,
                "probe_key_count": 5,
                "baseline_keys_sha256": "e" * 64,
                "probe_keys_sha256": "e" * 64,
            },
            "checks": [{"id": f"B{i}", "status": "PASS"} for i in range(4)],
        },
    )
    _write(
        product_path,
        {
            "product_id": "product-test",
            "contract_id": "qrc-v2-parent",
            "oos_seal": {
                "final_oos_market_partitions_opened": False,
                "performance_metrics_computed": False,
            },
            "matrix": {
                "rows": 2,
                "feature_count": 50,
                "date_max": "2024-12-17",
                "files": [{"year": 2024}],
            },
        },
    )
    _write(
        verification_path,
        {
            "status": "PASS",
            "passed": True,
            "product_id": "product-test",
            "product_manifest_sha256": _sha(product_path),
            "checks": {
                "final_oos_partition_opened": False,
                "performance_metrics_computed": False,
                "matrix_rows": 2,
                "matrix_feature_count": 50,
            },
        },
    )
    _write(
        gate_path,
        {
            "gate_id": "M3-STRICT",
            "status": "PASS",
            "executed": True,
            "completed": True,
            "passed": True,
            "evidence": {
                "active_descendant_contract": {
                    "sha256": _sha(contract_path),
                    "contract_id": contract_id,
                    "canonical_hash": canonical_hash,
                },
                "strict_contract_validation": {"sha256": _sha(receipt_path)},
                "fixed_pit_audit": {
                    "sha256": _sha(pit_path),
                    "audit_id": "pit-audit-test",
                    "content_sha256": "c" * 64,
                },
                "behavior_pit_audit": {
                    "sha256": _sha(behavior_path),
                    "behavior_id": "pit-behavior-test",
                    "content_sha256": "d" * 64,
                },
                "data_product": {
                    "sha256": _sha(product_path),
                    "product_id": "product-test",
                    "samples": 2,
                    "features": 50,
                },
                "data_product_verification": {"sha256": _sha(verification_path)},
                "consumed_value_view": {"training_evidence_sha256": "b" * 64},
            },
        },
    )
    return EmpiricalEvidence(
        contract_path=contract_path,
        contract_receipt_path=receipt_path,
        pit_manifest_path=pit_path,
        behavior_manifest_path=behavior_path,
        m3_gate_path=gate_path,
        data_product_manifest_path=product_path,
        data_product_verification_path=verification_path,
    )


def test_empirical_gate_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("QLIB_PEERLITE_ALLOW_EMPIRICAL", raising=False)
    evidence = _ready_evidence(tmp_path)
    with pytest.raises(EmpiricalGateError, match="ALLOW_EMPIRICAL"):
        assert_empirical_ready(evidence)


def test_empirical_gate_accepts_exact_bound_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("QLIB_PEERLITE_ALLOW_EMPIRICAL", "true")
    assert_empirical_ready(_ready_evidence(tmp_path))


def test_empirical_gate_rejects_behavior_parent_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("QLIB_PEERLITE_ALLOW_EMPIRICAL", "true")
    evidence = _ready_evidence(tmp_path)
    behavior = json.loads(evidence.behavior_manifest_path.read_text())
    behavior["parent_audit"]["audit_id"] = "wrong-parent"
    _write(evidence.behavior_manifest_path, behavior)
    gate = json.loads(evidence.m3_gate_path.read_text())
    gate["evidence"]["behavior_pit_audit"]["sha256"] = _sha(evidence.behavior_manifest_path)
    _write(evidence.m3_gate_path, gate)
    with pytest.raises(EmpiricalGateError, match="fixed PIT parent"):
        assert_empirical_ready(evidence)


def test_empirical_gate_rejects_final_oos_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("QLIB_PEERLITE_ALLOW_EMPIRICAL", "true")
    evidence = _ready_evidence(tmp_path)
    product = json.loads(evidence.data_product_manifest_path.read_text())
    product["oos_seal"]["final_oos_market_partitions_opened"] = True
    _write(evidence.data_product_manifest_path, product)
    gate = json.loads(evidence.m3_gate_path.read_text())
    gate["evidence"]["data_product"]["sha256"] = _sha(evidence.data_product_manifest_path)
    _write(evidence.m3_gate_path, gate)
    with pytest.raises(EmpiricalGateError, match="opened final OOS"):
        assert_empirical_ready(evidence)
