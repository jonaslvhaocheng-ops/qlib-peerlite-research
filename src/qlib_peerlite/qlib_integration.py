from __future__ import annotations

from pathlib import Path
from typing import Any


def qlib_version() -> str:
    try:
        import qlib
    except ImportError as exc:
        raise RuntimeError("install the optional qlib extra: uv sync --extra qlib") from exc
    return str(qlib.__version__)


def record_run_with_qlib(
    *,
    experiment_name: str,
    recorder_name: str,
    parameters: dict[str, Any],
    metrics: dict[str, float],
    artifacts: list[str | Path],
) -> str:
    """Log one completed run through Qlib Recorder's MLflow-backed interface."""

    try:
        from qlib.workflow import R
    except ImportError as exc:
        raise RuntimeError("Qlib is not installed") from exc

    with R.start(experiment_name=experiment_name, recorder_name=recorder_name):
        R.log_params(**parameters)
        R.log_metrics(**metrics)
        for artifact in artifacts:
            R.save_objects(**{Path(artifact).name: Path(artifact)})
        recorder = R.get_recorder()
        return str(recorder.id)
