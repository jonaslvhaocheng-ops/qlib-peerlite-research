from __future__ import annotations

import numpy as np
import pytest
import torch

from qlib_peerlite.data.market_state import DAILY_STATE_COLUMNS
from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.models.losses import ConcordanceCorrelationLoss
from qlib_peerlite.models.peerlite import PeerLiteModel

try:
    from qlib_peerlite.data.verified_market_state import (
        VerifiedMarketStateDataset as _IntermediateVerifiedBase,
    )
except ImportError:
    _IntermediateVerifiedBase = object


def test_ccc_contract_uses_float64_population_reducers() -> None:
    prediction = torch.tensor([1.0, 2.5, -0.5, 4.0], dtype=torch.float32)
    target = torch.tensor([0.5, 3.0, 1.0, 2.0], dtype=torch.float32)

    loss = ConcordanceCorrelationLoss()(prediction, target)

    pred64 = prediction.numpy().astype(np.float64)
    target64 = target.numpy().astype(np.float64)
    covariance = np.mean((pred64 - pred64.mean()) * (target64 - target64.mean()))
    expected = 1.0 - (
        2.0
        * covariance
        / (
            np.var(pred64, ddof=0)
            + np.var(target64, ddof=0)
            + (pred64.mean() - target64.mean()) ** 2
            + 1e-8
        )
    )

    assert loss.dtype == torch.float64
    assert loss.item() == pytest.approx(expected, abs=1e-12, rel=0)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_ccc_contract_rejects_nonfinite_inputs(bad_value: float) -> None:
    prediction = torch.tensor([0.0, bad_value], dtype=torch.float32)
    target = torch.tensor([0.0, 1.0], dtype=torch.float32)

    with pytest.raises(ValueError, match="finite"):
        ConcordanceCorrelationLoss()(prediction, target)


def test_gate_rejects_plain_dataset_and_never_reads_legacy_market_channel() -> None:
    dataset = make_synthetic_dataset(
        n_dates=12,
        n_instruments=5,
        n_features=4,
        seed=7,
    )
    dataset.frame["legacy_market_fourth"] = 0.0
    dataset.market_columns = [
        "market_ret",
        "market_vol",
        "market_turnover",
        "legacy_market_fourth",
    ]
    for position, column in enumerate(DAILY_STATE_COLUMNS):
        dataset.frame[column] = (
            dataset.frame.index.get_level_values("datetime").factorize()[0] * (position + 1) / 100.0
        )
    dataset.market_state_columns = list(DAILY_STATE_COLUMNS)

    model = PeerLiteModel(
        4,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.1,
        market_dim=4,
        market_gate=True,
        loss="mse",
        seed=7,
        epochs=1,
        patience=1,
        cross_section_batch_size=2,
        device="cpu",
        model_id="PEERLITE_K16_MSE_GATE",
    )

    with pytest.raises(ValueError, match="M7 synthetic fit requires"):
        model.fit(dataset)


class _SelfAssertedMarketStateDataset(_IntermediateVerifiedBase):
    def __init__(self, delegate: object) -> None:
        self.delegate = delegate
        self.prepare_calls = 0

    def verify_integrity(self) -> None:
        return None

    def prepare(
        self,
        segment: str,
        col_set: str | list[str] = "all",
        data_key: str | None = None,
    ) -> object:
        self.prepare_calls += 1
        return self.delegate.prepare(segment, col_set=col_set, data_key=data_key)


def _gate_model() -> PeerLiteModel:
    return PeerLiteModel(
        4,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.1,
        market_dim=4,
        market_gate=True,
        loss="mse",
        seed=7,
        epochs=1,
        patience=1,
        cross_section_batch_size=2,
        device="cpu",
        model_id="PEERLITE_K16_MSE_GATE",
    )


def _self_asserted_dataset() -> _SelfAssertedMarketStateDataset:
    dataset = make_synthetic_dataset(
        n_dates=12,
        n_instruments=5,
        n_features=4,
        seed=7,
    )
    for position, column in enumerate(DAILY_STATE_COLUMNS):
        dataset.frame[column] = (
            dataset.frame.index.get_level_values("datetime").factorize()[0] * (position + 1) / 100.0
        )
    dataset.market_state_columns = list(DAILY_STATE_COLUMNS)
    return _SelfAssertedMarketStateDataset(dataset)


def test_gate_rejects_self_asserted_wrapper_before_prepare_on_fit_and_predict() -> None:
    fit_dataset = _self_asserted_dataset()
    with pytest.raises(
        ValueError,
        match="M7 synthetic fit requires",
    ):
        _gate_model().fit(fit_dataset)
    assert fit_dataset.prepare_calls == 0

    predict_dataset = _self_asserted_dataset()
    model = _gate_model()
    features = predict_dataset.delegate.prepare("train", col_set="feature")
    market = predict_dataset.delegate.prepare("train", col_set="market_state")
    model.standardizer.fit(features)
    model.market_standardizer.fit(market)
    model.feature_names = tuple(str(column) for column in features.columns)
    model.fitted = True
    with pytest.raises(
        ValueError,
        match="M7 prediction requires",
    ):
        model.predict(predict_dataset, segment="train")
    assert predict_dataset.prepare_calls == 0


def test_ccc_nonfinite_gradient_guard_runs_before_optimizer_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qlib_peerlite.m7.market_state import (
        SyntheticFixtureSpec,
        build_synthetic_m7_fixture,
    )

    dataset, capability = build_synthetic_m7_fixture(
        SyntheticFixtureSpec(
            "m7-synthetic-v1",
            7,
            "2000-01-03",
            12,
            5,
            4,
        )
    )
    observed = {"error_if_nonfinite": None, "optimizer_steps": 0}

    def nonfinite_clip(
        parameters: object,
        max_norm: float,
        *,
        error_if_nonfinite: bool = False,
    ) -> None:
        del parameters, max_norm
        observed["error_if_nonfinite"] = error_if_nonfinite
        raise RuntimeError("non-finite gradient norm")

    def forbidden_step(optimizer: object, closure: object = None) -> None:
        del optimizer, closure
        observed["optimizer_steps"] += 1

    monkeypatch.setattr(torch.nn.utils, "clip_grad_norm_", nonfinite_clip)
    monkeypatch.setattr(torch.optim.AdamW, "step", forbidden_step)

    model = PeerLiteModel(
        4,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.1,
        market_gate=False,
        loss="ccc",
        seed=7,
        epochs=1,
        patience=1,
        cross_section_batch_size=2,
        device="cpu",
        model_id="PEERLITE_K16_CCC",
    )
    with pytest.raises(RuntimeError, match="non-finite gradient norm"):
        model.fit(
            dataset,
            m7_authority=capability.for_candidate("PEERLITE_K16_CCC"),
        )

    assert observed == {
        "error_if_nonfinite": True,
        "optimizer_steps": 0,
    }
