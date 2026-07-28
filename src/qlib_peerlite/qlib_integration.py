from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

_ARTIFACT_ROOT: Path | None = None


def qlib_version() -> str:
    try:
        import qlib
    except ImportError as exc:
        raise RuntimeError("install the optional qlib extra: uv sync --extra qlib") from exc
    return str(qlib.__version__)


def initialize_qlib(
    *,
    provider_dir: str | Path,
    tracking_dir: str | Path,
) -> None:
    """Initialize Qlib with explicit local data and MLflow roots."""

    try:
        import qlib
    except ImportError as exc:
        raise RuntimeError("install the optional qlib extra: uv sync --extra qlib") from exc

    global _ARTIFACT_ROOT

    provider = Path(provider_dir).resolve()
    tracking = Path(tracking_dir).resolve()
    provider.mkdir(parents=True, exist_ok=True)
    tracking.mkdir(parents=True, exist_ok=True)
    _ARTIFACT_ROOT = tracking / "artifacts"
    _ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    qlib.init(
        provider_uri=str(provider),
        exp_manager={
            "class": "MLflowExpManager",
            "module_path": "qlib.workflow.expm",
            "kwargs": {
                "uri": f"sqlite:///{tracking / 'mlflow.db'}",
                "default_exp_name": "QlibPeerLite",
            },
        },
    )


def _recorder_scalar(value: Any) -> str | int | float | bool:
    if isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("recorder parameters must be finite")
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_run_with_qlib(
    *,
    experiment_name: str,
    recorder_name: str,
    parameters: dict[str, Any],
    metrics: dict[str, float] | None,
    artifacts: list[str | Path],
) -> str:
    """Log one completed run through Qlib Recorder's MLflow-backed interface."""

    try:
        from mlflow.tracking import MlflowClient
        from qlib.workflow import R
    except ImportError as exc:
        raise RuntimeError("Qlib is not installed") from exc

    if _ARTIFACT_ROOT is None:
        raise RuntimeError("initialize_qlib must be called before recording")
    client = MlflowClient(tracking_uri=R.get_uri())
    if client.get_experiment_by_name(experiment_name) is None:
        directory = hashlib.sha256(experiment_name.encode("utf-8")).hexdigest()[:20]
        artifact_location = (_ARTIFACT_ROOT / directory).resolve()
        artifact_location.mkdir(parents=True, exist_ok=False)
        client.create_experiment(experiment_name, artifact_location=artifact_location.as_uri())

    with R.start(experiment_name=experiment_name, recorder_name=recorder_name):
        R.log_params(**{key: _recorder_scalar(value) for key, value in parameters.items()})
        if metrics:
            if any(not math.isfinite(float(value)) for value in metrics.values()):
                raise ValueError("recorder metrics must be finite")
            R.log_metrics(**metrics)
        for artifact in artifacts:
            path = Path(artifact).resolve()
            if not path.is_file():
                raise FileNotFoundError(path)
            R.log_artifact(str(path))
        recorder = R.get_recorder()
        return str(recorder.id)
