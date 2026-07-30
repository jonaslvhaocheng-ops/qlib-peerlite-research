# True Status Card

- Current phase: `M8-INSTITUTIONAL-EVALUATION`
- Executed / completed / engineering gate: `yes / no / FAIL_RETAINED`
- Research decisions:
  - `PEERLITE_K16_CCC`: `HOLD`
  - `PEERLITE_K16_MSE_GATE`: `HOLD`
- Active pre-final-OOS model path: `PEERLITE_K16_MSE_BASELINE`
- M8 institutional/final-OOS evaluation: `HOLD_OPERATIONAL_CONFIRMATION_INCOMPLETE`
- Final-OOS access count: `0`

## M8 outcome

The frozen confirmation runner was stopped after discovering that it journaled
fit starts durably but did not import them into the authoritative ledger before
training. Two seed-19 folds completed, a third fit started and was interrupted,
and no later work ran. The exact starts are now reconciled and independently
verified.

The frozen no-retry rule blocks resuming or replacing those fits. Statistical,
portfolio, negative-control and final-OOS gates are therefore
`NOT_RUN_DEPENDENCY_STOP`. This is an engineering-governance HOLD, not a
negative Alpha result. PeerLite remains a research baseline and is not promoted.

## Strongest evidence

- Frozen recovery spec:
  `contracts/immutable/m7_empirical_execution_spec_v3.json`
- Qualified market-state evidence:
  `evidence/prerequisites/m7/m7_market_state_product.json`
- Run manifest:
  `evidence/m7/runs/m7_isolated_increments_20260730_v3/run_manifest.json`
- Independent verification:
  `evidence/m7/verifications/m7_isolated_increments_20260730_v3/verification_receipt.json`
- Project gate:
  `evidence/gates/M7_huatai_increments_gate.json`
- Predictions verified: `1,898,028`
- Rolling fold checkpoint replays: `14 exact`
- Deterministic refits: `2 exact`
- Qlib Recorder readbacks: `2`
- M8 gate: `evidence/gates/M8_institutional_evaluation_gate.json`
- M8 reconciliation:
  `evidence/m8/failures/m8_confirmation_20260730_v1/recovery/reconciliation_receipt.json`
- M8 independent verification:
  `evidence/m8/verifications/m8_confirmation_20260730_v1/verification_receipt.json`
- Cumulative append-only budget: `9 candidate evaluations / 64 fit starts`
- OOS access-log SHA256:
  `6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190`

## Screening results

| Candidate | Net IR | Baseline Net IR | Delta | Positive folds | Bootstrap lower 95% | Stress Net IR | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CCC only | -0.0079 | 0.0600 | -0.0679 | 42.9% | -0.3907 | -0.2468 | HOLD |
| Market Gate only | -0.0635 | 0.0600 | -0.1235 | 28.6% | -0.3321 | -0.3458 | HOLD |

Both M7 modules remain inactive. M8 began but did not complete its five-seed
confirmation. No combined CCC+Gate experiment, final-OOS opening, Alpha claim
or production claim is authorized.

## Decision boundary

The current M8 run is closed and cannot be retried. Any later confirmation
would require a separately governed path and may not reinterpret the retained
partial folds, revive CCC/Gate, or weaken the untouched final-OOS boundary.
