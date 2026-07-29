# M6.5 v40 Adversarial Design Review

- Reviewer context: `/root/m65_v24_adversarial_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject: `m6_5_repair_change_design_v40.md`
- Subject SHA-256: `a4f4a6539225c4ac02d4dcfa0971593d72c7e226dc69c683a58b2e2819c4076b`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=4 / P2=3 / P3=0`

## Blocker status

| Review item | Status |
|---|---|
| distinct typed schemas and contracts | PARTIAL |
| one-way trust equality | CLOSED |
| filesystem mutation denial | PARTIAL |
| observation evidence and digest coverage | CLOSED |
| per-execution sandbox receipts | PARTIAL |
| closed replay plan | OPEN |
| duplicate-before-promotion | CLOSED |
| LP lease digest | CLOSED |

## P1 findings

### Inner result contracts allow schema or reference substitution

`run_authority_generation_v10.md` does not fully freeze candidate rows, metric values, prediction rows and checkpoint bytes as dedicated immutable typed objects. It also does not require the fit/refit content checkpoint and metric references to equal the corresponding receipt references.

Minimum repair: define dedicated immutable file or manifest schemas with fixed event-local paths, file and canonical digests, row/schema/key/value digests and exact equality between content and receipt references; reject free maps, extra references and cross-event references.

### Sandbox receipt slot is vulnerable to framing and traversal

`m7_change_design_v18.md` uses a raw delimiter for `execution_id` and a free-form `closure_id` directory segment.

Minimum repair: use length-prefix framing over a closed sorted input identity; use the closure canonical SHA as the directory segment; resolve from a trusted root FD with no-follow and no-dot-segment enforcement.

### Replay plan uses ambiguous reference types

`score_replay_plan_v1.md` uses a generic `ArtifactRefV1` for Markdown, canonical JSON and binary or Parquet inputs even though these objects require different identity rules.

Minimum repair: distinguish immutable file references from canonical-JSON references, or wrap every raw file in an exact JSON manifest; freeze the unique target schema and digest semantics for each field.

### Replay output, transactions and terminal receipts are incomplete

The replay output slot lacks a fixed output-root identity, safe path grammar, no-follow containment, role separation and capacity transaction binding. Pair and aggregate receipts are prose rather than exact schemas, and pair-to-model merged-prediction equality is not mandatory.

Minimum repair: bind a fixed output-root policy and identity; derive safe no-follow paths from a root FD; bind PREPARED/COMMITTED reservation transactions; define exact fixed-path PairReceipt and AggregateResult schemas, digest preimages, crash states, complete 14-pair coverage and rejection of extra outputs.

## P2 findings

### Output-FD-only write authority is not mechanically evidenced

Sandbox receipts do not record and revalidate file-descriptor device, inode, flags and allowed operation sets. The oracle does not yet prove that all write-like syscalls target only authorized output FDs.

Minimum repair: record FD identity and flags and define the complete write-operation oracle, including shared mappings and metadata mutations.

### Test matrix omits adversarial cases

Add closure traversal, execution-identity collision, receipt/content mismatch, raw-file reference substitution, replay traversal, symlink or alias output, model/pair mismatch and crash-after-output-before-receipt cases.

### Matrix Base lacks an explicit path

`m7_behavior_to_test_matrix_v18.md` names only the v17 base SHA.

Minimum repair: state the exact base path and SHA.

## Confirmed properties

- All v40 and recursive base hashes match.
- Reservation duplicate checks precede promotion.
- Root containment, provisional temp charging and lease-to-claim DAG remain intact.
- Authorization-to-policy trust remains a one-way DAG.
- Observation evidence and historical manifest coverage are closed.
- M6 remains `6/44`; M7, fit, replay, real data, PIT, budget mutation and final OOS remain unauthorized.

## Residual boundary

This was a read-only design review. No execution authority was created and no workflow was run.
