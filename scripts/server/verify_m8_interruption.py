#!/usr/bin/env python3
"""Independently verify the retained M8 interruption and its fail-closed boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qlib_peerlite.governance.artifacts import atomic_write_json, sha256_file
from qlib_peerlite.governance.trial_ledger import verify_ledger_prefix

EXPECTED = {
    "legacy_journal": "744edff52d1e59c2a507d2fa0b472427600a09a00bf4613ddc03a173fb899996",
    "canonical_journal": "adad825b70a27bac9f75c474168c8d386006b0e9fe5205478a6bc808af8f8d32",
    "reconciliation_receipt": (
        "d6af9d1779b424d3a1ffc28857095c8c3dd528b9b6a08795c38a47eb1c69286b"
    ),
    "wf_2018_receipt": "88e554a6cc6ef52d31d48d22d9644f8c05b4ded655206627189b29a72e456437",
    "wf_2019_receipt": "eacc7f25048f39d3358f834f00e71fb7d4156ec02deab4bcde13cd410ad1fec2",
    "ledger": "57cff58227f29930e46fbe4271a38162d795f68645ad386017be52de12fab671",
    "oos_log": "6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190",
}


def run(project_root: Path, failure_dir: Path, output: Path) -> dict[str, object]:
    paths = {
        "legacy_journal": failure_dir / "trial_journal.jsonl",
        "canonical_journal": failure_dir / "recovery/trial_journal_v2.jsonl",
        "reconciliation_receipt": (
            failure_dir / "recovery/reconciliation_receipt.json"
        ),
        "wf_2018_receipt": failure_dir / "seed_19/folds/wf_2018/fold_receipt.json",
        "wf_2019_receipt": failure_dir / "seed_19/folds/wf_2019/fold_receipt.json",
        "ledger": project_root / "contracts/trial_ledger.jsonl",
        "oos_log": project_root / "contracts/oos_access_log.jsonl",
    }
    for name, path in paths.items():
        if sha256_file(path) != EXPECTED[name]:
            raise RuntimeError(f"M8 interruption evidence hash mismatch: {name}")

    prefix = verify_ledger_prefix(
        paths["ledger"],
        expected_prefix_sha256=EXPECTED["ledger"],
        expected_counts={"candidate_evaluations": 9, "model_fits": 64},
    )
    receipt = json.loads(paths["reconciliation_receipt"].read_text(encoding="utf-8"))
    if (
        receipt.get("status") != "PASS_RETAINED_FAILURE"
        or receipt.get("confirmation_complete") is not False
        or receipt.get("retry_authorized") is not False
        or receipt.get("candidate_evaluations_after") != 9
        or receipt.get("model_fits_after") != 64
        or receipt.get("final_oos_market_partitions_opened") is not False
    ):
        raise RuntimeError("M8 reconciliation invariant mismatch")

    for fold_id in ("wf_2018", "wf_2019"):
        fold_receipt = json.loads(
            (failure_dir / f"seed_19/folds/{fold_id}/fold_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        if (
            fold_receipt.get("status") != "PASS"
            or fold_receipt.get("checkpoint_replay") != "PASS_EXACT"
            or fold_receipt.get("final_oos_market_partitions_opened") is not False
        ):
            raise RuntimeError(f"completed fold receipt mismatch: {fold_id}")
    if (failure_dir / "seed_19/folds/wf_2020/fold_receipt.json").exists():
        raise RuntimeError("interrupted wf_2020 must not have a completion receipt")

    result: dict[str, object] = {
        "schema_version": "qlib_peerlite_m8_interruption_verification_v1",
        "status": "PASS_RETAINED_FAILURE",
        "retained_candidate_evaluations": 1,
        "retained_model_fit_starts": 3,
        "completed_fit_receipts": 2,
        "interrupted_fit_starts": 1,
        "ledger_candidate_evaluations": prefix.candidate_evaluations,
        "ledger_model_fits": prefix.model_fits,
        "ledger_sha256": EXPECTED["ledger"],
        "oos_access_log_sha256": EXPECTED["oos_log"],
        "confirmation_complete": False,
        "statistical_gates": "NOT_RUN_DEPENDENCY_STOP",
        "final_oos": "NOT_OPENED",
        "research_decision": "HOLD_OPERATIONAL_CONFIRMATION_INCOMPLETE",
    }
    atomic_write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--failure-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
