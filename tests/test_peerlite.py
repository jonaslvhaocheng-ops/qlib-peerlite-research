from __future__ import annotations

import copy

import numpy as np
import torch

from qlib_peerlite.models.losses import ConcordanceCorrelationLoss
from qlib_peerlite.models.peerlite import PeerLiteNetwork


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
        assert model(torch.randn(1, 12)).shape == (1,)
        score = model(torch.randn(9, 12), valid_mask=torch.tensor([True] * 8 + [False]))
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
