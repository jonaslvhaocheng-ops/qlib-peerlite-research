from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from qlib_peerlite.governance.m4_evidence import (
    M4EvidenceError,
    verify_m4_evidence,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_DIR = PROJECT_ROOT / "evidence/qlib/foundation_20260728_v2"
ANALYSIS_DIR = PROJECT_ROOT / "evidence/qlib/analysis_mechanics_20260728_v1"


def test_current_m4_evidence_bundle_passes_independent_verification() -> None:
    result = verify_m4_evidence(
        project_root=PROJECT_ROOT,
        foundation_dir=FOUNDATION_DIR,
        analysis_dir=ANALYSIS_DIR,
    )

    assert result["status"] == "PASS"
    assert result["fold_count"] == 7
    assert result["data_rows"] == 1_658_525
    assert result["feature_count"] == 50
    assert result["final_oos_market_partitions_opened"] is False


def test_foundation_manifest_drift_is_rejected(tmp_path: Path) -> None:
    copied_foundation = tmp_path / "foundation"
    shutil.copytree(FOUNDATION_DIR, copied_foundation)
    manifest_path = copied_foundation / "foundation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "FAIL"
    manifest_path.chmod(0o640)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(M4EvidenceError, match="content hash mismatch"):
        verify_m4_evidence(
            project_root=PROJECT_ROOT,
            foundation_dir=copied_foundation,
            analysis_dir=ANALYSIS_DIR,
        )
