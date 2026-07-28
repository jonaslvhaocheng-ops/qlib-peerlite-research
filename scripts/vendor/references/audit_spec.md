# Point-in-Time Audit Specification

Version: `pit_audit_spec_v1`

This is the deterministic interface used by `scripts/audit_pit.py`. It audits the values actually proposed for a training matrix; it does not repair data, mutate a research contract, train a model, backtest, or calculate alpha.

## Decision model

Claims are fixed before the audit:

- `MARKET_RECONSTRUCTIBLE`: public release and declared-vendor availability are no later than `prediction_time`. A later local ingest is disclosed but does not invalidate this claim.
- `SYSTEM_REPLAYABLE`: the market claim passes and the exact value was also ingested and parse-ready in the historical research system by `prediction_time`.

Every check and the overall result use exactly `PASS`, `NEEDS_EVIDENCE`, or `FAIL`, with precedence `FAIL > NEEDS_EVIDENCE > PASS`.

- Missing or ambiguous semantics, versions, receipts, or coverage are `NEEDS_EVIDENCE`.
- A temporal violation, semantic contradiction, forbidden proxy, malformed value, or hash/binding mismatch is `FAIL`.
- `PASS` requires complete evidence for the stated claim.

`SAMPLE_ONLY` can find failures but its positive ceiling is `NEEDS_EVIDENCE`. Only `FULL_TRAINING_INPUT`, a hash-bound matrix manifest, exact row/population/cell coverage, and all-pass checks can produce an overall `PASS`.

## Audit request

`audit_request.json` uses `request_version: pit_audit_request_v1`. Paths are relative to the request. All hashes are lowercase SHA-256 over exact file bytes.

```json
{
  "request_version": "pit_audit_request_v1",
  "request_id": "stable-caller-id",
  "run_at": "2026-07-26T12:00:00+08:00",
  "claim": "MARKET_RECONSTRUCTIBLE",
  "coverage": {
    "scope": "FULL_TRAINING_INPUT",
    "expected_row_count": 100,
    "extraction_query_sha256": "64hex",
    "extraction_receipt_id": "immutable-receipt-id",
    "population": {
      "basis_id": "population-receipt-id",
      "snapshot_sha256": "64hex",
      "authority_source_sha256": "64hex",
      "selection_rule_sha256": "64hex",
      "universe_history_mode": "PIT_HISTORY",
      "includes_inactive_and_delisted": true,
      "expected_security_time_keys": 20,
      "universe_version": "immutable-version",
      "universe_hash": "64hex"
    }
  },
  "artifacts": {
    "data": {
      "path": "training_evidence.csv",
      "sha256": "64hex",
      "format": "csv",
      "source_id": "source-id",
      "source_version": "immutable-version",
      "snapshot_id": "snapshot-id",
      "snapshot_binding_mode": "IDENTITY_SNAPSHOT",
      "source_snapshot_sha256": "64hex"
    },
    "schema": {"path": "schema.json", "sha256": "64hex"},
    "dictionary": {
      "path": "dictionary.json",
      "sha256": "64hex",
      "dictionary_id": "dictionary-id",
      "version": "immutable-version",
      "source_uri": "authoritative-locator"
    },
    "time_semantics": {"path": "time_semantics.json", "sha256": "64hex"},
    "research_contract": {
      "path": "research_contract.json",
      "sha256": "64hex",
      "adapter": "quant_contract_v2",
      "contract_id": "contract-id",
      "canonical_hash": "64hex",
      "validation_receipt": {
        "path": "contract_validation.json",
        "sha256": "64hex"
      }
    },
    "label_definition": {
      "path": "label_definition.json",
      "sha256": "64hex",
      "label_spec_hash": "64hex"
    },
    "label_schedule": {
      "path": "label_schedule.json",
      "sha256": "64hex",
      "schedule_id": "immutable-schedule-id",
      "version": "1"
    },
    "review_authority": {
      "path": "review_authority.json",
      "sha256": "64hex",
      "authority_id": "governance-authority-id",
      "version": "immutable-version"
    },
    "label_interval_authority": {
      "path": "label_interval_authority.json",
      "sha256": "64hex",
      "authority_id": "interval-authority-id",
      "version": "immutable-version"
    },
    "calendar": {
      "path": "calendar.csv",
      "sha256": "64hex",
      "calendar_id": "venue-calendar-id",
      "version": "immutable-version",
      "timezone": "IANA/Zone",
      "source_uri": "authoritative-locator"
    },
    "population_manifest": {
      "path": "population_manifest.json",
      "sha256": "64hex",
      "population_id": "population-receipt-id",
      "version": "immutable-version",
      "source_uri": "authoritative-locator"
    },
    "population_source": {
      "path": "population_source.json",
      "sha256": "64hex",
      "authority_id": "population-receipt-id",
      "version": "immutable-version",
      "source_uri": "authoritative-locator"
    },
    "matrix_manifest": {
      "path": "matrix_manifest.json",
      "sha256": "64hex",
      "manifest_id": "immutable-matrix-id",
      "version": "1"
    }
  }
}
```

The validation receipt must bind `status: PASS`, `strict: true`, contract file hash, contract ID, canonical hash, validator identity, and validator version. `quant_contract_v2` accepts only `qrc_validation_receipt_v1` from `quant-research-contract.validate_contract`, with `validator_version: quant_contract_v2` and a valid `validator_bundle_sha256`. The audit recomputes that digest from the locally installed official validator plus its shared library, requires equality, and reruns official `--strict` validation on the exact contract. `pit_contract_validation_receipt_v1` is accepted only by the synthetic `pit_contract_binding_v1` adapter. A missing local official validator is `NEEDS_EVIDENCE`; a false, mismatched, cross-adapter, stale-bundle, or locally rejected receipt is `FAIL`. A receipt is hash-bound evidence, not protection against deliberate forgery.

`snapshot_binding_mode` is explicit. In `IDENTITY_SNAPSHOT`,
`source_snapshot_sha256` must equal the verified bytes of
`training_evidence.csv`; changing any consumed value while retaining the frozen
snapshot therefore fails. `DERIVED_EXTRACT` is reserved for a source container
plus an independently hash-bound extraction receipt linking source snapshot,
query hash, receipt ID, exact output hash and row count. That receipt is not yet
implemented in v1, so `DERIVED_EXTRACT` is `NEEDS_EVIDENCE`, never an inferred
PASS.

## Consumed-value evidence view

The data artifact is a long-form CSV with one row per value actually consumed:

| Group | Exact columns |
| --- | --- |
| Identity/value | `row_id`, `security_id`, `feature_name`, `feature_value` |
| Core clocks | `prediction_time`, `event_time`, `published_time`, `vendor_available_time`, `ingested_time`, `parse_ready_time`, `ingestion_batch_id`, `ingested_object_sha256`, `tradable_time`, `label_start_time`, `label_end_time` |
| Split/universe | `split`, `universe_member`, `universe_announced_time`, `universe_effective_from`, `universe_effective_to`, `security_status` |
| Vintage/adjustment | `revision_id`, `revision_known_time`, `adjustment_mode`, `adjustment_known_time`, `adjustment_invariance_pass` |
| Market state/identity | `halt_time`, `quote_resume_time`, `trade_resume_time`, `calendar_session_id`, `identifier_valid_from`, `identifier_valid_to` |

The primary key is `row_id`; the analytical grain is `(security_id, prediction_time, feature_name)`. Both consumed-value and calendar CSVs require non-empty, unique header names and exactly one cell per header in every physical record. Duplicate headers, extra cells and missing cells are parse failures; no first/last duplicate-column convention is accepted.

Enums:

- `split`: `TRAIN`, `MODEL_SELECTION`, `OOS`
- `security_status`: `ACTIVE`, `DELISTED`, `SUSPENDED`
- `adjustment_mode`: `RAW`, `PIT_ADJUSTED`, `FULL_HISTORY_ADJUSTED`

All non-null timestamps are offset-aware ISO-8601. `adjustment_known_time`, halt/resume times, and the two `*_to` fields may be null only when the schema and dictionary document that condition. For `universe_effective_to` and `identifier_valid_to`, `null_semantics` is structured and must be exactly `OPEN_ENDED_POSITIVE_INFINITY`, `UNKNOWN`, or `FORBIDDEN`.

## Supporting artifacts

### Schema

`schema.json` uses:

```json
{
  "schema_version": "pit_evidence_schema_v1",
  "primary_key": ["row_id"],
  "grain": ["security_id", "prediction_time", "feature_name"],
  "columns": {
    "row_id": {"type": "string", "nullable": false}
  }
}
```

Allowed types are `string`, `float`, `integer`, `boolean`, and `timestamp`. The schema, CSV header, and fixed 32-column set must agree exactly. `SYSTEM_REPLAYABLE` additionally requires a non-empty `ingestion_batch_id` and a valid SHA-256 for the exact historical ingested object on every row; timestamps alone do not identify the version held by the system.

### Dictionary

`dictionary.json` uses `schema_version: pit_field_dictionary_v1` and records `dictionary_id`, `version`, `source_uri`, and `semantic_source_document_sha256`. Every consumed column has an exact `semantic_role`, definition, and source locator.

Every consumed feature records:

```json
{
  "definition": "exact value meaning",
  "source_locator": "document/API field locator",
  "use": "PRICE_LEVEL|RETURN|VOLUME|SHARES|OTHER",
  "event_time_policy": "OBSERVED_BY_PREDICTION|KNOWN_FUTURE_OBJECT",
  "unit": "declared unit",
  "basis": "raw/restated/other exact basis",
  "grain": "economic observation grain",
  "null_semantics": "meaning of null",
  "adjustment_policy": {
    "basis": "factor base",
    "convention": "vendor convention",
    "allowed_modes": ["RAW"],
    "source_locator": "authoritative locator"
  },
  "domain_policy": {
    "kind": "BOUNDED|MIN|MAX|UNBOUNDED",
    "min": 0,
    "max": 1,
    "source_locator": "authoritative locator"
  }
}
```

Only fields required by the chosen domain kind are present. Every required `min` or `max` is a finite JSON number, not a boolean, and `BOUNDED` requires `min <= max`. All JSON inputs reject duplicate object keys and non-standard `NaN`/`Infinity` literals. V1 accepts only `RAW` under its declared basis. It fails closed on both `PIT_ADJUSTED` and `FULL_HISTORY_ADJUSTED`: the consumed-value view cannot independently recompute raw value, factor, ex-date, and base-date provenance, and a declared invariance boolean or unverified test digest cannot lift that restriction. Field meaning is never inferred from a name, dtype, correlation, or similar field.

`security_id.identity_stability` must be `permanent`; ticker alone is not eligible.

For `universe_effective_to` and `identifier_valid_to`, a null is positive infinity only when the schema declares `nullable: true` and the exact field policy is `OPEN_ENDED_POSITIVE_INFINITY`. `UNKNOWN` yields `NEEDS_EVIDENCE`; `FORBIDDEN` or `nullable: false` makes a null contradictory.

### Time semantics

`time_semantics.json` uses `schema_version: pit_time_semantics_v1`, an IANA timezone, a tzdb version, and `availability_comparison: LT|LE`. Its `roles` map contains one exact, sourced binding for every timestamp column. Different roles may have equal timestamp values but may not alias one consumed field. `EVENT_TIME.source_field` and `VENDOR_AVAILABLE_TIME.source_field` must equal the raw field names frozen in the selected contract source.

For `quant_contract_v2`, prose rules require `contract_interpretation.status: PASS` plus a SHA-256 of each exact contract text at:

- `time_semantics.prediction_time`
- `time_semantics.data_cutoff_rule`
- `time_semantics.availability_rule`
- `time_semantics.execution_time_rule`
- `time_semantics.label_start_rule`
- `time_semantics.label_end_rule`
- `time_semantics.holding_period`
- `scope.universe.definition`
- `scope.universe.pit_membership_rule`
- the selected `data.sources[*].revision_policy`
- `target.corporate_action_rule`
- `target.overlap_rule`
- `splits.purge_embargo_rule`
- `splits.sample_dependency.purge_rule`
- `splits.sample_dependency.embargo_duration`
- `splits.sample_dependency.embargo_basis`

`contract_interpretation.resolved` must bind the executed `availability_comparison`, mark both revision and universe policies `PASS`, and set `population_history_mode` equal to the executed request/authority mode. Production embargo duration must use canonical `<N> eligible trading days` text. Its machine-parsed integer must equal `embargo_sessions`; `embargo_basis_sha256` must bind the exact frozen basis text; `embargo_implementation` must be `UNASSIGNED_SPLIT_GAP`; and `boundary_calendar_complete: true` plus `boundary_calendar_sha256` must bind the audited calendar. These hashes bind an explicit interpretation; they do not prove that a human interpretation of unrestricted prose is correct.

The resolved interpretation also binds
`label_schedule_receipt_hash`. Semantic authorization lives in the separate
schedule and review-authority artifacts described below; it is not a
self-asserted field inside `time_semantics.json`.

### Calendar

`calendar.csv` has exactly `session_id,open_time,close_time,break_start,break_end`. It represents the declared calendar version, including early closes and breaks. Open/close and non-null break times are offset-aware. Each session requires `open_time < close_time`; a non-null break requires both endpoints and `open < break_start < break_end < close`. Sessions ordered by open time must not overlap: every next open is at or after the prior close.

### Label

`label_definition.json` uses `schema_version: pit_label_definition_v1`, `label_id`, structured `definition`, `source_locator`, `interval_closure: LEFT|BOTH`, `overlap_policy: NO_CROSS_SPLIT_OVERLAP`, and exact `purge_rule`, `purge_embargo_rule`, `embargo_duration`, and `embargo_basis` text copied from the contract adapter.

Its `contract_bindings` contains SHA-256 values over the exact contract target formula, neutralization rule, corporate-action rule, overlap rule, purge rule, purge/embargo rule, embargo duration, and embargo basis. `label_id` and `label_spec_version` also equal the frozen target. A missing binding is `NEEDS_EVIDENCE`; a mismatch is `FAIL`.

`label_spec_hash` is SHA-256 over canonical JSON of the entire definition artifact excluding `label_spec_hash`. It must match the request and frozen contract.

### Executable label schedule and authorities

`label_schedule.json` is separate from the label definition so the label
specification can be frozen before its timestamps are resolved. It uses
`schema_version: pit_label_schedule_v1`, immutable `schedule_id` and `version`,
one mode, and a canonical `receipt_hash`. It binds:

- contract adapter, ID, canonical hash, and SHA-256 values for the exact
  prediction, execution, label-start, label-end, and holding-period rules;
- label ID, label-spec version, and label-spec hash;
- one mode-specific resolver; and
- a semantic-review receipt whose normalized resolver and contract-rule bundle
  hashes agree with the schedule.

The semantic review has
`trust_root_kind: HUMAN_SEMANTIC_REVIEW`,
`scope: CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY`,
`decision: APPROVED`, reviewer ID/authority, review time, required excluded
inputs (`data_rows`, `audit_status`, `backtest_results`), and its own canonical
receipt. A production QRC review must satisfy:

```text
contract.frozen_at <= semantic_review.reviewed_at <= request.run_at
```

Minimal common shape:

```json
{
  "schema_version": "pit_label_schedule_v1",
  "schedule_id": "immutable-schedule-id",
  "version": "1",
  "mode": "FROZEN_EXACT_INTERVAL_SET",
  "contract_binding": {
    "adapter": "quant_contract_v2",
    "contract_id": "contract-id",
    "contract_canonical_hash": "64hex",
    "rule_hashes": {
      "prediction_time": "64hex",
      "execution_time": "64hex",
      "label_start": "64hex",
      "label_end": "64hex",
      "holding_period": "64hex"
    },
    "rule_bundle_sha256": "64hex"
  },
  "label_binding": {
    "label_id": "label-id",
    "label_spec_version": "immutable-version",
    "label_spec_hash": "64hex"
  },
  "resolver": {
    "interval_authority_id": "authority-id",
    "interval_authority_version": "immutable-version",
    "interval_authority_artifact_sha256": "64hex",
    "interval_authority_receipt_hash": "64hex"
  },
  "semantic_review": {
    "trust_root_kind": "HUMAN_SEMANTIC_REVIEW",
    "scope": "CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY",
    "decision": "APPROVED",
    "reviewer_id": "reviewer-id",
    "reviewer_authority": "governance-authority-id",
    "reviewed_at": "offset-aware timestamp",
    "contract_rule_bundle_sha256": "64hex",
    "normalized_resolver_sha256": "64hex",
    "excluded_inputs": ["data_rows", "audit_status", "backtest_results"],
    "receipt_hash": "64hex"
  },
  "receipt_hash": "64hex"
}
```

`rule_bundle_sha256` is the canonical JSON hash of `rule_hashes`;
`normalized_resolver_sha256` is the canonical JSON hash of `resolver`. The
review receipt excludes only its own `receipt_hash`; the schedule receipt
excludes only the schedule's top-level `receipt_hash`. Missing or `AMBIGUOUS`
review is `NEEDS_EVIDENCE`; `REJECTED` or an unsupported decision is `FAIL`.

`review_authority.json` uses
`schema_version: pit_semantic_review_authority_v1`, immutable authority
identity/version, source URI, canonical receipt, and reviewer entries with
authorized scopes and half-open validity intervals. The reviewer and scope must
be authorized at `reviewed_at`.

Minimal review-authority shape:

```json
{
  "schema_version": "pit_semantic_review_authority_v1",
  "authority_id": "governance-authority-id",
  "version": "immutable-version",
  "source_uri": "governance://review-authority/version",
  "reviewers": [
    {
      "reviewer_id": "reviewer-id",
      "allowed_scopes": [
        "CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY"
      ],
      "valid_from": "2026-01-01T00:00:00Z",
      "valid_to": "2027-01-01T00:00:00Z"
    }
  ],
  "receipt_hash": "64hex"
}
```

Its `receipt_hash` excludes only the top-level receipt field. Reviewer
authorization uses `[valid_from, valid_to)` and does not authorize another
scope, reviewer, or time. `reviewer_id` is unique within one v1 authority;
duplicate authorization records are `FAIL` rather than being resolved by file
order.

The schedule supports two deliberately small execution modes.

#### Frozen exact interval set

`FROZEN_EXACT_INTERVAL_SET` uses the four-field resolver shown in the common
shape and binds this separate authority:

```json
{
  "schema_version": "pit_label_interval_authority_v1",
  "authority_id": "interval-authority-id",
  "version": "immutable-version",
  "source_uri": "governance://label-interval-authority/version",
  "population_manifest_sha256": "64hex",
  "expected_sample_count": 100,
  "expected_interval_set_sha256": "64hex",
  "generator": {
    "code_sha256": "64hex",
    "parameters_sha256": "64hex",
    "input_snapshot_sha256": "64hex",
    "source_locator": "immutable generator/run locator"
  },
  "receipt_hash": "64hex"
}
```

The authority receipt excludes only its top-level `receipt_hash`. Its
population hash must equal the exact audited population-manifest file. The
audited training CSV file hash cannot equal `generator.input_snapshot_sha256`;
this is only a direct circularity guard, not proof that the generator is
independent.

The interval-set digest is reproducible as follows:

1. For every fully parsed sample, form
   `(security_id, prediction_time, tradable_time, label_start_time,
   label_end_time)`.
2. Convert each timestamp to UTC and serialize it as offset-aware ISO-8601
   using `datetime.astimezone(timezone.utc).isoformat()`. The UTC suffix is
   `+00:00`, not `Z`; non-zero fractional seconds are retained.
3. Deduplicate identical five-string tuples, then sort the tuples
   lexicographically.
4. Convert each tuple to a JSON array and the complete ordered set to a JSON
   array. Encode canonical JSON as UTF-8 with object keys sorted,
   `ensure_ascii=false`, separators `,` and `:`, and no added whitespace.
5. SHA-256 those exact bytes. `expected_sample_count` equals the number of
   unique tuples.

The resulting digest must equal `expected_interval_set_sha256`, and the
materialized data must reproduce the complete frozen set.

#### Session close offsets

`SESSION_CLOSE_OFFSETS` uses exactly this resolver:

```json
{
  "calendar_id": "venue-calendar-id",
  "calendar_version": "immutable-version",
  "calendar_artifact_sha256": "64hex",
  "timezone": "IANA/Zone",
  "base_session_field": "calendar_session_id",
  "prediction_offset_from_session_open_seconds": 0,
  "execution_offset_sessions": 1,
  "execution_offset_from_session_open_seconds": 0,
  "start_offset_sessions": 1,
  "horizon_sessions": 5
}
```

Let `S[i]` be the row's `calendar_session_id` in sessions ordered by
`open_time`, and let `open(j)` and `close(j)` come from the exact bound
calendar. The executor resolves:

```text
prediction_time = open(i) + prediction_offset_from_session_open_seconds
tradable_time   = open(i + execution_offset_sessions)
                  + execution_offset_from_session_open_seconds
label_start_time = close(i + start_offset_sessions)
label_end_time   = close(i + start_offset_sessions + horizon_sessions)
```

All offsets are non-negative non-boolean integers and `horizon_sessions` is
positive. Prediction and execution must lie inside their resolved sessions,
execution must also satisfy the calendar break predicate, label start cannot
precede execution, and every resolved timestamp must exactly equal the
consumed row. Insufficient future-calendar coverage is `NEEDS_EVIDENCE`;
invalid offsets, contradictory bindings, or timestamp mismatches are `FAIL`.

All v1 schedule objects and related authority artifacts described here are
closed schemas. The only permitted keys are those shown above for the schedule,
`contract_binding`, `rule_hashes`, `label_binding`, the selected resolver,
`semantic_review`, `review_authority`, each reviewer,
`label_interval_authority`, and its generator. A key from the other resolver
mode or any unknown key is `FAIL`; v1 never ignores extension metadata. A
future field, resolver, or semantic variant requires a new schema version,
explicit migration rules, and new adversarial tests. The interval-authority
artifact is required only for exact mode and should be absent from a
session-mode request.

File receipts do not by themselves prove organizational authority. Production
qualification therefore requires request-external runtime anchors:

```text
--trusted-review-authority-sha256 64hex
--trusted-semantic-review-receipt-sha256 64hex
--trusted-interval-authority-sha256 64hex   # exact mode only
```

The review-authority anchor identifies who may review; the semantic-review
receipt anchor pins the exact approved contract-rule bundle, normalized
resolver, reviewer, scope and review time. The operator obtains all applicable
values from governance outside the audit request and never derives them from
the request being audited. No applicable anchor yields `NEEDS_EVIDENCE`; a
supplied anchor that does not match yields `FAIL`. The internal synthetic
adapter remains test-only and cannot create a production trust anchor.

### Population authority and manifest

`population_source.json` is the independent authority snapshot. It uses `schema_version: pit_population_source_v1` and records `authority_id`, `version`, `source_uri`, `selection_rule_sha256`, `history_mode: PIT_HISTORY`, `includes_inactive_and_delisted: true`, `records`, and a canonical `receipt_hash`. Each source record contains `security_id`, offset-aware `prediction_time`, `security_status: ACTIVE|DELISTED|SUSPENDED`, boolean `eligible`, and an exact `source_locator`.

`population_manifest.json` is derived from that authority. It uses `schema_version: pit_population_manifest_v1` and records `population_id`, `version`, `source_uri`, `authority_source_sha256`, `selection_rule_sha256`, matching history/lifecycle declarations, expected counts, and the complete eligible key set. Each key contains `security_id`, offset-aware `prediction_time`, lifecycle status, and an exact source locator.

Each receipt is canonical SHA-256 over its artifact excluding `receipt_hash`. `expected_key_set_sha256` binds the sorted normalized manifest key set and `expected_status_counts` binds lifecycle composition. The contract universe hash and request `snapshot_sha256`, `authority_source_sha256`, and `universe_hash` all bind the exact authority-source file; IDs, versions, selection rule, history and lifecycle flags agree across authority, manifest, and request. The manifest keys/statuses and materialized data keys/statuses must equal the eligible authority records exactly. Metadata, synchronized self-declarations, or an empty eligible authority population cannot pass `U002`.

### Training-matrix manifest

`matrix_manifest.json` uses `schema_version: pit_matrix_manifest_v1`. It proves what cells should exist independently of the cells that happened to be materialized:

```json
{
  "schema_version": "pit_matrix_manifest_v1",
  "manifest_id": "immutable-matrix-id",
  "version": "1",
  "layout": {
    "mode": "RECTANGULAR",
    "applicability_rule": "ALL_FEATURES_APPLY_TO_EVERY_POPULATION_KEY",
    "applicability_rule_sha256": "64hex"
  },
  "sample_prediction_axis": {
    "population_manifest_sha256": "64hex",
    "population_manifest_receipt_hash": "64hex",
    "population_source_sha256": "64hex",
    "expected_security_time_keys": 20,
    "expected_key_set_sha256": "64hex"
  },
  "feature_axis": {
    "feature_spec_version": "immutable-feature-spec",
    "features": ["feature_a", "feature_b"],
    "expected_feature_count": 2,
    "feature_set_sha256": "64hex",
    "feature_semantics_sha256": "64hex",
    "feature_spec_hash": "64hex"
  },
  "label_axis": {
    "label_id": "frozen-label-id",
    "label_spec_version": "immutable-label-spec",
    "label_spec_hash": "64hex",
    "label_schedule_id": "immutable-schedule-id",
    "label_schedule_version": "1",
    "label_schedule_receipt_hash": "64hex",
    "prediction_time_rule_sha256": "64hex",
    "execution_time_rule_sha256": "64hex",
    "label_start_rule_sha256": "64hex",
    "label_end_rule_sha256": "64hex"
  },
  "expected_cell_count": 40,
  "expected_cell_key_set_sha256": "64hex",
  "receipt_hash": "64hex"
}
```

The sample axis binds the exact authority-backed population artifacts. The feature list is sorted, unique, non-empty, and its count is a non-boolean integer. `feature_semantics_sha256` binds the complete dictionary entry for every feature on that axis. Its `feature_spec_hash` must equal both the canonical `pit_matrix_feature_spec_v1` payload—including that semantic digest—and the feature-spec hash frozen by the research contract. The label axis binds the canonical label identity/version/hash, executable schedule identity/version/receipt, and the frozen prediction/execution/start/end rules.

For `RECTANGULAR`, the executor derives the expected set as the Cartesian product of the normalized population keys and frozen feature axis. It does not trust an enumerated cell list. The observed set at grain `(security_id, prediction_time_utc, feature_name)` must equal that expected set exactly, while all features for one sample must also share one split and label interval. Counts are non-negative, non-boolean integers, and the canonical sorted-set digests and manifest receipt must match.

`SPARSE_EXPLICIT` is reserved but cannot qualify in v1. A sparse input remains `NEEDS_EVIDENCE` until its applicability rule and complete expected-cell set are frozen through the upstream research contract and independently validated. Omitting the matrix manifest from a `FULL_TRAINING_INPUT` request is also `NEEDS_EVIDENCE`; a `SAMPLE_ONLY` request may omit it only for diagnostic rejection and can never pass.

### Contract adapters

- `quant_contract_v2` is the production adapter. This Skill consumes its frozen identity, source fields and revision policy, snapshot hashes, timezone/calendar, universe, label and target policies, split windows, purge, and embargo rules. For this adapter, `data.sources[*].snapshot_id` is the frozen source version and `scope.decision_calendar` must be canonical `<calendar_id>@<version>` so both request bindings are contract-controlled. It verifies the upstream official receipt but does not reimplement that Skill's canonicalizer.
- `pit_contract_binding_v1` exists only for deterministic synthetic tests. Its canonical hash is verified locally, the production CLI rejects it, and the internal test harness labels a successful run `TEST_ONLY`, never `QUALIFIED`.

If an intended source, label, universe, calendar, or time rule differs from the frozen contract, the result is `FAIL`; the only governance path is a new `quant-research-contract` Change Request.

## Fixed checks

| ID | PASS boundary |
| --- | --- |
| `I001` | Required files parse strictly; CSV headers are unique and every row width matches; exact data bytes bind to the declared snapshot path; exact hashes, artifact identities/versions, non-boolean counts, extraction identifiers, and matrix/schedule/authority receipts match. |
| `I002` | Adapter-authorized frozen contract/receipt, request-external review-authority, exact semantic-review-receipt and applicable interval-authority anchors, reviewer authorization/time, raw `source_field` mappings, interpretation hashes, and exact source, snapshot, feature-axis, label-axis, schedule, universe, calendar, and policy bindings match. |
| `S001` | Fixed schema and exact versioned semantics cover every matrix-axis feature; no proxy is used. |
| `T001` | Time roles are distinct and sourced; timestamps are offset-aware; IANA zone and tzdb version exist. |
| `T002` | `published <= vendor_available <= ingested <= parse_ready` holds for every row; `OBSERVED_BY_PREDICTION` also requires `event <= published`; market cutoff passes; system claim additionally places ingest/parse by prediction and binds historical object identity; prediction is no later than tradable time. |
| `T003` | Selected revision/vintage was known at prediction. |
| `U001` | Membership was announced by prediction and prediction lies inside `[effective_from,effective_to)`. |
| `U002` | Independent `pit_population_source_v1`, derived manifest, request/contract/matrix-axis hashes, and materialized keys/statuses agree exactly and cover PIT history, inactive securities, and delistings. |
| `C001` | Calendar provenance matches; session and break endpoints are strictly ordered; adjacent sessions do not overlap; tradable time is inside the exact or schedule-resolved execution session and outside breaks. |
| `M001` | Permanent identity is documented and valid at prediction. |
| `A001` | Adjustment mode agrees with documented basis; only `RAW` is allowed; `PIT_ADJUSTED` and `FULL_HISTORY_ADJUSTED` fail closed in v1. |
| `H001` | Halt/resume timestamps are causally ordered; no resume exists without a halt; intended trading waits for trade resume, never quote resume alone. |
| `Q001` | Primary key and analytical grain are unique, and observed matrix cells equal the independently derived population-by-feature set exactly. |
| `Q002` | Required values are present, declared types parse, and numerics are finite. |
| `Q003` | Sourced finite hard-domain declarations and value checks pass; permitted extremes are not labeled anomalous without a sourced ex-ante rule. |
| `L001` | Canonical label/schedule bindings hold; exact-authority tuples or session offsets reproduce prediction, execution, label start and label end; and all features for one security/prediction share one split and label interval. |
| `L002` | Exact purge/embargo policies bind; rows stay inside frozen split windows; no label enters another split; the canonical embargo count/basis bind and the clean calendar gap after `max(nominal boundary, latest left-split label_end)` satisfies it. Same-split concurrency is reported only. |

## Temporal predicates

With the frozen comparison (`<` for `LT`, `<=` for `LE`):

```text
MARKET_RECONSTRUCTIBLE:
  published_time and vendor_available_time [comparison] prediction_time

SYSTEM_REPLAYABLE:
  MARKET_RECONSTRUCTIBLE
  ingested_time and parse_ready_time [comparison] prediction_time
  ingestion_batch_id is present
  ingested_object_sha256 is a valid exact-object SHA-256

OBSERVED_BY_PREDICTION:
  event_time [comparison] prediction_time

all claims:
  published_time <= vendor_available_time <= ingested_time <= parse_ready_time
  if event_time_policy == OBSERVED_BY_PREDICTION:
    event_time <= published_time
  prediction_time <= tradable_time
  revision_known_time [comparison] prediction_time
  universe_announced_time [comparison] prediction_time
  universe_effective_from <= prediction_time < universe_effective_to
  identifier_valid_from <= prediction_time < identifier_valid_to
  prediction_time <= label_start_time < label_end_time
```

Open-ended `*_to` fields mean positive infinity only when the schema permits null and the exact structured dictionary policy is `OPEN_ENDED_POSITIVE_INFINITY`.

## Outputs and execution

For every parseable request, the script writes:

- `audit_manifest.json`: immutable identity, content SHA-256, `report_sha256`, claim, result, coverage, contract binding, matched runtime trust anchors, input lineage, all 17 checks, evidence digests, findings, limitations, and one minimal next action.
- `audit_report.md`: deterministic `pit_audit_report_v1` rendering of that same manifest.

Qualification is not inferred from `status` alone:

- production handoff requires `status: PASS`, `pit_qualification: QUALIFIED`, `evidence_ceiling: PASS`, `contract_binding.execution_boundary: PRODUCTION_CLI`, and `contract_binding.test_only_adapter: false`;
- an internal synthetic-adapter pass is labeled `TEST_ONLY`;
- `NEEDS_EVIDENCE` maps to `UNRESOLVED`;
- `FAIL` maps to `NOT_QUALIFIED`.

Every check `PASS` contains the verified data hash/version, source snapshot, dictionary ID/version/hash, semantic locators, checked row count, and evidence digest. Violation examples are capped; counts remain visible.

`content_sha256` is calculated over the manifest core before `audit_id` and hash fields are added. `report_sha256` binds the exact UTF-8 report bytes. The report must reproduce the content hash, audit ID, status, findings, lineage, and check evidence digests. Consumers reject any mismatch.

This executor certifies supplied-cell eligibility only. For a derived feature, the final handoff is a two-manifest bundle: this immutable PIT manifest/report pair plus the separately executed behavior manifest/report defined in `behavior_spec.md`. The behavior request binds the parent PIT audit; the PIT executor does not ingest or silently incorporate the later behavior result. A raw directly consumed value instead carries an explicit `NOT_APPLICABLE` behavior rationale at the orchestration layer.

The executor writes and fsyncs both files in a sibling staging directory, verifies the report digest, then atomically renames the directory to the requested output path. An existing non-empty output is never overwritten; neither file is treated as published before the directory rename succeeds.

```bash
python3 scripts/audit_pit.py audit_request.json \
  --output-dir new_empty_directory \
  --trusted-review-authority-sha256 64hex \
  --trusted-semantic-review-receipt-sha256 64hex \
  --trusted-interval-authority-sha256 64hex
```

Trust-anchor options are repeatable to support controlled key/authority
rotation. They are runtime inputs, not fields copied from
`audit_request.json`.

Exit codes: `0 PASS`, `2 NEEDS_EVIDENCE`, `3 FAIL`, `64 invocation/internal error`. The output directory must be new or empty so a prior audit cannot be overwritten silently.
