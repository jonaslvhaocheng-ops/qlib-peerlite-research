#!/usr/bin/env python3
"""Run the two frozen isolated M7 increments on pre-final-OOS development data."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import resource
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import torch

from qlib_peerlite.data.market_state_product import (
    load_qualified_market_state_product,
)
from qlib_peerlite.data.qlib_dataset import build_qlib_fold, load_bound_product_frame
from qlib_peerlite.data.schema import score_frame
from qlib_peerlite.data.splits import annual_folds
from qlib_peerlite.evaluation.bootstrap import bootstrap_ir_difference
from qlib_peerlite.evaluation.institutional import (
    AShareCostSchedule,
    backtest_weekly_executable,
)
from qlib_peerlite.evaluation.metrics import evaluate_predictions, information_ratio
from qlib_peerlite.governance.artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    environment_report,
    sha256_file,
)
from qlib_peerlite.governance.gates import EmpiricalEvidence, assert_empirical_ready
from qlib_peerlite.governance.trial_ledger import (
    LedgerPrefixBinding,
    RunIntent,
    TrialLimits,
    assert_journal_starts_reconciled,
    exclusive_run_lease,
    ledger_sha256,
    reconcile_started_events,
)
from qlib_peerlite.m7.checkpoint import M7CheckpointContext
from qlib_peerlite.m7.empirical import _state_binding_sha256, build_empirical_m7_fit
from qlib_peerlite.m7.prerequisites import validate_screening_prerequisites
from qlib_peerlite.models.common import seed_everything
from qlib_peerlite.models.peerlite import PeerLiteModel
from qlib_peerlite.qlib_integration import initialize_qlib, record_run_with_qlib

SHANGHAI = ZoneInfo("Asia/Shanghai")
FAMILY_ID = "QLIB_PEERLITE_M7_INITIAL_SCREEN_V1"
CUBLAS_WORKSPACE_CONFIG = ":4096:8"


def now() -> str:
    return datetime.now(SHANGHAI).isoformat()


def _sha_payload(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _dates_sha256(frame: pd.DataFrame) -> str:
    dates = pd.DatetimeIndex(frame.index.get_level_values("datetime")).unique().sort_values()
    return hashlib.sha256(
        "\n".join(date.isoformat() for date in dates).encode("ascii")
    ).hexdigest()


def _durable_journal_append(path: Path, event: dict[str, Any]) -> None:
    payload = canonical_json_bytes(event) + b"\n"
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _started_event(
    *,
    intent: RunIntent,
    sequence: int,
    event: str,
    evaluation_id: str,
    model_id: str,
    purpose: str,
    fit_id: str | None = None,
    fold_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "qlib_peerlite_run_journal_event_v2",
        "run_id": intent.run_id,
        "event_seq": sequence,
        "source_event_id": f"{intent.run_id}:{sequence:06d}",
        "run_intent_sha256": intent.content_sha256,
        "event": event,
        "timestamp": now(),
        "family_id": intent.family_id,
        "execution_spec_content_sha256": intent.execution_spec_content_sha256,
        "evaluation_id": evaluation_id,
        "model_id": model_id,
        "seed": 7,
        "purpose": purpose,
        "counts_as_candidate_evaluation": event == "CANDIDATE_EVALUATION_STARTED",
        "counts_as_model_fit": event == "MODEL_FIT_STARTED",
    }
    if event == "MODEL_FIT_STARTED":
        payload["fit_id"] = fit_id
        payload["fold_id"] = fold_id
    payload["event_sha256"] = _sha_payload(payload)
    return payload


def _reconcile(
    *,
    journal: Path,
    ledger: Path,
    intent: RunIntent,
    journal_root: Path,
    prefix: LedgerPrefixBinding,
    limits: TrialLimits,
) -> None:
    reconcile_started_events(
        journal,
        ledger,
        run_intent=intent,
        journal_root=journal_root,
        expected_ledger_prefix=prefix,
        limits=limits,
    )
    assert_journal_starts_reconciled(
        journal,
        ledger,
        run_intent=intent,
        journal_root=journal_root,
    )


def _evidence_paths(project_root: Path, product_dir: Path) -> EmpiricalEvidence:
    return EmpiricalEvidence(
        contract_path=project_root / "contracts/immutable/research_contract_pit_v2.json",
        contract_receipt_path=project_root
        / "contracts/immutable/contract_validation_pit_v2.json",
        pit_manifest_path=project_root
        / "evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json",
        behavior_manifest_path=project_root
        / "evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json",
        m3_gate_path=project_root / "evidence/gates/M3_pit_data_gate.json",
        data_product_manifest_path=product_dir / "data_product_manifest.json",
        data_product_verification_path=project_root
        / "evidence/data_products/pit_data_product_verify_20260728_v3"
        / "data_product_verification.json",
    )


def _load_execution_panel(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if frame["datetime"].max() >= pd.Timestamp("2025-01-01"):
        raise RuntimeError("execution panel crosses final OOS")
    return frame.set_index(["datetime", "instrument"]).sort_index()


def _portfolio_panel(scores: pd.Series, execution: pd.DataFrame) -> pd.DataFrame:
    score_dates = scores.index.get_level_values("datetime").unique()
    panel = execution.loc[
        execution.index.get_level_values("datetime").isin(score_dates)
    ].copy()
    aligned_scores = scores.reindex(panel.index)
    panel["eligible"] = panel["eligible"].astype(bool) & aligned_scores.notna()
    panel["score"] = aligned_scores.fillna(-1e30).astype(float)
    return panel[
        [
            "score",
            "forward_return",
            "carry_return",
            "overnight_return",
            "eligible",
            "can_buy",
            "can_sell",
            "adv20",
        ]
    ]


def _evaluate_portfolios(
    *,
    candidate_scores: pd.Series,
    baseline_scores: pd.Series,
    execution: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Any]:
    costs = AShareCostSchedule()
    paths: dict[str, dict[str, pd.DataFrame]] = {}
    for name, scores in (
        ("candidate", candidate_scores),
        ("baseline", baseline_scores),
    ):
        panel = _portfolio_panel(scores, execution)
        paths[name] = {}
        for scenario, stress in (("base", False), ("stress", True)):
            returns, holdings, trades = backtest_weekly_executable(
                panel,
                costs=costs,
                stress=stress,
            )
            paths[name][scenario] = returns
            returns.reset_index().to_parquet(output_dir / f"{name}_{scenario}_returns.parquet")
            holdings.to_parquet(output_dir / f"{name}_{scenario}_holdings.parquet", index=False)
            trades.to_parquet(output_dir / f"{name}_{scenario}_trades.parquet", index=False)
    reference_panel = _portfolio_panel(baseline_scores, execution)
    reference, reference_holdings, reference_trades = backtest_weekly_executable(
        reference_panel,
        mode="equal_weight_universe",
        costs=costs,
    )
    reference.reset_index().to_parquet(output_dir / "market_reference_returns.parquet")
    reference_holdings.to_parquet(
        output_dir / "market_reference_holdings.parquet", index=False
    )
    reference_trades.to_parquet(
        output_dir / "market_reference_trades.parquet", index=False
    )
    candidate = paths["candidate"]["base"]["net_return"]
    baseline = paths["baseline"]["base"]["net_return"]
    aligned = pd.concat(
        [candidate.rename("candidate"), baseline.rename("baseline")], axis=1
    ).dropna()
    bootstrap = bootstrap_ir_difference(
        aligned["candidate"],
        aligned["baseline"],
        block_length=4,
        draws=2_000,
        seed=7,
    )
    fold_rows = []
    for year, section in aligned.groupby(aligned.index.year):
        fold_rows.append(
            {
                "fold_id": f"wf_{year}",
                "candidate_net_ir": information_ratio(section["candidate"]),
                "baseline_net_ir": information_ratio(section["baseline"]),
                "net_ir_delta": information_ratio(section["candidate"])
                - information_ratio(section["baseline"]),
            }
        )
    folds = pd.DataFrame(fold_rows)
    folds.to_parquet(output_dir / "fold_comparison.parquet", index=False)
    positive_fold_fraction = float((folds["net_ir_delta"] > 0).mean())
    overall_delta = information_ratio(candidate) - information_ratio(baseline)
    stress_ir = information_ratio(paths["candidate"]["stress"]["net_return"])
    screen_pass = (
        overall_delta > 0
        and positive_fold_fraction >= 0.60
        and bootstrap["ir_delta_ci_2_5"] > 0
        and stress_ir > 0
    )
    return {
        "decision": "SCREEN_PASS" if screen_pass else "HOLD",
        "overall_net_ir_delta_vs_peerlite_mse": overall_delta,
        "positive_fold_fraction": positive_fold_fraction,
        "bootstrap": bootstrap,
        "candidate_base_net_ir": information_ratio(candidate),
        "candidate_stress_net_ir": stress_ir,
        "baseline_base_net_ir": information_ratio(baseline),
        "market_reference_base_net_ir": information_ratio(reference["net_return"]),
        "weekly_observations": len(aligned),
        "final_oos_metrics_computed": False,
    }


def run(
    *,
    project_root: Path,
    product_dir: Path,
    market_state_product: Path,
    market_state_qualification: Path,
    execution_panel: Path,
    spec_path: Path,
    output_dir: Path,
    tracking_dir: Path,
    ledger_path: Path,
) -> None:
    project_root = project_root.resolve()
    product_dir = product_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    journal = output_dir / "trial_journal.jsonl"
    try:
        if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != CUBLAS_WORKSPACE_CONFIG:
            raise RuntimeError("strict CUDA determinism environment is not active")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if (
            spec.get("status") != "FROZEN"
            or spec.get("family_id") != FAMILY_ID
            or spec.get("schema_version") != "qlib_peerlite_m7_execution_spec_v3"
            or spec.get("forbidden") is None
        ):
            raise RuntimeError("M7 execution specification is not frozen")
        recovery = spec.get("recovery")
        if (
            not isinstance(recovery, dict)
            or recovery.get("kind") != "ONE_PRE_OUTCOME_HARNESS_REPLACEMENT"
            or recovery.get("no_second_replacement") is not True
        ):
            raise RuntimeError("M7 recovery binding is absent or outside the frozen scope")
        ancestor_dir = (
            project_root
            / "artifacts/runs"
            / str(recovery["ancestor_run_id"])
        )
        ancestor_failure = ancestor_dir / "failure_receipt.json"
        ancestor_journal = ancestor_dir / "trial_journal.jsonl"
        if (
            sha256_file(ancestor_failure) != recovery["failure_receipt_sha256"]
            or sha256_file(ancestor_journal) != recovery["trial_journal_sha256"]
            or ledger_sha256(ledger_path) != recovery["ledger_sha256_before"]
        ):
            raise RuntimeError("M7 recovery evidence or ledger state mismatch")
        prerequisite_bundle = validate_screening_prerequisites(project_root)
        assert_empirical_ready(_evidence_paths(project_root, product_dir))
        product = load_bound_product_frame(product_dir, verify_all_files=True)
        if product.frame.index.get_level_values("datetime").max() >= pd.Timestamp(
            "2025-01-01"
        ):
            raise RuntimeError("M7 product crosses final OOS")
        qualified_state = load_qualified_market_state_product(
            market_state_product,
            market_state_qualification,
        )
        state_spec = spec.get("market_state", {})
        if (
            qualified_state.product_id != state_spec.get("product_id")
            or qualified_state.claim != state_spec.get("claim")
        ):
            raise RuntimeError("qualified market-state identity differs from the frozen spec")
        state = qualified_state.state
        product_dates = pd.DatetimeIndex(
            product.frame.index.get_level_values("datetime").unique()
        ).sort_values()
        if not state.index.equals(product_dates):
            raise RuntimeError("qualified market-state dates do not match the model date axis")
        execution = _load_execution_panel(execution_panel)
        baseline_path = (
            project_root
            / "artifacts/runs/m6_peerlite_20260728_v1/PEERLITE_K16_MSE/predictions.parquet"
        )
        baseline_table = pd.read_parquet(baseline_path)
        baseline_scores = baseline_table.set_index(["datetime", "instrument"])["score"].sort_index()
        if baseline_scores.index.get_level_values("datetime").max() >= pd.Timestamp(
            "2025-01-01"
        ):
            raise RuntimeError("M6 baseline prediction crosses final OOS")
        budget_binding = {
            "schema_version": "qlib_peerlite_m7_budget_runtime_v1",
            "candidate_limit": spec["schedule"]["limits"]["candidate_evaluations"],
            "model_fit_limit": spec["schedule"]["limits"]["model_fits"],
            "candidate_order": spec["schedule"]["candidate_order"],
            "fits_per_candidate": 8,
        }
        market_binding = {
            "schema_version": "qlib_peerlite_m7_market_state_runtime_v1",
            "state_binding_sha256": _state_binding_sha256(state),
            "product_manifest_sha256": qualified_state.product_manifest_sha256,
            "qualification_receipt_sha256": (
                qualified_state.qualification_receipt_sha256
            ),
            "state_file_sha256": qualified_state.state_file_sha256,
            "columns": [
                "mkt_trend_20",
                "mkt_vol_20",
                "mkt_breadth_1d",
                "mkt_turnover_20",
            ],
        }
        spec_sha256 = sha256_file(spec_path)
        intent = RunIntent(
            run_id=spec["run_id"],
            family_id=FAMILY_ID,
            execution_spec_content_sha256=spec_sha256,
            budget_limit_binding=budget_binding,
            market_state_authority_binding=market_binding,
        )
        prefix_binding_doc = json.loads(
            (
                project_root
                / "contracts/changes/m7_initial_screen_budget_binding_v2.json"
            ).read_text(encoding="utf-8")
        )
        close = prefix_binding_doc["m6_close"]
        prefix = LedgerPrefixBinding(
            sha256=close["prefix_sha256"],
            candidate_evaluations=close["candidate_evaluations"],
            model_fits=close["model_fits"],
            prefix_bytes=close["prefix_bytes"],
        )
        limits = TrialLimits(
            candidate_evaluations=spec["schedule"]["limits"]["candidate_evaluations"],
            model_fits=spec["schedule"]["limits"]["model_fits"],
        )
        initialize_qlib(
            provider_dir=tracking_dir / "empty_provider",
            tracking_dir=tracking_dir / "mlflow",
        )
        environment = environment_report(project_root)
        environment["determinism"] = {
            "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
        }
        atomic_write_json(output_dir / "environment.json", environment)
        fold_specs = {fold.fold_id: fold for fold in annual_folds()}
        sequence = 0
        results: list[dict[str, Any]] = []
        with exclusive_run_lease(ledger_path):
            for candidate_index, candidate in enumerate(spec["candidates"]):
                model_id = candidate["model_id"]
                candidate_dir = output_dir / model_id
                candidate_dir.mkdir()
                reuses_ancestor_evaluation = candidate_index == 0
                if reuses_ancestor_evaluation:
                    evaluation_id = str(recovery["reused_evaluation_id"])
                else:
                    evaluation_id = f"{spec['run_id']}:{model_id}:seed7"
                    sequence += 1
                    candidate_event = _started_event(
                        intent=intent,
                        sequence=sequence,
                        event="CANDIDATE_EVALUATION_STARTED",
                        evaluation_id=evaluation_id,
                        model_id=model_id,
                        purpose="M7_INITIAL_SCREEN",
                    )
                    _durable_journal_append(journal, candidate_event)
                    _reconcile(
                        journal=journal,
                        ledger=ledger_path,
                        intent=intent,
                        journal_root=output_dir.parent,
                        prefix=prefix,
                        limits=limits,
                    )
                prediction_parts: list[pd.DataFrame] = []
                score_parts: list[pd.Series] = []
                label_parts: list[pd.Series] = []
                reference_scores: pd.Series | None = None
                fold_receipts: list[dict[str, Any]] = []
                for fold_id in spec["schedule"]["fold_ids"]:
                    sequence += 1
                    fit_id = (
                        str(recovery["replacement_fit_id"])
                        if reuses_ancestor_evaluation
                        and fold_id == spec["schedule"]["fold_ids"][0]
                        else f"{evaluation_id}:{fold_id}"
                    )
                    event = _started_event(
                        intent=intent,
                        sequence=sequence,
                        event="MODEL_FIT_STARTED",
                        evaluation_id=evaluation_id,
                        model_id=model_id,
                        purpose="ROLLING_SCREEN_FIT",
                        fit_id=fit_id,
                        fold_id=fold_id,
                    )
                    _durable_journal_append(journal, event)
                    _reconcile(
                        journal=journal,
                        ledger=ledger_path,
                        intent=intent,
                        journal_root=output_dir.parent,
                        prefix=prefix,
                        limits=limits,
                    )
                    started = time.monotonic()
                    seed_everything(7)
                    torch.cuda.empty_cache()
                    torch.cuda.reset_peak_memory_stats()
                    qlib_fold = build_qlib_fold(
                        product,
                        fold_specs[fold_id],
                        embargo_sessions=spec["schedule"]["embargo_sessions"],
                    )
                    train = qlib_fold.dataset.prepare("train", col_set="feature")
                    valid = qlib_fold.dataset.prepare("valid", col_set="feature")
                    context = M7CheckpointContext(
                        family_id=FAMILY_ID,
                        run_id=intent.run_id,
                        fit_id=fit_id,
                        candidate_id=model_id,
                        model_id=model_id,
                        seed=7,
                        fold_id=fold_id,
                        purpose="ROLLING_SCREEN_FIT",
                        execution_spec_sha256=spec_sha256,
                        budget_sha256=_sha_payload(budget_binding),
                        prerequisite_bundle_sha256=prerequisite_bundle.bundle_sha256,
                        lease_event_sha256=event["event_sha256"],
                        authoritative_ledger_sha256=ledger_sha256(ledger_path),
                        training_dates_sha256=_dates_sha256(train),
                        validation_dates_sha256=_dates_sha256(valid),
                        state_binding_sha256=(
                            _state_binding_sha256(state)
                            if candidate["parameters"]["market_gate"]
                            else None
                        ),
                    )
                    dataset_binding = _sha_payload(
                        {
                            "product_manifest_sha256": product.product_manifest_sha256,
                            "fold_id": fold_id,
                            "key_sha256": qlib_fold.key_sha256,
                        }
                    )
                    verified_dataset, authority = build_empirical_m7_fit(
                        delegate=qlib_fold.dataset,
                        state=state,
                        candidate_id=model_id,
                        context=context,
                        dataset_binding_sha256=dataset_binding,
                    )
                    model = PeerLiteModel(**candidate["parameters"])
                    model.fit(verified_dataset, m7_authority=authority)
                    scores = model.predict(verified_dataset)
                    labels = verified_dataset.prepare("test", col_set="label").iloc[:, 0]
                    labels = labels.loc[scores.index].astype(float)
                    checkpoint = candidate_dir / "folds" / fold_id / "checkpoint"
                    checkpoint.parent.mkdir(parents=True)
                    model.save_checkpoint(checkpoint)
                    replay = PeerLiteModel.load_checkpoint(
                        checkpoint, device=candidate["parameters"]["device"]
                    ).predict(verified_dataset)
                    if not np.array_equal(scores.to_numpy(), replay.to_numpy()):
                        raise RuntimeError(f"M7 checkpoint replay mismatch: {model_id}/{fold_id}")
                    if fold_id == spec["schedule"]["deterministic_refit_fold"]:
                        reference_scores = scores.copy()
                    prediction_parts.append(
                        score_frame(scores.index, scores.to_numpy(), model_id, fold_id)
                    )
                    score_parts.append(scores)
                    label_parts.append(labels)
                    receipt = {
                        "schema_version": "qlib_peerlite_m7_fold_receipt_v1",
                        "semantic_version": "m7_fold_receipt_v1",
                        "status": "PASS",
                        "fit_id": fit_id,
                        "model_id": model_id,
                        "fold_id": fold_id,
                        "diagnostic_metrics": evaluate_predictions(scores, labels),
                        "training_summary": model.training_summary(),
                        "checkpoint_replay": "PASS_EXACT",
                        "elapsed_seconds": time.monotonic() - started,
                        "gpu_peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                        "process_max_rss_kib": int(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        ),
                        "final_oos_market_partitions_opened": False,
                    }
                    receipt_path = checkpoint.parent / "fold_receipt.json"
                    atomic_write_json(receipt_path, receipt)
                    fold_receipts.append(
                        {
                            "fold_id": fold_id,
                            "path": str(receipt_path.relative_to(output_dir)),
                            "sha256": sha256_file(receipt_path),
                        }
                    )
                    del model, replay, verified_dataset, authority, qlib_fold
                    gc.collect()
                    torch.cuda.empty_cache()
                if reference_scores is None:
                    raise RuntimeError("deterministic reference score is missing")
                fold_id = spec["schedule"]["deterministic_refit_fold"]
                sequence += 1
                fit_id = f"{evaluation_id}:{fold_id}:deterministic_refit"
                event = _started_event(
                    intent=intent,
                    sequence=sequence,
                    event="MODEL_FIT_STARTED",
                    evaluation_id=evaluation_id,
                    model_id=model_id,
                    purpose="DETERMINISTIC_REFIT",
                    fit_id=fit_id,
                    fold_id=fold_id,
                )
                _durable_journal_append(journal, event)
                _reconcile(
                    journal=journal,
                    ledger=ledger_path,
                    intent=intent,
                    journal_root=output_dir.parent,
                    prefix=prefix,
                    limits=limits,
                )
                qlib_fold = build_qlib_fold(
                    product,
                    fold_specs[fold_id],
                    embargo_sessions=spec["schedule"]["embargo_sessions"],
                )
                train = qlib_fold.dataset.prepare("train", col_set="feature")
                valid = qlib_fold.dataset.prepare("valid", col_set="feature")
                context = M7CheckpointContext(
                    family_id=FAMILY_ID,
                    run_id=intent.run_id,
                    fit_id=fit_id,
                    candidate_id=model_id,
                    model_id=model_id,
                    seed=7,
                    fold_id=fold_id,
                    purpose="DETERMINISTIC_REFIT",
                    execution_spec_sha256=spec_sha256,
                    budget_sha256=_sha_payload(budget_binding),
                    prerequisite_bundle_sha256=prerequisite_bundle.bundle_sha256,
                    lease_event_sha256=event["event_sha256"],
                    authoritative_ledger_sha256=ledger_sha256(ledger_path),
                    training_dates_sha256=_dates_sha256(train),
                    validation_dates_sha256=_dates_sha256(valid),
                    state_binding_sha256=(
                        _state_binding_sha256(state)
                        if candidate["parameters"]["market_gate"]
                        else None
                    ),
                )
                verified_dataset, authority = build_empirical_m7_fit(
                    delegate=qlib_fold.dataset,
                    state=state,
                    candidate_id=model_id,
                    context=context,
                    dataset_binding_sha256=_sha_payload(
                        {
                            "product_manifest_sha256": product.product_manifest_sha256,
                            "fold_id": fold_id,
                            "key_sha256": qlib_fold.key_sha256,
                        }
                    ),
                )
                refit = PeerLiteModel(**candidate["parameters"])
                refit.fit(verified_dataset, m7_authority=authority)
                refit_scores = refit.predict(verified_dataset)
                if not np.array_equal(reference_scores.to_numpy(), refit_scores.to_numpy()):
                    raise RuntimeError(f"M7 deterministic refit mismatch: {model_id}")
                atomic_write_json(
                    candidate_dir / "deterministic_refit_receipt.json",
                    {
                        "schema_version": "qlib_peerlite_m7_refit_receipt_v1",
                        "semantic_version": "m7_refit_receipt_v1",
                        "status": "PASS_EXACT",
                        "fit_id": fit_id,
                        "model_id": model_id,
                        "fold_id": fold_id,
                        "score_rows": len(refit_scores),
                    },
                )
                predictions = pd.concat(prediction_parts, ignore_index=True).sort_values(
                    ["datetime", "instrument"], ignore_index=True
                )
                prediction_path = candidate_dir / "predictions.parquet"
                predictions.to_parquet(prediction_path, index=False)
                all_scores = pd.concat(score_parts).sort_index()
                all_labels = pd.concat(label_parts).sort_index()
                evaluation = _evaluate_portfolios(
                    candidate_scores=all_scores,
                    baseline_scores=baseline_scores.loc[all_scores.index],
                    execution=execution,
                    output_dir=candidate_dir,
                )
                metrics = {
                    "schema_version": "qlib_peerlite_m7_metrics_v1",
                    "semantic_version": "m7_metrics_v1",
                    "status": "PASS",
                    "model_id": model_id,
                    "diagnostic": evaluate_predictions(all_scores, all_labels),
                    "portfolio_screen": evaluation,
                    "claim_ceiling": spec["claim_ceiling"],
                }
                metrics_path = candidate_dir / "metrics.json"
                atomic_write_json(metrics_path, metrics)
                recorder_id = record_run_with_qlib(
                    experiment_name="qlib_peerlite_m7_isolated_increments",
                    recorder_name=f"{model_id.lower()}-{spec['run_id']}",
                    parameters={
                        "stage": "M7-ISOLATED-INCREMENTS",
                        "model_id": model_id,
                        "seed": 7,
                        "prerequisite_bundle_sha256": prerequisite_bundle.bundle_sha256,
                        "final_oos_opened": False,
                    },
                    metrics={
                        "rank_ic_mean": metrics["diagnostic"]["rank_ic_mean"],
                        "net_ir_delta": evaluation[
                            "overall_net_ir_delta_vs_peerlite_mse"
                        ],
                    },
                    artifacts=[prediction_path, metrics_path],
                )
                results.append(
                    {
                        "model_id": model_id,
                        "decision": evaluation["decision"],
                        "prediction_rows": len(predictions),
                        "prediction_sha256": sha256_file(prediction_path),
                        "metrics_sha256": sha256_file(metrics_path),
                        "fold_receipts": fold_receipts,
                        "model_fits": 8,
                        "qlib_recorder_id": recorder_id,
                        "reused_ancestor_evaluation": reuses_ancestor_evaluation,
                    }
                )
                del refit, verified_dataset, authority, qlib_fold
                gc.collect()
                torch.cuda.empty_cache()
        manifest = {
            "schema_version": "qlib_peerlite_m7_run_manifest_v1",
            "semantic_version": "m7_run_manifest_v1",
            "status": "PASS",
            "stage": "M7-ISOLATED-INCREMENTS",
            "created_at": now(),
            "claim_ceiling": spec["claim_ceiling"],
            "prerequisite_bundle_sha256": prerequisite_bundle.bundle_sha256,
            "execution_spec_sha256": spec_sha256,
            "product_manifest_sha256": product.product_manifest_sha256,
            "market_state_product_manifest_sha256": (
                qualified_state.product_manifest_sha256
            ),
            "market_state_qualification_receipt_sha256": (
                qualified_state.qualification_receipt_sha256
            ),
            "execution_panel_sha256": sha256_file(execution_panel),
            "trial_ledger_sha256_after": ledger_sha256(ledger_path),
            "new_candidate_evaluation_starts": 1,
            "successful_model_fits_this_run": 16,
            "step_eight_candidate_evaluations": 2,
            "step_eight_counted_model_fit_starts": 17,
            "step_eight_failed_model_fits": 1,
            "recovery_ancestor": {
                "run_id": recovery["ancestor_run_id"],
                "failure_receipt_sha256": recovery["failure_receipt_sha256"],
                "trial_journal_sha256": recovery["trial_journal_sha256"],
            },
            "candidates": results,
            "combination_authorized": False,
            "final_oos_market_partitions_opened": False,
            "final_oos_metrics_computed": False,
        }
        atomic_write_json(output_dir / "run_manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        atomic_write_json(
            output_dir / "failure_receipt.json",
            {
                "schema_version": "qlib_peerlite_m7_failure_v1",
                "semantic_version": "m7_failure_v1",
                "status": "FAIL",
                "created_at": now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "final_oos_market_partitions_opened": False,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--market-state-product", type=Path, required=True)
    parser.add_argument("--market-state-qualification", type=Path, required=True)
    parser.add_argument("--execution-panel", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    run(
        project_root=args.project_root,
        product_dir=args.product_dir,
        market_state_product=args.market_state_product,
        market_state_qualification=args.market_state_qualification,
        execution_panel=args.execution_panel,
        spec_path=args.spec,
        output_dir=args.output_dir,
        tracking_dir=args.tracking_dir,
        ledger_path=args.ledger,
    )


if __name__ == "__main__":
    main()
