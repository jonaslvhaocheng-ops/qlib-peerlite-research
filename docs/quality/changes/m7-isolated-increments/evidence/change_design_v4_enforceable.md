# M7 complete engineering design — enforceable revision

- Status: `READY FOR INDEPENDENT REVIEW / EMPIRICAL NOT AUTHORIZED`
- Owner: Qlib PeerLite research mainline
- Risk: `R3`
- Supersedes:
  `docs/quality/changes/m7-isolated-increments/evidence/change_design_v3_complete.md`
- Requirement:
  complete and test only `PEERLITE_K16_CCC` and
  `PEERLITE_K16_MSE_GATE`.
- Scope authority:
  `contracts/changes/m7_complete_engineering_cr_v1.json`
- Architecture:
  `docs/quality/changes/m7-isolated-increments/evidence/architecture_confirmation.md`

## 1. Problem and scope

### Current observable behavior

The first tranche has a numerically stable CCC primitive and a non-finite
gradient guard. Dataset-level Gate fit/predict is intentionally denied before
data access. The complete step-eight engineering package is still absent.

The prior complete design was not implementation-ready because callers could
construct self-declared audit/prerequisite objects, recovery trusted a boolean,
checkpoint execution identity was incomplete, and coverage had no protected
mechanical denominator.

### Desired observable behavior

1. Both isolated M7 models have deterministic, Qlib-compatible engineering
   journeys that end in the unchanged score schema:
   `(datetime, instrument) -> score`.
2. A bounded synthetic test path can exercise CCC, Gate, checkpoint and score
   behavior without accepting caller-provided research data.
3. A real-data M7 fit is rejected before dataset reads unless fixed
   prerequisite artifacts are valid and a matching counted start is durably
   reconciled into the authoritative trial ledger.
4. No engineering test can create an authoritative candidate/fit event,
   consume budget, access final OOS, or support an Alpha claim.

### Non-goals

- no real-data M7 fit, screening result or model selection in this change;
- no automatic freeze or substitute for official cost/benchmark evidence;
- no CCC+Gate model;
- no SAM, multitask, Transformer sequence encoder, text, LLM, minute, tick or
  L2 module;
- no production scheduler, signal service, monitoring or order interface;
- no modification of the frozen final-OOS boundary.

### Constraints

- M6 v1 checkpoints and non-gated MSE behavior remain compatible.
- The M7 package has no network/database dependency and owns no authoritative
  ledger storage.
- All prohibited paths fail before dataset `prepare`, tensor construction,
  optimizer creation, checkpoint creation or output writes.
- New `src/qlib_peerlite/m7` code has exactly 100% line and branch coverage
  under a repository-owned protected profile.

## 2. Repository evidence and current flow

- `data.dataset.PanelDataset` is the ordinary Qlib-like research dataset.
- `data.market_state` computes the four ordered daily market-state values and
  digests, but it is not execution authority.
- `models.peerlite.PeerLiteModel` owns model fit/predict/checkpoint behavior.
- `governance.trial_ledger` already validates `RunIntent`, append-only v2
  journal events, reconciliation, prefix identity and hard caps.
- `governance.artifacts` owns canonical JSON bytes and atomic writes.
- `contracts/cost_spec.json` is
  `PLANNED_NEEDS_CURRENT_FEE_RECEIPT`.
- `contracts/benchmark_spec.json` is
  `PLANNED_NEEDS_SOURCE_CERTIFICATE`.
- `contracts/changes/m7_initial_screen_budget_binding_v2.json` explicitly says
  `DESIGN_ONLY_NOT_EXECUTION_AUTHORITY` and `execution_authorized=false`.

Therefore the current empirical result is and remains `NOT_RUN`.

## 3. Options

### Option A — caller-supplied receipts plus object-level self-consistency

This is small but unsafe. A caller can manufacture mutually consistent
objects, so it cannot distinguish engineering mechanics from empirical
authority. Rejected.

### Option B — allow all synthetic `PanelDataset` values under a mode flag

This is easy to test but unsafe. A mode string cannot prove that the panel is
synthetic, and a real panel could enter the engineering path. Rejected.

### Option C — generated synthetic capability plus externally reconciled
empirical lease

The engineering path generates its complete bounded dataset internally from a
frozen fixture specification and never accepts `PanelDataset`. The empirical
path requires a repository-owned prerequisite validator and a fit lease
derived from an already reconciled authoritative start event. Selected.

This preserves one model implementation while separating two authorities:
mechanics-only synthetic capability and empirical fit authority.

## 4. Target package and dependency direction

```text
qlib_peerlite.m7.ccc
qlib_peerlite.m7.market_state
qlib_peerlite.m7.prerequisites
qlib_peerlite.m7.run_state
qlib_peerlite.m7.checkpoint
        ↓
models.peerlite (thin composition adapter)
        ↓
existing data / governance utilities
```

Allowed imports are `m7 -> existing data/governance helpers` and
`models.peerlite -> m7 public contracts`. The governance package never imports
M7. Persistence remains owned by `governance.trial_ledger`.

## 5. Component designs

### 5.1 CCC numerical contract

`m7.ccc` owns:

```text
CCC_CONTRACT_VERSION = qlib_peerlite_ccc_numerical_contract_v1
CCC_EPSILON = 1e-8
ConcordanceCorrelationLoss
ccc_contract_payload()
```

Contract:

- inputs must be finite float32 and shape-compatible;
- population reducers and returned scalar use float64;
- variance/covariance use population correction zero;
- singleton input returns float64 MSE;
- degenerate finite inputs remain finite;
- training order is `backward`, then
  `clip_grad_norm_(error_if_nonfinite=True)`, then `optimizer.step`;
- a non-finite aggregate gradient norm causes no optimizer update.

`models.losses` re-exports the class for compatibility.

### 5.2 Generated synthetic M7 capability

`m7.market_state` owns:

```text
SyntheticFixtureSpec(
  fixture_version,
  seed,
  start_date,
  trading_days,
  instruments,
  feature_count
)

SyntheticM7Dataset
SyntheticFitCapability

build_synthetic_m7_fixture(spec) ->
  tuple[SyntheticM7Dataset, SyntheticFitCapability]
```

The only allowed specification is a frozen finite set used by repository
tests. Bounds are:

- reserved date interval `2000-01-03` through `2001-12-31`;
- `8 <= trading_days <= 64`;
- `2 <= instruments <= 16`;
- feature count equals the PeerLite test configuration;
- deterministic NumPy generator and exact algorithm version;
- no file, dataframe, `PanelDataset`, path, database or network input.

The factory internally generates features, labels, train/validation segments
and the four daily state columns. It computes canonical index, segment,
schema, value and logical hashes. Both returned types:

- are final;
- require module-private construction tokens;
- own immutable copies;
- recompute integrity before every read;
- are mutually bound by fixture SHA256;
- cannot be converted into empirical authority;
- carry `claim_ceiling=SYNTHETIC_MECHANICS_ONLY`.

An ordinary `PanelDataset`, caller-created dataframe, subclass, mode string or
lookalike is rejected before any data read. The synthetic capability is
accepted only with its paired exact dataset and exact candidate identity.

### 5.3 Verified empirical market-state dataset

Gate empirical execution additionally requires:

```text
VerifiedMarketStateBinding(
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

VerifiedMarketStateDataset
```

There is no public factory that accepts caller-declared `PASS` objects.
Construction belongs to the empirical lease verifier in §5.5. It reads the
fixed prerequisite bundle, fixed PIT receipt and future-poison receipt from
the paths registered in §5.4, parses their canonical contents, checks their
subject/product hashes, then builds the final wrapper with a module-private
token.

The wrapper:

- accepts only the exact four `DAILY_STATE_COLUMNS` in frozen order;
- requires exact date coverage with no shift/fill/fallback;
- broadcasts by date only after receipt and product validation;
- owns private base/state copies;
- returns copies from `prepare`;
- recomputes every binding digest before reads;
- rejects caller mutation, source substitution and receipt substitution.

PIT mode for this engineering change is `VERIFY / synthetic-only`. Synthetic
tests can reject incorrect mechanics but can never produce a PIT `PASS` or
`QUALIFIED` empirical claim.

### 5.4 Fixed prerequisite registry

`m7.prerequisites` owns a code constant
`M7_PREREQUISITE_REGISTRY_V1`. Callers cannot supply names, paths, status
locators, expected statuses, semantic versions or validity ranges.

Each registry entry freezes:

```text
name
repository-relative path
expected schema_version
status JSON pointer
allowed exact terminal status
semantic-version JSON pointer
optional valid_from / valid_to JSON pointers
subject-binding JSON pointers
```

Required entries and exact terminal statuses:

| Name | Fixed path | Required status |
|---|---|---|
| official_fee_receipt | `evidence/prerequisites/m7/official_fee_receipt.json` | `PASS` |
| cost_spec | `contracts/cost_spec.json` | `FROZEN` |
| benchmark_source_certificate | `evidence/prerequisites/m7/benchmark_source_certificate.json` | `PASS` |
| benchmark_spec | `contracts/benchmark_spec.json` | `FROZEN` |
| exchange_calendar | `evidence/prerequisites/m7/exchange_calendar.json` | `PASS` |
| weekly_rebalance_mapper | `evidence/prerequisites/m7/weekly_rebalance_mapper.json` | `PASS` |
| score_to_position_rule | `evidence/prerequisites/m7/score_to_position_rule.json` | `PASS` |
| execution_unfilled_rule | `evidence/prerequisites/m7/execution_unfilled_rule.json` | `PASS` |
| adv_capacity_rule | `evidence/prerequisites/m7/adv_capacity_rule.json` | `PASS` |
| cost_implementation | `evidence/prerequisites/m7/cost_implementation.json` | `PASS` |
| portfolio_implementation | `evidence/prerequisites/m7/portfolio_implementation.json` | `PASS` |
| benchmark_implementation | `evidence/prerequisites/m7/benchmark_implementation.json` | `PASS` |
| ir_implementation | `evidence/prerequisites/m7/ir_implementation.json` | `PASS` |
| m6_k16_outputs | `evidence/prerequisites/m7/m6_k16_outputs.json` | `PASS` |
| m6_reference_portfolio | `evidence/prerequisites/m7/m6_reference_portfolio.json` | `PASS` |
| development_folds | `evidence/prerequisites/m7/development_folds.json` | `PASS` |
| final_oos_seal | `evidence/prerequisites/m7/final_oos_seal.json` | `PASS` |

`validate_screening_prerequisites(repo_root)` has no artifact-list argument.
It:

1. resolves only the fixed registry paths below `repo_root`;
2. rejects missing files, symlinks, non-regular files and path escapes;
3. reads bytes once and strictly parses JSON, rejecting duplicate keys,
   non-finite numbers and non-canonical encodings;
4. checks file SHA256 against fixed cross-bindings where a parent artifact
   names it;
5. parses status/version/effective dates from the fixed JSON pointers;
6. checks subject hashes, complete interval coverage and the final-OOS seal;
7. returns a frozen `M7ScreeningPrerequisiteBundleV1` and bundle hash.

The public input type contains only `repo_root`; there is no caller-provided
terminal status. Current planned cost and benchmark specs therefore fail
deterministically before journal, dataset, model or output access.

### 5.5 Fit authority and durable start acknowledgement

`m7.run_state` defines two final capabilities:

```text
SyntheticFitCapability
EmpiricalFitLease
```

Only §5.2 can issue the synthetic capability.

Only this factory can issue an empirical lease:

```python
verify_reconciled_empirical_fit_lease(
    *,
    repo_root: Path,
    run_intent: RunIntent,
    journal_path: Path,
    journal_root: Path,
    authoritative_ledger_path: Path,
    candidate_id: str,
    seed: int,
    fold_id: str,
    purpose: str,
    source_event_id: str,
) -> EmpiricalFitLease
```

The factory:

1. validates the fixed prerequisite bundle;
2. requires family `QLIB_PEERLITE_M7_INITIAL_SCREEN_V1`;
3. verifies the `RunIntent` execution-spec, budget and market-state authority
   bindings against fixed artifact content;
4. reads the v2 journal event and requires exact candidate, seed, fold,
   purpose, event sequence and source event identity;
5. calls existing `assert_journal_starts_reconciled`;
6. rereads the authoritative ledger and requires the matching normalized
   event, M6 prefix `6/44`, maximum `8/60`, and no semantic duplicate;
7. binds the lease to the prerequisite bundle, run intent, journal event,
   authoritative ledger prefix and, for Gate, verified state binding;
8. returns a final private-token lease.

The M7 package never appends authoritative events. An external orchestrator
must append and fsync a `MODEL_FIT_STARTED` journal event, reconcile it under
the existing ledger lock, then call this verifier. This is the only empirical
fit sequence.

Any start event is counted even if the process crashes before `fit`; there is
no replacement or retry. Therefore recovery never accepts
`fit_call_proven_absent: bool`.

### 5.6 Pure sequencing and recovery receipts

The pure state machine fixes:

```text
candidates = [PEERLITE_K16_CCC, PEERLITE_K16_MSE_GATE]
seed = 7
fits = [wf_2018 ... wf_2024, wf_2018_DETERMINISTIC_REFIT]
baseline = 6 candidates / 44 fits
hard cap = 8 candidates / 60 fits
```

Pure transitions emit `EventIntent`; they never claim durability. The
orchestrator supplies a `ReconciledStartReceipt` produced by §5.5 before the
state becomes `FIT_AUTHORIZED`.

Legal transitions:

```text
NOT_AUTHORIZED
  -> PREREQUISITES_VERIFIED
  -> CANDIDATE_INTENT
  -> CANDIDATE_RECONCILED
  -> FIT_INTENT
  -> FIT_AUTHORIZED
  -> FIT_SUCCESS | FIT_FAILED | FIT_INTERRUPTED
  -> next fit | candidate terminal
  -> RUN_HOLD | RUN_SCREEN_COMPLETE
```

Rules:

- CCC always precedes Gate.
- CCC fit failure/interruption stops its remaining fits and Gate becomes
  `NOT_STARTED_DEPENDENCY_STOP`.
- CCC performance `HOLD` after eight successful fits does not by itself block
  the isolated Gate experiment.
- Gate failure/interruption holds the run.
- duplicate, reordered or mismatched candidate/seed/fold/purpose/event fails
  with no new state.
- terminal replay is a byte-stable no-op.
- counts never exceed `8/60`.

Recovery uses only persisted evidence:

```text
recover_from_journal(
  prior_state,
  verified_journal_prefix,
  verified_authoritative_ledger_prefix,
  optional_terminal_fit_receipt
)
```

- no reconciled start means no lease and no fit was authorized;
- a reconciled start without terminal receipt becomes `FIT_INTERRUPTED` and
  remains counted;
- a terminal receipt must bind the same lease/event/checkpoint/output hashes;
- recovery never retries or reclaims a counted start.

### 5.7 PeerLite integration

`PeerLiteModel.fit(dataset, *, m7_authority=None)` dispatches:

- base MSE: existing M6 behavior, no M7 authority accepted;
- CCC/Gate synthetic: exact `SyntheticM7Dataset` plus its paired
  `SyntheticFitCapability`;
- CCC empirical: exact `PanelDataset` plus `EmpiricalFitLease`;
- Gate empirical: exact `VerifiedMarketStateDataset` plus
  `EmpiricalFitLease` bound to the same market-state digest.

Authority type, candidate, seed, fold, purpose and dataset identity are checked
before `prepare`. No duck typing or subclass acceptance is allowed.

Gate behavior:

- fit the market-state standardizer on one row per unique training date;
- broadcast transformed daily state back to stocks by exact date;
- no state shift/fill/fallback;
- verify the state binding before fit and every predict;
- retain O(NK) PeerLite complexity.

Synthetic and empirical paths call the same private tensor-training core only
after their distinct public authorizations pass.

### 5.8 Checkpoint v2 identity

M7 checkpoint metadata has two hashes:

1. `semantic_state_sha256`: model state independent of execution location;
2. `execution_binding_sha256`: exact authorized fit identity.

`semantic_state_sha256` includes:

- candidate/model ID and objective contract version;
- ordered model config and K;
- feature and market-state column order;
- feature and market standardizer payloads;
- validation metric `MSE`, improvement delta `1e-10`, patience and selected
  epoch;
- canonical sorted tensor names, dtype, shape and contiguous CPU bytes;
- Gate binding or explicit null.

`execution_binding_sha256` includes:

- family ID;
- run ID and fit ID;
- candidate/model ID;
- seed, fold ID and purpose;
- execution-spec, budget and prerequisite-bundle hashes;
- reconciled lease event and authoritative-ledger-prefix hashes;
- training and validation date hashes;
- verified market-state binding or explicit null;
- semantic-state hash.

Version dispatch is exact:

| Schema | Allowed model | Required behavior |
|---|---|---|
| `qlib_peerlite_checkpoint_v1` | existing non-gated MSE only | preserve M6 loading and prediction |
| `qlib_peerlite_checkpoint_v2` | CCC or Gate only | require all semantic and execution fields |
| other/missing/mixed | none | reject before state load |

Cross-candidate, cross-seed, cross-fold, cross-purpose, cross-lease and
cross-market-state reuse is rejected. Timestamp and filesystem location are
excluded only from semantic state; they cannot replace execution identity.

### 5.9 Protected coverage policy

Implementation adds:

`/.engineering-quality/coverage-policy.json`

with profile `m7-core`:

```text
format = coveragepy-json
branch = true
source_roots = ["src/qlib_peerlite/m7"]
omit = []
command = [
  ".venv/bin/python", "-m", "pytest", "-q",
  "tests/test_m7_*.py",
  "--cov=src/qlib_peerlite/m7",
  "--cov-branch",
  "--cov-report=json:{raw_report}"
]
```

The controller inventories every authored `.py` file below the source root;
new files are automatically in the denominator. Line and branch must both be
exactly 100%. The policy, raw report and revision-specific receipt hashes are
bound by `quality_ledger.py capture-coverage`.

GitHub workflow `m7-quality-gate.yml` uses pinned actions/controller, Python
3.11 and locked dependencies, and exposes the exact required job name
`m7-external-quality-gate`. It runs ledger `check-ci`, Ruff, full pytest and
the protected coverage profile. CODEOWNERS already protects every workflow,
quality configuration and quality evidence path.

## 6. Success sequences

### Synthetic CCC

1. Build a frozen fixture spec.
2. Internally generate the paired synthetic dataset/capability.
3. Fit CCC through the public model boundary.
4. Save/reload v2 checkpoint.
5. Predict finite scores with the exact expected MultiIndex.
6. Repeat with the same seed/environment and prove selected epoch,
   semantic hash and score bits match.
7. Confirm zero authoritative ledger or final-OOS effects.

### Synthetic Gate

The same sequence uses internally generated daily state. It additionally
proves exact state binding, unique-date standardization, state corruption
rejection and future-poison invariance. The claim ceiling remains
`SYNTHETIC_MECHANICS_ONLY`.

### Empirical preflight rejection

Calling `validate_screening_prerequisites` against the current repository
observes planned cost/benchmark statuses and returns a contract error. A
model-call sentinel proves there was no dataset read, tensor, optimizer,
journal append, checkpoint or output effect.

## 7. Failure, concurrency and recovery

- Contract failures raise `M7ContractError(ValueError)`.
- Transition/recovery failures raise `M7StateError(ValueError)`.
- No retry, fallback, proxy, partial wrapper or partial checkpoint exists.
- A lease is immutable and bound to one exact fit.
- Authoritative append/reconcile stays under the existing file lock and
  fsync/atomic-write behavior.
- Two processes racing for the same semantic fit cannot both obtain different
  valid leases because the existing ledger rejects semantic duplicates.
- An interrupted counted start is retained and the run holds; it is never
  retried.
- Failed checkpoint save cannot expose a valid v2 marker.
- No function deletes or mutates prerequisite evidence.

## 8. Compatibility, rollout and rollback

Rollout order:

1. add protected coverage policy and M7 exceptions/digest primitives;
2. move CCC implementation behind compatibility re-export;
3. add generated synthetic dataset/capability;
4. add fixed prerequisite validator;
5. add empirical lease verification and pure sequencing/recovery;
6. add checkpoint v2 and thin PeerLite dispatch;
7. add Gate model path;
8. pass green tests, independent code review, synthetic black-box E2E and CI.

Rollback removes M7 package and v2 integration, restores unconditional Gate
denial, and leaves M6 v1 checkpoints/artifacts untouched. No data migration is
required.

## 9. Verification obligations

- CCC numeric, singleton, degenerate, gradient and non-finite update cases.
- Synthetic fixture bounds, deterministic generation, exact-type rejection,
  mutation isolation and claim ceiling.
- Gate schema/date/key/value/digest, no-fill, future-poison, corruption and
  unique-date standardization cases.
- All 17 prerequisite statuses parsed from canonical file contents; missing,
  planned, duplicate-key, noncanonical, symlink, path and binding failures.
- Lease rejection for unreconciled, mismatched, duplicate, over-cap and
  non-M7 events.
- Every legal/illegal state transition, interruption and recovery branch.
- Checkpoint semantic/execution metamorphic mutations and v1 compatibility.
- Score schema and deterministic replay.
- zero authoritative side effects in every synthetic and rejection path.
- exact 100% line and branch coverage for the complete M7 package.
- three black-box journeys from §6.

## 10. Ordered implementation steps

1. Record a refreshed test design and expected-red proof for all new contracts.
2. Add the protected coverage policy.
3. Implement M7 exceptions, digest utilities and CCC compatibility surface.
4. Implement generated synthetic fixture/capability.
5. Implement fixed prerequisite registry and strict parser.
6. Implement empirical lease verification and pure sequencing/recovery.
7. Implement checkpoint v2 identity and version dispatch.
8. Integrate exact CCC/Gate authority dispatch into PeerLite.
9. Complete unit, property, contract and integration tests.
10. Run protected coverage, full regressions, independent code review,
    black-box E2E and external CI.

Each step is independently reversible and must not perform a real fit or write
an authoritative trial event.

## 11. Open decisions

None inside this engineering change. Official fee evidence, benchmark source
certificate, frozen cost/benchmark specifications, complete PIT certification
and empirical start events remain external prerequisites. Their absence is an
intentional `NOT_RUN`, not an implementation default.

## Verdict

`PASS / READY FOR INDEPENDENT R3 DESIGN REVIEW`

This design authorizes engineering implementation only after independent
review `PASS`. It does not authorize real M7 training, candidate/fit budget
events, performance evaluation, combined CCC+Gate or final-OOS access.
