#!/usr/bin/env python3
"""Run the frozen four new PeerLite confirmation seeds on pre-final-OOS data."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import torch

from qlib_peerlite.data.qlib_dataset import build_qlib_fold, load_bound_product_frame
from qlib_peerlite.data.schema import score_frame
from qlib_peerlite.data.splits import annual_folds
from qlib_peerlite.governance.artifacts import append_jsonl, atomic_write_json, sha256_file
from qlib_peerlite.models.common import seed_everything
from qlib_peerlite.models.peerlite import PeerLiteModel

TZ = ZoneInfo("Asia/Shanghai")
SEEDS = (19, 42, 73, 101)
FOLDS = tuple(f"wf_{year}" for year in range(2018, 2025))
MODEL_ID = "PEERLITE_K16_MSE"


def now() -> str:
    return datetime.now(TZ).isoformat()


def canonical_hash(value: dict[str, object]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    payload = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def model_parameters(seed: int) -> dict[str, object]:
    return {
        "input_dim": 50,
        "hidden_dim": 64,
        "num_peers": 16,
        "num_heads": 4,
        "dropout": 0.1,
        "market_dim": 0,
        "market_gate": False,
        "loss": "mse",
        "seed": seed,
        "epochs": 100,
        "patience": 12,
        "learning_rate": 0.001,
        "weight_decay": 0.0001,
        "gradient_clip_norm": 1.0,
        "cross_section_batch_size": 16,
        "device": "cuda",
        "model_id": MODEL_ID,
    }


def run(project_root: Path, product_dir: Path, output_dir: Path) -> None:
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise RuntimeError("strict CUBLAS workspace configuration is required")
    if os.environ.get("QLIB_PEERLITE_ALLOW_EMPIRICAL") != "true":
        raise RuntimeError("empirical activation is required")
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    journal = output_dir / "trial_journal.jsonl"
    contract_path = project_root / "contracts/immutable/research_contract_m8_v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["contract"]["status"] != "FROZEN":
        raise RuntimeError("M8 contract is not frozen")
    if contract["method_scope"]["max_model_fits"] != 128:
        raise RuntimeError("unexpected M8 cumulative fit budget")
    oos_log = project_root / "contracts/oos_access_log.jsonl"
    expected_oos_hash = contract["splits"]["final_oos_policy"]["access_log_snapshot_hash"]
    if sha256_file(oos_log) != expected_oos_hash:
        raise RuntimeError("final-OOS log changed before confirmation")
    product = load_bound_product_frame(product_dir, verify_all_files=True)
    if product.frame.index.get_level_values("datetime").max() >= pd.Timestamp("2025-01-01"):
        raise RuntimeError("confirmation input crosses final OOS")
    fold_map = {fold.fold_id: fold for fold in annual_folds()}
    append_jsonl(journal, {"event": "M8_CONFIRMATION_STARTED", "timestamp": now()})
    seed_outputs: list[dict[str, object]] = []
    for seed in SEEDS:
        seed_dir = output_dir / f"seed_{seed}"
        seed_dir.mkdir()
        evaluation_id = f"{output_dir.name}:{MODEL_ID}:seed{seed}"
        append_jsonl(
            journal,
            {
                "event": "CANDIDATE_EVALUATION_STARTED",
                "timestamp": now(),
                "evaluation_id": evaluation_id,
                "model_id": MODEL_ID,
                "seed": seed,
                "counts_as_candidate_evaluation": True,
            },
        )
        tables: list[pd.DataFrame] = []
        receipts: list[dict[str, object]] = []
        for fold_id in FOLDS:
            fit_id = f"{evaluation_id}:{fold_id}"
            append_jsonl(
                journal,
                {
                    "event": "MODEL_FIT_STARTED",
                    "timestamp": now(),
                    "evaluation_id": evaluation_id,
                    "fit_id": fit_id,
                    "model_id": MODEL_ID,
                    "seed": seed,
                    "fold_id": fold_id,
                    "counts_as_model_fit": True,
                },
            )
            started = time.monotonic()
            seed_everything(seed)
            torch.cuda.empty_cache()
            fold = build_qlib_fold(product, fold_map[fold_id], embargo_sessions=5)
            model = PeerLiteModel(**model_parameters(seed))
            model.fit(fold.dataset)
            scores = model.predict(fold.dataset, segment="test")
            checkpoint = seed_dir / "folds" / fold_id / "checkpoint"
            checkpoint.parent.mkdir(parents=True)
            model.save_checkpoint(checkpoint)
            replay = PeerLiteModel.load_checkpoint(checkpoint, device="cuda").predict(
                fold.dataset, segment="test"
            )
            if not scores.index.equals(replay.index) or not np.array_equal(
                scores.to_numpy(), replay.to_numpy()
            ):
                raise RuntimeError(f"checkpoint replay mismatch {seed}/{fold_id}")
            table = score_frame(scores.index, scores.to_numpy(), MODEL_ID, fold_id)
            table["seed"] = seed
            tables.append(table)
            receipt = {
                "status": "PASS",
                "fit_id": fit_id,
                "seed": seed,
                "fold_id": fold_id,
                "rows": len(table),
                "elapsed_seconds": time.monotonic() - started,
                "checkpoint_replay": "PASS_EXACT",
                "final_oos_market_partitions_opened": False,
            }
            receipt["content_sha256"] = canonical_hash(receipt)
            receipt_path = checkpoint.parent / "fold_receipt.json"
            atomic_write_json(receipt_path, receipt)
            receipts.append(
                {
                    "path": str(receipt_path.relative_to(output_dir)),
                    "sha256": sha256_file(receipt_path),
                }
            )
            append_jsonl(
                journal,
                {
                    "event": "MODEL_FIT_COMPLETED",
                    "timestamp": now(),
                    "fit_id": fit_id,
                    "status": "PASS",
                    "counts_as_model_fit": False,
                },
            )
            del model, replay, fold
            gc.collect()
            torch.cuda.empty_cache()
        predictions = pd.concat(tables, ignore_index=True)
        prediction_path = seed_dir / "predictions.parquet"
        predictions.to_parquet(prediction_path, index=False, compression="zstd")
        seed_outputs.append(
            {
                "seed": seed,
                "prediction_path": str(prediction_path.relative_to(output_dir)),
                "prediction_sha256": sha256_file(prediction_path),
                "rows": len(predictions),
                "fold_receipts": receipts,
            }
        )
    manifest = {
        "schema_version": "qlib_peerlite_m8_confirmation_manifest_v1",
        "status": "PASS",
        "model_id": MODEL_ID,
        "new_seeds": list(SEEDS),
        "reused_seed": 7,
        "folds": list(FOLDS),
        "candidate_evaluations": len(SEEDS),
        "model_fits": len(SEEDS) * len(FOLDS),
        "outputs": seed_outputs,
        "contract_sha256": sha256_file(contract_path),
        "oos_log_sha256": sha256_file(oos_log),
        "final_oos_market_partitions_opened": False,
    }
    manifest["content_sha256"] = canonical_hash(manifest)
    atomic_write_json(output_dir / "run_manifest.json", manifest)
    append_jsonl(journal, {"event": "M8_CONFIRMATION_COMPLETED", "timestamp": now()})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.project_root.resolve(), args.product_dir.resolve(), args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
