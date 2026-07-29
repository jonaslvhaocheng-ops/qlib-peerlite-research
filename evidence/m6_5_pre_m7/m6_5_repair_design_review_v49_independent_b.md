# M6.5 v49 Independent Adversarial R3 Design Review B

- Reviewer context: `/root/m65_v45_adversarial_retry`
- Author context: `/root`
- Independence: distinct read-only review context; this review did not author v49
- Skill: `eng-review-design`
- Risk: `R3`
- Subject: `evidence/m6_5_pre_m7/m6_5_repair_change_design_v49.md`
- Subject SHA-256: `bac89c843cbb394240c852015b2eb910f5249f95564e231edd2d25dd13fadf4a`
- Architecture: `evidence/m6_5_pre_m7/architecture_confirmation_v29.md`
- Observed quality-ledger revision: `268` from `m6_5_repair_change_design_v49_result.json`
- Review scope: only RunIntent dual-authority presence/pairing and V1/V2 identity
- Verdict: `NEEDS_CHANGES`

## Findings

### [P1] Frozen RunIntent retains mutable authority dictionaries

**Section:** v49 “Data ownership and state transitions”, “Concurrency and idempotency”, and implementation steps 1–3.

**Scenario:** A caller constructs a fully bound intent, reads `content_sha256` to create a journal start, then mutates either the original nested dictionary or any nested list/dictionary retained by the intent. `@dataclass(frozen=True)` prevents field reassignment but does not freeze the dictionaries. Because `content_sha256` is a recomputed property, the same object now produces a different V2 identity.

**Impact:** The claimed immutable identity is not immutable. A later journal/reconciliation check can fail only after a durable journal side effect, or different consumers can observe different identities for the same `RunIntent`. This contradicts construction-time failure, idempotency, and the assertion that the object has no state transition.

**Evidence:** v49 lines 26–27, 84–85, 110–112, and 119–127; `trial_ledger.py` lines 107–115 and 146–164. The current expected-red test covers only an unbound M7 constructor and cannot expose post-construction mutation.

**Direction:** At construction, recursively validate and canonicalize both bindings, take an owned immutable snapshot (or canonical bytes), and cache the V2 identity from that snapshot. Do not retain caller-owned mutable containers as identity authority.

### [P1] V2 “canonical” identity does not meet the frozen canonical contract

**Section:** v49 “Constraints and assumptions” and “Interfaces and schemas”.

**Scenario:** A top-level `dict` contains non-string keys, a non-JSON value, or canonically equivalent Unicode strings in different NFC forms. It passes `RunIntent.__post_init__`; failure or identity divergence occurs only when `content_sha256` is later evaluated. The repository serializer sorts/compacts JSON and rejects NaN, but it does not NFC-normalize recursively.

**Impact:** Invalid V2 authority content is not rejected at the promised construction boundary, and logically equivalent normative bindings can receive different identities. Fixing the shared serializer globally would risk changing historical V1 hashes, so the design still leaves a material compatibility decision undocumented.

**Evidence:** v49 lines 26, 38–40, 82–85, and 119–127; `trial_ledger.py` lines 139–164; `governance/artifacts.py` lines 18–25; closure-v6 component contract requires UTF-8/NFC canonical JSON.

**Direction:** Specify a V2-only recursive canonicalization/validation rule, including string-key enforcement, NFC collision rejection, supported JSON value types, and construction-time serialization. Preserve the exact existing V1 payload and serializer path byte-for-byte.

### [P2] The design overstates the implemented caller and verification surface

**Section:** v49 “Success sequence”, “Verification obligations”, and “Implementation plan”.

**Scenario:** The only production composition caller, `scripts/reconcile_trial_ledger.py`, has no arguments or loader for either authority and always constructs an unbound intent. With the M7 family it can only fail; no current caller can execute the documented “load frozen authorities → fully-bound intent → start event” path. The sole new test checks only rejection when both bindings are absent.

**Impact:** Lines 182 and 191 characterize steps 1–4 and the slice as landed/PASS without repository evidence for V2 creation, V1 byte-compatible hashing, partial/type rejection, binding-mutation identity changes, or pre-side-effect integration. This is a design-evidence overclaim, even though deferring full recursive authority validation remains a valid scope choice.

**Evidence:** v49 lines 114–117, 162–182, and 189–192; `scripts/reconcile_trial_ledger.py` lines 36–60; `tests/test_m65_expected_red.py` lines 8–16; existing V1 caller coverage in `tests/test_trial_ledger.py` and `tests/test_reconcile_trial_ledger_cli.py`.

**Direction:** Label the current state as a RunIntent-class-only partial implementation until the bounded synthetic caller seam and the stated V1/V2 identity obligations exist. Do not claim the frozen-authority-to-start-event journey is landed.

## P0–P3 summary

- P0: 0
- P1: 2
- P2: 1
- P3: 0

## Verdict

`NEEDS_CHANGES`

Earliest repair issue: `RUN_INTENT_V2_IDENTITY_IS_SHALLOWLY_MUTABLE`.

The family-specific dual-presence rule, pairwise rejection, and preservation of the existing unbound V1 payload shape are good bounded choices and should be retained. No finding requests full binding-schema validation, replay, fit, PIT, data, CCC, or Gate work.

Unresolved decisions are limited to how V2 takes an owned immutable canonical snapshot while preserving exact V1 hashes, and how the document labels the not-yet-integrated caller/test state.

## Normalized design-review result

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 268,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "RUN_INTENT_V2_IDENTITY_IS_SHALLOWLY_MUTABLE",
  "summary": "The bounded dual-authority rule is directionally correct, but caller-owned mutable dictionaries make one RunIntent produce changing V2 hashes; V2 canonicalization is not construction-time/NFC exact; and current callers/tests do not support the document's landed integration claim.",
  "issue_type": "design",
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_design_review_v49_independent_b.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v49.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v48.md",
    "evidence/m6_5_pre_m7/m6_5_normative_closure_manifest_v6.json",
    "evidence/m6_5_pre_m7/architecture_confirmation_v29.md",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "src/qlib_peerlite/governance/artifacts.py",
    "scripts/reconcile_trial_ledger.py",
    "tests/test_trial_ledger.py",
    "tests/test_reconcile_trial_ledger_cli.py",
    "tests/test_m65_expected_red.py"
  ],
  "blockers": [
    "RUN_INTENT_V2_IDENTITY_IS_SHALLOWLY_MUTABLE",
    "RUN_INTENT_V2_CANONICALIZATION_IS_NOT_CONSTRUCTION_TIME_NFC_EXACT",
    "V2_CALLER_AND_VERIFICATION_SURFACE_NOT_LANDED"
  ],
  "reviewed_design_evidence_hash": "sha256:bac89c843cbb394240c852015b2eb910f5249f95564e231edd2d25dd13fadf4a",
  "independence": {
    "mode": "independent-agent",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/m65_v45_adversarial_retry"
  }
}
```

This review did not edit the quality ledger and did not run tests, replay, fit, PIT, real-data access, CCC, or Gate work.
