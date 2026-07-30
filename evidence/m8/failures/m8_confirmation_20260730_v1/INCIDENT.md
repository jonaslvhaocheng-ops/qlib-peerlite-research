# M8 Confirmation Incident

The frozen M8 confirmation started on 2026-07-30. The runner wrote durable
local start events, but did not reconcile each start into the authoritative
append-only trial ledger before calling `model.fit`.

The run was stopped immediately after the defect was identified:

- seed 19 / `wf_2018`: completed with exact checkpoint replay;
- seed 19 / `wf_2019`: completed with exact checkpoint replay;
- seed 19 / `wf_2020`: started and interrupted;
- all later folds and seeds: not started;
- final OOS: not opened.

The retained journal was converted through a narrowly validated recovery path
into four canonical counted events: one candidate evaluation and three model
fit starts. The server-authoritative ledger now totals 9 candidate evaluations
and 64 fit starts.

The frozen rule `no_retry_after_started_fit=true` makes this confirmation
incomplete and non-retryable. M8 is therefore closed as
`HOLD_OPERATIONAL_CONFIRMATION_INCOMPLETE`. The two completed folds are
incident evidence only and must not be used to make a performance claim.
