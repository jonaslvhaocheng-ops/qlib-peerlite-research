# Architecture Confirmation V30 — RunIntent Red-Test Delta

- Mode: `confirmation`
- Parent architecture: `architecture_confirmation_v29.md`
- Risk: `R3`
- Verdict: `PASS`

## Changed surface since v29

Only the expected-red test portfolio changed: a synthetic test now demonstrates that caller mutation of nested
V2 authority dictionaries changes the current `RunIntent` identity. No production module, dependency,
configuration, runtime, data owner, process, service or deployment boundary changed in this delta.

## Boundary confirmation

- The defect and planned repair remain owned by `governance.trial_ledger.RunIntent`.
- The test ends at the pure class seam; it performs no filesystem, journal, ledger, replay, fit, PIT, data,
  budget or OOS action.
- V50 preserves the trusted single-process/operator architecture and historical non-M7 V1 compatibility.
- The M7 caller, journal event V3 and full authority schema remain explicitly deferred to their existing v48
  workstreams.
- No new abstraction is justified beyond the local V2 normalizer/freezer and identity cache approved in v50.

## Evidence-lifecycle note

Architecture evidence binds the stable design and review artifacts, not mutable implementation/test files that
are expected to change during the routed implementation cycle. Source and test exactness remain owned by the
later source-bound implementation, tests-green and code-review stages.

## Decision

The v28/v29 architecture remains sufficient. Continue the existing quality route for the v50 class-only repair;
do not enter replay, fit, PIT, real data, CCC, Gate, budget mutation or final OOS.
