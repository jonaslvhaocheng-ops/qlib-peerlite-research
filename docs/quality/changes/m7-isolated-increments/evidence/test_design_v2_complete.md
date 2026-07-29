# M7 complete engineering test design

- Risk: `R3`
- Design basis SHA256:
  `17fc01b65e7ef354b28d81bd4272d8842b4d572eadaff51d92dfd4baccba08c6`
- Scope: isolated CCC and Gate engineering only
- Empirical claim ceiling: `NOT_RUN`

## Behavior-to-test matrix

| ID | Behavior / invariant | Case and layer | Setup | Oracle |
|---|---|---|---|---|
| C1 | CCC uses float64 population contract | unit/property | finite float32 vectors, singleton, constants | exact NumPy reference; finite float64 scalar |
| C2 | CCC rejects invalid inputs | unit/boundary | empty, mismatch, float64, NaN/Inf, invalid epsilon | `ValueError` before reducer |
| C3 | non-finite gradients never update weights | integration/fault | patched clip returns error | `error_if_nonfinite=True`, zero optimizer steps |
| S1 | synthetic M7 fixture is internally generated and deterministic | contract/property | allowed spec repeated | identical fixture/capability hashes and frames |
| S2 | synthetic boundary cannot accept research data | negative/contract | `PanelDataset`, dataframe, lookalike, mismatched capability | rejection before `prepare` |
| S3 | fixture bounds and claim ceiling are fixed | unit/boundary | bad dates/sizes/features/seed | rejection; exact `SYNTHETIC_MECHANICS_ONLY` |
| G1 | Gate uses exact four daily state columns | integration | generated Gate fixture | finite score with exact MultiIndex/name |
| G2 | Gate standardizer fits one row per training date | integration/invariant | repeated stocks per date | fitted mean equals unique-date state mean |
| G3 | Gate rejects state mutation/substitution | negative/property | mutate private/source/returned data and mismatch capability | source/returned mutation isolated; digest mismatch rejects |
| G4 | future poison does not alter past state/scores | property | change generated future-only state after cutoff | past state digest/score bits unchanged |
| P1 | prerequisite diagnostic is registry-owned and never fit authority | contract | current repository plus forged PASS root | planned cost/benchmark reported; bundle cannot be passed to model |
| P2 | prerequisite parser fails closed | decision table | missing, symlink, duplicate key, noncanonical, wrong schema/status/version/hash/date | `M7ContractError`, no empirical authority/output |
| A1 | no empirical lease/model path exists | static/contract | imports, arbitrary lease lookalike, ordinary `PanelDataset` | no lease factory; every empirical-looking input rejects before `prepare` |
| A2 | exact candidate configuration is frozen | mutation/contract | mutate K/hidden/heads/dropout/gate/market_dim/loss/seed | every mutation rejects before data access |
| R1 | sequencing is CCC then Gate with 2/16 increment and 8/60 cap | state/property | legal transitions | exact immutable states/counts |
| R2 | illegal/replayed transitions are safe | state/negative | duplicate/reorder/wrong identity/cap | error or byte-stable terminal no-op; no count drift |
| R3 | recovery uses persisted receipts only | state/recovery | actual temp journal/ledger/terminal files | no digest/boolean API; reconciled-only interrupts; bound terminal succeeds |
| K1 | checkpoint v2 semantic identity is complete | unit/metamorphic | mutate weight/scaler/config/objective/state | semantic hash changes |
| K2 | checkpoint v2 execution identity is complete | unit/metamorphic | mutate candidate/seed/fold/purpose/lease/prereq/state | execution hash changes and load rejects |
| K3 | v1 compatibility and exact dispatch | integration | base MSE v1 plus exact synthetic CCC/Gate v2 | v1 M7, empirical/arbitrary v2, mixed/unknown/cross-model reject before state load |
| Q1 | score interface stays uniform | integration | CCC and Gate synthetic fit/predict | Series name `score`, unique sorted `(datetime,instrument)` |
| Z1 | rejection paths have zero prohibited effects | negative | sentinels for prepare/optimizer/write | no dataset/tensor/optimizer/journal/checkpoint/output effect |
| E1 | public synthetic CCC journey | black-box | clean process, fixed fixture | fit/save/load/predict/replay PASS, zero authority effects |
| E2 | public synthetic Gate journey | black-box | clean process, fixed fixture | binding/standardization/save/load/predict PASS |
| E3 | current empirical preflight | black-box | repository planned specs | deterministic `NOT_RUN`, zero model/journal/OOS effects |
| A3 | all M7 policy is protected in `m7.adapter` | static/mutation/coverage | inspect imports and mutate every adapter branch | no duplicate M7 policy in PeerLite; raw report lists adapter at 100% |
| CI1 | external M7 gate is deployable and pinned | static/contract | parse workflow/controller path | exact job, pinned actions/controller, locked install, tests/E2E/coverage |

## Fixtures, seams and determinism

- Tests use only internally generated reserved-date fixtures or temporary
  repositories/journals; no real market data or external service.
- Seed is fixed to `7`; CPU, frozen dropout `0.1`, hidden64/K16/4 heads and one
  to three epochs keep tests deterministic and candidate-compatible.
- Journal/ledger integration uses the existing canonical v2 event helpers and
  temporary directories.
- Side-effect sentinels replace only external effects, never the policy under
  test.
- Hash oracles use independently assembled canonical bytes; training behavior
  is asserted through public fit/predict/checkpoint outputs.

## Coverage obligations

- Complete authored denominator: every `.py` below
  `src/qlib_peerlite/m7`.
- `m7.adapter` owns all M7 candidate, authority and checkpoint-dispatch policy
  and is automatically included.
- Exact line coverage: `100%`.
- Exact branch coverage: `100%`.
- No omit/exclude rule.
- No manual adapter coverage fallback is permitted.

## Critical E2E journeys

`E1`, `E2` and `E3` are required. They run through public Python package
interfaces in a clean process and retain sanitized JSON output. Synthetic
success is mechanics-only; empirical preflight must end `NOT_RUN`.

## Verdict

`PASS`

```text
reason_code=M7_COMPLETE_TEST_MATRIX_READY
issue_type=null
next_route=tests-red
```
