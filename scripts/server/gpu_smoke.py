#!/usr/bin/env python3
"""Deterministic server environment and CUDA smoke test."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import lightgbm
import qlib
import torch

from qlib_peerlite.models.peerlite import PeerLiteNetwork


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    torch.manual_seed(7)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available to PyTorch")
    device = torch.device("cuda:0")
    model = PeerLiteNetwork(
        input_dim=12,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.0,
    ).to(device)
    features = torch.randn(64, 12, device=device, requires_grad=True)
    target = torch.randn(64, device=device)
    prediction = model(features)
    loss = torch.nn.functional.mse_loss(prediction, target)
    loss.backward()
    if not torch.isfinite(loss):
        raise RuntimeError("CUDA smoke loss is not finite")
    if features.grad is None or not torch.isfinite(features.grad).all():
        raise RuntimeError("CUDA smoke backward gradient is invalid")

    receipt = {
        "schema_version": "qlib_peerlite_server_environment_v1",
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "status": "PASS",
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "packages": {
            "qlib": qlib.__version__,
            "lightgbm": lightgbm.__version__,
            "torch": torch.__version__,
            "torch_cuda_build": torch.version.cuda,
        },
        "gpu": {
            "name": torch.cuda.get_device_name(0),
            "device_count": torch.cuda.device_count(),
            "capability": list(torch.cuda.get_device_capability(0)),
        },
        "smoke": {
            "cross_section_stocks": 64,
            "features": 12,
            "parameter_count": model.parameter_count,
            "forward_shape": list(prediction.shape),
            "loss_finite": True,
            "backward_gradient_finite": True,
        },
        "claim_boundary": "environment mechanics only; no PIT or alpha evidence",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
