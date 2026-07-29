# RunIntent V2 Independent R3 Code Review — R2

## Findings

No P0, P1, P2, or P3 findings.

The previous sole P2,
`RUN_INTENT_V2_CONSTRUCTOR_TYPE_CONTRACT_MISMATCH`, is closed.

## Verdict

`PASS`

- P0: 0
- P1: 0
- P2: 0
- P3: 0

This is a code-review PASS for the bounded RunIntent slice at source digest
`sha256:8968e7b8e172ceea730e4251cb90a8d902e46ffa406da3fb4fe47b32e950f477`.
It is not an M6.5 phase PASS and does not authorize replay, fit, PIT, real data, budget mutation, CCC, Gate,
caller/event-V3 integration, or final OOS.

## Scope reviewed

- `src/qlib_peerlite/governance/trial_ledger.py`, limited to lines 69-138 and 180-330 plus immediate existing
  identity consumers.
- `tests/test_m65_expected_red.py`
- `tests/test_run_intent_v2.py`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/test_run_intent_v2_coverage_edges.py`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/verify_run_intent_v2_coverage.py`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/run_intent_v2_coverage.json`
- Current constructor-repair implementation and tests-green receipts.

Reviewer context: `/root/m65_v25_design_review`  
Author/implementation context: `/root`  
Independence: distinct read-only reviewer context.

## Evidence checked

### Previous P2 closure

- `RunIntent.__init__` now declares both constructor inputs as exact
  `dict[str, Any] | None`, matching v50 and the runtime exact-type checks.
- Normalized snapshots are owned by private
  `_budget_limit_binding` and `_market_state_authority_binding` fields.
- Public `budget_limit_binding` and `market_state_authority_binding` are getter-only properties returning
  `Mapping[str, Any] | None`.
- The API regression independently checks the constructor type hints, property descriptors, and property return
  hints. Its expected-red receipt records the former Mapping/dict mismatch before the repair.

### Frozen dataclass semantics

- The custom initializer assigns every frozen dataclass field on each successful V1/V2 path using
  `object.__setattr__`; no caller-owned authority container is retained.
- Equality remains content-based because both private frozen snapshots retain the default `compare=True`.
- Canonical binding bytes and cached content hash remain `compare=False` and `repr=False`, so implementation
  caches do not alter logical equality or representation.
- The private snapshots are `repr=False`; generated repr remains stable and contains only the three public core
  identity inputs. The two read-only properties remain the supported authority-view API.
- MappingProxy/tuple/scalar recursion continues to prevent mutation through either public property.

### Identity and canonicalization

- The historical V1 branch retains the same schema string, three-field payload, global serializer call, and
  known SHA-256 regression.
- The V2 full payload, recursive exact-JSON validation, NFC normalization/collision rejection, cycle handling,
  per-binding bytes, and cached content hash are unchanged from the reviewed v50 implementation.
- The known V2 hash, authority sensitivity, caller-alias mutation, exposed deep immutability, dict/list cycles,
  shared acyclic child, nonfinite/unsupported values, and NFC cases remain covered.

### Fresh execution evidence

- Current `trial_ledger.py` SHA-256:
  `5ae99fc9f870937b2db518703e07d18db9bbf7dac8facbdca0432ade07b5de94`
- Current `tests/test_run_intent_v2.py` SHA-256:
  `84265bc443db7a4b405d54610c131db311128f1750bdbd0c2900379383aaef66`
- Current coverage JSON SHA-256:
  `ea7f099b9ccf53412ef4b6bf79aaab1a0d5b92c077bee05cb6eecf299b7e034e`
- Controller evidence at the reviewed source digest reports:
  - API regression: 1 passed;
  - instrumented RunIntent V2 suite and edge probes: 27 passed;
  - focused RunIntent/ledger/CLI regression: 34 passed;
  - full repository regression: 86 passed;
  - Ruff: PASS.
- Direct inspection of the raw coverage JSON shows no missing line or branch in protected ranges 69-138 and
  180-330. Those ranges accurately contain the normalizer/freezer and complete custom RunIntent initializer,
  properties, and cached identity seam.
- The quality ledger currently records revision 302 and the exact reviewed source digest.

## Residual risks / unverified items

- Supplied execution receipts were inspected but not rerun by this read-only reviewer.
- Full authority-schema validation, M7 caller loading, journal/retained event V3, and empirical execution remain
  explicit future work and are not proven by this PASS.
- Existing V1 callers are the only repository call sites; no caller consumes the future V2 properties yet.

## Normalized code-review result

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 302,
  "stage_id": "code-review",
  "skill": "eng-review-code",
  "mode": "review",
  "verdict": "PASS",
  "reason_code": "RUN_INTENT_V2_CONSTRUCTOR_API_P2_CLOSED",
  "summary": "The sole prior P2 is closed: RunIntent now exposes exact-dict constructor parameters and separate read-only Mapping properties backed by owned frozen snapshots. Custom frozen-dataclass equality, repr and field ownership are coherent; V1/V2 hashing and canonicalization are unchanged; fresh 27/34/86, Ruff and protected branch-coverage evidence bind the reviewed source digest.",
  "issue_type": null,
  "artifact_paths": [
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/code_review_run_intent_v2_r2_independent.md"
  ],
  "evidence_paths": [
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/code_review_run_intent_v2_independent.md",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/tests_red_constructor_api_v4.md",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/implementation_constructor_api_repair.md",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/tests_green_constructor_api_repair.md",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/run_intent_v2_coverage.json",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/verify_run_intent_v2_coverage.py",
    "docs/quality/changes/m6-5-pre-m7-repair/evidence/test_run_intent_v2_coverage_edges.py",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v50.md",
    "evidence/m6_5_pre_m7/m6_5_repair_design_review_v50_independent.md",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "tests/test_m65_expected_red.py",
    "tests/test_run_intent_v2.py"
  ],
  "commands": [
    "read-only source, call-site, hash, quality-ledger, receipt and raw coverage-JSON inspection"
  ],
  "blockers": [],
  "subject_digest": "sha256:8968e7b8e172ceea730e4251cb90a8d902e46ffa406da3fb4fe47b32e950f477",
  "independence": {
    "mode": "independent-agent",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/m65_v25_design_review"
  }
}
```

No product, test, design, quality-ledger, replay, fit, PIT, real-data, budget, CCC, Gate, or final-OOS artifact
was modified or executed by this review.
