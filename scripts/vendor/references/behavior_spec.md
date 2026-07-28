# Point-in-Time Behavior Proof Specification

Version: `pit_behavior_spec_v1`  
Certification status: `NOVEL_CANDIDATE`

This module tests one narrow claim: a hash-bound pair of feature-pipeline runs
preserved the declared point-in-time output invariant. It does not replace
`pit_audit_spec_v1`, prove vendor semantics, prove that a mutation generator was
honest, certify a full training input, train a model, or authorize deployment or
capital use.

## Decision model

Every check and the overall result use exactly `PASS`, `NEEDS_EVIDENCE`, or
`FAIL`, with precedence `FAIL > NEEDS_EVIDENCE > PASS`.

- Missing files, hashes, receipt fields, protected-key declarations, or a
  non-empty protected population are `NEEDS_EVIDENCE`.
- A supplied but malformed artifact, hash or receipt contradiction, duplicate
  canonical output key, invalid probe construction, protected-key drift, or
  protected-value drift is `FAIL`.
- `PASS` means only that the supplied, hash-bound pair satisfied this
  specification. It is not a general proof that all executions are PIT-safe.

## Request and receipt

Run:

```bash
python3 scripts/audit_behavior.py /absolute/path/behavior_request.json \
  --output-dir /absolute/path/new_output_directory
```

`behavior_request.json` has this interface:

```json
{
  "request_version": "pit_behavior_request_v1",
  "request_id": "stable-caller-id",
  "probe_type": "FUTURE_POISON",
  "artifacts": {
    "baseline_raw_snapshot": {"path": "raw-before.json", "sha256": "64hex"},
    "probe_raw_snapshot": {"path": "raw-after.json", "sha256": "64hex"},
    "code_or_query": {"path": "feature.sql", "sha256": "64hex"},
    "parameters": {"path": "parameters.json", "sha256": "64hex"},
    "environment": {"path": "environment.json", "sha256": "64hex"},
    "baseline_output": {"path": "baseline.csv", "sha256": "64hex"},
    "probe_output": {"path": "probe.csv", "sha256": "64hex"},
    "pit_audit_manifest": {"path": "audit_manifest.json", "sha256": "64hex"},
    "perturbation_ledger": {"path": "ledger.json", "sha256": "64hex"},
    "pipeline_receipt": {"path": "receipt.json", "sha256": "64hex"}
  }
}
```

Paths are relative to the request unless absolute. Every declared SHA-256 is
lowercase and binds exact file bytes. The auditor never substitutes a nearby
file or infers an undeclared artifact.

The feature-pipeline receipt is:

```json
{
  "receipt_version": "pit_behavior_receipt_v1",
  "receipt_id": "immutable-receipt-id",
  "request_id": "stable-caller-id",
  "probe_type": "FUTURE_POISON",
  "baseline_run_id": "run-before",
  "probe_run_id": "run-after",
  "artifact_sha256": {
    "baseline_raw_snapshot": "64hex",
    "probe_raw_snapshot": "64hex",
    "code_or_query": "64hex",
    "parameters": "64hex",
    "environment": "64hex",
    "baseline_output": "64hex",
    "probe_output": "64hex",
    "pit_audit_manifest": "64hex",
    "perturbation_ledger": "64hex"
  },
  "parent_audit": {
    "audit_id": "pit-audit-id",
    "content_sha256": "64hex",
    "status": "PASS"
  },
  "protection": {
    "comparison": "LE",
    "protected_through": "2025-01-31T16:00:00Z",
    "expected_key_count": 100,
    "expected_keys_sha256": "64hex"
  },
  "probe": {
    "mutation_type": "FUTURE_POISON",
    "mutation_time_min": "2025-02-01T00:00:00Z",
    "canary_sample_ids": []
  }
}
```

The receipt must bind both run IDs and the exact baseline/probe raw snapshots,
code or query, parameters, environment, outputs, parent PIT audit manifest, and
perturbation ledger. The bound parent must be a `PASS`
`pit_audit_manifest_v1` whose `contract_binding.adapter` is the production
`quant_contract_v2`, `execution_boundary` is `PRODUCTION_CLI`, and
`test_only_adapter` is false. The auditor independently recomputes its canonical
`content_sha256` and derived `audit_id`, and requires
`pit_qualification: QUALIFIED`, `evidence_ceiling: PASS`,
`coverage_matrix.scope: FULL_TRAINING_INPUT`, and exactly the 17 fixed checks all
`PASS`. An unresolved or sample-only parent keeps the behavior result unresolved;
a failed, synthetic-adapter, or internally inconsistent parent fails the
combined gate. Hash equality establishes byte identity, not truth or
organizational attestation.

## Verifiable perturbation ledger

The two raw snapshots use `pit_behavior_snapshot_v1`:

```json
{
  "snapshot_version": "pit_behavior_snapshot_v1",
  "records": [
    {
      "raw_key": "immutable-raw-record-key",
      "sample_id": "security-or-sample-id",
      "available_time": "2025-02-01T00:00:00Z",
      "revision_known_time": "2025-02-02T00:00:00Z",
      "universe_known_time": "2025-02-03T00:00:00Z",
      "payload": {"source fields": "arbitrary strict JSON"}
    }
  ]
}
```

`raw_key` is unique within a snapshot. The auditor hashes the canonical JSON of
each whole record and computes the exact add/update/delete diff. It then verifies
the independently supplied ledger:

```json
{
  "ledger_version": "pit_perturbation_ledger_v1",
  "baseline_snapshot_sha256": "64hex",
  "probe_snapshot_sha256": "64hex",
  "entries": [
    {
      "raw_key": "immutable-raw-record-key",
      "operation": "UPDATE",
      "change_type": "FUTURE_POISON",
      "known_time": "2025-02-01T00:00:00Z",
      "baseline_record_sha256": "64hex-or-null",
      "probe_record_sha256": "64hex-or-null"
    }
  ]
}
```

Ledger keys, operations, and record hashes must equal the recomputed snapshot
diff exactly. Missing snapshots, ledger, or probe-scope fields are
`NEEDS_EVIDENCE`; a supplied ledger that omits, invents, or misstates a real
change is `FAIL`.

## Canonical paired output

Both replay outputs are UTF-8 CSV with exactly:

```text
sample_id,prediction_time,feature_name,feature_value_json
```

The canonical key is `(sample_id, prediction_time, feature_name)`.
`sample_id` and `feature_name` are non-empty exact strings without surrounding
whitespace. `prediction_time` is an offset-aware ISO-8601 timestamp normalized
to UTC with six fractional digits and `Z`. `feature_value_json` is one finite
JSON scalar: string, number, boolean, or null. Numbers are compared by their
normalized decimal value, so `1`, `1.0`, and `1e0` are equal.

Duplicate canonical keys fail. Protected keys are those with
`prediction_time <= protected_through`. Their sorted canonical JSON encoding is
SHA-256 bound by `expected_keys_sha256`; an empty protected key set cannot pass.
Baseline and probe protected key sets must be identical, and every protected
value must be identical.

## Probe rules

Exactly one probe is declared:

| Probe | Required construction | Protected invariant |
| --- | --- | --- |
| `PREFIX_REPLAY` | Snapshot bytes are equal and the verified ledger/diff is empty; run IDs are distinct. | Re-execution cannot change any protected key or value. |
| `FUTURE_POISON` | Ledger/diff is non-empty; every before/after changed record has `available_time > protected_through`; their minimum equals `mutation_time_min`. | A verified strictly future input perturbation cannot change the protected prefix. |
| `REVISION_REPLAY` | Ledger/diff is non-empty; every before/after changed record has `revision_known_time > protected_through`; their minimum equals `mutation_time_min`. | A verified later revision cannot rewrite protected historical features. |
| `UNIVERSE_CANARY` | Ledger/diff is non-empty; every before/after changed record belongs to a declared unique `canary_sample_ids` member and has `universe_known_time > protected_through`. | Protected keys/values remain fixed and no declared canary appears in the protected output. |

For `FUTURE_POISON` and `REVISION_REPLAY`, `mutation_time_min` is recomputed from
the changed snapshot records, not trusted as a free-standing declaration.

## Fixed checks and failure conditions

| ID | PASS boundary | Hard `FAIL` examples |
| --- | --- | --- |
| `B001` | All ten request artifacts exist, exact request hashes match, and the bound parent PIT audit is `PASS`. | Malformed supplied hash, hash mismatch, malformed supplied receipt/parent JSON, failed parent audit. |
| `B002` | Receipt identity, run IDs, hashes, protection, exact snapshot/ledger diff, and probe scope agree. | Request/receipt contradiction, ledger/diff mismatch, changed out-of-scope raw record, non-future poison/revision, wrong snapshot equality, invalid canary list. |
| `B003` | Both outputs parse canonically, have unique keys, and baseline protected keys match the receipt count/digest. | Malformed supplied CSV/value/timestamp, duplicate key, expected-key count or digest mismatch. |
| `B004` | Protected key sets and values match; protected canaries are absent. | Any protected key added/dropped, any protected value changed, or any protected canary emitted. |

Missing evidence is never converted into a failure merely because it is absent.
Conversely, an observed invariant violation is never softened to
`NEEDS_EVIDENCE`.

## Outputs

A parseable invocation atomically publishes:

- `behavior_manifest.json`, version `pit_behavior_manifest_v1`, containing the
  tri-state result, `NOVEL_CANDIDATE` designation, input lineage, protection
  digest, all four checks, findings, limitations, content hash, behavior ID, and
  exact report hash.
- `behavior_report.md`, a short deterministic view of the same result.

Exit codes are `0` for `PASS`, `2` for `NEEDS_EVIDENCE`, `3` for `FAIL`, and
`64` for invocation/internal errors. A non-empty output directory is never
overwritten.

## Research gap and certification boundary

This rule is `NOVEL_CANDIDATE` because paired counterfactual replay is useful
negative evidence but is not yet a source-backed completeness proof. The exact
record diff and probe scope are executable here, but the meanings of
`available_time`, `revision_known_time`, and `sample_id` remain upstream semantic
trust roots. An untested branch, hidden external state, nondeterministic
dependence not triggered by the pair, or coordinated omission from the parent
population and both outputs can still escape detection.

The preset rejection condition is any reproducible protected key/value change,
protected canary appearance, ledger/diff mismatch, out-of-scope changed raw
record, invalid probe construction, or hash/receipt contradiction. Promotion
beyond `NOVEL_CANDIDATE` requires source-backed semantics for the snapshot scope
fields, broader adversarial coverage, and evidence that the expected protected
population was established outside the pipeline under test. Until then, this
module supplements but never upgrades the fixed PIT audit.
