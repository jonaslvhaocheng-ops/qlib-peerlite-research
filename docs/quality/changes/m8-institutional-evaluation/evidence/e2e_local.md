# M8 Local E2E Evidence

## Journey 1 — retained incident verification

- Mode: quantitative workflow / CLI
- Entry point: `scripts/server/verify_m8_interruption.py`
- Input: versioned retained M8 journal, two completed fold receipts,
  reconciled ledger and frozen OOS access log
- Expected: exit 0 and `PASS_RETAINED_FAILURE`
- Actual: exit 0; ledger 9 candidate evaluations / 64 fit starts;
  confirmation incomplete; final OOS `NOT_OPENED`
- Cleanup: verifier output written only to `/tmp`
- Result: PASS

Command:

```text
uv run python scripts/server/verify_m8_interruption.py --project-root . --failure-dir evidence/m8/failures/m8_confirmation_20260730_v1 --output /tmp/m8_verification_e2e.json
```

## Journey 2 — duplicate recovery rejection

- Mode: quantitative workflow / CLI
- Entry point: `scripts/server/reconcile_m8_interrupted_run.py`
- Preconditions: immutable reconciliation receipt already exists
- Expected: non-zero exit before any ledger mutation
- Actual: exit 1 with `FileExistsError`; ledger SHA256 before and after was
  `57cff58227f29930e46fbe4271a38162d795f68645ad386017be52de12fab671`
- Cleanup: no persistent output
- Result: PASS

## Overall

Local E2E verdict: PASS. This proves retained-failure verification and
duplicate-recovery rejection. It does not substitute for an independent code
review or the live external CI gate.
