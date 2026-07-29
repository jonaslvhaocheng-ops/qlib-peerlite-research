# Architecture Confirmation V29 — Bound RunIntent Slice

- Mode: `confirmation`
- Parent architecture: `architecture_confirmation_v28.md`
- Source digest: `sha256:fb90c454682976c2a1e23039a5643cb3511d1802a22ce611712a3ac12bdc53e7`
- Verdict: `PASS`

## Changed surface

The only new production behavior is inside
`src/qlib_peerlite/governance/trial_ledger.py`: `RunIntent` can carry the already-approved budget and
market-state authority bindings, and the M7 initial-screen family rejects their absence.

## Boundary confirmation

- Ownership remains in `governance.trial_ledger`; no data/model/Qlib/Torch module dependency was added.
- The dependency direction is unchanged: caller/composition root constructs an intent, governance validates
  and hashes it, journal/ledger consumers use that immutable identity.
- Historical non-M7 intents retain V1 hashing, so immutable M6 evidence is not migrated or rewritten.
- Bound intents use V2 hashing; the schema change is local to the future M7 authority namespace.
- No new process, service, database, data owner, runtime, deployment unit, privileged control plane or
  shared mutable state was introduced.
- Enforcement remains unit/contract tests plus Ruff and the existing engineering-quality route.

## Decision

The v28 trusted single-process research architecture fully contains this slice. No redesign, package move,
new public service or cross-boundary abstraction is warranted. Subsequent implementation remains limited to
the approved v48 closure and synthetic tests; replay, fit, PIT, real data, budget mutation and final OOS stay
forbidden.
