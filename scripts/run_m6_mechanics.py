#!/usr/bin/env python3
"""Create a synthetic-only PeerLite M6 mechanics receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import torch

from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.governance.artifacts import atomic_write_json, sha256_file
from qlib_peerlite.models.peerlite import PeerLiteModel, PeerLiteNetwork

SHANGHAI = ZoneInfo("Asia/Shanghai")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def mechanics(project_root: Path, output_path: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite mechanics receipt: {output_path}")

    torch.manual_seed(7)
    network_results: list[dict[str, Any]] = []
    for num_peers in (16, 32):
        network = PeerLiteNetwork(
            50,
            hidden_dim=64,
            num_peers=num_peers,
            num_heads=4,
            dropout=0.0,
        )
        network.eval()
        values = torch.randn(37, 50)
        permutation = torch.randperm(len(values))
        with torch.no_grad():
            original = network(values)
            permuted = network(values[permutation])
            max_permutation_error = float(
                (permuted - original[permutation]).abs().max()
            )
            variable_shapes = {
                str(size): list(network(torch.randn(size, 50)).shape)
                for size in (1, 7, 37)
            }
            base = torch.randn(11, 50)
            extended = torch.cat([base, torch.full((1, 50), float("nan"))])
            mask = torch.tensor([True] * 11 + [False])
            base_score = network(base)
            masked_score, assignment, attention = network(
                extended,
                valid_mask=mask,
                return_attention=True,
            )
            max_mask_error = float((base_score - masked_score[:-1]).abs().max())
        if max_permutation_error > 1e-5:
            raise RuntimeError("PeerLite permutation equivariance tolerance failed")
        if max_mask_error > 1e-6 or masked_score[-1].item() != 0.0:
            raise RuntimeError("PeerLite missing-row isolation failed")
        if torch.count_nonzero(assignment[-1]) or torch.count_nonzero(attention[:, -1]):
            raise RuntimeError("PeerLite missing-row masks are not zero")
        if network.parameter_count >= 500_000:
            raise RuntimeError("PeerLite parameter budget exceeded")
        network_results.append(
            {
                "num_peers": num_peers,
                "parameter_count": network.parameter_count,
                "permutation_equivariance": {
                    "status": "PASS",
                    "max_absolute_error": max_permutation_error,
                    "tolerance": 1e-5,
                },
                "variable_cross_section_shapes": variable_shapes,
                "single_stock": "PASS",
                "masked_missing_row": {
                    "status": "PASS",
                    "max_valid_score_error": max_mask_error,
                    "invalid_score": float(masked_score[-1]),
                },
                "complexity_witness": {
                    "assignment_shape": list(assignment.shape),
                    "attention_shape": list(attention.shape),
                    "expected_order": "O(NK)",
                    "stock_pair_tensor_materialized": False,
                },
            }
        )

    dataset = make_synthetic_dataset(n_dates=36, n_instruments=20, n_features=8)
    model_config = {
        "hidden_dim": 16,
        "num_peers": 16,
        "num_heads": 4,
        "dropout": 0.1,
        "epochs": 3,
        "patience": 2,
        "device": "cpu",
        "seed": 7,
    }
    first = PeerLiteModel(8, **model_config).fit(dataset)
    second = PeerLiteModel(8, **model_config).fit(dataset)
    first_score = first.predict(dataset)
    second_score = second.predict(dataset)
    if not first_score.index.equals(second_score.index) or not np.array_equal(
        first_score.to_numpy(),
        second_score.to_numpy(),
    ):
        raise RuntimeError("PeerLite fixed-seed synthetic refit is not exact")
    if first_score.index.names != ["datetime", "instrument"]:
        raise RuntimeError("PeerLite score index violates the unified interface")
    if not np.isfinite(first_score.to_numpy()).all():
        raise RuntimeError("PeerLite synthetic scores contain a non-finite value")
    with tempfile.TemporaryDirectory(prefix="peerlite-m6-mechanics-") as directory:
        checkpoint = Path(directory) / "checkpoint"
        first.save_checkpoint(checkpoint)
        restored = PeerLiteModel.load_checkpoint(checkpoint, device="cpu")
        restored_score = restored.predict(dataset)
        if not np.array_equal(first_score.to_numpy(), restored_score.to_numpy()):
            raise RuntimeError("PeerLite checkpoint replay is not exact")
        checkpoint_inventory = {
            str(path.relative_to(checkpoint)): sha256_file(path)
            for path in sorted(checkpoint.rglob("*"))
            if path.is_file()
        }

    receipt = {
        "schema_version": "qlib_peerlite_m6_mechanics_receipt_v1",
        "status": "PASS",
        "created_at": datetime.now(SHANGHAI).isoformat(),
        "track": "SYNTHETIC_ONLY",
        "network_checks": network_results,
        "model_checks": {
            "unified_interface": "(datetime, instrument) -> score",
            "score_rows": len(first_score),
            "finite_scores": True,
            "fixed_seed_refit": "PASS_EXACT",
            "checkpoint_replay": "PASS_EXACT",
            "checkpoint_inventory": checkpoint_inventory,
            "training_summary": first.training_summary(),
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": "cpu",
        },
        "code": {
            "src/qlib_peerlite/models/peerlite.py": sha256_file(
                project_root / "src/qlib_peerlite/models/peerlite.py"
            ),
            "src/qlib_peerlite/models/common.py": sha256_file(
                project_root / "src/qlib_peerlite/models/common.py"
            ),
            "tests/test_peerlite.py": sha256_file(
                project_root / "tests/test_peerlite.py"
            ),
            "scripts/run_m6_mechanics.py": sha256_file(Path(__file__).resolve()),
        },
        "real_data_accessed": False,
        "real_labels_accessed": False,
        "counts_as_candidate_evaluation": False,
        "counts_as_model_fit": False,
        "final_oos_market_partitions_opened": False,
        "claim_ceiling": "MECHANICS_ONLY",
    }
    receipt["content_sha256"] = content_hash(receipt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_path, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = mechanics(args.project_root, args.output)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "content_sha256": receipt["content_sha256"],
                "real_data_accessed": False,
                "counts_as_model_fit": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
