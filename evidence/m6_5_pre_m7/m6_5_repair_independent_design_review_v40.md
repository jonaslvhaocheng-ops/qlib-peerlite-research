# M6.5 v40 Independent Design Review

- Reviewer context: `/root/m65_v25_design_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject: `m6_5_repair_change_design_v40.md`
- Subject SHA-256: `a4f4a6539225c4ac02d4dcfa0971593d72c7e226dc69c683a58b2e2819c4076b`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=4 / P2=1`

## Blocker status

| Review item | Status |
|---|---|
| distinct wrapper/content IDs and fixed inner typed contracts | PARTIAL |
| one-way trusted-policy equality | PASS |
| path-mutation deny and execution-specific receipt slot | PARTIAL |
| JSONL evidence location, digests and manifest coverage | PASS |
| duplicate scan before promotion | PASS |
| LP lease inventory digest | PASS, with one naming ambiguity |
| closed replay plan and full replay identity | FAIL |

## Findings

### P1 — inner metrics and rows are not closed typed contracts

`run_authority_generation_v10.md` separates wrapper and content schema IDs, but candidate rows, synthetic rows, metrics, checkpoint bytes and prediction rows do not all have fixed event-local paths, exact field schemas, complete digest identities and cross-object equality requirements. A valid wrapper can therefore still refer to foreign rows, metrics or checkpoint bytes.

Minimum repair: freeze dedicated event-local paths, schemas, fields and identities for observations, prediction rows, metrics and checkpoint bytes; require every inner reference to remain inside the same `runs/<g20>/results/<event_key>/` subtree and reject cross-event references.

### P1 — sandbox receipt identity permits collision or path escape

`m7_change_design_v18.md` derives `execution_id` with a raw delimiter over incompletely constrained fields and uses a free-form `closure_id` as a path component. Delimiter collisions and `/`, `..` or control-character path escape remain possible.

Minimum repair: length-prefix every execution identity field; derive the receipt directory from the closure canonical digest or impose a strict safe-ID grammar that rejects separators, dot segments and control characters.

### P1 — worker lock lifetime is not closed

The inherited run-authority design requires the worker to hold the event lock at entry, but does not state that the same open file description remains held through the durable OUTCOME transition. A stale worker could continue after a reconciler publishes `INTERRUPTED`.

Minimum repair: require the worker to hold the same open lock FD from lease grant through OUTCOME receipt fsync; revalidate FD identity under the lock at every publication boundary; a worker that loses the lock must be terminated and have no output-write authority.

### P1 — replay identity and replay plan conflict

`score_replay_identity_v1.md` says the outer plan binds output paths and file SHA before execution, while `score_replay_plan_v1.md` correctly says only output slots are known before execution and output SHA belongs in post-run receipts. The plan also lacks exact PairReceipt and AggregateResult schemas and safe output-path rules.

Minimum repair: publish a new replay identity version that binds only immutable inputs and safe output slots before execution; put output hashes only in exact post-run receipt schemas; close fixed paths, coverage, aggregate digest and safe relative-path grammar.

### P2 — lease digest field naming is ambiguous

The inventory schema uses `event_seq`, while the digest preimage says `LP(seq)`.

Minimum repair: use `LP(canonical ASCII decimal event_seq)` and state the encoding of every digest field.

## Confirmed properties

- The v40 subject, all direct specifications and pointer hashes match.
- Wrapper and content schema IDs are distinct.
- Authorization-to-policy equality is one-way.
- Major path-mutation syscalls are denied and unsupported platforms fail closed.
- JSONL observation evidence and manifest coverage are defined.
- Reservation duplicate scanning precedes promotion.
- Lease inventory uses field-wise length-prefixing.
- M6 remains `6/44`; M7, fit, replay, real data, PIT, budget mutation and final OOS remain unauthorized.

## Residual boundary

Passing a repaired design review would authorize only the next synthetic test-design stage. It would not authorize M7 implementation, fitting, replay, real-data or final-OOS access.
