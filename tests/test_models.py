from __future__ import annotations

import numpy as np

from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.models.lightgbm_model import LightGBMBaseline
from qlib_peerlite.models.mlp import MLPBaseline
from qlib_peerlite.models.peerlite import PeerLiteModel


def test_lightgbm_baseline_outputs_unified_scores() -> None:
    dataset = make_synthetic_dataset(n_dates=45, n_instruments=24, n_features=8)
    model = LightGBMBaseline(n_estimators=30, early_stopping_rounds=5, seed=7)
    model.fit(dataset)
    scores = model.predict(dataset)
    assert scores.index.names == ["datetime", "instrument"]
    assert np.isfinite(scores).all()


def test_lightgbm_checkpoint_roundtrip(tmp_path) -> None:
    dataset = make_synthetic_dataset(n_dates=45, n_instruments=24, n_features=8)
    model = LightGBMBaseline(n_estimators=30, early_stopping_rounds=5, seed=7).fit(dataset)
    expected = model.predict(dataset)
    checkpoint = tmp_path / "lightgbm"
    model.save_checkpoint(checkpoint)
    restored = LightGBMBaseline.load_checkpoint(checkpoint)

    np.testing.assert_allclose(restored.predict(dataset), expected, rtol=0, atol=0)
    assert restored.standardizer.to_payload() == model.standardizer.to_payload()


def test_mlp_and_peerlite_fit_small_synthetic_panel() -> None:
    dataset = make_synthetic_dataset(n_dates=36, n_instruments=20, n_features=8)
    mlp = MLPBaseline(
        8, hidden_dim=16, epochs=3, patience=2, batch_size=256, device="cpu"
    ).fit(dataset)
    peer = PeerLiteModel(
        8,
        hidden_dim=16,
        num_peers=16,
        num_heads=4,
        dropout=0.0,
        epochs=3,
        patience=2,
        device="cpu",
    ).fit(dataset)
    assert len(mlp.predict(dataset)) == len(peer.predict(dataset))
    assert np.isfinite(peer.predict(dataset)).all()


def test_mlp_is_seed_reproducible_and_checkpoint_reloadable(tmp_path) -> None:
    dataset = make_synthetic_dataset(n_dates=36, n_instruments=20, n_features=8)
    kwargs = {
        "hidden_dim": 16,
        "dropout": 0.1,
        "epochs": 3,
        "patience": 2,
        "batch_size": 256,
        "device": "cpu",
        "seed": 7,
    }
    first = MLPBaseline(8, **kwargs).fit(dataset)
    second = MLPBaseline(8, **kwargs).fit(dataset)
    first_scores = first.predict(dataset)
    np.testing.assert_allclose(second.predict(dataset), first_scores, rtol=0, atol=0)

    checkpoint = tmp_path / "mlp"
    first.save_checkpoint(checkpoint)
    restored = MLPBaseline.load_checkpoint(checkpoint, device="cpu")
    np.testing.assert_allclose(restored.predict(dataset), first_scores, rtol=0, atol=0)
    assert restored.training_summary() == first.training_summary()
