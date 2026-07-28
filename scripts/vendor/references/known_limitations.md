# Known limitations

## Evidence ceilings

- Public release or exchange records can support `MARKET_RECONSTRUCTIBLE`; they cannot prove what a proprietary research system had received. `SYSTEM_REPLAYABLE` requires immutable internal ingestion/version evidence.
- SEC explicitly provides no exact timestamp for first web availability of filing content. Acceptance time plus a generic latency assumption cannot prove exact system arrival.
- Sampling can find counterexamples but cannot certify row-complete correctness. Any positive sampled result is capped at `NEEDS_EVIDENCE`.
- The independent population source prevents a manifest and consumed data from defining their universe in tandem, but it cannot prove that the upstream authority omitted no eligible security. Preserve the authority version, selection rule, lifecycle coverage, records, receipt and locators for independent challenge.
- A paired behavior replay can expose a future-sensitive pipeline, but a finite probe set cannot prove that every branch, cache, dependency or external state is future-independent. Its positive result remains supplemental `NOVEL_CANDIDATE` evidence.
- V1 can qualify only `IDENTITY_SNAPSHOT`, where the frozen source-snapshot hash is the exact consumed CSV hash. A container-to-extract path remains `NEEDS_EVIDENCE` until a separately governed extraction receipt binds source snapshot, query, output bytes and row count; v1 does not force equality silently or pretend that query metadata alone proves lineage.

## Data-source limits

- The public source set is strongest for U.S. equities and U.S. filings. Other venues, asset classes, auction rules, breaks, price limits, contract rolls and symbology require venue/product-specific evidence.
- Living vendor and exchange pages may change. A URL and retrieval date are contextual evidence, not a substitute for an archived methodology, extract ID or content hash.
- Vendor transformations, redistribution latency and overwritten histories may be undocumented. The Skill must leave those checks unresolved rather than infer them.
- Permanent identifiers are provider-specific. CRSP PERMNO evidence does not validate a different vendor's identifier or mapping table.

## Semantic and temporal limits

- No universal ontology resolves all vendor field meanings. The exact-semantics rule is deliberately conservative and remains `NOVEL_CANDIDATE` until adversarial tests show it neither accepts aliases nor rejects documented equivalence.
- V1 has no universal statistical outlier classifier. It rejects missing, non-finite, mistyped and sourced hard-domain violations, but it does not call a permitted extreme anomalous without a predeclared, source-backed rule.
- Historical timezone databases are themselves revised. Record the tzdb version used; very old local-time history may remain uncertain.
- Calendar validity is venue-, product- and session-specific. A daily close calendar does not establish intraday auction, quote or tradability semantics.
- Halt, quote-resume and trade-resume fields depend on feed definitions. If only one undifferentiated “resume” field exists, the result is `NEEDS_EVIDENCE`.
- Contract interpretation hashes prove that the reviewed prose has not changed; they do not prove that the structured interpretation is economically correct. V1 therefore requires an authorized reviewer, a validity interval, a review receipt, a request-external review-authority hash, and a second request-external hash for the exact semantic-review receipt. Subject to genuine external governance, the first proves that the reviewer was allowlisted and the second that those exact approval bytes were accepted; neither proves that the organization or reviewer is correct.
- The runtime verifies only membership in caller-supplied hash allowlists. It cannot prove that the caller obtained the authority, semantic-approval or interval allowlists independently rather than deriving them from the request. V1 uses governance-pinned hashes rather than reviewer public-key signatures. Distribution, approval, rotation and protection of those allowlists remain external controls.
- `semantic_review.excluded_inputs` and the review receipt hash-bind the reviewer's assertion; they cannot prove that a human review occurred, that the named reviewer controlled the identity, or that the reviewer did not inspect training rows, audit status or backtest outcomes.
- Exact label schedules bind a separately anchored interval-authority artifact and execute its full prediction/execution/label tuple set, but the executor does not rerun or authenticate the declared generator code, parameters or input snapshot. The generator and its upstream inputs remain challengeable trust roots.
- Requiring `generator.input_snapshot_sha256` to differ from the audited training CSV hash blocks only direct identical-byte self-reference. It does not establish independence from a copy, transform, synchronized extract, hidden service or coordinated generator.
- `SESSION_CLOSE_OFFSETS` intentionally covers a compact family: prediction and execution at session-open offsets, label start/end at session closes, including next-session execution. Auctions, volume-triggered clocks, intraday bars, non-close label endpoints, and multi-venue routing need a new resolver mode plus independent tests; they are not approximated by the closest offset.
- A mutation ledger proves internal consistency only to the extent that its record index is complete and bound to the raw snapshots. An omitted raw record, dishonest generator or hidden service call remains outside the proof unless independently attested.
- A rectangular matrix receipt assumes every declared feature applies to every eligible sample/prediction pair. V1 never qualifies `SPARSE_EXPLICIT`; a future extension would need the complete expected cell set and applicability rule frozen through the QRC feature specification plus new independent validation and attacks.

## Adjustment and label limits

- V1 accepts only `RAW`. It fails closed on `PIT_ADJUSTED` because the consumed-value view cannot independently recompute the adjustment, and on `FULL_HISTORY_ADJUSTED`, including returns with a claimed invariance test. Supporting either mode later requires an independently executable, source-bound transformation proof and new adversarial tests.
- Same-split label overlap is dependence, not automatically train/test leakage. Report it for weighting/effective-sample-size analysis; fail only forbidden cross-split interval overlap or a frozen contract violation.
- A fixed row gap is not a proof of non-overlap when horizons vary or calendars are irregular. Compare explicit label intervals.
- V1 executes production embargo only as `UNASSIGNED_SPLIT_GAP` with canonical `<N> eligible trading days` text, an exact basis hash, and a complete audited boundary calendar. The net gap begins after the later of the nominal boundary and the left split's latest consumed label end. Other grammars or implementations remain `NEEDS_EVIDENCE`.

## Scope

- The audit establishes evidence about supplied data and transformations; it does not prove economic usefulness, alpha, execution feasibility or production readiness.
- The fixed executor audits supplied final cells and does not by itself prove that feature code avoided future inputs. Derived-feature handoff additionally requires the separate behavior specification. A directly consumed raw value's `NOT_APPLICABLE` rationale is an orchestration-layer governance record in v1, not a machine-enforced PIT-manifest field.
- It does not train models. After failure it may propose only the smallest diagnostic or repair plan, and a repaired dataset requires a new audit identity and evidence chain.
- The standard-library reference executor materializes the consumed-value CSV and interval state in memory. It fails closed on resource exhaustion, but very large institutional matrices need a separately validated streaming or distributed executor that preserves the same hashes, checks and full-coverage receipt; v1 does not merge partition-level PASS results.
- The QRC path reruns the locally installed official strict validator and matches its validator/library bundle digest, but that installation remains a trust root, not a cryptographic signature or organizational attestation. The synthetic PIT receipt is never valid for a production QRC contract.
- Production `QUALIFIED` depends on request-external review-authority and exact semantic-review-receipt SHA-256 anchors, plus an interval-authority anchor in exact mode. With no applicable anchor the result is `NEEDS_EVIDENCE`; a mismatched supplied anchor is `FAIL`. Rotation and distribution of those anchors are organizational controls outside this Skill.
- The production adapter interprets QRC `snapshot_id` as the frozen source version and requires `scope.decision_calendar` in canonical `<calendar_id>@<version>` form. An older frozen contract that lacks those bindings remains `NEEDS_EVIDENCE`; repairing it requires a derived contract, not an audit-side assumption.
- `audit_report.md` is a deterministic view of `audit_manifest.json`; the manifest binds its exact bytes with `report_sha256`. Both files are fsynced in a sibling staging directory and published by one atomic directory rename. Atomicity still depends on local filesystem semantics, and either file is untrusted when separated from its pair.
