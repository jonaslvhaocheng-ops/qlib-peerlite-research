# RunIntent V2 Independent R3 Code Review

## Findings

### [P2] Make the constructor annotation match the exact-dict input contract

- Location: `src/qlib_peerlite/governance/trial_ledger.py:187-188,244-247`
- Trigger: A typed caller supplies a `Mapping[str, Any]` that is not an exact built-in `dict`, such as
  `MappingProxyType` or `UserDict`, as either authority binding.
- Impact: The public dataclass signature declares the input valid, but construction raises `TypeError`. This
  makes the RunIntent API internally inconsistent and leaves a hidden caller decision before the later
  composition-root/event-V3 slice. The mismatch is especially relevant because the post-construction attribute
  intentionally is a read-only `Mapping`, while v50 separately fixes the constructor input as
  `dict[str, Any] | None`.
- Evidence: v50 lines 94-102 distinguish the exact-dict constructor interface from the post-construction
  read-only Mapping/tuple view. The implementation annotates both init fields as `Mapping[str, Any] | None` but
  rejects anything whose exact type is not `dict`. Current tests exercise the runtime rejection only; they
  cannot detect that the declared constructor API admits the rejected values.
- Direction: Preserve the v50 exact-dict runtime rule and expose an init signature that declares exact dict
  inputs, while retaining read-only Mapping-valued properties after construction. A custom initializer,
  `InitVar` plus private frozen storage, or an equivalent bounded representation is sufficient. Add an API-level
  regression that checks the constructor contract without widening accepted runtime types.

## Verdict

`NEEDS_CHANGES`

- P0: 0
- P1: 0
- P2: 1
- P3: 0

Earliest repair issue: `product-code` (with a matching API/test assertion). This review does not authorize or
assess replay, fit, PIT, real data, budget mutation, CCC, Gate, caller/event-V3 integration, or final OOS.

## Scope reviewed

- Source digest:
  `sha256:1f471d4195d93c27f1db31e2158205c97dc8dda371f3e46787c26d4c072779a7`
- `src/qlib_peerlite/governance/trial_ledger.py`: RunIntent V2 normalizer, freezer, cached bytes/hash, public
  dataclass surface, and existing identity consumers.
- `tests/test_m65_expected_red.py`
- `tests/test_run_intent_v2.py`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/test_run_intent_v2_coverage_edges.py`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/verify_run_intent_v2_coverage.py`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/run_intent_v2_coverage.json`

Reviewer context: `/root/m65_v25_design_review`  
Author/implementation context: `/root`  
Independence: distinct read-only reviewer context.

## Evidence checked

- v50 design SHA-256:
  `d056f83c4ecd2f5a4a135a0e5ff24bd46a510be6e9590f675627c268f9318f0e`
- Independent v50 design PASS SHA-256:
  `8c9bb077e26d95de71793ae7f373ed11d8986b4571f072afee1af551ef327d19`
- Current `trial_ledger.py` SHA-256:
  `f550bc9aa57c76b4683adff47a4f896a9b156b365c9672c5645f800c79b015eb`
- Current test SHA-256 values:
  - `tests/test_m65_expected_red.py`:
    `0cf121359cc0ff317f9667ffae507249469a44258f7c28487308347fdcb0639f`
  - `tests/test_run_intent_v2.py`:
    `44c3fbdddc9788dd86d734327d082dab1b373c2b1dc1099faf0f32dcff625a45`
- Tests-green receipt and implementation evidence both bind the requested source digest.
- Coverage JSON SHA-256:
  `4763f878c9da952ac11af59c00a94fe3ec436a8a210c4478eddd3c8a814e34aa`.
  Its raw missing-line and missing-branch lists contain no entries in protected ranges 69-138 and 180-295;
  those ranges accurately cover the recursive normalizer/freezer and RunIntent construction/cache seam.
- The supplied receipts report 26 instrumented RunIntent/edge tests, 33 focused regression tests, 85 full-suite
  tests, and Ruff success, with source digest unchanged before/after the protected commands.

## Preserved strengths

- The V1 path retains the historical three-field payload, schema string, serializer, and hard-coded known hash.
- V2 rejects exact-type violations, non-string keys, nonfinite floats, unsupported objects, direct/indirect
  dict cycles, and list cycles; repeated acyclic aliases remain valid.
- NFC normalization covers nested keys and values, and normalized-key collisions fail at construction.
- Owned normalized containers are recursively frozen as MappingProxy/tuple/scalars; cached binding bytes and
  content hash are excluded from equality and repr.
- `content_sha256` returns the construction-time cached value.
- Existing callers remain V1-shaped and no M7 loader, journal/event V3, replay, fit, PIT, data, CCC, or Gate path
  was added in this slice.

## Residual risks / unverified items

- The supplied execution receipts were inspected but not rerun in this read-only review.
- Full authority-schema validation and byte-identical event-V3 embedding remain explicit future work and are not
  evidence supplied by this slice.
- The coverage verifier relies on the router receipt to bind the regenerated report to the source digest; the
  current receipt and file hashes are consistent.

## Normalized code-review result

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 294,
  "stage_id": "code-review",
  "skill": "eng-review-code",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "RUN_INTENT_V2_CONSTRUCTOR_TYPE_CONTRACT_MISMATCH",
  "summary": "The V2 normalization, deep freeze, cached identity, V1 compatibility and protected coverage evidence are otherwise coherent, but RunIntent publicly annotates Mapping inputs while rejecting every non-exact-dict Mapping at runtime. Align the constructor API with the frozen exact-dict contract and add an API regression.",
  "issue_type": "product-code",
  "artifact_paths": [
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/code_review_run_intent_v2_independent.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v50.md",
    "evidence/m6_5_pre_m7/m6_5_repair_design_review_v50_independent.md",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/implementation_run_intent_v2.md",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/tests_green_run_intent_v2.md",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/run_intent_v2_coverage.json",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/verify_run_intent_v2_coverage.py",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/test_run_intent_v2_coverage_edges.py",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "tests/test_m65_expected_red.py",
    "tests/test_run_intent_v2.py"
  ],
  "commands": [
    "read-only source, call-site, hash, ledger, receipt and coverage-JSON inspection"
  ],
  "blockers": [
    "RunIntent authority-binding constructor annotation accepts Mapping while runtime and v50 require exact dict."
  ],
  "subject_digest": "sha256:1f471d4195d93c27f1db31e2158205c97dc8dda371f3e46787c26d4c072779a7",
  "independence": {
    "mode": "independent-agent",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/m65_v25_design_review"
  }
}
```

No product, test, design, quality-ledger, replay, fit, PIT, real-data, budget, CCC, Gate, or final-OOS artifact
was modified or executed by this review.
