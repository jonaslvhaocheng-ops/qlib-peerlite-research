# M7 complete engineering design

- Status: `IMPLEMENTATION-READY / EMPIRICAL NOT AUTHORIZED`
- Owner: Qlib PeerLite research mainline
- Risk: `R3`
- Requirement: complete and test all step-eight engineering surfaces for the
  two isolated candidates `PEERLITE_K16_CCC` and
  `PEERLITE_K16_MSE_GATE`.
- Scope authority:
  `contracts/changes/m7_complete_engineering_cr_v1.json`
- Architecture:
  `architecture_confirmation.md`

## 1. Problem and scope

### Current behavior

The first tranche implements the CCC primitive and rejects dataset-level Gate
use. The repository does not yet have:

- a concrete value/provenance-bound market-state dataset;
- complete M7 checkpoint metadata and semantic replay;
- a zero-event prerequisite validator;
- the exact CCC-then-Gate run/recovery state machine;
- a protected complete-package coverage profile.

### Desired behavior

The repository must support deterministic synthetic CCC and Gate journeys
through the public Qlib-compatible model boundary while making empirical M7
execution impossible unless separately frozen external evidence is supplied.

### Non-goals

- no real-data candidate fit or performance conclusion;
- no cost/benchmark proxy or automatic freeze;
- no trial-ledger write from the M7 package;
- no final-OOS read;
- no CCC+Gate combined model;
- no SAM, multitask, sequence Transformer, text, LLM or high-frequency module.

### Constraints

- score output remains `(datetime, instrument) -> score`;
- M6 v1 checkpoints and non-gated MSE behavior remain compatible;
- M7 package is in-process and has no network/database dependency;
- all new M7 core code has 100% line and branch coverage;
- every failure occurs before the first prohibited effect.

## 2. Repository evidence and current flow

- `data.market_state` already produces and validates the four ordered daily
  state values plus population/key/state digests.
- `data.dataset.PanelDataset` owns the Qlib-like segment and column interface.
- `models.peerlite.PeerLiteModel` owns fit/predict/checkpoint integration.
- `governance.trial_ledger` owns durable budget events and caps.
- `governance.artifacts` owns canonical JSON and atomic file writes.
- Current `cost_spec.json` and `benchmark_spec.json` are `PLANNED`.

Current gated flow terminates at `PeerLiteModel.fit()` before data access.
The proposed flow inserts verified contracts without changing the external
score schema.

## 3. Options

### Option A — distribute additions across data, model and governance packages

Advantages: fewer new folders and superficially smaller imports.

Disadvantages: M7 policy is split across three owners; protected coverage
would include large M6 modules; rollback and audit boundaries are unclear.

### Option B — one cohesive `qlib_peerlite.m7` package with thin adapters

Advantages: complete M7 ownership and coverage denominator; no new runtime;
one-way dependencies; M6 rollback is local; synthetic authority is explicit.

Disadvantages: one additional package and a small compatibility re-export for
CCC.

### Decision

Choose Option B. It is lower operational complexity and produces the shortest
auditable boundary for this change.

## 4. Components and interfaces

### 4.1 `m7.ccc`

Owns:

- `CCC_CONTRACT_VERSION = "qlib_peerlite_ccc_numerical_contract_v1"`;
- `CCC_EPSILON = 1e-8`;
- `ConcordanceCorrelationLoss`;
- `ccc_contract_payload()`.

`models.losses` re-exports the class for compatibility. Inputs are finite
float32; reducers/result are float64; population correction is zero;
singleton uses float64 MSE. Trainer clipping remains
`error_if_nonfinite=True`.

### 4.2 `m7.market_state`

Public immutable types:

```text
AuditReceipt(
  audit_kind: FIXED_PIT | FUTURE_POISON,
  verdict: PASS,
  subject_sha256,
  receipt_sha256
)

MarketStateExpectation(
  product_sha256,
  manifest_sha256,
  fixed_pit_receipt_sha256,
  future_poison_receipt_sha256,
  base_index_sha256,
  segment_contract_sha256,
  date_sha256,
  key_sha256,
  schema_sha256,
  value_sha256,
  logical_sha256
)

VerifiedMarketStateBinding(same identities and computed digests)
```

All digests are lowercase SHA256 strings. Exact columns are
`DAILY_STATE_COLUMNS` in order.

Factory:

```python
build_verified_market_state_dataset(
    *,
    base_dataset: PanelDataset,
    state_product: pd.DataFrame,
    manifest_sha256: str,
    fixed_pit_receipt: AuditReceipt,
    future_poison_receipt: AuditReceipt,
    expectation: MarketStateExpectation,
) -> VerifiedMarketStateDataset
```

Procedure:

1. Validate the daily product and exact coverage of all base-dataset dates.
2. Canonically hash the validated product including population/key/state
   metadata and compare `product_sha256`.
3. Require both PASS receipts to bind that product and the expected receipt
   hashes.
4. Copy the base dataset and exact-date broadcast four float32 state columns.
5. Compute base index, segments, dates, full `(datetime,instrument)` keys,
   schema/order, canonical float32 value bits and combined logical digest.
6. Compare every expectation before construction.
7. Store private owned copies and a frozen binding.

`VerifiedMarketStateDataset`:

- is final (`__init_subclass__` rejects);
- constructor requires a module-private token;
- `prepare()` recomputes integrity before reads and returns copies;
- exposes only the immutable `binding`;
- `verify_integrity()` compares every final logical component;
- no shift, fill, fallback or legacy `market` access.

Caller mutation of source or returned frames cannot change private values.

### 4.3 `m7.prerequisites`

Types:

```text
PrerequisiteArtifact(
  name, path, sha256, terminal_status,
  semantic_version, valid_from?, valid_to?
)

M7ScreeningPrerequisiteBundleV1(
  artifacts, bundle_sha256
)
```

Validator:

```python
validate_screening_prerequisites(
    repo_root: Path,
    artifacts: Sequence[PrerequisiteArtifact],
) -> M7ScreeningPrerequisiteBundleV1
```

Exact required names/statuses:

- `official_fee_receipt`: PASS
- `cost_spec`: FROZEN
- `benchmark_source_certificate`: PASS
- `benchmark_spec`: FROZEN
- `exchange_calendar`: PASS
- `weekly_rebalance_mapper`: PASS
- `score_to_position_rule`: PASS
- `execution_unfilled_rule`: PASS
- `adv_capacity_rule`: PASS
- `cost_implementation`: PASS
- `portfolio_implementation`: PASS
- `benchmark_implementation`: PASS
- `ir_implementation`: PASS
- `m6_k16_outputs`: PASS
- `m6_reference_portfolio`: PASS
- `development_folds`: PASS
- `final_oos_seal`: PASS

The validator requires exact set equality, safe repository-relative regular
files, current content hashes, nonempty semantic versions and terminal
statuses. M7 result/output paths, self-reference, symlinks, final-OOS data
paths and validity gaps fail. It performs no writes and accepts no default or
proxy.

### 4.4 `m7.run_state`

Constants:

```text
candidates = [PEERLITE_K16_CCC, PEERLITE_K16_MSE_GATE]
fits = [wf_2018 ... wf_2024, wf_2018_REFIT]
baseline budget = 6 candidates / 44 fits
hard cap = 8 candidates / 60 fits
```

`M7RunState` is frozen and contains run/candidate/fit statuses, next indices,
counted starts and immutable emitted event intents. Transition functions
return a new state; they do not write files.

Legal API:

```text
authorize_run(bundle, execution_spec_sha256, budget_sha256) -> AUTHORIZED
start_next_candidate(state) -> STARTED + CANDIDATE_EVALUATION_STARTED
start_next_fit(state) -> STARTED + MODEL_FIT_STARTED
finish_active_fit(state, SUCCESS|FAILED|INTERRUPTED)
finish_active_candidate(state, SCREEN_PASS|HOLD)
recover(state, fit_call_proven_absent: bool)
finish_run(state)
```

Rules:

- authorization consumes zero;
- durable-intent start increments exactly once before work;
- CCC always starts first;
- failed/interrupted CCC fit holds run and reports Gate
  `NOT_STARTED_DEPENDENCY_STOP`;
- CCC performance HOLD after eight successful fits still permits Gate;
- Gate failure holds run;
- terminal replay is a byte-stable no-op;
- duplicate/reordered/wrong candidate, seed, fold, purpose or transition fails
  with no new state;
- no retry or replacement after a counted fit start;
- counts can never exceed 8/60.

### 4.5 `m7.checkpoint`

Types:

```text
M7CheckpointContext(
  execution_spec_sha256,
  budget_sha256,
  prerequisite_bundle_sha256,
  training_dates_sha256,
  validation_dates_sha256
)
```

Helpers canonicalize:

- ordered model config;
- standardizer payloads;
- objective contract payload;
- validation metric MSE, delta `1e-10`, patience, selected epoch;
- canonical model-state hash (sorted tensor names, dtype, shape, CPU contiguous
  bytes);
- Gate binding or explicit null;
- context hashes.

`semantic_state_sha256` excludes timestamp, filesystem path, run ID and fit
ID. Mutation of weight, scaler, material config, objective version or Gate
binding changes it.

### 4.6 PeerLite integration

`PeerLiteModel.fit(dataset, m7_context=None)`:

- M6 non-gated MSE ignores M7 context and preserves v1 behavior.
- CCC and Gate require `M7CheckpointContext`.
- Gate first requires exact `VerifiedMarketStateDataset` and verifies it
  before feature reads.
- Gate market standardizer fits one row per unique training date; transformed
  values broadcast back to stocks.
- the model captures train/validation date digests, objective metadata and
  Gate binding for checkpoint.

`save_checkpoint`:

- M6 writes existing v1 schema.
- CCC/Gate writes `qlib_peerlite_checkpoint_v2` with complete M7 metadata and
  semantic hash.

`load_checkpoint` supports v1 and v2. A loaded Gate model requires an
equivalent verified dataset on predict and compares every binding field before
feature reads.

## 5. Success sequence

### Synthetic CCC

1. Build synthetic `M7CheckpointContext`.
2. Fit CCC on `PanelDataset`.
3. Save/reload v2 checkpoint.
4. Predict exact score index and finite values.
5. Refit same seed/environment and prove selected epoch, semantic hash and
   every score bit match.

### Synthetic Gate

1. Build causal daily state product and independent expected digests.
2. Build verified wrapper with two PASS audit receipts.
3. Fit Gate with context.
4. Save/reload and predict using an equivalent verified wrapper.
5. Prove binding equality and exact replay.

### Empirical preflight

Current planned cost/benchmark artifacts fail prerequisite validation before
dataset/model/journal/output access. Empirical status remains `NOT_RUN`.

## 6. Failure and recovery

- All validation errors use `M7ContractError(ValueError)`.
- All transition errors use `M7StateError(ValueError)`.
- No retry, fallback or partial wrapper is returned.
- Failed checkpoint save leaves no claimed valid M7 metadata; existing atomic
  JSON and create-new checkpoint directory semantics remain.
- A crash after start intent is recovered as interrupted/HOLD; a proven
  pre-start crash consumes zero.
- No function deletes or mutates authoritative evidence.

## 7. Compatibility, security and performance

- M6 public imports, v1 checkpoints and scores remain unchanged.
- `models.losses.ConcordanceCorrelationLoss` stays import-compatible.
- No secrets, network, SQL, subprocess or dynamic code execution enters M7.
- Wrapper memory is one private panel copy plus four float32 columns.
- Gate attention remains O(NK); hashing is O(rows) before fit/predict and does
  not change model asymptotics.
- No pickle is used for M7 metadata.

## 8. Rollout and rollback

1. Add package and tests behind no empirical runner.
2. Enable synthetic CCC.
3. Enable synthetic Gate only through verified wrapper.
4. Add pure prerequisite/run-state surfaces.
5. Pass protected coverage, independent review, synthetic E2E and CI.

Rollback removes M7 package/integration and restores unconditional Gate denial.
M6 artifacts need no migration.

## 9. Verification obligations

- CCC numeric, degenerate, gradient and validation/early-stop contracts.
- Verified wrapper schema/date/key/value/digest, defensive copy, corruption,
  future poison and substitution failures.
- unique-date market standardization.
- complete prerequisite decision table and zero side effects.
- all legal/illegal run transitions, count caps, interruption and idempotency.
- semantic checkpoint include/exclude metamorphic tests.
- M6 v1 compatibility and score schema.
- denial of final-OOS paths.
- three critical synthetic E2E journeys from §5.
- complete `src/qlib_peerlite/m7` line and branch coverage at 100%.

## 10. Implementation order

1. Add `m7` exceptions, digest primitives and CCC compatibility re-export.
2. Add verified market-state binding/factory/wrapper.
3. Integrate exact Gate verification and unique-date standardization.
4. Add checkpoint context and v2 semantic metadata/reload checks.
5. Add prerequisite validator.
6. Add pure run-state machine.
7. Add protected coverage runner/policy for the complete M7 package.
8. Run focused/full tests, independent review, synthetic E2E and CI.

## 11. Open decisions

None. Official cost/benchmark values and empirical authority are external
inputs, not hidden implementation decisions; their absence intentionally
leaves empirical M7 `NOT_RUN`.

## Verdict

`PASS / READY FOR INDEPENDENT R3 DESIGN REVIEW`
