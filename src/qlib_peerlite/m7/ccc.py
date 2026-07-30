from __future__ import annotations

import torch
from torch import nn

CCC_CONTRACT_VERSION = "qlib_peerlite_ccc_numerical_contract_v1"
CCC_EPSILON = 1e-8


def ccc_contract_payload() -> dict[str, object]:
    return {
        "schema_version": CCC_CONTRACT_VERSION,
        "epsilon": CCC_EPSILON,
        "input_dtype": "float32",
        "reducer_dtype": "float64",
        "variance_correction": 0,
        "singleton": "mse",
    }


class ConcordanceCorrelationLoss(nn.Module):
    """One minus Lin's CCC under the frozen M7 numerical contract."""

    def __init__(self, eps: float = CCC_EPSILON) -> None:
        super().__init__()
        if not torch.isfinite(torch.tensor(eps, dtype=torch.float64)) or eps <= 0:
            raise ValueError("CCC epsilon must be finite and positive")
        self.eps = float(eps)

    def forward(self, prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        prediction = prediction.reshape(-1)
        target = target.reshape(-1)
        if prediction.numel() != target.numel() or prediction.numel() == 0:
            raise ValueError("CCC inputs must be non-empty and have equal size")
        if prediction.dtype != torch.float32 or target.dtype != torch.float32:
            raise ValueError("CCC inputs must be float32 tensors")
        if not torch.isfinite(prediction).all() or not torch.isfinite(target).all():
            raise ValueError("CCC inputs must be finite")

        prediction64 = prediction.to(dtype=torch.float64)
        target64 = target.to(dtype=torch.float64)
        if prediction64.numel() == 1:
            loss = torch.mean((prediction64 - target64) ** 2)
        else:
            pred_mean = prediction64.mean()
            target_mean = target64.mean()
            covariance = ((prediction64 - pred_mean) * (target64 - target_mean)).mean()
            denominator = (
                torch.var(prediction64, correction=0)
                + torch.var(target64, correction=0)
                + (pred_mean - target_mean) ** 2
                + torch.tensor(self.eps, dtype=torch.float64, device=prediction.device)
            )
            loss = 1.0 - (2.0 * covariance / denominator)
        if not torch.isfinite(loss):
            raise ValueError("CCC calculation produced a non-finite loss")
        return loss


__all__ = [
    "CCC_CONTRACT_VERSION",
    "CCC_EPSILON",
    "ConcordanceCorrelationLoss",
    "ccc_contract_payload",
]
