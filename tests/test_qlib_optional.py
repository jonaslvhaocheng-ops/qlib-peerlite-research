from __future__ import annotations

import json
from pathlib import Path

import pytest

from qlib_peerlite.qlib_integration import initialize_qlib, record_run_with_qlib


@pytest.mark.qlib
def test_qlib_optional_version() -> None:
    qlib = pytest.importorskip("qlib")
    assert qlib.__version__ == "0.9.7"


@pytest.mark.qlib
def test_qlib_recorder_logs_real_artifact_bytes(tmp_path: Path) -> None:
    pytest.importorskip("qlib")
    artifact = tmp_path / "receipt.json"
    artifact.write_text(json.dumps({"status": "MECHANICS_ONLY"}), encoding="utf-8")
    initialize_qlib(
        provider_dir=tmp_path / "provider",
        tracking_dir=tmp_path / "mlruns",
    )
    recorder_id = record_run_with_qlib(
        experiment_name="qlib_foundation_test",
        recorder_name="artifact_binding",
        parameters={"track": "SYNTHETIC", "nested": {"seed": 7}},
        metrics=None,
        artifacts=[artifact],
    )
    from qlib.workflow import R

    recorder = R.get_recorder(
        recorder_id=recorder_id,
        experiment_name="qlib_foundation_test",
    )
    assert "receipt.json" in recorder.list_artifacts()
    downloaded = Path(recorder.download_artifact("receipt.json"))
    assert downloaded.read_bytes() == artifact.read_bytes()
