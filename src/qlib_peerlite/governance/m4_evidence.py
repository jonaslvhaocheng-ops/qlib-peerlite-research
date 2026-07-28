from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import sha256_file


class M4EvidenceError(RuntimeError):
    """Raised when the downloaded M4 evidence bundle is incomplete or inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise M4EvidenceError(message)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M4EvidenceError(f"cannot read evidence object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise M4EvidenceError(f"evidence root must be an object: {path}")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _verify_content_hash(value: Mapping[str, Any], label: str) -> None:
    declared = value.get("content_sha256")
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
    _require(declared == actual, f"{label} content hash mismatch")


def _verify_code_binding(project_root: Path, receipt: Mapping[str, Any], label: str) -> None:
    binding = receipt.get("code_binding")
    _require(isinstance(binding, Mapping), f"{label} code binding is missing")
    files = binding.get("files")
    _require(isinstance(files, Mapping) and bool(files), f"{label} code file inventory is empty")
    for relative_path, declared_hash in files.items():
        _require(
            isinstance(relative_path, str) and isinstance(declared_hash, str),
            f"{label} code binding entry is malformed",
        )
        path = project_root / relative_path
        _require(path.is_file(), f"{label} bound code file is missing: {relative_path}")
        _require(
            sha256_file(path) == declared_hash,
            f"{label} bound code file changed: {relative_path}",
        )


def _verify_foundation(
    project_root: Path,
    foundation_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = foundation_dir / "foundation_manifest.json"
    receipt_path = foundation_dir / "qlib_foundation_receipt.json"
    _require(manifest_path.is_file(), "foundation manifest is missing")
    _require(receipt_path.is_file(), "foundation receipt is missing")
    manifest = _load(manifest_path)
    receipt = _load(receipt_path)
    _verify_content_hash(manifest, "foundation manifest")
    _verify_content_hash(receipt, "foundation receipt")

    _require(
        manifest.get("status") == "PASS"
        and manifest.get("final_oos_market_partitions_opened") is False
        and manifest.get("performance_metrics_computed") is False,
        "foundation manifest does not preserve the M4 boundary",
    )
    receipt_item = manifest.get("receipt")
    recorder = manifest.get("qlib_recorder")
    _require(isinstance(receipt_item, Mapping), "foundation receipt binding is missing")
    _require(isinstance(recorder, Mapping), "foundation Recorder binding is missing")
    receipt_sha = sha256_file(receipt_path)
    _require(
        receipt_item.get("path") == receipt_path.name
        and receipt_item.get("sha256") == receipt_sha
        and receipt_item.get("content_sha256") == receipt.get("content_sha256"),
        "foundation manifest does not bind the downloaded receipt",
    )
    _require(
        recorder.get("artifact") == receipt_path.name
        and recorder.get("artifact_sha256") == receipt_sha
        and recorder.get("tracking_backend") == "SQLITE"
        and isinstance(recorder.get("recorder_id"), str)
        and bool(recorder.get("recorder_id")),
        "foundation Qlib Recorder readback is incomplete or mismatched",
    )

    _require(
        receipt.get("status") == "PASS"
        and receipt.get("gate") == "M4_QLIB_FOUNDATION"
        and receipt.get("claim_ceiling") == "MECHANICS_ONLY",
        "foundation receipt is not a mechanics-only PASS",
    )
    _verify_code_binding(project_root, receipt, "foundation")

    empirical = receipt.get("empirical_gate")
    _require(
        isinstance(empirical, Mapping) and empirical.get("result") == "PASS",
        "foundation receipt lacks an empirical-gate PASS",
    )
    upstream_paths = {
        "m3_gate_sha256": project_root / "evidence/gates/M3_pit_data_gate.json",
        "contract_sha256": project_root / "contracts/immutable/research_contract_pit_v2.json",
        "fixed_pit_manifest_sha256": project_root
        / "evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json",
        "behavior_manifest_sha256": project_root
        / "evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json",
    }
    for field, path in upstream_paths.items():
        _require(path.is_file(), f"foundation upstream evidence is missing: {path}")
        _require(
            empirical.get(field) == sha256_file(path),
            f"foundation upstream binding changed: {field}",
        )

    product = receipt.get("data_product")
    product_manifest_path = (
        project_root / "data/manifests/pit_data_product_2012_2024_v3/data_product_manifest.json"
    )
    _require(isinstance(product, Mapping), "foundation data-product receipt is missing")
    _require(product_manifest_path.is_file(), "bound data-product manifest is missing")
    _require(
        product.get("manifest_sha256") == sha256_file(product_manifest_path)
        and product.get("product_id") == "pit_data_product_2012_2024_v3"
        and product.get("rows") == 1_658_525
        and product.get("feature_count") == 50
        and product.get("date_max") == "2024-12-17"
        and str(product.get("date_max")) < "2025-01-01",
        "foundation data-product identity or boundary mismatch",
    )
    partition_hashes = product.get("partition_sha256")
    _require(
        isinstance(partition_hashes, list)
        and len(partition_hashes) == 13
        and all(isinstance(value, str) and len(value) == 64 for value in partition_hashes),
        "foundation partition inventory is incomplete",
    )

    safeguards = receipt.get("safeguards")
    _require(
        isinstance(safeguards, Mapping)
        and safeguards.get("model_fits") == 0
        and safeguards.get("signals_evaluated") == 0
        and safeguards.get("portfolio_backtests") == 0
        and safeguards.get("performance_metrics_computed") is False
        and safeguards.get("final_oos_market_partitions_opened") is False,
        "foundation receipt crossed a prohibited M4 boundary",
    )

    folds = receipt.get("rolling_folds")
    expected_ids = [f"wf_{year}" for year in range(2018, 2025)]
    _require(
        isinstance(folds, list)
        and [fold.get("fold_id") for fold in folds if isinstance(fold, Mapping)] == expected_ids,
        "foundation does not contain the declared seven rolling folds",
    )
    for fold in folds:
        _require(isinstance(fold, Mapping), "rolling-fold receipt is malformed")
        _require(fold.get("feature_count") == 50, "rolling-fold feature count mismatch")
        counts = fold.get("row_counts")
        segments = fold.get("segments")
        digests = fold.get("key_sha256")
        _require(
            isinstance(counts, Mapping)
            and set(counts) == {"train", "valid", "test"}
            and all(isinstance(value, int) and value > 0 for value in counts.values()),
            "rolling-fold row counts are incomplete",
        )
        _require(
            isinstance(segments, Mapping) and set(segments) == {"train", "valid", "test"},
            "rolling-fold segments are incomplete",
        )
        train = segments["train"]
        valid = segments["valid"]
        test = segments["test"]
        _require(
            isinstance(train, list)
            and isinstance(valid, list)
            and isinstance(test, list)
            and len(train) == len(valid) == len(test) == 2
            and train[1] < valid[0] <= valid[1] < test[0] <= test[1]
            and test[1] < "2025-01-01",
            "rolling-fold chronology or final-OOS boundary failed",
        )
        _require(
            isinstance(digests, Mapping)
            and set(digests) == {"train", "valid", "test"}
            and all(isinstance(value, str) and len(value) == 64 for value in digests.values()),
            "rolling-fold key digests are incomplete",
        )

    replay = receipt.get("deterministic_replay")
    first_fold_hash = hashlib.sha256(_canonical_json(folds[0]).encode("utf-8")).hexdigest()
    _require(
        isinstance(replay, Mapping)
        and replay.get("fold_id") == "wf_2018"
        and replay.get("result") == "PASS"
        and replay.get("receipt_sha256") == first_fold_hash,
        "foundation deterministic replay binding failed",
    )
    return manifest, receipt


def _verify_analysis(
    project_root: Path,
    analysis_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = analysis_dir / "analysis_mechanics_manifest.json"
    receipt_path = analysis_dir / "analysis_mechanics_receipt.json"
    _require(manifest_path.is_file(), "analysis-mechanics manifest is missing")
    _require(receipt_path.is_file(), "analysis-mechanics receipt is missing")
    manifest = _load(manifest_path)
    receipt = _load(receipt_path)
    _verify_content_hash(manifest, "analysis-mechanics manifest")
    _verify_content_hash(receipt, "analysis-mechanics receipt")

    _require(
        manifest.get("status") == "PASS"
        and manifest.get("track") == "SYNTHETIC"
        and manifest.get("real_data_rows") == 0
        and manifest.get("real_performance_metrics_computed") is False
        and manifest.get("final_oos_market_partitions_opened") is False,
        "analysis-mechanics manifest is not a synthetic-only PASS",
    )
    receipt_item = manifest.get("receipt")
    recorder = manifest.get("qlib_recorder")
    _require(isinstance(receipt_item, Mapping), "analysis receipt binding is missing")
    _require(isinstance(recorder, Mapping), "analysis Recorder binding is missing")
    receipt_sha = sha256_file(receipt_path)
    _require(
        receipt_item.get("path") == receipt_path.name
        and receipt_item.get("sha256") == receipt_sha
        and receipt_item.get("content_sha256") == receipt.get("content_sha256")
        and recorder.get("receipt_artifact_sha256") == receipt_sha
        and isinstance(recorder.get("recorder_id"), str)
        and bool(recorder.get("recorder_id")),
        "analysis manifest does not bind the Recorder-readback receipt",
    )
    outputs = manifest.get("outputs")
    _require(isinstance(outputs, Mapping) and len(outputs) == 2, "synthetic outputs missing")
    for filename, declared_hash in outputs.items():
        path = analysis_dir / str(filename)
        _require(path.is_file(), f"synthetic output is missing: {filename}")
        _require(sha256_file(path) == declared_hash, f"synthetic output hash mismatch: {filename}")

    _require(
        receipt.get("status") == "PASS"
        and receipt.get("gate") == "M4_QLIB_ANALYSIS_MECHANICS"
        and receipt.get("track") == "SYNTHETIC"
        and receipt.get("claim_ceiling") == "MECHANICS_ONLY",
        "analysis receipt is not a synthetic mechanics-only PASS",
    )
    _verify_code_binding(project_root, receipt, "analysis mechanics")
    safeguards = receipt.get("safeguards")
    _require(
        isinstance(safeguards, Mapping)
        and safeguards.get("real_data_rows") == 0
        and safeguards.get("model_fits") == 0
        and safeguards.get("real_performance_metrics_computed") is False
        and safeguards.get("final_oos_market_partitions_opened") is False,
        "analysis receipt crossed a prohibited M4 boundary",
    )

    signal = receipt.get("signal_mechanics")
    _require(
        isinstance(signal, Mapping)
        and signal.get("prediction_rows") == signal.get("label_rows")
        and signal.get("prediction_rows", 0) > 0
        and signal.get("prediction_index_names") == ["datetime", "instrument"],
        "synthetic Qlib signal mechanics are incomplete",
    )
    expected_signal = {
        "sig_analysis/ic.pkl",
        "sig_analysis/ric.pkl",
        "sig_analysis/long_short_r.pkl",
        "sig_analysis/long_avg_r.pkl",
    }
    _require(
        set(recorder.get("signal_artifacts", [])) == expected_signal,
        "Qlib signal-analysis artifact inventory is incomplete",
    )
    _require(
        set(recorder.get("portfolio_artifacts", []))
        == {
            "synthetic_portfolio/synthetic_holdings.parquet",
            "synthetic_portfolio/synthetic_portfolio_returns.parquet",
        },
        "Qlib portfolio artifact inventory is incomplete",
    )

    portfolio = receipt.get("portfolio_mechanics")
    _require(
        isinstance(portfolio, Mapping)
        and portfolio.get("top_fraction") == 0.10
        and portfolio.get("max_name_weight") == 0.02
        and portfolio.get("adv_participation_limit") == 0.05
        and portfolio.get("cost_bps_per_side") == 10.0
        and 0 < portfolio.get("max_observed_weight", 0) <= 0.02
        and 0 < portfolio.get("max_observed_invested_weight", 0) <= 1.0
        and portfolio.get("minimum_observed_cost", 0) > 0,
        "synthetic portfolio safeguards or frozen mechanics mismatch",
    )
    return manifest, receipt


def verify_m4_evidence(
    *,
    project_root: Path,
    foundation_dir: Path,
    analysis_dir: Path,
) -> dict[str, Any]:
    """Independently verify downloaded M4 server evidence against local source bytes."""

    project_root = project_root.resolve()
    foundation_dir = foundation_dir.resolve()
    analysis_dir = analysis_dir.resolve()
    foundation_manifest, foundation_receipt = _verify_foundation(
        project_root,
        foundation_dir,
    )
    analysis_manifest, analysis_receipt = _verify_analysis(project_root, analysis_dir)
    return {
        "foundation_manifest_sha256": sha256_file(foundation_dir / "foundation_manifest.json"),
        "foundation_receipt_sha256": sha256_file(foundation_dir / "qlib_foundation_receipt.json"),
        "foundation_content_sha256": foundation_receipt["content_sha256"],
        "analysis_manifest_sha256": sha256_file(analysis_dir / "analysis_mechanics_manifest.json"),
        "analysis_receipt_sha256": sha256_file(analysis_dir / "analysis_mechanics_receipt.json"),
        "analysis_content_sha256": analysis_receipt["content_sha256"],
        "fold_count": len(foundation_receipt["rolling_folds"]),
        "data_rows": foundation_receipt["data_product"]["rows"],
        "feature_count": foundation_receipt["data_product"]["feature_count"],
        "foundation_recorder_id": foundation_manifest["qlib_recorder"]["recorder_id"],
        "analysis_recorder_id": analysis_manifest["qlib_recorder"]["recorder_id"],
        "real_data_model_fits": foundation_receipt["safeguards"]["model_fits"],
        "real_data_signal_evaluations": foundation_receipt["safeguards"]["signals_evaluated"],
        "real_data_portfolio_backtests": foundation_receipt["safeguards"]["portfolio_backtests"],
        "final_oos_market_partitions_opened": False,
        "performance_metrics_computed": False,
        "status": "PASS",
    }
