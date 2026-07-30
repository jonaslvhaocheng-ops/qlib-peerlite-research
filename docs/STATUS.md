# True Status Card

- Current phase: `M7-HUATAI-ISOLATED-INCREMENTS`
- Executed / completed / engineering gate: `yes / yes / PASS`
- Research decisions:
  - `PEERLITE_K16_CCC`: `HOLD`
  - `PEERLITE_K16_MSE_GATE`: `HOLD`
- Active v0 model path: `PEERLITE_K16_MSE_BASELINE`
- M8 institutional/final-OOS evaluation: `NOT_STARTED`
- Final-OOS access count: `0`

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
- Cumulative append-only budget: `8 candidate evaluations / 61 fit starts`
- OOS access-log SHA256:
  `6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190`

## Screening results

| Candidate | Net IR | Baseline Net IR | Delta | Positive folds | Bootstrap lower 95% | Stress Net IR | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CCC only | -0.0079 | 0.0600 | -0.0679 | 42.9% | -0.3907 | -0.2468 | HOLD |
| Market Gate only | -0.0635 | 0.0600 | -0.1235 | 28.6% | -0.3321 | -0.3458 | HOLD |

Both modules failed the preregistered screen. They remain implemented and
auditable but are inactive in the v0 research path. No combined CCC+Gate
experiment, five-seed confirmation, final-OOS opening, Alpha claim or
production claim is authorized.

## Only permitted next phase

M8 may be planned separately. It must preserve the frozen final-OOS boundary
and may not revive CCC or Gate through post-result tuning. Step 8 is closed.
