from __future__ import annotations

import torch
from torch import nn


class ConcordanceCorrelationLoss(nn.Module):
    """One minus Lin's concordance correlation coefficient."""

    def __init__(self, eps: float = 1e-8) -> None:
        super().__init__()
        self.eps = eps

    def forward(self, prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        prediction = prediction.reshape(-1)
        target = target.reshape(-1)
        if prediction.numel() < 2:
            return torch.mean((prediction - target) ** 2)
        pred_mean = prediction.mean()
        target_mean = target.mean()
        covariance = ((prediction - pred_mean) * (target - target_mean)).mean()
        pred_var = ((prediction - pred_mean) ** 2).mean()
        target_var = ((target - target_mean) ** 2).mean()
        ccc = 2.0 * covariance / (
            pred_var + target_var + (pred_mean - target_mean) ** 2 + self.eps
        )
        return 1.0 - ccc
