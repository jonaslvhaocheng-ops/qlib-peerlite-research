#!/usr/bin/env python3
"""Reconcile durable server-side trial starts into the authoritative ledger.

This command must run on the research server: it is intentionally not a tool
for appending a locally mirrored ledger.  It only releases a run for fitting
after the caller has separately checked that all of its journal starts were
reconciled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from qlib_peerlite.governance.artifacts import atomic_write_json, canonical_json_bytes, sha256_file
from qlib_peerlite.governance.trial_ledger import (
    LedgerPrefixBinding,
    RunIntent,
    TrialLedgerError,
    TrialLimits,
    assert_journal_starts_reconciled,
    reconcile_started_events,
)


def _content_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--journal-root", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--execution-spec-content-sha256", required=True)
    parser.add_argument("--expected-prefix-sha256", required=True)
    parser.add_argument("--expected-prefix-candidates", required=True, type=int)
    parser.add_argument("--expected-prefix-fits", required=True, type=int)
    parser.add_argument("--expected-prefix-bytes", required=True, type=int)
    parser.add_argument("--candidate-limit", required=True, type=int)
    parser.add_argument("--model-fit-limit", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    intent = RunIntent(
        run_id=args.run_id,
        family_id=args.family_id,
        execution_spec_content_sha256=args.execution_spec_content_sha256,
    )
    prefix = LedgerPrefixBinding(
        sha256=args.expected_prefix_sha256,
        candidate_evaluations=args.expected_prefix_candidates,
        model_fits=args.expected_prefix_fits,
        prefix_bytes=args.expected_prefix_bytes,
    )
    limits = TrialLimits(
        candidate_evaluations=args.candidate_limit,
        model_fits=args.model_fit_limit,
    )
    result = reconcile_started_events(
        args.journal,
        args.ledger,
        run_intent=intent,
        journal_root=args.journal_root,
        expected_ledger_prefix=prefix,
        limits=limits,
    )
    assert_journal_starts_reconciled(
        args.journal,
        args.ledger,
        run_intent=intent,
        journal_root=args.journal_root,
    )
    journal = args.journal.resolve()
    journal_root = args.journal_root.resolve()
    journal_relpath = journal.relative_to(journal_root).as_posix()
    receipt: dict[str, Any] = {
        "schema_version": "qlib_peerlite_trial_ledger_reconciliation_v2",
        "status": "PASS",
        "run_intent": {
            "run_id": intent.run_id,
            "family_id": intent.family_id,
            "execution_spec_content_sha256": intent.execution_spec_content_sha256,
            "content_sha256": intent.content_sha256,
        },
        "journal": {
            "server_path": str(journal),
            "relpath": journal_relpath,
            "sha256": sha256_file(journal),
        },
        "ledger": {
            "server_path": str(args.ledger.resolve()),
            "sha256_before": result.ledger_sha256_before,
            "sha256_after": result.ledger_sha256_after,
        },
        "expected_historical_prefix": {
            "sha256": prefix.sha256,
            "candidate_evaluations": prefix.candidate_evaluations,
            "model_fits": prefix.model_fits,
            "bytes": prefix.prefix_bytes,
        },
        "limits": {
            "candidate_evaluations": limits.candidate_evaluations,
            "model_fits": limits.model_fits,
        },
        "appended_events": result.appended_events,
        "candidate_evaluations_before": result.candidate_evaluations_before,
        "model_fits_before": result.model_fits_before,
        "candidate_evaluations_after": result.candidate_evaluations_after,
        "model_fits_after": result.model_fits_after,
        "all_journal_starts_reconciled": True,
    }
    receipt["content_sha256"] = _content_hash(receipt)
    atomic_write_json(args.receipt, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TrialLedgerError, OSError, ValueError) as exc:
        print(f"trial-ledger reconciliation failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
