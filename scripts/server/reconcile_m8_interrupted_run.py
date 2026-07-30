#!/usr/bin/env python3
"""Retain the interrupted M8 starts in the authoritative append-only ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qlib_peerlite.governance.artifacts import atomic_write_json, sha256_file
from qlib_peerlite.governance.m8_recovery import (
    canonicalize_interrupted_m8_journal,
    write_canonical_jsonl,
)
from qlib_peerlite.governance.trial_ledger import (
    LedgerPrefixBinding,
    RunIntent,
    TrialLimits,
    assert_journal_starts_reconciled,
    ledger_sha256,
    reconcile_started_events,
)

FAMILY_ID = "QLIB_PEERLITE_M8_CONFIRMATION_V1"
RECOVERY_RUN_ID = "m8_confirmation_20260730_v1_recovery"
EXPECTED_LEGACY_JOURNAL_SHA256 = (
    "744edff52d1e59c2a507d2fa0b472427600a09a00bf4613ddc03a173fb899996"
)
EXPECTED_PREFIX = LedgerPrefixBinding(
    sha256="56693d40e28d41609bb50caec99776e0907f7ee9d5ff28ae82328aecd8de8feb",
    candidate_evaluations=8,
    model_fits=61,
    prefix_bytes=35_637,
)
LIMITS = TrialLimits(candidate_evaluations=27, model_fits=128)


def run(
    *,
    project_root: Path,
    legacy_journal: Path,
    canonical_journal: Path,
    ledger: Path,
    receipt: Path,
) -> dict[str, object]:
    spec = project_root / "contracts/immutable/m8_institutional_evaluation_spec_v1.json"
    oos_log = project_root / "contracts/oos_access_log.jsonl"
    if sha256_file(legacy_journal) != EXPECTED_LEGACY_JOURNAL_SHA256:
        raise RuntimeError("retained legacy M8 journal hash mismatch")
    if receipt.exists():
        raise FileExistsError("M8 reconciliation receipt already exists")
    expected_oos = (
        "6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190"
    )
    if sha256_file(oos_log) != expected_oos:
        raise RuntimeError("final-OOS access log changed before M8 recovery")

    intent = RunIntent(
        run_id=RECOVERY_RUN_ID,
        family_id=FAMILY_ID,
        execution_spec_content_sha256=sha256_file(spec),
    )
    if not canonical_journal.exists():
        write_canonical_jsonl(
            canonical_journal,
            canonicalize_interrupted_m8_journal(
                legacy_journal,
                run_intent=intent,
            ),
        )
    before = ledger_sha256(ledger)
    result = reconcile_started_events(
        canonical_journal,
        ledger,
        run_intent=intent,
        journal_root=canonical_journal.parent.parent,
        expected_ledger_prefix=EXPECTED_PREFIX,
        limits=LIMITS,
    )
    assert_journal_starts_reconciled(
        canonical_journal,
        ledger,
        run_intent=intent,
        journal_root=canonical_journal.parent.parent,
    )
    document: dict[str, object] = {
        "schema_version": "qlib_peerlite_m8_interruption_reconciliation_v1",
        "status": "PASS_RETAINED_FAILURE",
        "run_id": "m8_confirmation_20260730_v1",
        "legacy_journal_sha256": sha256_file(legacy_journal),
        "canonical_journal_sha256": sha256_file(canonical_journal),
        "ledger_sha256_before": before,
        "ledger_sha256_after": ledger_sha256(ledger),
        "candidate_evaluations_before": result.candidate_evaluations_before,
        "candidate_evaluations_after": result.candidate_evaluations_after,
        "model_fits_before": result.model_fits_before,
        "model_fits_after": result.model_fits_after,
        "appended_events": result.appended_events,
        "completed_fit_receipts": 2,
        "interrupted_fit_starts": 1,
        "confirmation_complete": False,
        "retry_authorized": False,
        "research_decision": "HOLD_OPERATIONAL_CONFIRMATION_INCOMPLETE",
        "oos_access_log_sha256": expected_oos,
        "final_oos_market_partitions_opened": False,
    }
    atomic_write_json(receipt, document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--legacy-journal", type=Path, required=True)
    parser.add_argument("--canonical-journal", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
