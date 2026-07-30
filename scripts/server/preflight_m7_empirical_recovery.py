#!/usr/bin/env python3
"""Zero-fit validation of the frozen M7 empirical recovery path."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from qlib_peerlite.data.market_state_product import (
    load_qualified_market_state_product,
)
from qlib_peerlite.data.qlib_dataset import build_qlib_fold, load_bound_product_frame
from qlib_peerlite.data.splits import annual_folds
from qlib_peerlite.governance.artifacts import canonical_json_bytes, sha256_file
from qlib_peerlite.governance.gates import assert_empirical_ready
from qlib_peerlite.governance.trial_ledger import ledger_sha256
from qlib_peerlite.m7.checkpoint import M7CheckpointContext
from qlib_peerlite.m7.empirical import _state_binding_sha256, build_empirical_m7_fit
from qlib_peerlite.m7.prerequisites import validate_screening_prerequisites
from scripts.server.run_m7_empirical import FAMILY_ID, _dates_sha256, _evidence_paths


def _sha_payload(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def preflight(
    *,
    project_root: Path,
    product_dir: Path,
    market_state_product: Path,
    market_state_qualification: Path,
    spec_path: Path,
    ledger_path: Path,
) -> dict[str, object]:
    project_root = project_root.resolve()
    product_dir = product_dir.resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if (
        spec.get("status") != "FROZEN"
        or spec.get("schema_version") != "qlib_peerlite_m7_execution_spec_v3"
        or spec.get("family_id") != FAMILY_ID
    ):
        raise RuntimeError("M7 recovery specification is not frozen")
    recovery = spec["recovery"]
    ancestor = project_root / "artifacts/runs" / recovery["ancestor_run_id"]
    if (
        sha256_file(ancestor / "failure_receipt.json")
        != recovery["failure_receipt_sha256"]
        or sha256_file(ancestor / "trial_journal.jsonl")
        != recovery["trial_journal_sha256"]
        or ledger_sha256(ledger_path) != recovery["ledger_sha256_before"]
    ):
        raise RuntimeError("M7 recovery evidence or ledger state mismatch")

    prerequisites = validate_screening_prerequisites(project_root)
    assert_empirical_ready(_evidence_paths(project_root, product_dir))
    product = load_bound_product_frame(product_dir, verify_all_files=True)
    state_product = load_qualified_market_state_product(
        market_state_product,
        market_state_qualification,
    )
    state = state_product.state
    product_dates = pd.DatetimeIndex(
        product.frame.index.get_level_values("datetime").unique()
    ).sort_values()
    if not state.index.equals(product_dates):
        raise RuntimeError("qualified market-state dates do not match the model date axis")

    fold_id = spec["schedule"]["fold_ids"][0]
    fold = build_qlib_fold(
        product,
        {item.fold_id: item for item in annual_folds()}[fold_id],
        embargo_sessions=spec["schedule"]["embargo_sessions"],
    )
    train = fold.dataset.prepare("train", col_set="feature")
    valid = fold.dataset.prepare("valid", col_set="feature")
    spec_sha256 = sha256_file(spec_path)
    candidate_rows: list[dict[str, object]] = []
    for candidate_index, candidate in enumerate(spec["candidates"]):
        model_id = candidate["model_id"]
        fit_id = (
            recovery["replacement_fit_id"]
            if candidate_index == 0
            else f"{spec['run_id']}:{model_id}:seed7:{fold_id}"
        )
        context = M7CheckpointContext(
            family_id=FAMILY_ID,
            run_id=spec["run_id"],
            fit_id=fit_id,
            candidate_id=model_id,
            model_id=model_id,
            seed=7,
            fold_id=fold_id,
            purpose="ROLLING_SCREEN_FIT",
            execution_spec_sha256=spec_sha256,
            budget_sha256=_sha_payload(spec["schedule"]["limits"]),
            prerequisite_bundle_sha256=prerequisites.bundle_sha256,
            lease_event_sha256="0" * 64,
            authoritative_ledger_sha256=ledger_sha256(ledger_path),
            training_dates_sha256=_dates_sha256(train),
            validation_dates_sha256=_dates_sha256(valid),
            state_binding_sha256=(
                _state_binding_sha256(state)
                if candidate["parameters"]["market_gate"]
                else None
            ),
        )
        dataset, _ = build_empirical_m7_fit(
            delegate=fold.dataset,
            state=state,
            candidate_id=model_id,
            context=context,
            dataset_binding_sha256=_sha_payload(
                {
                    "product_manifest_sha256": product.product_manifest_sha256,
                    "fold_id": fold_id,
                    "key_sha256": fold.key_sha256,
                }
            ),
        )
        feature_rows = len(dataset.prepare("train", col_set="feature"))
        state_rows = len(dataset.prepare("train", col_set="market_state"))
        candidate_rows.append(
            {
                "model_id": model_id,
                "fit_id": fit_id,
                "train_feature_rows": feature_rows,
                "train_state_rows": state_rows,
            }
        )
    return {
        "schema_version": "qlib_peerlite_m7_recovery_preflight_v1",
        "status": "PASS",
        "model_fit_calls": 0,
        "candidate_evaluation_starts": 0,
        "ledger_sha256": ledger_sha256(ledger_path),
        "prerequisite_bundle_sha256": prerequisites.bundle_sha256,
        "market_state_rows": len(state),
        "fold_id": fold_id,
        "candidates": candidate_rows,
        "final_oos_market_partitions_opened": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--market-state-product", type=Path, required=True)
    parser.add_argument("--market-state-qualification", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    result = preflight(
        project_root=args.project_root,
        product_dir=args.product_dir,
        market_state_product=args.market_state_product,
        market_state_qualification=args.market_state_qualification,
        spec_path=args.spec,
        ledger_path=args.ledger,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
