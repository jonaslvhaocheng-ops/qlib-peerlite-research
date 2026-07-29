# M7 first-tranche independent R3 design review

- Reviewed design SHA256:
  `311a5c222c7cedc3c0b17d29f4ee993f02fcbcf3bb0da18818f75085d7714163`
- Architecture SHA256:
  `d52857d30f9bbfa33a1808c13f76ff1a91aa36494441f1f1c48f87a1d63ba950`
- Ledger revision: `19`
- Author context: `/root`
- Reviewer context: `/root/m65_v25_design_review`
- Mode: independent, read-only

## [P2] Abstract marker cannot enforce the claimed verified Gate boundary

**Section:** `change_design_v2.md` §7 / implementation-boundary refresh

**Scenario:** a caller can subclass `VerifiedMarketStateDataset`, implement a
no-op `verify_integrity()`, and return arbitrary four-column data from
`prepare()`. That object passes the current `isinstance` check and reaches a
gated `fit()`.

**Impact:** the ABC is a self-asserted marker, not a value/provenance integrity
boundary. It contradicts the claim that gated fitting remains impossible and
provides no immutable binding for checkpoint verification.

**Direction:** before the concrete controlled factory exists, reject every
gated `fit/predict` unconditionally. Alternatively, implement the concrete
factory and immutable binding now. A no-op subclass and missing binding must
fail before tensor access.

## [P2] CCC trainer does not yet reject non-finite gradients

**Section:** CCC numerical contract / §7 tranche boundary

**Scenario:** `objective.backward()` can produce NaN/Inf gradients;
`clip_grad_norm_` lacks `error_if_nonfinite=True`, after which
`optimizer.step()` still runs.

**Impact:** this violates the v2 requirement that any non-finite gradient
fails the fit and may contaminate parameters. Section 7 also does not clearly
assign this remaining trainer-level obligation to a later tranche.

**Direction:** either add the gradient-finite guard in this tranche or state
explicitly that only the primitive CCC dtype/reducer/input-finite subset is
closed and retain the guard for the next tranche. Test that the optimizer does
not execute after an injected non-finite gradient.

## Confirmed

- No frozen prerequisite bundle, M7 execution spec, authoritative runner or
  state machine exists; formal empirical training and budget consumption
  remain unauthorized.
- Cost and benchmark specifications remain unfrozen.
- The CCC primitive formula now matches the float32-input, float64-reducer,
  population-statistic, singleton-MSE and finite-input contract.
- Validation MSE and `best - 1e-10` early stopping remain aligned.
- Concrete factory, checkpoint binding, prerequisite validator and state
  machine remain future tranches.
- Final OOS was not accessed and no real training was run.

## Verdict

`NEEDS_CHANGES`

```text
P0=0 / P1=0 / P2=2 / P3=0
reason_code=M7_FIRST_TRANCHE_FAIL_CLOSED_CONTRACT_INCOMPLETE
issue_type=contract
earliest_repair_stage=change-design
```
