from __future__ import annotations

import pytest
import torch

from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.models.losses import ConcordanceCorrelationLoss
from qlib_peerlite.models.peerlite import PeerLiteModel


@pytest.mark.parametrize("bad_eps", [0.0, float("nan")])
def test_ccc_contract_rejects_invalid_epsilon(bad_eps: float) -> None:
    with pytest.raises(ValueError, match="epsilon"):
        ConcordanceCorrelationLoss(eps=bad_eps)


def test_ccc_contract_rejects_empty_mismatched_and_non_float32_inputs() -> None:
    loss = ConcordanceCorrelationLoss()
    with pytest.raises(ValueError, match="non-empty"):
        loss(torch.tensor([], dtype=torch.float32), torch.tensor([], dtype=torch.float32))
    with pytest.raises(ValueError, match="equal size"):
        loss(torch.tensor([1.0], dtype=torch.float32), torch.tensor([1.0, 2.0]))
    with pytest.raises(ValueError, match="float32"):
        loss(torch.tensor([1.0], dtype=torch.float64), torch.tensor([1.0]))
    with pytest.raises(ValueError, match="float32"):
        loss(torch.tensor([1.0]), torch.tensor([1.0], dtype=torch.float64))


def test_ccc_contract_singleton_is_float64_mse_and_gradient_reaches_float32() -> None:
    singleton = ConcordanceCorrelationLoss()(
        torch.tensor([3.0], dtype=torch.float32),
        torch.tensor([1.5], dtype=torch.float32),
    )
    assert singleton.dtype == torch.float64
    assert singleton.item() == pytest.approx(2.25, abs=0, rel=0)

    parameter = torch.nn.Parameter(torch.tensor([0.5, -0.25], dtype=torch.float32))
    prediction = parameter * torch.tensor([1.0, 2.0], dtype=torch.float32)
    target = torch.tensor([0.0, 1.0], dtype=torch.float32)
    ConcordanceCorrelationLoss()(prediction, target).backward()
    assert parameter.grad is not None
    assert parameter.grad.dtype == torch.float32
    assert torch.isfinite(parameter.grad).all()
    assert torch.count_nonzero(parameter.grad).item() > 0


def test_ccc_contract_rejects_nonfinite_target_and_result() -> None:
    with pytest.raises(ValueError, match="finite"):
        ConcordanceCorrelationLoss()(
            torch.tensor([0.0, 1.0], dtype=torch.float32),
            torch.tensor([0.0, float("nan")], dtype=torch.float32),
        )

    loss = ConcordanceCorrelationLoss()
    loss.eps = float("nan")
    with pytest.raises(ValueError, match="non-finite loss"):
        loss(
            torch.tensor([0.0, 1.0], dtype=torch.float32),
            torch.tensor([0.0, 1.0], dtype=torch.float32),
        )


def test_gated_market_frame_is_closed_until_verified_factory_exists() -> None:
    dataset = make_synthetic_dataset(
        n_dates=12,
        n_instruments=5,
        n_features=4,
        seed=7,
    )
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
    with pytest.raises(
        ValueError,
        match="exact verified M7 dataset",
    ):
        model._market_frame(dataset, "train")
