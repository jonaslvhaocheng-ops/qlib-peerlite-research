#!/usr/bin/env python3
"""Read-only, checkpoint-by-checkpoint archival replay of the frozen M6 run.

This acceptance job is deliberately not a training runner.  It imports only
the archived ``0af4572`` source tree, reconstructs every frozen development
fold, reloads all fourteen saved checkpoints and compares exact keys/scores to
the saved prediction partitions.  It never calls ``fit`` or opens 2025+ data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PREDICTION_COLUMNS = ["datetime", "instrument", "score", "model_id", "fold_id"]
FROZEN_M6_REVISION = "0af45727d7f51af1c5a597d4a06fa5f95e34f758"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def key_digest(index: pd.MultiIndex) -> str:
    digest = hashlib.sha256()
    for timestamp, instrument in index:
        digest.update(pd.Timestamp(timestamp).isoformat().encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(str(instrument).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def score_digest(scores: pd.Series) -> str:
    digest = hashlib.sha256()
    for (timestamp, instrument), value in scores.items():
        digest.update(pd.Timestamp(timestamp).isoformat().encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(str(instrument).encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(float(value).hex().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_saved_fold_scores(path: Path, *, model_id: str, fold_id: str) -> pd.Series:
    frame = pd.read_parquet(path)
    if list(frame.columns) != PREDICTION_COLUMNS:
        raise RuntimeError(f"saved prediction schema mismatch: {model_id}/{fold_id}")
    selected = frame.loc[(frame["model_id"] == model_id) & (frame["fold_id"] == fold_id)].copy()
    if selected.empty:
        raise RuntimeError(f"saved prediction partition is missing: {model_id}/{fold_id}")
    selected["datetime"] = pd.to_datetime(selected["datetime"]).dt.tz_localize(None).dt.normalize()
    selected["instrument"] = selected["instrument"].astype(str)
    if selected.duplicated(["datetime", "instrument"]).any():
        raise RuntimeError(f"duplicate saved prediction keys: {model_id}/{fold_id}")
    values = selected["score"].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError(f"non-finite saved prediction score: {model_id}/{fold_id}")
    selected = selected.sort_values(["datetime", "instrument"], ignore_index=True)
    index = pd.MultiIndex.from_frame(selected[["datetime", "instrument"]])
    index.names = ["datetime", "instrument"]
    return pd.Series(selected["score"].to_numpy(dtype=float), index=index, name="score")


def assert_exact_replay(
    expected: pd.Series,
    replay: pd.Series,
    *,
    model_id: str,
    fold_id: str,
) -> None:
    if not expected.index.equals(replay.index):
        raise RuntimeError(f"replay key mismatch: {model_id}/{fold_id}")
    if not np.array_equal(expected.to_numpy(dtype=float), replay.to_numpy(dtype=float)):
        raise RuntimeError(f"replay score mismatch: {model_id}/{fold_id}")


def verify_frozen_source(source_root: Path, *, expected_revision: str) -> dict[str, Any]:
    manifest_path = source_root / "frozen_source_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != "qlib_peerlite_frozen_source_v1":
        raise RuntimeError("frozen source manifest schema mismatch")
    if manifest.get("git_commit") != expected_revision:
        raise RuntimeError("frozen source revision does not match M6 pre-run revision")
    spec_path = source_root / "contracts/immutable/m6_peerlite_execution_spec_v1.json"
    spec = load_json(spec_path)
    bindings = spec.get("code_binding", {}).get("files")
    if not isinstance(bindings, dict) or not bindings:
        raise RuntimeError("frozen M6 spec code bindings are missing")
    for relative_path, expected_sha256 in bindings.items():
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise RuntimeError("frozen M6 spec code binding is malformed")
        path = source_root / relative_path
        if not path.is_file() or sha256_file(path) != expected_sha256:
            raise RuntimeError(f"frozen M6 source code binding mismatch: {relative_path}")
    if spec.get("content_sha256") != content_hash(spec):
        raise RuntimeError("frozen M6 spec content hash mismatch")
    return spec


def verify_run_manifest(run_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    manifest = load_json(run_dir / "run_manifest.json")
    spec_binding = manifest.get("spec")
    if not isinstance(spec_binding, dict):
        raise RuntimeError("M6 run manifest spec binding is missing")
    # The historical server path recorded in the manifest is environmental
    # evidence only.  The caller separately compares the frozen archive's
    # source-spec file hash to this immutable binding.
    if spec_binding.get("content_sha256") != spec.get("content_sha256"):
        raise RuntimeError("M6 run manifest spec content binding mismatch")
    safeguards = manifest.get("safeguards")
    if (
        not isinstance(safeguards, dict)
        or safeguards.get("final_oos_market_partitions_opened") is not False
    ):
        raise RuntimeError("M6 run manifest opens final OOS")
    return manifest


def _fold_receipt(path: Path, *, model_id: str, fold_id: str) -> dict[str, Any]:
    receipt = load_json(path)
    if (
        receipt.get("status") != "PASS"
        or receipt.get("model_id") != model_id
        or receipt.get("fold_id") != fold_id
        or receipt.get("checkpoint_replay") != "PASS_EXACT"
        or receipt.get("final_oos_market_partitions_opened") is not False
    ):
        raise RuntimeError(f"historical fold receipt is invalid: {model_id}/{fold_id}")
    if receipt.get("content_sha256") != content_hash(receipt):
        raise RuntimeError(f"historical fold receipt content hash mismatch: {model_id}/{fold_id}")
    return receipt


def run(
    *,
    frozen_source_root: Path,
    frozen_source_archive: Path,
    expected_frozen_source_archive_sha256: str,
    expected_revision: str,
    product_dir: Path,
    run_dir: Path,
    historical_verification: Path,
    expected_historical_verification_sha256: str,
    ledger_path: Path,
    output_dir: Path,
    device: str,
) -> dict[str, Any]:
    """Reconstruct the fourteen saved M6 folds without a single fit call."""

    frozen_source_root = frozen_source_root.resolve()
    frozen_source_archive = frozen_source_archive.resolve()
    product_dir = product_dir.resolve()
    run_dir = run_dir.resolve()
    historical_verification = historical_verification.resolve()
    ledger_path = ledger_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise RuntimeError(f"archival replay output already exists: {output_dir}")
    if sha256_file(frozen_source_archive) != expected_frozen_source_archive_sha256:
        raise RuntimeError("frozen-source archive hash mismatch")
    frozen_manifest_path = frozen_source_root / "frozen_source_manifest.json"
    spec = verify_frozen_source(frozen_source_root, expected_revision=expected_revision)
    source_spec_path = frozen_source_root / "contracts/immutable/m6_peerlite_execution_spec_v1.json"
    source_spec_hash = sha256_file(source_spec_path)
    manifest = verify_run_manifest(run_dir, spec)
    manifest_spec = manifest.get("spec", {})
    if manifest_spec.get("sha256") != source_spec_hash:
        raise RuntimeError("M6 run manifest source-spec file hash mismatch")
    if sha256_file(historical_verification) != expected_historical_verification_sha256:
        raise RuntimeError("historical M6 verification receipt hash mismatch")
    historical_receipt = load_json(historical_verification)
    if historical_receipt.get("content_sha256") != content_hash(historical_receipt):
        raise RuntimeError("historical M6 verification receipt content hash mismatch")
    ledger_sha256_before = sha256_file(ledger_path)

    frozen_src = str(frozen_source_root / "src")
    if frozen_src not in sys.path:
        sys.path.insert(0, frozen_src)
    from qlib_peerlite.data.qlib_dataset import build_qlib_fold, load_bound_product_frame
    from qlib_peerlite.data.splits import annual_folds
    from qlib_peerlite.models.peerlite import PeerLiteModel

    product = load_bound_product_frame(product_dir, verify_all_files=True)
    if product.frame.index.get_level_values("datetime").max() >= pd.Timestamp("2025-01-01"):
        raise RuntimeError("archival replay would cross the final-OOS boundary")
    folds = {fold.fold_id: fold for fold in annual_folds()}
    expected_fold_ids = list(spec.get("schedule", {}).get("fold_ids", []))
    if sorted(folds) != sorted(expected_fold_ids):
        raise RuntimeError("frozen annual-fold definitions do not match the M6 spec")

    output_dir.mkdir(parents=True, exist_ok=False)
    candidates: list[dict[str, Any]] = []
    try:
        for candidate in spec.get("candidates", []):
            model_id = candidate.get("model_id")
            parameters = candidate.get("parameters")
            if not isinstance(model_id, str) or not isinstance(parameters, dict):
                raise RuntimeError("frozen M6 candidate specification is malformed")
            if parameters.get("market_gate") is not False or parameters.get("loss") != "mse":
                raise RuntimeError(
                    "archival replay may only load frozen M6 MSE/no-gate checkpoints"
                )
            prediction_path = run_dir / model_id / "predictions.parquet"
            candidate_folds: list[dict[str, Any]] = []
            for fold_id in expected_fold_ids:
                fold_receipt_path = run_dir / model_id / "folds" / fold_id / "fold_receipt.json"
                checkpoint_dir = fold_receipt_path.parent / "checkpoint"
                receipt = _fold_receipt(fold_receipt_path, model_id=model_id, fold_id=fold_id)
                checkpoint_inventory = receipt.get("checkpoint")
                if not isinstance(checkpoint_inventory, dict):
                    raise RuntimeError(
                        f"historical checkpoint inventory is missing: {model_id}/{fold_id}"
                    )
                expected_checkpoint = {
                    "metadata.json": sha256_file(checkpoint_dir / "metadata.json"),
                    "state_dict.pt": sha256_file(checkpoint_dir / "state_dict.pt"),
                }
                if checkpoint_inventory != expected_checkpoint:
                    raise RuntimeError(f"historical checkpoint hash mismatch: {model_id}/{fold_id}")
                qlib_fold = build_qlib_fold(
                    product,
                    folds[fold_id],
                    embargo_sessions=int(spec["schedule"]["embargo_sessions"]),
                )
                if (
                    receipt.get("row_counts") != qlib_fold.row_counts
                    or receipt.get("key_sha256") != qlib_fold.key_sha256
                ):
                    raise RuntimeError(
                        f"reconstructed fold structure mismatch: {model_id}/{fold_id}"
                    )
                model = PeerLiteModel.load_checkpoint(checkpoint_dir, device=device)
                replay = model.predict(qlib_fold.dataset, segment="test")
                saved = load_saved_fold_scores(prediction_path, model_id=model_id, fold_id=fold_id)
                assert_exact_replay(saved, replay, model_id=model_id, fold_id=fold_id)
                if model_id == "PEERLITE_K16_MSE" and fold_id == "wf_2018":
                    deterministic = load_json(
                        run_dir
                        / model_id
                        / "deterministic_refit"
                        / fold_id
                        / "deterministic_refit_receipt.json"
                    )
                    if deterministic.get("reference_score_sha256") != score_digest(replay):
                        raise RuntimeError("M6 deterministic-refit reference digest mismatch")
                candidate_folds.append(
                    {
                        "fold_id": fold_id,
                        "checkpoint_metadata_sha256": sha256_file(checkpoint_dir / "metadata.json"),
                        "checkpoint_state_sha256": sha256_file(checkpoint_dir / "state_dict.pt"),
                        "keys_sha256": key_digest(replay.index),
                        "scores_sha256": score_digest(replay),
                        "rows": len(replay),
                        "exact_match": True,
                    }
                )
                del model, qlib_fold, replay, saved
            candidates.append(
                {
                    "model_id": model_id,
                    "prediction_sha256": sha256_file(prediction_path),
                    "folds": candidate_folds,
                }
            )
        if sum(len(candidate["folds"]) for candidate in candidates) != 14:
            raise RuntimeError("archival replay did not cover exactly fourteen M6 fold checkpoints")
        receipt: dict[str, Any] = {
            "schema_version": "qlib_peerlite_m6_archival_checkpoint_replay_v1",
            "status": "PASS",
            "claim_ceiling": "M6_HISTORICAL_ENGINEERING_REPLAY_ONLY",
            "frozen_source": {
                "root": str(frozen_source_root),
                "archive": str(frozen_source_archive),
                "archive_sha256": expected_frozen_source_archive_sha256,
                "manifest_sha256": sha256_file(frozen_manifest_path),
                "git_commit": expected_revision,
                "m6_execution_spec_sha256": source_spec_hash,
                "m6_execution_spec_content_sha256": spec["content_sha256"],
            },
            "product": {
                "path": str(product_dir),
                "manifest_sha256": product.product_manifest_sha256,
                "date_max": product.frame.index.get_level_values("datetime")
                .max()
                .date()
                .isoformat(),
                "final_oos_market_partitions_opened": False,
            },
            "run": {
                "path": str(run_dir),
                "run_manifest_sha256": sha256_file(run_dir / "run_manifest.json"),
            },
            "verifier": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "historical_verification": {
                "path": str(historical_verification),
                "sha256": expected_historical_verification_sha256,
            },
            "ledger": {
                "path": str(ledger_path),
                "sha256_before": ledger_sha256_before,
                "sha256_after": sha256_file(ledger_path),
                "mutated": sha256_file(ledger_path) != ledger_sha256_before,
            },
            "candidates": candidates,
            "checkpoint_replays": 14,
            "model_fit_calls": 0,
            "trial_ledger_mutated": False,
            "final_oos_market_partitions_opened": False,
            "portfolio_backtests": 0,
            "cost_adjusted_metrics_computed": False,
        }
        if receipt["ledger"]["mutated"] is not False:
            raise RuntimeError("archival replay unexpectedly mutated the trial ledger")
        receipt["content_sha256"] = content_hash(receipt)
        atomic_write_json(output_dir / "archival_replay_receipt.json", receipt)
        return receipt
    except Exception:
        # Preserve no ambiguous PASS artifact if a fold fails halfway through.
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-source-root", required=True, type=Path)
    parser.add_argument("--frozen-source-archive", required=True, type=Path)
    parser.add_argument("--expected-frozen-source-archive-sha256", required=True)
    parser.add_argument("--expected-revision", default=FROZEN_M6_REVISION)
    parser.add_argument("--product-dir", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--historical-verification", required=True, type=Path)
    parser.add_argument("--expected-historical-verification-sha256", required=True)
    parser.add_argument("--ledger-path", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run(
        frozen_source_root=args.frozen_source_root,
        frozen_source_archive=args.frozen_source_archive,
        expected_frozen_source_archive_sha256=args.expected_frozen_source_archive_sha256,
        expected_revision=args.expected_revision,
        product_dir=args.product_dir,
        run_dir=args.run_dir,
        historical_verification=args.historical_verification,
        expected_historical_verification_sha256=args.expected_historical_verification_sha256,
        ledger_path=args.ledger_path,
        output_dir=args.output_dir,
        device=args.device,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"M6 archival replay failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
