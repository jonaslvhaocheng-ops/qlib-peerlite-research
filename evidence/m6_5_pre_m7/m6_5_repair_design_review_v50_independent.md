# M6.5 v50 Independent R3 Design Review

- Reviewer context: `/root/m65_v45_adversarial_retry`
- Author context: `/root`
- Independence: distinct review context; this reviewer did not author v50
- Skill: `eng-review-design`
- Risk: `R3`
- Subject: `evidence/m6_5_pre_m7/m6_5_repair_change_design_v50.md`
- Subject SHA-256: `d056f83c4ecd2f5a4a135a0e5ff24bd46a510be6e9590f675627c268f9318f0e`
- Architecture: `evidence/m6_5_pre_m7/architecture_confirmation_v29.md`
- Observed quality-ledger revision: `272` from `m6_5_repair_change_design_v50_result.json`
- Review scope: the two P1 and one P2 findings from the independent v49 review
- Verdict: `PASS`

## Findings

No P0, P1, P2, or P3 findings.

## Closure assessment

### Caller-owned nested mutation — closed

v50 moves recursive validation, normalization, serialization, identity creation, and ownership transfer into
`RunIntent.__post_init__`. The object retains an owned recursively read-only Mapping/tuple/scalar snapshot and
a cached hash rather than caller-owned dictionaries. Mutation of the original top-level or nested containers
therefore cannot change the constructed object or its V2 identity. Mutation through the exposed snapshot is
required to fail.

This is a design conclusion only. The current `trial_ledger.py` still has the v49 shallow dictionaries and
recomputed property, and v50 accurately labels the immutable repair as not yet implemented.

### V2 recursive canonicalization — closed

The V2-only normalizer now explicitly:

- accepts exact JSON-shaped primitives, lists, and dictionaries;
- requires string keys;
- recursively NFC-normalizes keys and string values;
- rejects post-normalization key collisions;
- rejects cycles using the active recursion stack;
- rejects tuples, sets, bytes, custom mappings/encoders, non-JSON values, NaN, and infinities;
- serializes normalized plain values once with UTF-8, sorted keys, compact separators, and no NaN.

All rejection occurs during construction, before an object or downstream side effect exists. Keeping this path
local to V2 avoids changing the repository-wide serializer.

### V1 byte compatibility — closed

The unbound non-M7 V1 path retains the exact existing schema string, three-field payload, and
`canonical_json_bytes` call. The new private caches are specified as excluded from representation and equality,
and no global serializer change is proposed. The verification obligation includes a known-hash V1 regression
plus existing journal/CLI regressions.

### Class-only landed-state wording — closed

v50 explicitly states that the current production caller remains V1-shaped and that caller loading, journal
event V3, retained event V3, and complete authority-schema validation are not implemented by this slice. Its
implementation plan is prospective, and line 195 accurately states that the current code has not implemented
the immutable/canonical repair.

### Future event V3 feasibility — sufficient

The design retains per-binding canonical bytes and an owned immutable public snapshot. A later bounded event-V3
slice can embed values decoded from those canonical bytes or expose a dedicated snapshot export without reading
the caller's original object. That future API choice does not alter this slice's identity semantics and is
properly left to the explicitly non-goal event integration.

## P0–P3 summary

- P0: 0
- P1: 0
- P2: 0
- P3: 0

## Verdict

`PASS`

The design closes all three v49 findings without widening the architecture or claiming implementation that is
not present. Preserve the V2-local canonicalization boundary, the owned immutable snapshot, the cached identity,
and the byte-exact untouched V1 path during implementation and code review.

There are no unresolved blocking decisions in this design slice.

## Normalized design-review result

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 272,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "PASS",
  "reason_code": "V50_CLOSES_V49_RUN_INTENT_IDENTITY_FINDINGS",
  "summary": "V50 closes the v49 mutable-identity, V2 canonicalization, and landed-state findings: construction creates an owned deep-read-only canonical snapshot and cached V2 hash, rejects cycles/NFC collisions/non-JSON/nonfinite values before side effects, preserves the exact V1 serializer path, and explicitly leaves caller/event integration unimplemented.",
  "issue_type": null,
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_design_review_v50_independent.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v50.md",
    "evidence/m6_5_pre_m7/m6_5_repair_design_review_v49_independent_b.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v49.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v48.md",
    "evidence/m6_5_pre_m7/m6_5_normative_closure_manifest_v6.json",
    "evidence/m6_5_pre_m7/architecture_confirmation_v29.md",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "src/qlib_peerlite/governance/artifacts.py",
    "scripts/reconcile_trial_ledger.py"
  ],
  "blockers": [],
  "reviewed_design_evidence_hash": "sha256:d056f83c4ecd2f5a4a135a0e5ff24bd46a510be6e9590f675627c268f9318f0e",
  "independence": {
    "mode": "independent-agent",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/m65_v45_adversarial_retry"
  }
}
```

This review did not edit the quality ledger or any design/production source, and it did not run tests, replay,
fit, PIT, real-data access, CCC, or Gate work.
