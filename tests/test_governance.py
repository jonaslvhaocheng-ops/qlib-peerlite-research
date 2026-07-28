from __future__ import annotations

from pathlib import Path

import pytest

from qlib_peerlite.governance.gates import (
    EmpiricalEvidence,
    EmpiricalGateError,
    assert_empirical_ready,
)


def test_empirical_gate_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("QLIB_PEERLITE_ALLOW_EMPIRICAL", raising=False)
    evidence = EmpiricalEvidence(
        contract_path=tmp_path / "contract.json",
        contract_receipt_path=tmp_path / "receipt.json",
        pit_manifest_path=tmp_path / "pit.json",
        behavior_manifest_path=tmp_path / "behavior.json",
    )
    with pytest.raises(EmpiricalGateError, match="ALLOW_EMPIRICAL"):
        assert_empirical_ready(evidence)
