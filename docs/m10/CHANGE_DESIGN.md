# M10 Shadow Production Change Design

## Problem and observable result

The research repository has reproducible model and evaluation mechanics but no
safe operational wrapper. M9 also proves that no model is authorized for
production. M10 must therefore supply production-quality orchestration controls
without creating a path that can trade or imply model promotion.

The observable result is a deterministic CLI cycle that accepts only a
synthetic, hash-bound score bundle; decides whether the configured schedule is
due; validates freshness and schema; records health; emits idempotent paper
intents; and publishes a terminal manifest. A rejection before trusted
transaction state exists returns a structured error with no mutation. A
failure after reservation publishes a halted cycle with a local alert and no
intent output.

## Scope

In scope:

- strict configuration and authorization preflight;
- Asia/Shanghai schedule decision;
- unified score artifact validation;
- freshness, integrity and model/track monitoring;
- immutable per-cycle local alerts;
- idempotent paper-intent sink;
- atomic cycle manifest and CLI;
- tests, coverage, runbook and CI.

Non-goals:

- training, scoring from market data or model selection;
- final-OOS access;
- live broker, network, credential or account integration;
- cron/daemon deployment;
- portfolio optimization, execution algorithms or real position state;
- a production or investment claim.

## Constraints and assumptions

- M9 remains immutable and has `production_authorized=false`.
- The current policy accepts only `track=SYNTHETIC` and
  `execution_mode=paper`.
- Prediction input follows the existing five-column score interface.
- A caller supplies an explicit clock to tests; the CLI uses a timezone-aware
  current time unless `--as-of` is supplied.
- Each due cycle consumes exactly one cross-section for one pinned calendar
  session. M10 does not claim general exchange-calendar correctness.
- Every output directory is new. Existing completed cycles are resolved only
  through the idempotency index.

## Alternatives

### A. External workflow engine plus broker sandbox

Airflow/Prefect and a broker SDK could provide scheduling and paper trading.
This adds services, network dependencies, credentials and retry semantics while
there is no promoted model. It makes the unsafe boundary larger and cannot
improve the current research conclusion. Rejected for M10.

### B. In-process fail-closed control plane

Pure policy functions plus an atomic local artifact sink keep the public
contract small and fully testable. An external scheduler can invoke the CLI
later. There is deliberately no live adapter. Selected.

### C. Documentation-only production plan

This avoids execution risk but cannot verify schema, freshness, idempotency,
alerts or forbidden-state behavior. Rejected because the user asked to build
and test the step.

## Interfaces and schemas

### Shadow policy

Required fields:

- `schema_version=qlib_peerlite_shadow_policy_v1`
- `capability=SHADOW_ONLY`
- `input_track=SYNTHETIC`
- `execution_mode=paper`
- timezone, session close, rebalance weekday and schedule cutoff;
- pinned calendar path and hash;
- maximum signal age and future-skew tolerance;
- maximum prediction bytes, rows and unique instruments;
- top fraction, maximum name weight and maximum paper intents;
- exact M9 gate path/hash;
- permitted synthetic model IDs.

Unknown fields are rejected. Keys containing broker/account/credential/secret
semantics are rejected before model validation.

### Source manifest

The source manifest binds:

- exact prediction Parquet SHA-256;
- row count;
- model ID;
- `track=SYNTHETIC`;
- prediction timestamp;
- score schema version.
- exactly one signal session date and a timezone-aware prediction time after
  that session's configured close.

### Cycle output

```text
<state-root>/
  reservations/<cycle-id>.json
  idempotency/<cycle-id>.json
  cycles/<cycle-id>/
    signal_manifest.json
    paper_intents.json
    monitoring.json
    alert.json
    cycle_manifest.json
```

Cycle IDs must match `m10s-YYYYMMDD-HHMMSS-[0-9a-f]{12}`. The state root must
be a real directory rather than a symlink, every derived path must resolve
below it, and none of the managed parents may be a symlink.

The terminal manifest binds the policy, M9 gate, input bytes and every cycle
artifact. Temporary directories live on the same filesystem and are fsynced
before one atomic rename.

`cycle_manifest.json` contains `content_sha256`, calculated over canonical JSON
with that field omitted. One terminal verifier is the only accepted reader for
replay and repair. It verifies:

- schema, cycle ID, terminal state and request digest;
- canonical `content_sha256`;
- exact state-specific inventory:
  - `COMPLETE`: `signal_manifest.json`, `monitoring.json`,
    `paper_intents.json`;
  - `HALTED`: `monitoring.json`, `alert.json`;
  - `NOT_DUE`: no subordinate artifact;
- absence of forbidden extra files and symlinks;
- every declared artifact byte count and SHA-256.

Any mismatch is `TERMINAL_CORRUPTION`. A corrupt terminal directory is never
returned and never used to create or repair an idempotency record.

An idempotency index has the fixed schema
`qlib_peerlite_idempotency_index_v1`: cycle ID, request digest, terminal state,
relative terminal-manifest path, terminal-manifest SHA-256 and committed time.
If an index exists, it is validated before reservation handling:

- malformed content, a missing terminal directory, a mismatched digest/path or
  a terminal-verifier failure is `IDEMPOTENCY_INDEX_CORRUPTION`;
- an existing valid index is read-only and may never be overwritten;
- index creation uses exclusive no-overwrite semantics;
- repair is allowed only when the index does not exist and the complete
  terminal verifier has already accepted the matching terminal cycle.

## Control flow

1. Load and validate policy; reject unsafe keys and non-shadow modes.
2. Verify the configured M9 gate bytes and terminal HOLD invariants.
3. Validate the cycle-ID grammar and state-root containment. Reject symlinks in
   the managed path.
4. Open the prediction file with no-follow semantics, reject it above
   `max_input_bytes`, read it once, and hash and parse the same immutable byte
   buffer. Inspect Parquet metadata before table materialization and reject a
   declared row count above `max_rows`.
   Steps 1–4 are preflight: any rejection returns a stable JSON error on stderr,
   exits nonzero and creates or changes no file below the state root.
5. Derive the request digest from cycle ID, policy, source manifest and the
   captured prediction bytes.
6. Resolve the transaction:
   - if an idempotency index exists, validate its complete schema and require
     that it references a fully verified terminal cycle with the same request
     digest; return only that verified result;
   - an invalid, orphaned or mismatched index is
     `IDEMPOTENCY_INDEX_CORRUPTION` and is retained unchanged;
   - pass any terminal cycle directory through the complete terminal verifier;
     only a verified terminal with a matching request digest is committed;
     then repair a missing idempotency record and return it;
   - a terminal directory or reservation with a different digest is
     `IDEMPOTENCY_COLLISION`;
   - otherwise create `reservations/<cycle-id>.json` with `O_EXCL`, containing
     request digest, owner UUID and creation time;
   - a matching fresh reservation is `CYCLE_IN_PROGRESS`;
   - one contender may recover a matching reservation older than the fixed
     timeout by atomically renaming it to a unique stale record and acquiring a
     new reservation. Only the successful rename may proceed.
7. Evaluate the pinned session calendar. `NOT_DUE` is a committed terminal
   result with no table materialization and no paper intents. A due cycle
   requires the local date to be a configured session, the configured
   rebalance weekday and `as_of >= run_after`.
8. Validate one score cross-section:
   - every row has the same `datetime`;
   - that date equals the due cycle's local session date;
   - manifest prediction time has the same local date, is no earlier than
     session close and is not later than `as_of + future_skew`;
   - age is measured from manifest prediction time;
   - every instrument matches `SYNTH_[A-Z0-9]{1,24}`;
   - row and unique-instrument counts remain within policy bounds.
9. Run finite-score, duplicate-key, track, model and hash checks.
10. On any failed check, write one immutable per-cycle alert into the staging
    directory and publish a halted terminal cycle with no
    `paper_intents.json`.
11. On success, rank the single cross-section deterministically by score
    descending then instrument ascending. Emit capped equal-weight paper
    intents.
12. Fsync files and staging directory, then atomically rename staging to
    `cycles/<cycle-id>`. This rename is the sole commit point. Atomically write
    the matching committed idempotency record with exclusive no-overwrite
    creation and remove the owned reservation. A concurrent existing index must
    validate as the same committed result or the call fails closed. A crash
    after the rename is repaired from the verified terminal manifest on replay.

## Failure, retry and concurrency

- Preflight errors use stable codes and structured stderr, with no local state
  mutation because a trusted transaction target does not yet exist.
- Transaction errors after reservation use stable codes and publish one
  `HALTED` cycle plus `alert.json`.
- No automatic retry exists inside the cycle; scheduling systems decide when
  to invoke again.
- Identical replay is read-only and returns the original manifest.
- Same ID/different bytes is a hard collision.
- Reservation creation is exclusive. Concurrent losers either report
  `CYCLE_IN_PROGRESS` or re-read the committed terminal directory.
- The terminal cycle directory is authoritative; the idempotency record is a
  repairable index, never a second commit point.
- Existing indexes are never overwritten. Orphaned, malformed or mismatched
  indexes are retained and fail closed.
- Replay and repair cannot read terminal JSON directly; both must call the
  complete terminal verifier.
- A per-cycle alert is published inside the same transaction. No shared
  append-only journal or top-level alert index participates in the commit.
- Partial staging directories never count as completed state.
- A corrupt terminal directory is retained for forensics and blocks the cycle
  ID; it is never overwritten or silently repaired.
- A recovering process may remove only its own stale reservation record after
  acquiring the replacement reservation; it never deletes a terminal cycle.

## Compatibility and migration

No existing interface changes. The CLI receives two new commands and the
package exports new names only. The synthetic demo and all M0–M9 artifacts
remain unchanged.

## Rollout and rollback

- Rollout is local/CI shadow execution only.
- The committed policy cannot enable live mode.
- Rollback removes the M10 package, CLI commands and config; M0–M9 remain
  valid.
- A future promoted model requires a new contract, gate, policy schema and
  separately reviewed adapter. It cannot mutate this policy.

## Observability and security

- Stable check/error codes, terminal state, timestamps and artifact hashes are
  recorded.
- No raw features, labels, holdings, secrets or personal data enter alerts.
- Config loading rejects secret-shaped and broker-shaped fields recursively.
- No network library or subprocess call appears in the production package.
- Input bounds are checked before expensive parsing. A synthetic declaration
  alone is insufficient; every instrument must use the enforced namespace.

## Ordered implementation

1. Add tests for policy/live rejection and M9 authorization.
2. Add tests for pinned-session timing, one-cross-section semantics and
   monitoring failures.
3. Add tests for bounded immutable-byte loading, path containment, synthetic
   identity, paper-intent determinism, reservation recovery and crash repair.
4. Implement the production package without external services.
5. Add CLI commands and committed shadow policy.
6. Execute black-box success and rejection journeys.
7. Publish M10 engineering gate as `SHADOW_READY` with live deployment `HOLD`.

## Verdict

Implementation-ready. No unresolved material design decision remains.
