# M7 CCC / Market-State Gate isolated increments

- Status: `IMPLEMENTATION-READY DESIGN / NOT EXECUTION AUTHORITY`
- Owner: M7 isolated-increments change
- Risk: `R3`
- Base: M6 K16 MSE, M6 close `6/44`, M6.5 external `PASS`

## Problem and scope

### Current behavior

The repository already contains a CCC loss primitive and a small state gate,
but they have never been authorized or empirically run. The gate-enabled model
currently asks a dataset for the legacy generic `col_set="market"`; the repaired
dataset and PIT-safe state builder instead expose a distinct
`col_set="market_state"`. Directly enabling the current flags would therefore
violate the repaired data boundary.

### Desired behavior

Implement exactly two isolated M7 candidates:

1. `PEERLITE_K16_CCC`: identical to M6 K16 except for per-date CCC loss.
2. `PEERLITE_K16_MSE_GATE`: identical to M6 K16 MSE except for the frozen
   four-dimensional, PIT-qualified daily state gate.

Both retain the unified score interface, seven rolling folds, seed 7, one exact
`wf_2018` deterministic refit, and the M6 checkpoint/Recorder conventions.

### Non-goals

- no CCC+Gate candidate;
- no K32, extra seed, replacement fit, hyperparameter search, Transformer,
  SAM, multitask, text, LLM, minute, tick, or L2 work;
- no final-OOS access;
- no promotion, Alpha, investability, or production claim;
- no new service, database, package, or orchestration framework.

### Frozen constraints

- Starting ledger: 6 candidate evaluations / 44 fits.
- M7 ceiling: 8 candidate evaluations / 60 fits.
- Exact candidate order: CCC, then Gate.
- Each candidate: seven fold fits plus one `wf_2018` refit.
- Any started fit counts. No replacement.
- Final decisions: `SCREEN_PASS` or `HOLD`.

## Repository evidence and current flow

```text
Qlib/PanelDataset
  -> PeerLiteModel.fit
  -> train-fold standardizer
  -> date cross-section batches
  -> PeerLiteNetwork
  -> loss
  -> checkpoint + score
```

Relevant existing surfaces:

- `models/losses.py`: Lin CCC implementation with singleton MSE fallback.
- `models/peerlite.py`: M6-compatible model, state gate, fitting, checkpoint.
- `data/market_state.py`: exact input allow-list, T-known population, 4D daily
  state and integrity hashes.
- `data/dataset.py`: separate legacy `market` and repaired `market_state`
  channels.
- `governance/trial_ledger.py`: append-only run intent and budget identity.
- M5/M6 server runners and verifiers: fold loop, deterministic refit, Recorder,
  prediction and receipt patterns.

## Options

### Option A — bounded in-place extension with a phase-specific runner

Keep one `PeerLiteModel`, make the state channel exact and fail-closed, add an
M7 spec validator plus M7 runner/verifier, and reuse M6 artifact patterns.

- Correctness: isolates the two actual deltas.
- Complexity: smallest change; no duplicated trainer.
- Compatibility: M6 non-gated checkpoints remain loadable.
- Testability: loss and state paths can be tested independently.
- Reversibility: M7 files and gated branch can be removed without migrating M6.

### Option B — two new model subclasses with copied training loops

Create `PeerLiteCCCModel` and `PeerLiteGateModel`.

- Advantage: explicit class names.
- Cost: duplicates early stopping, batching, checkpoint, replay, and future bug
  fixes; makes “only one delta” harder to prove.

### Option C — reproduce the historical multi-process syscall sandbox design

Use the v1–v20 supervisor/worker/FD protocol before the first M7 fit.

- Advantage: stronger hostile-process containment.
- Cost: adds a runtime and large operational surface unrelated to the
  scientific question; it does not improve PIT qualification or model
  comparison evidence.

### Decision

Choose Option A. Option B weakens experimental isolation through duplicate
code. Option C is disproportionate for a single-user research server and would
delay the next falsifiable artifact.

## Proposed design

### 1. Loss behavior

`ConcordanceCorrelationLoss` remains the only CCC primitive:

```text
ccc = 2*cov(p,y) /
      (var(p)+var(y)+(mean(p)-mean(y))^2+1e-8)
loss = 1-ccc
```

- Compute one loss per valid date cross-section.
- Fewer than two valid stocks falls back to MSE.
- Reject non-finite prediction, target, or resulting loss.
- Preserve the M6 date-batch construction, seed, shuffling, optimizer,
  learning rate, early stopping, and validation MSE. Only the training
  objective changes.
- The objective for a padded batch is the mean of its per-date losses, exactly
  as the current `_batched_objective` contract.

This avoids the historical design's one-date-per-optimizer-step change, which
would confound the loss comparison.

### 2. Gate data boundary

The authoritative gate path must:

1. request only `col_set="market_state"`;
2. require the exact ordered columns:
   `mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20`;
3. require one finite, bit-identical row for every stock on a date;
4. require exact coverage of all train/valid/test dates;
5. fit market mean/std on unique training dates only, with `ddof=0` and
   zero-scale replacement by 1;
6. transform valid/test without refit, fill, shift, or fallback;
7. preserve the MarketStateProduct date/key/state hashes in the execution
   manifest and checkpoint metadata.

Legacy `market` columns, missing dates, extra state columns, alternate order,
duplicates, non-finite values, or inconsistent same-date rows fail before a
fit event.

### 3. Gate network

The Gate candidate freezes:

```text
4 -> Linear(64) -> GELU -> Linear(64) -> Sigmoid -> multiply by 2
```

The gate multiplies the encoded stock state after the MLP encoder and before
peer assignment. K=16, hidden=64, heads=4, dropout=0.1 and all other M6
parameters remain unchanged. Complexity remains O(NK); parameter count stays
below 500,000.

### 4. Governance and execution specification

Add an M7 spec validator that binds:

- M6 execution spec, M6 gate, M6 close prefix `6/44`;
- M6.5 external PASS run/head/merge commit;
- research contract, M3 product/gate and seven folds;
- candidate/model registries;
- budget binding v2 and exact 2/16 roster;
- M6 K16 reference predictions and metrics;
- MarketStateProduct manifest plus PIT fixed/behavior receipts for Gate;
- code and environment hashes;
- final-OOS seal;
- frozen weekly portfolio/cost/benchmark mapping used only for screen
  comparison.

The derived immutable execution spec is created only after implementation,
tests, independent reviews, state-product PIT qualification, and protected CI
pass. Until then, model construction tests are synthetic and create no journal
event.

The authoritative server runner accepts only the frozen spec and an
M7-specific V2 `RunIntent`. It validates all bindings before the first
candidate event. Event and fit identities must exactly match
`m7_initial_screen_budget_binding_v2.json`.

### 5. Success sequence

1. Verify M6/M6.5, contract, product, code, environment, OOS seal and ledger
   prefix.
2. Verify the complete state product and its two PIT receipts before the Gate
   candidate is eligible.
3. Atomically reserve the exact 2/16 roster.
4. Run CCC seven folds, exact checkpoint reloads, and `wf_2018` refit.
5. Run Gate seven folds, exact checkpoint reloads, and `wf_2018` refit.
6. Independently verify hashes, prediction schema, Recorder readback,
   deterministic refits, budget counts, and absence of final-OOS access.
7. Compare each candidate separately with the frozen M6 K16 reference.

### 6. Screen decision

For each candidate independently, using the frozen weekly mapper, benchmark,
and cost rules on pre-final-OOS rolling test folds:

- combined cost-adjusted excess IR delta versus M6 K16 must be `> 0`;
- fold-level IR delta must be `> 0` in at least 5 of 7 folds;
- stress-cost cumulative net excess must be `>= 0`;
- all engineering, PIT, replay, budget, and output gates must pass.

If every condition holds: `SCREEN_PASS`. Otherwise: `HOLD`.

`SCREEN_PASS` does not authorize five-seed confirmation, CCC+Gate combination,
M8, or final OOS.

### 7. Failure and recovery

- Any invalid binding or state product: fail before journal reservation.
- Any started candidate/fit failure: retain the event, consume its budget slot,
  stop the run, emit `HOLD`; never replace it.
- Existing terminal event on exact rerun: verify and return no-op.
- Ambiguous/incomplete journal recovery: fail closed and require independent
  reconciliation; do not infer success from files.
- Partial output stays in the attempt namespace and cannot become a successful
  candidate receipt.

### 8. Interfaces and files

| Surface | Responsibility |
| --- | --- |
| `src/qlib_peerlite/models/losses.py` | finite CCC formula and singleton rule |
| `src/qlib_peerlite/models/peerlite.py` | exact `market_state` channel, 4D validation, unchanged M6 path |
| `src/qlib_peerlite/governance/m7_spec.py` | frozen spec and authority validation |
| `scripts/server/build_m7_market_state.py` | build hash-bound pre-OOS 4D product from qualified inputs |
| `scripts/server/run_m7_increments.py` | exact two-candidate execution |
| `scripts/server/verify_m7_increments.py` | independent outputs, replay, budget and boundary verification |
| `contracts/immutable/m7_*` | generated only after all pre-execution gates |

No new public package export is required. Existing non-gated M6 checkpoint
schema remains readable. Gated checkpoints must contain exact state column
order and train-only scaler payload; a gated checkpoint missing them fails.

### 9. Concurrency, security, privacy and resources

- One authoritative M7 run at a time under the existing append-only ledger
  lock.
- No network write, database mutation, order interface, credential material,
  PII, text, or LLM input.
- GPU execution only for empirical fits; local CPU synthetic tests only.
- Maximum empirical work is 16 fits; no retry can increase the ceiling.

### 10. Observability

Every run emits:

- run manifest and exact authority/spec hashes;
- per-fold receipt, checkpoint semantic hash, predictions and resource report;
- state product and PIT receipt hashes for Gate;
- trial-ledger before/after heads and counted events;
- Qlib Recorder identity/readback;
- per-candidate screen metrics and terminal decision;
- explicit `final_oos_market_partitions_opened=false`.

## Verification obligations

- CCC reference agreement, singleton, constant arrays, finite rejection,
  gradients, padding/date isolation, and “all else equals M6” configuration.
- Gate exact channel/column/order/date checks, legacy-channel rejection,
  future poison, same-date equality, train-only scaling, permutation
  equivariance, masks, checkpoint reload, and parameter/O(NK) bounds.
- Spec substitution, candidate combination, wrong seed/fold/fit ID, budget
  overflow, rerun/recovery, and final-OOS denial.
- Full synthetic end-to-end run with zero empirical budget effect.
- Independent verifier rejection for every material output/binding mutation.

## Ordered implementation plan

1. Add expected-red tests for CCC finite semantics and exact Gate state channel.
2. Repair `losses.py` and the gated `PeerLiteModel` path only.
3. Add M7 spec validator and synthetic fixtures for exact authority/budget
   denial.
4. Add state-product builder with manifest-only synthetic acceptance; run PIT
   audit before any empirical authority.
5. Add M7 runner and independent verifier by adapting the M6 fold/artifact
   loop without changing M6 files or immutable evidence.
6. Run full tests, Ruff, independent code review, E2E and protected external
   CI.
7. Freeze derived spec and execution authority only after every prerequisite
   is current PASS.
8. Execute exactly 2/16 on the server, independently verify, and issue two
   separate `SCREEN_PASS/HOLD` decisions.

## Open decisions

None. Any request to change candidates, seed, folds, state features, screen
thresholds, budget, or final-OOS boundary requires a new research-contract
change and cannot be decided during implementation.

## Verdict

`PASS FOR INDEPENDENT DESIGN REVIEW / M7 NOT YET AUTHORIZED`
