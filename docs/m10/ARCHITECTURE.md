# M10 Shadow Production Architecture

## Decision

M10 adds one bounded `qlib_peerlite.production` package and two public CLI
commands. It does not change the research, data, model, evaluation or portfolio
packages.

The current capability is permanently labelled `SHADOW_ONLY` because
`evidence/gates/M9_step_nine_terminal_gate.json` records
`production_authorized=false`. M10 has no broker implementation, network
client, credential field or live-order escape hatch.

## Runtime boundary

```text
immutable M9 gate ─────────────┐
shadow policy ─────────────────┼─> preflight
score parquet + source manifest┘       │
                                      v
schedule decision -> signal validation -> monitoring
                                           │
                       reject + local alert┤
                                           v
                                 paper intent sink
                                           │
                                           v
                               hash-bound cycle manifest
```

## Modules and ownership

| Module | Responsibility | May depend on |
| --- | --- | --- |
| `production.policy` | Strict shadow policy and M9 authorization decision | Pydantic, governance hashes |
| `production.schedule` | Pure Asia/Shanghai due-time decision | standard library |
| `production.signals` | Unified score-schema, temporal and integrity validation | pandas, governance hashes |
| `production.monitoring` | Deterministic health checks and local alert records | policy/signals |
| `production.orders` | Idempotent paper-intent persistence; reject all other modes | governance atomic I/O |
| `production.cycle` | Composition root and state machine | the five modules above |
| `cli` | User-facing preflight and shadow-cycle commands only | production public API |

Dependencies point inward to pure policy and schema code. No production module
may import a model trainer, Qlib Recorder, database client, broker SDK or final
OOS artifact.

## Public contracts

- Input predictions keep the existing columns
  `(datetime, instrument, score, model_id, fold_id)`.
- A source manifest binds the exact prediction bytes, track, model ID,
  prediction timestamp and declared row count.
- A cycle writes a new output directory atomically and never overwrites it.
- Paper intents contain only synthetic instrument IDs, target weights and an
  idempotency key. They are not executable broker orders.
- Every terminal cycle has a hash-bound manifest and immutable local alert
  evidence when halted.
- The atomically renamed terminal cycle directory is the sole commit point. A
  repeated cycle ID with identical inputs returns or repairs the original
  committed result; a repeated ID with different inputs fails closed.

## State and failure rules

```text
CREATED -> AUTHORIZED_SHADOW -> DUE -> SIGNAL_VALIDATED
        -> MONITORED -> PAPER_INTENTS_WRITTEN -> COMPLETE

trusted transaction failure -> HALTED + local alert + no paper intents
preflight rejection -> structured error + no state mutation
```

- `execution_mode != paper` is rejected while loading policy.
- Any broker endpoint, account, credential or secret-shaped configuration key
  is rejected.
- `production_authorized=true` does not enable live mode; M10 intentionally has
  no live adapter.
- Missing/tampered M9 evidence, stale/future signals, non-session dates,
  non-finite scores, duplicate keys, model/manifest mismatch, unsafe paths and
  idempotency collisions halt.
- Policy, authorization, unsafe-path and immutable-input failures occur before
  reservation and return a structured preflight error without writing state.
- Local alert-write failure propagates after reservation; a failed cycle cannot
  be reported healthy.
- Replay and crash repair use one terminal verifier that checks canonical
  manifest integrity, state-specific file inventory and every artifact hash
  before accepting a commit.

## Operability and security

- The scheduler is a deterministic decision function, not an autonomous daemon.
  Cron/systemd/Kubernetes may invoke the CLI later without changing policy.
- Monitoring and per-cycle alert artifacts are local, immutable and
  secret-free.
- Cycle IDs use a fixed safe grammar; state paths must remain below a
  non-symlink state root.
- Prediction bytes are opened without following symlinks, read once, bounded,
  hashed and parsed from the same in-memory snapshot.
- No environment variable containing credentials is read.
- Inputs and outputs are content-addressed with SHA-256.
- The default committed configuration is synthetic-only and paper-only.

## Enforcement

- Package import-boundary tests prevent broker/network/trainer dependencies.
- Unit and integration tests require 100% line and branch coverage for the new
  package.
- CLI E2E tests cover one successful synthetic shadow cycle and live-mode
  rejection with no forbidden state.
- GitHub CI runs the full suite and the dedicated M10 coverage profile.

## Claim boundary

An M10 engineering pass proves only that the shadow control plane fails closed
and is reproducible. It does not prove Alpha, model promotion, final-OOS
validity, broker connectivity, production capacity or permission to trade.
