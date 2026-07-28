# Validation report

Certification date: `2026-07-27`  
Specification: `pit_audit_spec_v1`  
Request format: `pit_audit_request_v1`

## Certification status

| Layer | Status |
| --- | --- |
| Fixed PIT executor (`audit_pit.py`) | `CERTIFIED — BOUNDED REFERENCE IMPLEMENTATION` |
| Behavior replay executor (`audit_behavior.py`) | `TESTED — NOVEL_CANDIDATE` |
| Navigation and orchestration guidance | `FORWARD-TESTED — NOT MACHINE-CERTIFIED` |

The fixed executor is certified only for the schemas, modes, claims, checks,
execution boundary and trust roots defined in `audit_spec.md`. Given exact,
immutable, hash-bound inputs; successful official QRC strict revalidation; and
applicable authority and exact semantic-review-receipt hashes supplied by the
caller from outside the audit request, it deterministically applies its
declared rules and fails closed on missing evidence or contradictions.

This certificate does not prove that an authority artifact is true, that its
allowlist was independently governed, that a reviewer was independent or
actually performed the stated review, that an interval generator is correct,
that a vendor or population authority is complete, or that no future
information bypassed the audited artifacts. It does not certify alpha, a model,
execution feasibility, deployment, or a capital decision. SHA-256 proves byte
identity, not truth.

## Final gate results

| Gate | Result | Evidence |
| --- | --- | --- |
| Official Skill structure | PASS | Official `quick_validate.py`: `Skill is valid!` |
| Syntax, system Python | PASS | Four scripts compiled with `/usr/bin/python3` |
| Syntax, bundled Python | PASS | Four scripts compiled with the bundled primary runtime |
| Fixed suite, system Python | PASS | 163/163 |
| Fixed suite, bundled Python | PASS | 163/163 |
| Synthetic adapter cases | PASS | 117/117: 89 declared fixtures plus 28 generated critical-binding probes |
| Production QRC registry | PASS | 46/46; fixed count, unique IDs/variants and digest |
| Critical-binding mutation gate | PASS | 29/29 targeted bindings: 28 digest-pinned table probes plus one official QRC contract-hash variant |
| Behavior replay suite | PASS | 18/18 |
| Fixed PIT check inventory | PASS | Exactly 17 unique checks in every fixed manifest |
| Output consistency | PASS | Manifest, report, check and semantic-trace hashes are independently recomputed |
| Deterministic replay | PASS | Identical inputs in another directory retain identity and report hash |
| Publication safety | PASS | Sibling staging, fsync, atomic directory rename and non-empty-target refusal are exercised |
| Production forward test | PASS | Official frozen QRC, runtime authority anchors, 17/17 checks, `QUALIFIED` |
| Independent red-team replay | PASS | Reproduced forged approval, snapshot drift, duplicate-CSV, schema-shadowing and overlapping-session cases fail after remediation |

Certified implementation snapshot:

| Component | SHA-256 |
| --- | --- |
| `SKILL.md` | `74ace3ccf09c946fa5f4745b1896109344698075dd17a5961f4612cd17f4bcb3` |
| `scripts/audit_pit.py` | `a617a49ff0f043b7cf7ff74e4843b381b6da7815053bb6ab185ccc3ad6135100` |
| `scripts/run_tests.py` | `458abf1e0535b93dcd3ec847a13a77623184bd26cdc0bc65172941a7551a95d9` |
| `scripts/audit_behavior.py` | `e79a1a2bdae5167ab74db73b14c513877c14e5e8cb191821693c6e804a8954d1` |
| `scripts/run_behavior_tests.py` | `70db982bb2fad809cca2f3cf153fcf1789357c9ae690f6ce0308f447540a046e` |
| `references/synthetic_cases.json` | `88513e64cc3d198a58dd3a106352be4ca999934839b3554e8f25bfa3e2194ada` |
| `references/audit_spec.md` | `defd89a3fdb9807d7bc708315f62df71ee88463e226b51bffa37cbb9e636335a` |
| `references/behavior_spec.md` | `ce321adb33d941c4b5db66a40ec771ed565e7d961272d61e4658f5739e4f412b` |
| Installed QRC validator bundle | `6dbb4fe1eb929a368b9608a7944c8ba3ae4b14d30cc07d9ff7b091dfefaeeb0b` |

Registry pins:

- Synthetic base case: SHA-256
  `1ccbe716d1ae1fc3324115beb5d580178bc39d8d49dbbdc9eee16eaf7c10f445`.
- Synthetic cases: `89`;
  SHA-256 `e493e231f6c7408578256c6a5e2ed0e6efaced42019716630d68f785b8e0684a`.
- Critical-binding mutations: `28`;
  SHA-256 `d3cc463f2a7863155b2c1f373210106f634a51cc4f52ca2b0fa459702c0d88c4`.
- Production QRC cases: `46`;
  SHA-256 `f1922ab52556439d33e91c6775eba3f6311f955ca311deff9a6f006605eef8ff`.

The 163 fixed cases comprise 13 expected `PASS` controls, 21 expected
`NEEDS_EVIDENCE` ceilings and 129 expected hard failures. The 89 declared
synthetic specifications live in `synthetic_cases.json`; 28 compact,
digest-pinned mutation descriptors are expanded from approved clean/session
templates; and the 46 production cases are the fixed `QRC_CASES` registry in
`scripts/run_tests.py`. The behavior suite is separate and does not upgrade the
fixed executor's result.

## High-risk boundaries exercised

| Boundary | Representative executable cases |
| --- | --- |
| Future availability and clock order | `future_feature_availability`; `inverse_availability_pipeline_clocks`; production QRC clock variants |
| Snapshot and parser integrity | consumed-value drift under a frozen snapshot; explicit identity/derived-extract modes; duplicate data/calendar headers; extra and missing CSV cells |
| Filing and field semantics | `filing_period_end_masquerades_as_release`; source-field and comparator conflicts |
| PIT universe and survivorship | `future_universe_announcement`; `survivor_population_omission`; coordinated data/manifest deletion |
| Adjustment basis | `future_full_history_adjustment`; arbitrary `PIT_ADJUSTED` value attacks |
| Calendar and tradability | early close, reversed break, equal open/close, `overlapping_calendar_sessions`, halt/resume attacks |
| Label timing and split leakage | cross-split overlap, purge/embargo conflicts, schedule horizon and execution-offset attacks |
| Executable label schedule | exact tuple digest, next-session execution, calendar-coverage ceiling and cross-mode field rejection |
| Authority governance | missing/mismatched runtime anchors, forged authorized-review receipt, review before contract freeze, unauthorized reviewer, duplicate reviewer ID |
| Closed v1 schemas | `exact_schedule_unknown_field_rejected`; review-authority and interval-generator shadow-field attacks |
| Matrix completeness | rectangular omission, sample-axis tamper, feature-semantic tamper, schedule binding and cell-digest tamper |
| Numeric and JSON validity | NaN, Infinity, duplicate JSON keys, boolean bounds and finite in-domain extremes |
| Claim boundary | market reconstruction versus system replay, missing ingestion receipt and explicit claim downgrade |

The combined fixed suite locks all four session-schedule timestamps, all
sample-axis hashes/counts, feature identity/version/hash/count/set bindings,
all label-axis identity/schedule/rule bindings, rectangular applicability, and
every closed schedule sub-schema. Retained controls cover execution time,
matrix count and schedule receipt; the 28 compact probes fill the prior
field-level gaps. The official QRC variant separately locks the contract-side
feature-spec hash that the synthetic fixture generator normally derives
automatically.

Every expected favorable case must trace each fixed check to artifact versions
and hashes, exact field semantics, source locators and external policy bindings.
A synthetic favorable case remains `TEST_ONLY`; only the production QRC path
can emit `QUALIFIED`.

## Label-schedule and trust-root validation

The fixed executor runs both supported schedule modes:

- `FROZEN_EXACT_INTERVAL_SET` compares the complete sorted unique tuple set
  `(security, prediction, execution, label start, label end)` with an
  independently bound interval-authority digest.
- `SESSION_CLOSE_OFFSETS` resolves prediction, execution, label start and label
  end against one exact calendar, including next-session execution and
  insufficient-horizon ceilings.

Production QRC qualification requires
`contract.frozen_at <= semantic_review.reviewed_at <= request.run_at`.
Review authority and the exact semantic-review receipt must match hashes
provided through the CLI outside the request; exact mode also requires the
interval-authority hash. Missing applicable anchors yield `NEEDS_EVIDENCE`;
mismatched anchors, duplicate reviewer identities, unknown v1 keys and binding
conflicts yield `FAIL`.

## Behavior-layer result

The behavior executor passed 18/18 deterministic checks for artifact and
receipt binding, ledger scope, parent PIT qualification, and protected
key/value invariance across the declared probes. It does not execute arbitrary
feature code or prove cache isolation. It remains `NOVEL_CANDIDATE`: a finite
artifact replay can expose declared prefix/full-input inconsistencies but
cannot prove that every branch, external service, cache or hidden dependency is
future-independent. Derived-feature handoff therefore preserves the fixed PIT
and behavior manifests separately.

## Forward test

A fresh non-capital production fixture was built from the installed
`quant-research-contract` Skill, frozen, strictly revalidated, bound to
request-external review-authority, exact semantic-review-receipt and
interval-authority hashes, and executed through the public CLI.

- Result: `PASS`
- PIT qualification: `QUALIFIED`
- Checks: `17/17 PASS`
- Audit ID: `pit-audit-v1-b488f425b47b7bd5bc06267b8766aefa`
- Content SHA-256:
  `b488f425b47b7bd5bc06267b8766aefa595ff26199773bf28eb00d80bffabc43`
- Report SHA-256:
  `4120049ef76d6814ff449278d2d76c748d1a7d0fe85e0602ba4920b9cfc5ca22`

The fixture contains no real security, capital allocation or trading decision.
It validates the declared implementation boundary, not empirical market truth.

## Evidence audit

- 23 primary, standards-body, exchange, regulator, vendor-methodology or formal
  technical sources are mapped to checks.
- 13 evidence cards cover the fixed and behavior checks.
- Classification count: 5 `SOURCE_BACKED`, 5 `ADAPTED`, 3
  `NOVEL_CANDIDATE`.
- All three novel candidates carry a `RESEARCH_GAP`, minimal proposed rule and
  preset failure condition.
- Evidence cutoff: `2026-07-27`.

The evidence cards justify rules, not the truth of a supplied dataset.
`source_map.md` records source versions and use boundaries.

## Reproduction commands

Run from the Skill root:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pit-system-pycache \
  /usr/bin/python3 -m py_compile \
  scripts/audit_pit.py scripts/run_tests.py \
  scripts/audit_behavior.py scripts/run_behavior_tests.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 scripts/run_tests.py

PYTHONPYCACHEPREFIX=/private/tmp/pit-bundled-pycache \
  /Users/jonas/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m py_compile \
  scripts/audit_pit.py scripts/run_tests.py \
  scripts/audit_behavior.py scripts/run_behavior_tests.py
PYTHONDONTWRITEBYTECODE=1 \
  /Users/jonas/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_tests.py

jq -e . references/synthetic_cases.json
ruby -ryaml -e \
  'YAML.safe_load(File.read("references/evidence_cards.yaml"), aliases: false)'

UV_CACHE_DIR=/private/tmp/pit-uv-cache uv run --with pyyaml python \
  /Users/jonas/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

## Residual limitations

The complete ceilings are normative in `known_limitations.md`. In particular,
the executor does not authenticate the organizational origin of runtime
allowlists, rerun the exact-interval generator, prove the truth or completeness
of external authorities, or certify distributed/partitioned execution. None of
those limits is silently promoted to `PASS`.
