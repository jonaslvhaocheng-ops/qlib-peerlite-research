from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts/server/verify_m6_peerlite_archival_replay.py"


def _module():
    spec = importlib.util.spec_from_file_location("m6_archival_replay", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archival_replay_score_digest_and_fold_loader_are_exact(tmp_path: Path) -> None:
    module = _module()
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2024-01-02"), "000001.SZ"),
            (pd.Timestamp("2024-01-02"), "000002.SZ"),
        ],
        names=["datetime", "instrument"],
    )
    scores = pd.Series([0.125, -0.5], index=index, name="score")
    assert module.score_digest(scores) == module.score_digest(scores.copy())

    predictions = pd.DataFrame(
        {
            "datetime": index.get_level_values("datetime"),
            "instrument": index.get_level_values("instrument"),
            "score": scores.to_numpy(),
            "model_id": ["PEERLITE_K16_MSE"] * 2,
            "fold_id": ["wf_2018"] * 2,
        }
    )
    path = tmp_path / "predictions.parquet"
    predictions.to_parquet(path, index=False)
    loaded = module.load_saved_fold_scores(
        path,
        model_id="PEERLITE_K16_MSE",
        fold_id="wf_2018",
    )
    pd.testing.assert_series_equal(loaded, scores)

    predictions.loc[1, "instrument"] = predictions.loc[0, "instrument"]
    predictions.to_parquet(path, index=False)
    with pytest.raises(RuntimeError, match="duplicate"):
        module.load_saved_fold_scores(
            path,
            model_id="PEERLITE_K16_MSE",
            fold_id="wf_2018",
        )


def test_archival_replay_rejects_non_exact_score_payload(tmp_path: Path) -> None:
    module = _module()
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2024-01-02"), "000001.SZ")], names=["datetime", "instrument"]
    )
    expected = pd.Series([np.float64(1.0)], index=index)
    replay = pd.Series([np.float64(1.0 + 1e-12)], index=index)
    with pytest.raises(RuntimeError, match="score mismatch"):
        module.assert_exact_replay(expected, replay, model_id="M", fold_id="wf_2018")
