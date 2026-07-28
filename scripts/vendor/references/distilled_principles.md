# Distilled principles

These principles define the audit's evidence logic. They do not authorize model training or repair the source data.

## Verdict algebra

Each in-scope check returns one of:

- `PASS`: complete evidence at the declared claim level supports the check.
- `FAIL`: observed evidence contradicts a hard rule.
- `NEEDS_EVIDENCE`: a required semantic, version, population or receipt is absent or incomplete.

Overall status is `FAIL` if any check fails; otherwise `NEEDS_EVIDENCE` if any in-scope check needs evidence; otherwise `PASS`. A sample-only inspection can discover failures, but its best possible positive conclusion is `NEEDS_EVIDENCE`, never `PASS`.

## Claim levels

`MARKET_RECONSTRUCTIBLE` means the value can be reconstructed from versioned market/public/vendor evidence that was available before `prediction_time`.

`SYSTEM_REPLAYABLE` is stricter: it additionally proves that the exact value/version was present in the research system before `prediction_time`, using immutable ingestion or snapshot evidence. Market availability must never be promoted to system replayability.

## Check principles

| Principle | Operational rule | Checks | Basis |
|---|---|---|---|
| Immutable audit identity | Hash every input; rerun the locally installed official QRC validator; bind exact consumed bytes to an explicit snapshot path, source version to its frozen snapshot ID, and calendar ID/version to canonical contract text; bind the independent population, review and interval authorities, exact semantic-review receipt, derived manifests, feature semantics, target formula/policies, label definition and executable schedule. Production trust hashes come from runtime governance outside the request. Bind exact report bytes and publish both outputs atomically. Hash equality proves identity only. | I001, I002, U002 | ADAPTED |
| Exact semantics | Require a version-matched dictionary for every used field, including unit, basis, grain, time semantics and structured null-end policy; bind the full feature-semantic projection into the frozen feature specification. Similar names or values cannot substitute; null is not assumed to mean infinity. | I002, S001 | NOVEL_CANDIDATE / RG01 |
| Role-separated clocks | Preserve event, publication, prediction, execution/tradable, ingestion, label-start and label-end times independently, with timezone and tzdb version. Bind event and vendor-availability roles to the frozen raw `source_field`; hash-bind every production contract interpretation. | I002, T001, L001 | SOURCE_BACKED / ADAPTED |
| Availability at the claimed ceiling | Preserve `published <= vendor_available <= ingested <= parse_ready`; observed features also require `event <= published`, while known-future objects retain their separate rule. Market evidence meets the prediction cutoff; system evidence also binds the exact ingested object and its cutoff. | T002 | NOVEL_CANDIDATE / RG02 |
| Vintage before value | Select the latest eligible revision as of prediction time before aggregation; “latest today” is not historical PIT evidence. | T003 | SOURCE_BACKED |
| PIT universe | Resolve index or pool membership from versioned announcements and effective intervals, never from a current constituent list; hash-bind and review the frozen universe rule and execute the same PIT history mode. | I002, U001 | SOURCE_BACKED / ADAPTED |
| Full lifecycle population | Freeze independent `pit_population_source_v1`, derive `pit_population_manifest_v1`, and require exact authority/manifest/materialized key and status agreement. Contract/request universe hashes bind the authority file; synchronized declarations or an empty authority cannot pass. | U002 | SOURCE_BACKED / ADAPTED |
| Stable dated identity | Join on a stable security identifier and dated mappings; ticker, name and current CUSIP are not timeless keys. | M001 | SOURCE_BACKED |
| Versioned market clock | Use the venue/product/session calendar in force, including holidays, early closes and breaks; require `open < close` and strict containment/order for any break. | C001 | SOURCE_BACKED |
| Tradability state | Model halt, quote resumption and trade resumption separately and in causal order. Reject orphan/pre-halt resumes and require trade resume before intended trading; a quote is not proof of tradability. | H001 | SOURCE_BACKED |
| RAW-only adjustment gate | V1 accepts only `RAW` under its declared basis. It rejects `PIT_ADJUSTED` because the consumed view cannot recompute full PIT factor lineage, and rejects `FULL_HISTORY_ADJUSTED` because a boolean or arbitrary digest is not executable proof. | A001 | ADAPTED |
| Declared training-cell grain | Freeze the expected `(security, prediction, feature)` cells plus one global label binding before testing completeness and uniqueness. Never derive the feature axis from observed rows, silently retain one duplicate, or allow a coordinated row/feature omission. V1 leaves every sparse layout unresolved. | Q001, L001 | ADAPTED |
| Executable label time | Keep the label definition separate from a frozen schedule. Execute either an externally anchored exact tuple authority or versioned calendar offsets for prediction, execution, start and horizon; require authorized semantic review after contract freeze and before audit time. Missing authority or calendar coverage stays unresolved; conflicting bytes, bindings or times fail. | I001, I002, C001, L001 | ADAPTED |
| Hard quality versus unsupported anomaly inference | Required missing, non-finite, dtype, invalid finite-domain declarations and hard-domain violations fail. A permitted extreme is neither failed nor labeled anomalous without a sourced ex-ante rule. | Q002, Q003 | ADAPTED |
| Executed split isolation | Hash-bind target, overlap, purge and embargo text; keep predictions inside frozen windows; fail labels entering another split; accept only canonical eligible-day duration and its basis hash; count the clean gap after `max(nominal boundary, latest left-split label_end)`. Same-split concurrency alone is not leakage. | I002, L001, L002 | ADAPTED |
| Counterfactual pipeline replay | Bind the fixed PIT audit, source snapshots, code/query, parameters, environment, perturbation ledger and paired outputs. A future-only, later-revision or future-universe perturbation must not change protected historical feature keys or values. This is supplemental negative evidence, not a completeness proof. | B001-B004 | NOVEL_CANDIDATE / RG03 |

## Minimum evidence chain for a PASS

For each passed field and prediction timestamp, the report must be able to traverse:

`official local contract revalidation + receipt/contract hash → request-external review-authority + exact semantic-approval + applicable interval-authority anchors → authorized executable label schedule → label/policy hashes → allowed source and raw source_field → exact extract/hash → independent population authority → derived population/matrix manifests and consumed-key equality → schema/dictionary version → field/null/time semantics → executed availability/vintage/label/split/clean-embargo predicates → RAW gate → evidence digest → manifest content/report hashes → atomic output directory`

Missing any required link changes the check to `NEEDS_EVIDENCE` or `FAIL`; it must not be filled by inference.

For a derived feature in `CERTIFY`, preserve the fixed-audit manifest and the
separate behavior manifest. A fixed-audit `PASS` establishes supplied-cell
eligibility; a behavior `PASS` establishes only that the declared replay probes
left the protected prefix invariant. Neither status inherits or replaces the
other.

## Minimal failure response

On failure, identify the smallest evidence request or source correction that could resolve the failing check. Do not impute values, silently shift timestamps, replace fields, rebuild the universe speculatively or begin training.
