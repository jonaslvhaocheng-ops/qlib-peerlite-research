# M7 isolated increments — executable test design

- Basis:
  `change_design_v2.md`
- Design review:
  `design_review_v2_independent.md` — `PASS`
- Risk: `R3`
- Empirical state: `M7 NOT_RUN`

## Scope

The portfolio covers only the four approved implementation surfaces:

1. CCC numerical and checkpoint contract.
2. Exact verified Gate state data/provenance binding.
3. M7 screening prerequisite validator.
4. Authorization, counted-start and recovery state machine.

It also preserves M6 model/checkpoint/score compatibility and the final-OOS
seal. No test may create a real candidate/fit ledger event or read real final
OOS.

## Behavior-to-test matrix

| ID | Behavior / invariant | Case | Layer | Setup / input | Oracle | Doubles | Coverage obligation | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CCC-U01 | CCC uses float64 population reducers | success | unit | fixed float32 vectors with hand-computable means/variance/covariance | loss equals independent NumPy float64 reference within `1e-12`; result dtype float64 | none | normal formula | required |
| CCC-U02 | singleton falls back to float64 MSE | boundary | unit | one prediction/target | exact float64 squared error | none | `<2` branch | required |
| CCC-U03 | constant equal, constant unequal and anti-correlated arrays follow frozen formula | boundary | unit | three fixed vector pairs | exact finite reference values; no divide-by-zero | none | zero-variance and epsilon branches | required |
| CCC-U04 | non-finite inputs/intermediate/loss fail | failure | unit | NaN, ±Inf, overflowing finite values | explicit numerical-contract error before optimizer step | none | every finite guard | required |
| CCC-U05 | gradient remains finite and reaches float32 parameters | success | unit | tiny linear layer plus CCC | all parameter gradients finite float32 and nonzero where expected | none | autograd cast path | required |
| CCC-U06 | padded dates are reduced independently | property | unit | two cross-sections plus padding/mask; alter padded values | batch loss equals mean of two reference date losses; padding mutation has no effect | none | date loop/mask path | required |
| CCC-U07 | validation stays MSE and tie keeps earliest epoch | transition | unit/integration | scripted network losses at delta below, equal to and above `1e-10` | replacement only for `valid < best-1e-10`; patience/selected epoch exact | scripted network outputs, not loss under test | early-stop decision table | required |
| CCC-C01 | checkpoint records full numerical contract | contract | integration | synthetic CCC fit/checkpoint | objective, contract version, dtypes, correction, epsilon, singleton, validation MSE and early-stop fields exact | synthetic dataset | metadata serialization/reload | required |
| CCC-C02 | semantic state hash ignores execution-instance fields | metamorphic | contract | same model/scalers/config with different timestamp/path/fit ID | semantic hashes equal | none | canonical include/exclude set | required |
| CCC-C03 | semantic state hash changes for material state | negative | contract | mutate weight, scaler, config, objective version or Gate binding | semantic hash changes for each mutation | none | every included field | required |
| GATE-U01 | exact four ordered columns are accepted | success | unit | two-date state product and base panel | wrapper created; schema/date/key/value/logical digests match independent canonical encoder | none | normal factory path | required |
| GATE-U02 | legacy `market` cannot satisfy Gate | regression/failure | integration | dataset with valid legacy market columns but no market_state wrapper | fail before candidate/fit/model construction | fake dataset only | repaired channel boundary | required |
| GATE-U03 | missing/extra/reordered/non-finite state columns fail | decision table | unit | one mutation per class | exact state-contract error; no wrapper | none | schema/order/finite branches | required |
| GATE-U04 | missing/extra/duplicate dates or inconsistent same-date rows fail | decision table | unit | mutate state coverage/broadcast rows | fail before wrapper publication | none | date and many-to-one branches | required |
| GATE-U05 | future poison cannot alter prior binding | metamorphic/PIT | integration | mutate rows strictly after protected date | prior date/key/value/logical digest unchanged | synthetic causal product | future-isolation path | required |
| GATE-U06 | caller mutations cannot alter private binding | security/property | unit | mutate source frame and returned prepare frame after factory | subsequent digest and values unchanged | none | defensive-copy branches | required |
| GATE-U07 | value/provenance substitution fails | negative | contract | values from product A with manifest/PIT receipts from B | factory rejects; zero side effects | synthetic signed manifests | identity/value coupling | required |
| GATE-U08 | digest recheck catches internal corruption | failure | unit | controlled fault seam changes private stored value after construction | fit/predict/reload fails before tensor use | explicit corruption seam | runtime revalidation | required |
| GATE-U09 | scaler fits unique training dates only | success/boundary | integration | repeated stocks/date plus extreme valid/test rows | train statistics equal unique-date ddof0 reference; valid/test do not alter them; zero scale→1 | synthetic wrapper | train-only preprocessing | required |
| GATE-U10 | Gate network remains permutation equivariant and mask-safe | property | unit | permuted stocks, padded invalid row | scores invert permutation; invalid row score/masks zero; valid rows unchanged | none | network invariant | required |
| GATE-C01 | gated checkpoint requires equivalent verified wrapper | contract | integration | save/reload then predict with same, mutated and missing bindings | same exact replay; mutated/missing binding rejected | synthetic wrapper | checkpoint binding path | required |
| PRE-U01 | complete prerequisite bundle validates | success | unit/contract | synthetic PASS/FROZEN artifacts with canonical hashes | immutable bundle identity returned | filesystem temp fixtures | all required bindings | required |
| PRE-U02 | every missing/planned/substituted prerequisite blocks at zero events | decision table | unit/contract | remove or alter each cost, benchmark, mapper, code, M6 reference, fold, seal binding | exact failure before journal write/model/data access | temp artifacts; journal spy | every prerequisite branch | required |
| PRE-U03 | result-dependent or cyclic prerequisite reference fails | security/negative | unit | bundle references M7 output or itself | fail closed at canonical validation | none | acyclic pre-result rule | required |
| LED-U01 | authorization roster consumes zero | state transition | unit | exact 2/16 roster, no start events | ledger remains 6/44 | temp journal/ledger | authorization≠counting | required |
| LED-U02 | durable start precedes candidate work and fit | integration | fault injection | callback records call order | ledger start durable/reconciled before data load or `fit` | fake model callback | start-before-work | required |
| LED-U03 | legal all-success sequence is unique | state transition | unit | CCC 8 successes then Gate 8 successes | exact states/order; counts 8/60; terminal run complete | pure state-machine fixture | every allowed transition | required |
| LED-U04 | CCC fit failure permanently skips Gate | state transition | unit | fail CCC third fit | counts 7/47; CCC HOLD; Gate `NOT_STARTED_DEPENDENCY_STOP`; run HOLD; no Gate decision | injected terminal failure | stop branch | required |
| LED-U05 | CCC performance HOLD does not skip Gate | state transition | unit | CCC fits succeed but screen fails | CCC HOLD then Gate starts normally | screen-decision fixture | isolation branch | required |
| LED-U06 | Gate fit failure consumes only started slots | state transition | unit | CCC success, fail Gate second fit | exact counts 8/54; Gate/run HOLD; no remaining starts | injected terminal failure | Gate stop branch | required |
| LED-U07 | crash after start becomes interrupted with no retry | recovery | integration | terminate between durable fit start and terminal | counted once; recovered interrupted/HOLD; second fit call forbidden | fault hook/process fixture | crash window | required |
| LED-U08 | crash before start consumes zero and may continue | recovery | integration | terminate before append | no count/event; recovery starts exact slot once after no-call proof | fault hook | pre-start branch | required |
| LED-U09 | exact terminal rerun is byte-stable no-op | idempotency | integration | replay exact RunIntent | no new events/files; terminal receipt bytes equal | temp ledger | no-op path | required |
| LED-U10 | duplicate, reordered, wrong ID/seed/fold/purpose or ambiguous recovery fails | decision table | unit/integration | one invalid mutation per class | explicit failure; ledger bytes unchanged | temp ledger | rejection branches | required |
| COMP-C01 | M6 non-gated checkpoint remains compatible | regression | integration | existing synthetic M6 checkpoint | exact score replay; state binding remains null/absent per v1 schema | existing public seam | backward compatibility | required |
| OUT-C01 | M7 scores preserve public schema | contract | integration | synthetic CCC and Gate predictions | unique finite `(datetime,instrument)` score; prediction columns exact | synthetic dataset | unified score output | required |
| OOS-S01 | production M7 surfaces deny final-OOS paths | static/contract | static + unit | path/date fixtures containing 2025+ or final partition ID | fail before read/open; no final-OOS access log entry | filesystem spy | seal branch | required |
| E2E-01 | synthetic CCC journey completes with zero empirical budget effect | E2E | E2E | frozen synthetic authority and dataset | checkpoint/reload/predictions/receipt PASS; authoritative ledger unchanged | synthetic-only adapter | public CCC journey | required |
| E2E-02 | synthetic Gate journey binds product through checkpoint | E2E | E2E | synthetic product/PIT receipts and panel | wrapper→fit→reload→predict exact; provenance hashes identical; authoritative ledger unchanged | synthetic-only adapter | public Gate journey | required |
| E2E-03 | planned cost/benchmark blocks empirical preflight | E2E/failure | E2E | current repository cost and benchmark specs | terminal `BLOCKED_BEFORE_EVENT`; no data load, model construction, journal or output | spies at external boundaries | critical fail-closed journey | required |

## Expected-red tranche

The first red-test commit must use the smallest set proving real current
defects:

1. `CCC-U01`: current CCC returns the input dtype instead of frozen float64.
2. `CCC-U04`: current CCC does not reject non-finite input.
3. `GATE-U02`: current gated model reads legacy `col_set="market"`.
4. `GATE-U07`: no value-bound verified wrapper currently exists.
5. `PRE-U02`: no M7 prerequisite validator currently exists.
6. `LED-U04`: no M7 run state machine currently exists.

Each failure must be the intended missing behavior, not an import, fixture,
environment or optional-Qlib failure. Product code remains unchanged in the
red phase.

## Fixtures and seams

- Pure fixed vectors and an independent NumPy float64 reference for CCC.
- Small two- or three-date panels with explicit state product, manifest, fixed
  audit and behavior receipts.
- Temporary append-only ledgers and journals; never use the authoritative
  `contracts/trial_ledger.jsonl`.
- A call-order observer around data-load/model-fit boundaries.
- Fault hooks immediately before/after durable start append and before
  terminal append.
- A controlled corruption seam on a test-only copy of the verified wrapper.
- Filesystem read/open spies for final-OOS denial.
- Synthetic Qlib-like `PanelDataset`; optional real Qlib tests remain separate
  and cannot be the only proof.

No test mocks the CCC formula, state digest, prerequisite validator or state
machine under test.

## Determinism

- Fixed seed 7.
- CPU, one thread where needed, no network, no wall-clock assertions.
- Canonical UTC timestamps supplied by fixtures.
- Stable instrument/date sorting.
- Exact equality for hashes, identities, state transitions, indices and
  checkpoint semantic payloads.
- Numerical tolerances only where the independent float64 oracle is compared
  with PyTorch reducers.

## Coverage obligations

All new/changed core authored code must reach:

```text
line coverage   = 100%
branch coverage = 100%
```

Protected roots:

- `src/qlib_peerlite/models/losses.py`
- changed gated paths in `src/qlib_peerlite/models/peerlite.py`
- the verified market-state binding module
- `src/qlib_peerlite/governance/m7_spec.py`
- the M7 state-machine module

Excluded from the denominator: generated artifacts, vendored code, immutable
historical evidence, CLI `if __name__` entry lines and defensive
platform-impossible branches only when a written exclusion names the
impossibility. Assertions must prove branch effects; executing a branch only
for coverage is insufficient.

## Critical E2E handoff

`eng-validate-e2e` owns E2E-01 through E2E-03. The empirical server run is not
an E2E prerequisite and remains blocked until cost, benchmark, state PIT,
authority and protected CI are all current PASS.

## Verdict

`PASS / READY FOR EXPECTED-RED TEST IMPLEMENTATION`

## First-tranche repair test refresh

The following tests replace the earlier abstract-wrapper assumption for the
current tranche:

| ID | Behavior | Setup | Oracle |
| --- | --- | --- | --- |
| GATE-R01 | no caller can self-assert verified state before the controlled factory exists | object with `verify_integrity()` no-op and a `prepare()` spy that can return valid feature/label/state frames | both `fit()` and fitted-model `predict()` raise `verified market_state factory is not available`; spy count remains zero |
| CCC-R01 | non-finite gradient cannot reach optimizer update | synthetic non-gated CCC fit; patched gradient clip records `error_if_nonfinite` and raises the same runtime error used for a non-finite total norm; optimizer `step()` spy | `error_if_nonfinite is True`; exception propagates; optimizer step count is zero |
| COMP-R01 | the denial does not affect M6 | existing non-gated MSE fit/checkpoint/predict replay | existing exact replay remains green |

The previously recorded CCC-U01/CCC-U04/GATE-U02 pre-change failures remain
valid red evidence for the primitive and legacy-channel repairs. The new
GATE-R01 and CCC-R01 tests must fail against the current intermediate source
for contract reasons, not import or fixture reasons.

The concrete Gate factory tests GATE-U01 and GATE-U03–U09, Gate checkpoint
GATE-C01, prerequisite tests, state-machine tests and Gate E2E remain future
tranches. They cannot be implemented or marked green in this tranche.
