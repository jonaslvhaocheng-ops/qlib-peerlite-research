from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .artifacts import sha256_file


class EmpiricalGateError(RuntimeError):
    """Raised when strict empirical work lacks immutable upstream evidence."""


@dataclass(frozen=True)
class EmpiricalEvidence:
    contract_path: Path
    contract_receipt_path: Path
    pit_manifest_path: Path
    behavior_manifest_path: Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_empirical_ready(evidence: EmpiricalEvidence) -> None:
    if os.environ.get("QLIB_PEERLITE_ALLOW_EMPIRICAL", "").lower() != "true":
        raise EmpiricalGateError("QLIB_PEERLITE_ALLOW_EMPIRICAL=true is required")

    for path in (
        evidence.contract_path,
        evidence.contract_receipt_path,
        evidence.pit_manifest_path,
        evidence.behavior_manifest_path,
    ):
        if not path.is_file():
            raise EmpiricalGateError(f"missing evidence artifact: {path}")

    contract = _load(evidence.contract_path)
    receipt = _load(evidence.contract_receipt_path)
    pit = _load(evidence.pit_manifest_path)
    behavior = _load(evidence.behavior_manifest_path)

    if contract.get("contract", {}).get("status") != "FROZEN":
        raise EmpiricalGateError("research contract is not FROZEN")
    if receipt.get("status") != "PASS" or not receipt.get("strict"):
        raise EmpiricalGateError("strict contract validation receipt is not PASS")
    if receipt.get("contract_file_sha256") != sha256_file(evidence.contract_path):
        raise EmpiricalGateError("contract validation receipt does not bind contract bytes")

    binding = pit.get("contract_binding", {})
    if (
        pit.get("status") != "PASS"
        or pit.get("pit_qualification") != "QUALIFIED"
        or pit.get("evidence_ceiling") != "PASS"
        or binding.get("execution_boundary") != "PRODUCTION_CLI"
        or binding.get("test_only_adapter") is not False
    ):
        raise EmpiricalGateError("PIT manifest is not a production PASS/QUALIFIED result")

    if behavior.get("status") != "PASS":
        raise EmpiricalGateError("derived-feature behavior audit is not PASS")
