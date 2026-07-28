#!/usr/bin/env python3
"""Verify Qlib signal analysis, Recorder and portfolio mechanics on synthetic data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from qlib_peerlite.data.synthetic import make_synthetic_dataset
from qlib_peerlite.evaluation.portfolio import backtest_weekly_top_fraction
from qlib_peerlite.governance.artifacts import sha256_file
from qlib_peerlite.qlib_integration import initialize_qlib, qlib_version

SHANGHAI = ZoneInfo("Asia/Shanghai")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def publish(
    *,
    project_root: Path,
    output_dir: Path,
    tracking_dir: Path,
) -> None:
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    tracking_dir = tracking_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("output directory must be new or empty")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        dataset = make_synthetic_dataset(
            n_dates=90,
            n_instruments=48,
            n_features=12,
            seed=7,
        )
        features = dataset.prepare("test", col_set="feature")
        label = dataset.prepare("test", col_set="label")
        score = (features["f00"] - 0.5 * features["f01"] + 0.1 * features["f02"]).rename("score")
        prediction = score.to_frame()

        portfolio_input = pd.concat(
            [score, label.iloc[:, 0].rename("forward_return")],
            axis=1,
        )
        portfolio_input["tradable"] = True
        portfolio_input["adv20"] = 2_000_000_000.0
        returns, holdings = backtest_weekly_top_fraction(
            portfolio_input,
            top_fraction=0.10,
            max_name_weight=0.02,
            adv_participation_limit=0.05,
            cost_bps_per_side=10.0,
            portfolio_notional=100_000_000.0,
            rebalance_weekday=4,
        )
        if returns.empty or holdings.empty:
            raise RuntimeError("synthetic portfolio mechanics produced empty output")
        if (
            not np.isfinite(returns.to_numpy(dtype=float)).all()
            or (returns["transaction_cost"] < 0).any()
            or (returns["invested_weight"] > 1.0 + 1e-12).any()
            or (holdings["weight"] > 0.02 + 1e-12).any()
        ):
            raise RuntimeError("synthetic portfolio safeguards failed")

        returns_path = staging / "synthetic_portfolio_returns.parquet"
        holdings_path = staging / "synthetic_holdings.parquet"
        returns.reset_index().to_parquet(returns_path, index=False)
        holdings.to_parquet(holdings_path, index=False)

        initialize_qlib(
            provider_dir=tracking_dir / "empty_provider",
            tracking_dir=tracking_dir / "mlflow",
        )
        from qlib.workflow import R
        from qlib.workflow.record_temp import SigAnaRecord

        experiment_name = "qlib_peerlite_m4_synthetic_analysis"
        with R.start(
            experiment_name=experiment_name,
            recorder_name="m4-synthetic-analysis-v1",
        ):
            recorder = R.get_recorder()
            recorder_id = str(recorder.id)
            recorder.save_objects(**{"pred.pkl": prediction, "label.pkl": label})
            SigAnaRecord(recorder=recorder, ana_long_short=True).generate()

            receipt = {
                "schema_version": "qlib_peerlite_analysis_mechanics_receipt_v1",
                "created_at": datetime.now(SHANGHAI).isoformat(),
                "status": "PASS",
                "gate": "M4_QLIB_ANALYSIS_MECHANICS",
                "track": "SYNTHETIC",
                "claim_ceiling": "MECHANICS_ONLY",
                "qlib": {
                    "version": qlib_version(),
                    "signal_analysis": "qlib.workflow.record_temp.SigAnaRecord",
                    "recorder_id": recorder_id,
                    "experiment_name": experiment_name,
                    "tracking_backend": "SQLITE",
                },
                "signal_mechanics": {
                    "prediction_rows": len(prediction),
                    "label_rows": len(label),
                    "prediction_index_names": list(prediction.index.names),
                    "qlib_artifacts_expected": [
                        "pred.pkl",
                        "label.pkl",
                        "sig_analysis/ic.pkl",
                        "sig_analysis/ric.pkl",
                        "sig_analysis/long_short_r.pkl",
                        "sig_analysis/long_avg_r.pkl",
                    ],
                },
                "portfolio_mechanics": {
                    "engine": "qlib_peerlite.evaluation.portfolio.backtest_weekly_top_fraction",
                    "rebalance_rows": len(returns),
                    "holding_rows": len(holdings),
                    "top_fraction": 0.10,
                    "max_name_weight": 0.02,
                    "adv_participation_limit": 0.05,
                    "cost_bps_per_side": 10.0,
                    "max_observed_weight": float(holdings["weight"].max()),
                    "max_observed_invested_weight": float(returns["invested_weight"].max()),
                    "minimum_observed_cost": float(returns["transaction_cost"].min()),
                },
                "code_binding": {
                    "mode": "EXPLICIT_SHA256",
                    "files": {
                        "scripts/server/verify_qlib_analysis_mechanics.py": sha256_file(
                            Path(__file__).resolve()
                        ),
                        "src/qlib_peerlite/data/synthetic.py": sha256_file(
                            project_root / "src/qlib_peerlite/data/synthetic.py"
                        ),
                        "src/qlib_peerlite/evaluation/portfolio.py": sha256_file(
                            project_root / "src/qlib_peerlite/evaluation/portfolio.py"
                        ),
                        "src/qlib_peerlite/qlib_integration.py": sha256_file(
                            project_root / "src/qlib_peerlite/qlib_integration.py"
                        ),
                        "uv.lock": sha256_file(project_root / "uv.lock"),
                    },
                },
                "safeguards": {
                    "real_data_rows": 0,
                    "model_fits": 0,
                    "real_performance_metrics_computed": False,
                    "final_oos_market_partitions_opened": False,
                },
                "limitations": [
                    "All signal and portfolio outputs are synthetic mechanics only.",
                    "No real-data model, signal evaluation, backtest or Alpha claim was produced.",
                    "This does not validate A-share execution, cost calibration or capacity.",
                ],
            }
            receipt["content_sha256"] = hashlib.sha256(
                canonical_json(receipt).encode("utf-8")
            ).hexdigest()
            receipt_path = staging / "analysis_mechanics_receipt.json"
            write_json(receipt_path, receipt)
            R.log_params(
                gate="M4_QLIB_ANALYSIS_MECHANICS",
                track="SYNTHETIC",
                claim_ceiling="MECHANICS_ONLY",
                final_oos_opened=False,
                real_data_rows=0,
            )
            R.log_artifact(str(receipt_path))
            R.log_artifact(str(returns_path), artifact_path="synthetic_portfolio")
            R.log_artifact(str(holdings_path), artifact_path="synthetic_portfolio")

        recorder = R.get_recorder(
            recorder_id=recorder_id,
            experiment_name=experiment_name,
        )
        artifacts = set(recorder.list_artifacts())
        for required in ("pred.pkl", "label.pkl", "analysis_mechanics_receipt.json"):
            if required not in artifacts:
                raise RuntimeError(f"Qlib Recorder artifact missing: {required}")
        signal_artifacts = set(recorder.list_artifacts("sig_analysis"))
        expected_signal = {
            "sig_analysis/ic.pkl",
            "sig_analysis/ric.pkl",
            "sig_analysis/long_short_r.pkl",
            "sig_analysis/long_avg_r.pkl",
        }
        if not expected_signal <= signal_artifacts:
            raise RuntimeError("Qlib signal-analysis artifacts are incomplete")
        portfolio_artifacts = set(recorder.list_artifacts("synthetic_portfolio"))
        expected_portfolio = {
            "synthetic_portfolio/synthetic_portfolio_returns.parquet",
            "synthetic_portfolio/synthetic_holdings.parquet",
        }
        if not expected_portfolio <= portfolio_artifacts:
            raise RuntimeError("synthetic portfolio artifacts are incomplete")

        downloaded = Path(recorder.download_artifact("analysis_mechanics_receipt.json"))
        if sha256_file(downloaded) != sha256_file(receipt_path):
            raise RuntimeError("Qlib Recorder receipt bytes differ")

        manifest = {
            "schema_version": "qlib_peerlite_analysis_mechanics_manifest_v1",
            "status": "PASS",
            "track": "SYNTHETIC",
            "receipt": {
                "path": receipt_path.name,
                "sha256": sha256_file(receipt_path),
                "content_sha256": receipt["content_sha256"],
            },
            "outputs": {
                returns_path.name: sha256_file(returns_path),
                holdings_path.name: sha256_file(holdings_path),
            },
            "qlib_recorder": {
                "experiment_name": experiment_name,
                "recorder_id": recorder_id,
                "receipt_artifact_sha256": sha256_file(downloaded),
                "signal_artifacts": sorted(expected_signal),
                "portfolio_artifacts": sorted(expected_portfolio),
            },
            "real_data_rows": 0,
            "real_performance_metrics_computed": False,
            "final_oos_market_partitions_opened": False,
        }
        manifest["content_sha256"] = hashlib.sha256(
            canonical_json(manifest).encode("utf-8")
        ).hexdigest()
        write_json(staging / "analysis_mechanics_manifest.json", manifest)

        for path in staging.iterdir():
            if path.is_file():
                path.chmod(0o440)
        staging.chmod(0o550)
        if output_dir.exists():
            output_dir.rmdir()
        os.replace(staging, output_dir)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "track": "SYNTHETIC",
                    "recorder_id": recorder_id,
                    "signal_artifacts": len(expected_signal),
                    "portfolio_artifacts": len(expected_portfolio),
                    "real_data_rows": 0,
                    "final_oos_market_partitions_opened": False,
                    "manifest_sha256": sha256_file(output_dir / "analysis_mechanics_manifest.json"),
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path, required=True)
    args = parser.parse_args()
    publish(
        project_root=args.project_root,
        output_dir=args.output_dir,
        tracking_dir=args.tracking_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
