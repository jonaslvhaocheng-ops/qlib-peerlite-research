# M7 isolated increments — architecture confirmation

## Verdict

`PASS / CONFIRMATION`

The existing single-package, single-runner architecture can contain the two
M7 increments without a new service, package, database, deployment unit, or
public score schema.

## Current-state evidence

| Boundary | Current owner | Evidence |
| --- | --- | --- |
| PeerLite network, fitting, checkpoint and score generation | `src/qlib_peerlite/models/peerlite.py` | `PeerLiteNetwork`, `PeerLiteModel` |
| CCC mathematical primitive | `src/qlib_peerlite/models/losses.py` | `ConcordanceCorrelationLoss` |
| T-known state population and four-dimensional aggregation | `src/qlib_peerlite/data/market_state.py` | exact input allow-list, forbidden label/execution fields, daily hashes |
| Separate dataset state channel | `src/qlib_peerlite/data/dataset.py` | `col_set="market_state"` distinct from legacy `col_set="market"` |
| Trial identity and append-only budget lifecycle | `src/qlib_peerlite/governance/trial_ledger.py` | frozen M6 `6/44` close and V2 run intent |
| Composition roots | `scripts/server/**` | phase-specific authoritative runners and independent verifiers |
| Public output | data schema and prior M5/M6 runners | `(datetime, instrument) -> score`; prediction table adds `model_id`, `fold_id` |

## Architectural drivers

- Preserve the M6 K16 topology and O(NK) complexity.
- Make each increment removable and independently falsifiable.
- Prevent label, future execution status, or the legacy generic market channel
  from entering the Gate path.
- Keep the 2-candidate/16-fit budget and final-OOS seal outside model code.
- Reuse the M5/M6 checkpoint, Recorder, replay, and prediction contracts.

## Confirmed target boundaries

```text
M7 frozen execution authority
        |
        v
phase-specific server runner
        |
        +--> CCC candidate
        |      PeerLite K16 MSE topology
        |      + ConcordanceCorrelationLoss only
        |
        +--> Gate candidate
               PIT-qualified MarketStateProduct
               -> exact market_state adapter
               -> PeerLite K16 MSE + 4D gate
        |
        v
unchanged score/checkpoint/Recorder contracts
```

### Dependency rules

1. `models` may depend on tensor/math utilities, but not on database, PIT
   evidence paths, trial ledgers, or final-OOS data.
2. `data.market_state` remains pure, label-free, and Qlib-independent.
3. The future M7 state adapter may depend on `data.market_state` and the
   dataset protocol; it must request only `col_set="market_state"`. It may
   never alias or fall back to `col_set="market"`.
4. M7 governance validates exact candidate IDs, M6 close, M6.5 external PASS,
   authority, budget, folds, seed, and state-product identity before the
   runner constructs a model.
5. The server runner is the composition root. It may call governance, data,
   and model modules; none of those modules may import the runner.
6. CCC and Gate share only the frozen M6 K16 base parameters and output
   contract. They may not share a combined configuration or result-based
   selection path.

## Public contracts and data ownership

- Model output remains a `score` Series keyed by
  `(datetime, instrument)`.
- Prediction files retain
  `datetime,instrument,score,model_id,fold_id`.
- `MarketStateProduct` owns exactly four state values per date:
  `mkt_trend_20`, `mkt_vol_20`, `mkt_breadth_1d`,
  `mkt_turnover_20`, plus integrity metadata outside the tensor.
- Training-fold preprocessors remain train-only. The Gate state
  standardizer must fit on the current fold's training dates only.
- Trial and fit counting remains owned by the append-only governance layer,
  not by `PeerLiteModel`.

## Existing gap to close in bounded design

`PeerLiteModel._market_frame()` currently requests the legacy
`col_set="market"` even though the repaired dataset exposes a distinct
`market_state` channel. This is a local interface defect, not a reason for a
new architecture. The implementation design must replace this implicit
generic-channel access with an M7-specific, exact state adapter and must add a
negative test proving that legacy market columns cannot satisfy Gate input.

The generic config/CLI also expose `loss="ccc"` and `market_gate=true`.
Authoritative M7 execution must therefore be allowed only by the M7 server
composition root after governance validation; the synthetic CLI cannot issue
an empirical M7 claim or budget event.

## Enforcement

- Unit/property tests for CCC formula, degeneracy, gradients, and
  cross-section isolation.
- State schema, future-poison, exact-date join, legacy-channel rejection, and
  train-only scaling tests.
- Candidate allow-list and forbidden-combination tests.
- Existing permutation, mask, parameter-budget, checkpoint, deterministic
  replay, prediction-schema, and final-OOS boundary tests.
- Ruff, complete pytest, independent design/code review, E2E, and protected
  GitHub CI.

## Evolution and rollback

- Add the M7 governance/spec and exact state adapter without changing M6
  immutable artifacts.
- Implement CCC and Gate as two separately registered paths.
- Run synthetic expected-red/green evidence before creating any execution
  authority.
- A failed candidate is retained as `HOLD`; its module/config can be removed
  without migrating M6 checkpoints or score consumers.
- No compatibility bridge from legacy `market` to `market_state` is allowed.

## Decisions

- Reuse the existing monorepo and process boundary.
- Do not add Transformer, SAM, multitask learning, text, LLM, minute, tick, or
  L2 modules.
- Do not combine CCC and Gate in M7.
- Do not treat historical M7 v1–v20 design documents as execution authority.

## Implementation-boundary refresh

Source digest reviewed:
`sha256:2585f87b0985b0f1fa90417c2f99b2f07187949f4dd4cc5873b8a6033b5459d7`.

The first implementation slice makes the already-approved boundary explicit:

- `models/losses.py` remains the sole CCC numerical-policy owner.
- `models/peerlite.py` no longer reads the legacy `market` channel for a Gate.
- `data/verified_market_state.py` is an in-process fail-closed type boundary,
  not a new service, data store, runtime, or public empirical authority.

The abstract type deliberately cannot manufacture verified data. A concrete
factory remains subject to the reviewed product/manifest/PIT contract and
cannot be used for an empirical fit while the prerequisite bundle is absent.
This preserves the existing model/data/governance layering and prevents a
plain Qlib-like dataset from self-asserting provenance.

## Complete step-eight engineering architecture

The user-authorized completion scope is bound by
`contracts/changes/m7_complete_engineering_cr_v1.json`. The earlier abstract
type seam remains rejected and is not restored.

### Target package

All new M7-owned policy lives under one cohesive package:

```text
src/qlib_peerlite/m7/
    ccc.py                  # numerical contract and metadata
    market_state.py         # immutable binding and controlled dataset factory
    prerequisites.py        # zero-event screening prerequisite validation
    run_state.py            # pure legal transitions and recovery decisions
    checkpoint.py           # canonical semantic payload/hash helpers
```

`PeerLiteModel` remains the Qlib model adapter. It may import public M7
contracts, but the M7 package never imports the model adapter, runner, trial
ledger, database or final-OOS paths. A future server composition root is the
only layer allowed to combine verified authority, a verified dataset and a
model.

### Ownership and dependency direction

```text
data.market_state ────────┐
data.dataset ─────────────┼──> m7.market_state
governance artifact types ┼──> m7.prerequisites / m7.run_state
models.peerlite ──────────┴──> m7 public contracts

m7 -X-> database / server runner / trial-ledger writer / final OOS
```

The M7 run state machine returns immutable decisions/events but does not write
the authoritative trial ledger. The existing governance layer remains the
sole persistence owner.

### Public contracts

- `VerifiedMarketStateBinding`: frozen identities and final broadcast-value
  digests.
- `VerifiedMarketStateDataset`: defensive-copy Qlib dataset wrapper created
  only by the controlled factory.
- `M7ScreeningPrerequisiteBundleV1`: immutable zero-event validation result.
- `M7RunState`: pure authorization/count/terminal state with exact legal
  transitions.
- checkpoint semantic payload/hash: excludes path/timestamp/fit ID and
  includes material model, scaler, objective and Gate binding state.
- model output remains the existing score Series keyed by
  `(datetime, instrument)`.

### Coverage and enforcement

The protected v0.3 coverage profile owns the complete
`src/qlib_peerlite/m7` directory and requires 100% line and branch coverage.
PeerLite integration paths are additionally exercised by contract tests,
complete repository tests and synthetic E2E. The profile cannot narrow below
the complete M7 package.

### Migration sequence

1. Establish the M7 package and protected coverage policy.
2. Move/re-export the CCC contract without changing its public import.
3. Implement the concrete verified-state wrapper and enable Gate only for it.
4. Implement prerequisite and run-state contracts with no persistent effects.
5. Add checkpoint semantic binding and exact synthetic replay.
6. Remove the temporary unconditional Gate denial.

Every intermediate state fails closed. M6 remains runnable and byte-compatible;
M7 empirical status remains `NOT_RUN`.
