# M8 Institutional Decision Report

## Decision

`HOLD_OPERATIONAL_CONFIRMATION_INCOMPLETE`

PeerLite K16 MSE remains the active pre-final-OOS research baseline. It is not
promoted, rejected, or approved for production. Final OOS was not opened.

## What happened

The five-seed confirmation began with seed 19. After `wf_2018` and `wf_2019`
completed and `wf_2020` started, the runner was found to violate the required
accounting order: it durably journaled each start but did not import that start
into the authoritative ledger before calling `model.fit`.

The run was stopped. One candidate evaluation and three fit starts were
retained, taking the cumulative ledger from 8/61 to 9/64. An independent
verifier confirmed the retained journal, completed fold receipts, missing
completion receipt for the interrupted fold, ledger prefix, and untouched OOS
access log.

## Gate results

| Gate | Result |
| --- | --- |
| Frozen scope | PASS |
| Pre-fit authoritative accounting | FAIL_RETAINED |
| Incident reconciliation | PASS_RETAINED_FAILURE |
| Five-seed confirmation | NOT_RUN_DEPENDENCY_STOP |
| Statistical stability | NOT_RUN_DEPENDENCY_STOP |
| Portfolio/cost/capacity | NOT_RUN_DEPENDENCY_STOP |
| Negative controls | NOT_RUN_DEPENDENCY_STOP |
| Final OOS | NOT_OPENED |

The frozen `no_retry_after_started_fit` rule prevents resuming or replacing the
interrupted confirmation. The partial folds are incident evidence only and
were not evaluated for predictive performance.

## Claims permitted

- Steps M0–M7 remain auditable at their existing claim ceilings.
- PeerLite K16 MSE is a pre-final-OOS research baseline.
- M8 protected the trial budget and final-OOS boundary after an operational
  defect.

No superiority, Alpha, investability, final-OOS, “top 1%,” or production claim
is permitted.

## Evidence

- Gate: `evidence/gates/M8_institutional_evaluation_gate.json`
- Incident: `evidence/m8/failures/m8_confirmation_20260730_v1`
- Independent verification:
  `evidence/m8/verifications/m8_confirmation_20260730_v1/verification_receipt.json`
- Authoritative ledger: `contracts/trial_ledger.jsonl`
- OOS access log: `contracts/oos_access_log.jsonl`

