# M10 Shadow Production Test Plan

## Scope and risk

Risk is R3. Tests must prove that a production-shaped interface cannot cross
the M9 HOLD boundary, that every accepted shadow artifact is deterministic and
tamper-evident, and that concurrency/crash states fail closed.

## Behavior-to-test matrix

| ID | Layer | Behavior and oracle |
| --- | --- | --- |
| POL-01 | unit | Valid committed policy loads as `SHADOW_ONLY/paper/SYNTHETIC`. |
| POL-02 | unit | Live mode, unknown keys and nested broker/account/credential/secret keys raise stable preflight codes. |
| AUTH-01 | unit | Exact M9 bytes with HOLD, zero OOS and no production authorization yield `SHADOW_ONLY`. |
| AUTH-02 | unit | Hash mismatch, promotion/production true, opened OOS or wrong decision rejects. |
| SCH-01 | unit | Pinned session + Friday + cutoff is due; before cutoff, non-session and non-rebalance days are not due. |
| PATH-01 | unit | Safe cycle ID and contained real state root pass; traversal IDs and symlink roots/parents fail. |
| INPUT-01 | integration | No-follow one-read snapshot binds the exact parsed Parquet bytes and source manifest. |
| INPUT-02 | integration | Symlink input, byte overflow, metadata row overflow, manifest hash/count/model/track mismatch reject before reservation. |
| SIG-01 | unit | One finite, unique, synthetic cross-section bound to the due session passes. |
| SIG-02 | unit | Multiple dates, wrong session, non-session IDs, NaN/Inf, duplicate keys, stale/future time and cardinality overflow fail. |
| ORD-01 | unit | Score-descending/instrument-ascending ranking creates deterministic capped equal-weight paper intents. |
| ORD-02 | unit | No function or policy can construct live/broker orders. |
| TX-01 | integration | Successful due cycle atomically publishes exact `COMPLETE` inventory and exclusive idempotency index. |
| TX-02 | integration | Post-reservation validation failure publishes exact `HALTED` inventory with alert and no paper intents. |
| TX-03 | integration | `NOT_DUE` publishes only a valid terminal manifest and no subordinate artifact. |
| TX-04 | integration | Policy, authorization, path and bounded-input preflight failures return structured errors with byte-identical state root. |
| ID-01 | integration | Identical replay returns the verified original without changing artifact bytes. |
| ID-02 | integration | Same cycle ID with changed input is `IDEMPOTENCY_COLLISION`. |
| ID-03 | integration | Fresh reservation reports in-progress; one stale matching reservation is recoverable. |
| ID-04 | integration | Verified terminal without index repairs the missing index; corrupt terminal never repairs. |
| ID-05 | integration | Malformed, orphaned or mismatched existing index is retained and fails closed. |
| TERM-01 | integration | Manifest self-hash, state schema, exact file set, byte counts and artifact hashes verify. |
| TERM-02 | integration | Modified/truncated/extra/symlink artifacts are `TERMINAL_CORRUPTION`. |
| BND-01 | static | Production package has no trainer, Qlib, broker, socket, requests, subprocess or credential dependency. |
| CLI-01 | E2E | Public preflight prints `SHADOW_ONLY`; public due cycle produces verified `COMPLETE`. |
| CLI-02 | E2E | Public live-policy attempt exits nonzero, emits structured error and writes no state. |

## Fixtures and determinism

- All score data is synthetic and instruments use `SYNTH_*`.
- Tests build a tiny Parquet buffer and source manifest under `tmp_path`.
- The calendar fixture is a small immutable JSON session list with a bound hash.
- Clock, owner UUID and reservation age are injected.
- No external process, database, network, credentials or wall-clock sleep is
  used.
- Concurrency state transitions are exercised through exclusive filesystem
  artifacts and deterministic injected times rather than timing races.

## Fault injection

- crash after terminal-directory rename but before index creation;
- stale reservation;
- malformed/orphaned/mismatched index;
- policy and M9 tampering;
- signal-file symlink and oversized metadata;
- every terminal file tampered, removed, added or replaced by symlink;
- alert and atomic-write failure through a controlled filesystem seam.

## Coverage obligation

Every authored file under `src/qlib_peerlite/production` is core. The dedicated
M10 coverage profile must enumerate that complete source root and reach exactly
100% line and branch coverage. Coverage cannot exclude testable branches.

## Critical journeys

### J1 — Shadow cycle

Invoke the public CLI with the committed shadow policy, pinned synthetic
calendar, valid M9 gate and one synthetic score cross-section. Require a
verified `COMPLETE` terminal cycle, deterministic paper intents, a committed
index and byte-identical replay.

### J2 — Live-order rejection

Invoke the public CLI with a policy requesting live execution. Require stable
nonzero exit, structured error, no state mutation and no network/broker
activity.

## Expected-red proof

Before production code exists, the M10 test module must fail with the explicit
reason `M10 production package is not implemented`. Syntax, fixture and
dependency failures do not satisfy red.

## Verdict

PASS — the matrix is executable, bounded and covers every approved design
obligation.
