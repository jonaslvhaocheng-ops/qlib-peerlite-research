# M7 isolated increments — contract closure v2

- Status: `IMPLEMENTATION-READY DESIGN / NOT EXECUTION AUTHORITY`
- Base design:
  `change_design.md`
- Base SHA256:
  `15d30f9fb46f1cec6099cf7fedf72d44cbff18ac7d2d5cc29122e12e5aceed2d`
- Review repaired:
  `design_review_v1_independent.md`
- Review SHA256:
  `a8227bec49d4038175a7fe0dd6295dff4083ed1dac6848c15b1d77bf22eca4c4`
- This document plus the hash-bound base is the complete v2 design bundle.
- All base sections not replaced below remain unchanged.

## 1. Screening prerequisite bundle

Before the first candidate-start or fit-start event, the authoritative M7
validator must accept one immutable `M7ScreeningPrerequisiteBundleV1`.

Required bindings:

| Binding | Required terminal state |
| --- | --- |
| effective broker/exchange/statutory fee receipt | `PASS`, with effective dates covering every development test date |
| `cost_spec` | `FROZEN`, exact commission, statutory fees, 10bp base and 20bp stress slippage |
| benchmark source certificate | `PASS`, PIT history and total-return/replication semantics fixed |
| `benchmark_spec` | `FROZEN` |
| exchange calendar and weekly rebalance mapper | immutable file and content hashes |
| score-to-position rule | top 10%, equal weight, 2% name cap |
| execution and unfilled-order rule | T+1 open; retain old position when unavailable |
| ADV/capacity rule | participation at most 5% of ADV20 |
| cost, portfolio, benchmark and IR implementations | exact code hashes |
| M6 K16 predictions/checkpoints/metrics | independently verified immutable hashes |
| M6 K16 reference holdings, trades, costs and weekly return products | independently generated and verified under the same bundle |
| input development dates/folds | exact seven-fold calendar hashes |
| final-OOS seal | `PASS`, 2025+ remains unopened |

The bundle contains file SHA256 plus content SHA256 where supported and a
canonical bundle hash. It must bind all formula versions and units:

- turnover = sum of absolute position-weight changes;
- base/stress costs are per side and include the frozen official fees;
- weekly net excess uses candidate net return minus the identically aligned
  frozen benchmark return;
- IR = mean(weekly excess) / sample std with `ddof=1` × `sqrt(52)`;
- cumulative net excess uses the compounded wealth-ratio definition frozen in
  the bundle.

Current `cost_spec.json` and `benchmark_spec.json` are still planned. Therefore:

```text
implementation and synthetic tests: allowed after quality gates
state-source/cost/benchmark evidence collection: read-only allowed
derived M7 execution spec: BLOCKED
candidate/fit event: BLOCKED
empirical model fit: BLOCKED
```

No default, proxy, “temporary” fee, price-index substitution, or post-result
freeze is allowed. The bundle must be frozen before the M7 execution spec and
cannot reference an M7 result.

## 2. Authorization and consumed-budget state machine

The term `authorization roster` replaces “atomic budget reservation.”
Authorization does not itself consume budget.

### Entities and states

```text
Run:
  AUTHORIZED -> STARTED -> TERMINAL_COMPLETE
                        -> TERMINAL_HOLD

Candidate:
  NOT_STARTED -> STARTED -> TERMINAL_SCREEN_PASS
                        -> TERMINAL_HOLD

Fit:
  NOT_STARTED -> STARTED -> TERMINAL_SUCCESS
                        -> TERMINAL_FAILED
                        -> TERMINAL_INTERRUPTED
```

`NOT_STARTED` is a report state, not a durable counted ledger event.

### Counting rules

- Durable `CANDIDATE_EVALUATION_STARTED` is appended and reconciled before any
  candidate-specific data load or fit. It consumes one candidate evaluation.
- Durable `MODEL_FIT_STARTED` is appended and reconciled before
  `PeerLiteModel.fit`. It consumes one fit.
- Terminal events never change counts.
- An authorized but unstarted roster slot consumes zero.
- Failed and interrupted started entities keep their consumed counts forever.
- Counts may be below 8/60 after a stopped run; they may never exceed them.

### Exact legal sequence

1. Validate every prerequisite with zero events.
2. Start CCC candidate.
3. For folds `wf_2018` … `wf_2024`, then the `wf_2018` refit:
   start one fit, reach a terminal fit state, then proceed.
4. Issue CCC terminal candidate state.
5. Only if all CCC fits reached `TERMINAL_SUCCESS`, start Gate candidate.
6. Execute the same ordered eight-fit sequence for Gate.
7. Issue Gate terminal candidate state and run terminal state.

### Failure and recovery

- CCC fit failure/interruption:
  - CCC candidate → `TERMINAL_HOLD`;
  - Gate remains report-only `NOT_STARTED_DEPENDENCY_STOP`;
  - run → `TERMINAL_HOLD`;
  - no Gate decision is issued and Gate consumes zero;
  - this run can never resume Gate.
- CCC completes but screens `HOLD` for performance:
  - Gate still runs, because the two increments are independent and Gate does
    not depend on CCC performance.
- Gate fit failure/interruption:
  - Gate → `TERMINAL_HOLD`;
  - run → `TERMINAL_HOLD`.
- An exact rerun of a terminal run verifies receipts and returns byte-stable
  no-op.
- A crash after a start event but before its terminal event is reconciled as
  `TERMINAL_INTERRUPTED` and then candidate/run `TERMINAL_HOLD`; the fit is
  never retried.
- A crash before a durable start event consumes nothing; recovery may continue
  only after proving no fit call occurred.
- Ambiguous duplicate IDs, incompatible journal suffixes, or multiple recovery
  candidates fail closed and require read-only reconciliation. No automatic
  slot release or replacement exists.

`SCREEN_PASS` and `HOLD` remain the only candidate decisions. Gate's
`NOT_STARTED_DEPENDENCY_STOP` is an execution report state, not a candidate
decision. Any future attempt to run the skipped Gate requires a new CR and new
budget authority; v2 authorizes no replacement.

## 3. Verified market-state value/provenance binding

Add an immutable `VerifiedMarketStateBinding` and a controlled
`VerifiedMarketStateDataset` factory. Callers cannot separately supply state
values and provenance strings.

### Factory inputs

- validated daily `MarketStateProduct`;
- its manifest;
- fixed PIT audit PASS receipt;
- future-poison behavior PASS receipt;
- exact Qlib base dataset and seven-fold date contract;
- expected hashes from the frozen execution spec.

### Factory procedure

1. Rehash and validate the product, manifest and both PIT receipts.
2. Validate exact state columns/order, one row per date, finite values,
   population count/keyset hash and per-date state hash.
3. Exact-date broadcast onto the base dataset index; no shift, fill or
   fallback.
4. Recompute from the final broadcast values:
   - ordered unique-date digest;
   - `(datetime,instrument)` key digest;
   - four-column schema/order digest;
   - canonical float32 value-bit digest;
   - combined logical digest.
5. Copy the broadcast values into private owned storage and make public reads
   return copies.
6. Create the immutable binding containing product/PIT identities plus all
   recomputed final-dataset digests.

### Consumption

- `VerifiedMarketStateDataset.prepare(..., col_set="market_state")` is the only
  authoritative Gate state interface.
- The Gate model requires this exact wrapper type and reads its immutable
  binding; legacy `market`, raw frames and caller-provided hash strings fail.
- Immediately before each fit and prediction, the wrapper recomputes its
  logical digest and compares it with the binding.
- Checkpoint metadata receives the binding from the wrapper used in the fit,
  not from model parameters.
- Reload/predict requires an equivalent verified wrapper and checks every
  digest before reading values.
- The independent verifier reconstructs the wrapper from the frozen product
  and proves the checkpoint binding and prediction input digest match.

This is an in-process immutable evidence boundary, not a new service.

## 4. CCC numerical, validation and checkpoint contract

Version: `qlib_peerlite_ccc_numerical_contract_v1`.

### Training objective

- Network prediction and target enter as finite float32 tensors.
- For each valid date cross-section, prediction and target are cast to
  float64 before every reducer.
- Means are arithmetic means in float64.
- Variance and covariance use population denominators (`correction=0`).
- Epsilon is float64 `1e-8`.
- A cross-section with fewer than two valid rows uses float64 mean MSE.
- CCC loss is a scalar float64 tensor; autograd propagates to float32
  parameters.
- A padded multi-date batch computes each date separately, stacks float64
  losses in date-batch order, then takes one float64 arithmetic mean.
- Any non-finite input, intermediate, loss or gradient fails the fit.

### Validation and early stopping

- Validation monitor remains M6-compatible MSE, not CCC.
- Per-date validation MSE is computed from finite float32 prediction/target
  with PyTorch mean reduction; the Python monitor is the arithmetic mean of
  per-date values in ascending date order.
- First finite epoch becomes best.
- Later epoch replaces best only when:

```text
valid_mse < best_valid_mse - 1e-10
```

- Equality and values within `1e-10` keep the earliest epoch.
- Patience remains 12 and all other M6 optimizer/batching/seed semantics remain
  unchanged.

### Checkpoint binding

Every M7 checkpoint records:

- `training_objective`: `CCC` or `MSE`;
- `training_objective_contract_version`;
- calculation/input/return dtypes, correction, epsilon and singleton rule;
- `validation_metric=MSE`;
- early-stop delta `1e-10`, patience and selected epoch;
- training/validation date digests;
- model config, standardizers and model-state hash;
- state binding or explicit `null` for CCC;
- execution spec, budget and prerequisite bundle hashes.

The `wf_2018` refit must reproduce selected epoch, checkpoint semantic state
hash, index and every score bit in the same frozen server environment.
Container-file byte equality is not required.

## 5. Updated implementation ordering

1. Freeze no empirical authority yet.
2. Test and implement the four contract surfaces:
   screening-bundle validator, state machine, verified state wrapper, CCC
   numerical metadata.
3. Run complete local quality stages and protected CI.
4. Obtain current official fee and benchmark evidence; build and independently
   verify the M6 reference portfolio products.
5. Build the real state product and pass fixed plus behavior PIT audits.
6. Freeze the prerequisite bundle.
7. Freeze the derived M7 execution spec and one-shot run intent.
8. Execute the exact state machine and independently verify.

Failure in steps 4–6 leaves M7 empirical status `NOT_RUN`; it does not trigger
proxy substitution.

## 6. Closure of v1 review findings

| Finding | Closure |
| --- | --- |
| P1 unfrozen cost/benchmark | §1 makes a complete frozen bundle a zero-event prerequisite |
| P1 ambiguous budget/recovery | §2 separates roster authorization from counted starts and fixes every stop/recovery state |
| P2 separable Gate data/provenance | §3 creates one verified wrapper and recomputes actual consumed-value digests |
| P2 incomplete CCC semantics | §4 freezes dtypes, reducers, monitor, early stop and checkpoint metadata |

## Verdict

`PASS FOR FRESH INDEPENDENT R3 DESIGN REVIEW / M7 NOT AUTHORIZED`

## 7. First implementation tranche — repaired fail-closed boundary

This tranche closes only the following current-code contracts:

1. CCC primitive: float32 finite inputs, float64 population reducers,
   epsilon `1e-8`, singleton float64 MSE and finite scalar result.
2. CCC trainer: after `backward()` and before any optimizer update, gradient
   clipping must use `error_if_nonfinite=True`. A non-finite total gradient
   norm raises and `optimizer.step()` is not called.
3. Gate denial: until the concrete controlled factory and immutable binding in
   §3 are implemented and reviewed, every gated `fit()` and `predict()` fails
   before state data, feature tensors, optimizer or checkpoint state are read.
   There is no marker class, subclass seam, provenance-string parameter,
   legacy `market` fallback or partially trusted wrapper.

The current `data/verified_market_state.py` abstract marker is rejected by
independent review and must be deleted in this tranche. `PeerLiteModel` may
retain the network-level Gate implementation for synthetic tensor unit tests,
but its dataset-level `_market_frame()` must unconditionally reject with an
explicit “verified market_state factory is not available” error whenever
`market_gate_enabled` is true.

Required current tests:

- the existing CCC float64 and non-finite-input expected-red cases turn green;
- a monkeypatched non-finite gradient norm proves the optimizer update callback
  remains uncalled;
- a plain dataset and an object attempting to self-assert verified methods both
  fail at the same Gate boundary before `prepare()` is invoked;
- non-gated M6 fit, checkpoint reload and prediction remain byte-stable.

The concrete factory, immutable binding, Gate checkpoint binding, screening
prerequisite validator and run state machine remain required by §§1–5 and
require separate current expected-red evidence before implementation. This
tranche therefore makes formal Gate fitting impossible; it does not claim the
Gate candidate is engineering-complete.

The implementation-boundary refresh in `architecture_confirmation.md` that
described an abstract verified-state type seam is superseded by this section.
The rest of the architecture decision remains unchanged.
