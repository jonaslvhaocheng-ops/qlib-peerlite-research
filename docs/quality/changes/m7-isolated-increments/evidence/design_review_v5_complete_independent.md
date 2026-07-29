# M7 complete engineering design — independent R3 review

- Reviewed design SHA256:
  `8524cf2289b0b6dea5773257ece8287810b66ccd01ac1ddfcf8afe9d069bf205`
- Architecture SHA256:
  `a65ec57e23fa2705351d3dcf77a8101317d89215cc78e0e970384f4784bd3b92`
- Change request SHA256:
  `9fa4ae01810de1d6f82ae0e7270239d6bab563511d098141ca226fd64ab19009`
- Ledger revision: `32`
- Author context: `/root`
- Reviewer context: `/root/m65_v45_adversarial_retry`
- Mode: independent, read-only

## Findings

### [P0] Empirical authority remains caller-forgeable

Section: `4.2 m7.market_state`, `4.6 PeerLite integration`

Scenario: a caller constructs a self-declared `PASS` audit receipt and matching
expectation/digests, then calls CCC or Gate `fit` with a real panel.

Impact: the proposed public factories validate self-consistency, not an
external authorization boundary. Real fitting can therefore bypass the change
request's explicit prohibition on empirical execution.

Evidence: the design accepts caller-provided receipt, expectation and hashes;
the model fit contract requires only the resulting context/wrapper and no
durably acknowledged fit authorization.

Direction: separate synthetic engineering execution from empirical execution.
Make the production M7 fit path require a fit lease derived from externally
anchored prerequisite evidence and an append-and-ack ledger transition.
Synthetic tests must use a synthetic-only dataset/lease path that cannot accept
an ordinary `PanelDataset` and cannot issue empirical events or claims.

### [P1] Prerequisite terminal status is caller-declared

Section: `4.3 m7.prerequisites`

Scenario: a `PLANNED` artifact is paired with caller metadata that says
`FROZEN` or `PASS`.

Impact: file hashes can match while the semantic prerequisite is still absent,
allowing an unauthorized empirical preflight.

Evidence: the proposed validator rehashes files but does not require terminal
status, semantic version and effective dates to be parsed from canonical
artifact content using fixed per-artifact locators.

Direction: freeze a repository-owned prerequisite registry. Parse each required
status and version from strict canonical content; do not accept those values as
caller fields.

### [P1] Run-state persistence and recovery are not enforceable

Section: `4.4 m7.run_state`

Scenario: a process crashes after a transition intent but before or after a
model call, then recovery receives a naked
`fit_call_proven_absent: bool`.

Impact: the system cannot distinguish a safely retryable intent from a
possibly-consumed fit, so exactly-once budget accounting is not proven.

Evidence: a pure transition is called durable without an append/ack boundary,
and recovery trusts a caller boolean rather than journal evidence.

Direction: distinguish pure event intent from durable acknowledgement. Issue a
fit lease only after an append-only journal append and readback. Recovery must
consume a verified recovery receipt derived from journal/model-call evidence,
never a naked boolean.

### [P1] Checkpoint identity is incomplete

Section: `4.5 m7.checkpoint`

Scenario: a checkpoint from a different candidate, seed, fold, purpose or
verified-state binding shares the listed execution-spec hashes.

Impact: a semantically wrong checkpoint can be accepted for another M7 fit.

Evidence: the context omits candidate/model identity, seed, fold, purpose,
fit-lease event and verified-state binding; the M6/v1 versus M7/v2 dispatch
rules are incomplete.

Direction: bind both semantic model state and execution identity. Include
family, candidate, model, seed, fold, purpose, config, prerequisite bundle,
fit-lease event and verified-state hashes, with an explicit version dispatch
table.

### [P2] Coverage policy is not mechanically frozen

Section: `9 Verification obligations`

Scenario: a green-test result selects a narrower test command or source
denominator.

Impact: the reported 100% can exclude new M7 source or branch paths.

Evidence: the design names a coverage goal but no exact protected policy path,
profile, branch mode, no-omit rule, automatic source inventory or CI identity.

Direction: freeze `.engineering-quality/coverage-policy.json` with one M7
profile, exact argv, `branch=true`, no exclusions, automatic inventory of the
whole `src/qlib_peerlite/m7` tree, immutable raw receipt and matching CI job.

## Finding counts

```text
P0=1 / P1=3 / P2=1 / P3=0
```

## Verdict

`NEEDS_CHANGES`

```text
reason_code=EMPIRICAL_AUTHORITY_AND_VERIFIED_EVIDENCE_NOT_ENFORCEABLE
issue_type=contract
next_route=change-design
```

The existing CCC primitive and unconditional Gate denial remain valid
first-tranche engineering evidence. This review does not authorize product
implementation, empirical training, candidate or fit-budget events, combined
CCC+Gate, or final-OOS access.

