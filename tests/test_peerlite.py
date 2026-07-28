from __future__ import annotations

import copy

import numpy as np
import pytest
import torch

from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.models.losses import ConcordanceCorrelationLoss
from qlib_peerlite.models.peerlite import PeerLiteModel, PeerLiteNetwork


def network() -> PeerLiteNetwork:
    torch.manual_seed(7)
    model = PeerLiteNetwork(
        12,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.0,
    )
    model.eval()
    return model


def test_peer_network_is_permutation_equivariant() -> None:
    model = network()
    values = torch.randn(37, 12)
    permutation = torch.randperm(len(values))
    with torch.no_grad():
        original = model(values)
        permuted = model(values[permutation])
    torch.testing.assert_close(permuted, original[permutation], rtol=1e-5, atol=1e-6)


def test_variable_cross_section_single_stock_and_mask() -> None:
    model = network()
    with torch.no_grad():
        for size in (1, 7, 37):
            assert model(torch.randn(size, 12)).shape == (size,)
        score = model(
            torch.randn(9, 12),
            valid_mask=torch.tensor([True] * 8 + [False]),
        )
    assert score.shape == (9,)
    assert score[-1].item() == 0.0


def test_parameter_budget_and_checkpoint_reload() -> None:
    model = network()
    assert model.parameter_count < 500_000
    clone = network()
    clone.load_state_dict(copy.deepcopy(model.state_dict()))
    values = torch.randn(21, 12)
    with torch.no_grad():
        torch.testing.assert_close(model(values), clone(values))


def test_ccc_loss_prefers_identical_ordered_values() -> None:
    loss = ConcordanceCorrelationLoss()
    target = torch.linspace(-1, 1, 32)
    identical = loss(target, target).item()
    reversed_value = loss(-target, target).item()
    assert identical < 1e-6
    assert reversed_value > 1.0


def test_attention_shapes_and_mass() -> None:
    model = network()
    with torch.no_grad():
        score, assignment, attention = model(torch.randn(23, 12), return_attention=True)
    assert score.shape == (23,)
    assert assignment.shape == (23, 16)
    assert attention.shape == (4, 23, 16)
    np.testing.assert_allclose(
        assignment.sum(dim=1).numpy(), np.ones(23), rtol=1e-5, atol=1e-6
    )
    np.testing.assert_allclose(
        attention.sum(dim=-1).numpy(), np.ones((4, 23)), rtol=1e-5, atol=1e-6
    )


def test_masked_missing_row_cannot_change_valid_scores() -> None:
    model = network()
    values = torch.randn(11, 12)
    extended = torch.cat([values, torch.full((1, 12), float("nan"))])
    valid_mask = torch.tensor([True] * 11 + [False])
    with torch.no_grad():
        expected = model(values)
        actual, assignment, attention = model(
            extended,
            valid_mask=valid_mask,
            return_attention=True,
        )
    torch.testing.assert_close(actual[:-1], expected, rtol=1e-5, atol=1e-6)
    assert actual[-1].item() == 0.0
    assert torch.count_nonzero(assignment[-1]).item() == 0
    assert torch.count_nonzero(attention[:, -1]).item() == 0


def test_valid_non_finite_features_and_empty_mask_fail_closed() -> None:
    model = network()
    values = torch.randn(4, 12)
    values[0, 0] = float("nan")
    with pytest.raises(ValueError, match="must be finite"):
        model(values)
    with pytest.raises(ValueError, match="at least one valid"):
        model(torch.randn(4, 12), valid_mask=torch.zeros(4, dtype=torch.bool))


def test_attention_storage_scales_with_stocks_times_peers() -> None:
    model = network()
    with torch.no_grad():
        _, assignment_small, attention_small = model(
            torch.randn(17, 12),
            return_attention=True,
        )
        _, assignment_large, attention_large = model(
            torch.randn(31, 12),
            return_attention=True,
        )
    assert assignment_small.numel() == 17 * 16
    assert assignment_large.numel() == 31 * 16
    assert attention_small.numel() == 4 * 17 * 16
    assert attention_large.numel() == 4 * 31 * 16


def test_model_seed_reproducibility_and_checkpoint_reload(tmp_path) -> None:
    dataset = make_synthetic_dataset(n_dates=36, n_instruments=20, n_features=8)
    config = {
        "hidden_dim": 16,
        "num_peers": 16,
        "num_heads": 4,
        "dropout": 0.1,
        "epochs": 3,
        "patience": 2,
        "device": "cpu",
        "seed": 7,
    }
    first = PeerLiteModel(8, **config).fit(dataset)
    second = PeerLiteModel(8, **config).fit(dataset)
    expected = first.predict(dataset)
    np.testing.assert_allclose(second.predict(dataset), expected, rtol=0, atol=0)

    checkpoint = tmp_path / "peerlite"
    first.save_checkpoint(checkpoint)
    restored = PeerLiteModel.load_checkpoint(checkpoint, device="cpu")
    np.testing.assert_allclose(restored.predict(dataset), expected, rtol=0, atol=0)
    assert restored.training_summary() == first.training_summary()
