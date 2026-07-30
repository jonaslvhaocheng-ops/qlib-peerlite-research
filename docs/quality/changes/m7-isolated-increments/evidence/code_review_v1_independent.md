# M7 complete engineering implementation — independent R3 code review

- Source digest:
  `sha256:e84ef9727bf2054849f05f3c5551d108c5c9fe1d1dba918d3578fd6393d3ff9f`
- Base:
  `deed0a6314a90099f4b9c0c258a89e36f7c95423`
- Author context: `/root`
- Reviewer context: `/root/m65_v24_adversarial_review`
- Mode: independent, read-only

## Findings

### [P0] Remove the caller-forgeable empirical fit authorization

The prerequisite validator accepts a caller-selected root containing minimal
self-declared PASS files. The lease verifier accepts caller-selected
journal/ledger paths and does not bind the frozen M6 `6/44` prefix or exact
execution/budget/state authorities. `PeerLiteModel` then accepts that lease
with any ordinary `PanelDataset` for CCC. This violates the CR prohibition on
empirical execution.

Direction: no empirical lease may authorize model fit in this change. Keep
empirical preflight fail-closed and `NOT_RUN` until a future, separately
reviewed authority CR exists.

### [P1] Enforce the frozen candidate configurations

Candidate classification uses only `model_id`. A CCC ID can be configured with
MSE/K32 and a Gate ID with the gate disabled.

Direction: validate the complete fixed candidate tuple at construction and
again at fit/load.

### [P1] Replace caller digest recovery with verified persisted evidence

Run transitions and recovery accept arbitrary 64-character strings and treat
any terminal digest as success.

Direction: recovery receipts must be derived by reading and matching journal,
ledger and terminal evidence. No raw digest parameters may advance state.

### [P1] Enforce checkpoint version and expected execution identity

External contexts use constant hashes; checkpoint validation checks only
self-consistency; v1/v2 model dispatch is not exact and state is loaded before
v2 validation.

Direction: v1 is base MSE only; v2 is the two exact synthetic candidates only.
Validate metadata and expected candidate configuration before state load.

### [P1] Do not claim a missing empirical Gate binding

No verified empirical Gate dataset exists and every empirical Gate lease is
rejected.

Direction: label the empirical Gate path `NOT_RUN / NOT IMPLEMENTED UNDER
CURRENT AUTHORITY`; do not represent it as completed engineering authority.

### [P1] Add the deployable protected M7 workflow

The local controller wrapper falls back to a workstation path and the promised
`m7-external-quality-gate` workflow is absent.

Direction: add the pinned GitHub workflow and make CI use its checked-out
controller; local fallback cannot count as external evidence.

### [P2] Complete the frozen behavior journeys

Missing evidence includes future-poison, persisted recovery, cross-context
checkpoint rejection and clean-process E1/E2/E3 zero-effect journeys. Changed
PeerLite authorization branches are outside protected coverage.

Direction: add these tests and include the changed PeerLite adapter in the
protected authored denominator.

### [P2] Separate pre-existing M6.5 archival changes from M7 scope

The worktree also contains the M6.5 external-pass archival replacement.

Direction: preserve it as a separate baseline commit/change; do not include it
in the M7 review diff.

## Verdict

`NEEDS_CHANGES`

```text
reason_code=M7_EMPIRICAL_AUTHORITY_BYPASS_AND_CONTRACT_GAPS
issue_type=contract
next_route=change-design
```

