# M6.5 Pre-M7 Test Design V2 — RunIntent Immutable V2 Slice

- Stage: `test-design`
- Risk: `R3`
- Design basis: `m6_5_repair_change_design_v50.md`
- Parent portfolio: `m6_5_test_design_v1.md`
- Status: `PASS / TESTS_NOT_WRITTEN_OR_RUN`
- Boundary: pure synthetic RunIntent fixtures; no replay, fit, PIT, real data, budget mutation, CCC, Gate or OOS.

## 1. Scope

This v2 portfolio replaces the RunIntent portion of v1 for the currently implemented slice. It does not
authorize or claim implementation of the remaining v1 state, recovery, archive, replay, CCC, checkpoint, Gate
or screen rows.

Observable scope is limited to:

1. M7 dual-authority presence and pairwise/type rejection.
2. Construction-time V2 recursive JSON/NFC validation.
3. Owned, recursively read-only snapshots and cached identity.
4. Exact historical V1 identity and current ledger/CLI compatibility.
5. Honest class-only boundary: no M7 caller or event V3 path.

## 2. Behavior-to-test matrix

| ID | Behavior / invariant | Case | Layer | Fixture / input | Exact oracle | Isolation | Coverage obligation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RI-U1 | M7 requires both bindings before identity exists | decision table | unit | absent/absent, budget-only, state-only, non-dict top-level values | each invalid row raises `TypeError` during construction; no object returned | pure constructor | family, pairwise and both type branches |
| RI-U2 | Valid V2 identity is canonical and cached | success | unit | two minimal nested authorities with fixed ASCII values | hard-coded independently computed SHA256; repeated property reads identical | no mocks | V2 normalize/serialize/cache success path |
| RI-U3 | Caller mutation cannot alter snapshot or identity | metamorphic | unit | retain aliases to top-level dict, nested dict and nested list; mutate all after construction | fixed hash and snapshot values unchanged | pure in-memory aliases | copy ownership plus nested dict/list freeze |
| RI-U4 | Exposed snapshot is recursively read-only | failure | unit | assign top-level key, nested key and nested sequence element/append | mutation raises `TypeError` or immutable-sequence error; hash unchanged | no mocks | mapping and sequence immutable representations |
| RI-U5 | NFC is recursive and collision-safe | equivalence/failure | unit | composed/decomposed keys and values at two nesting levels; two raw keys collapsing to one NFC key | equivalent logical payloads share hard-coded hash and normalized snapshot; collision raises at construction with path | standard-library `unicodedata` only for fixture setup | key/value normalization and collision branch |
| RI-U6 | Unsupported JSON forms fail at construction | decision table | unit | non-string key; tuple/set/bytes/custom mapping/custom object; self-cycle and indirect cycle; NaN/±Infinity | each row raises `TypeError` before `content_sha256` access | tiny local fixture classes | every type, finite and active-recursion rejection branch |
| RI-U7 | Material authority changes alter V2 identity | metamorphic | unit | change one leaf independently in budget and state fixtures | each mutation yields a hash distinct from the fixed RI-U2 hash | fresh constructor per row | both binding contributions |
| RI-C1 | Historical V1 bytes and consumers remain unchanged | contract/regression | contract | existing non-M7 fixture plus fixed run/family/spec tuple | exact pre-change hard-coded V1 SHA; current journal validation and reconciliation CLI tests pass unchanged | existing tmp filesystem fixtures | V1 payload/cache path and all existing consumer paths |
| RI-S1 | No unimplemented M7 integration is exposed | static boundary | static | inspect current CLI/call sites and public module surface | no M7 authority loader, event V3, replay, fit or real-data call added by this slice | `rg`/AST inspection | scope boundary, not percentage-bearing |

## 3. Fixtures and independent oracles

- `minimal_budget_binding` and `minimal_state_binding` are small nested JSON objects with dict/list/string,
  bool, null, int and finite float coverage.
- Mutation fixtures retain every original alias so a shallow copy cannot pass.
- Cycle fixtures cover `d["self"] = d` and `a → b → a`; repeated non-cyclic shared children remain valid.
- V1 and V2 expected hashes are checked in as literal constants computed once with a small standard-library-only
  reference snippet. The tests must not call the production serializer to derive their expected value.
- NFC collision uses two distinct source spellings that normalize to the same key.
- Tests use no clock, randomness, filesystem, network, Qlib, Torch, model or database.

## 4. Planned test ownership

- Extend `tests/test_m65_expected_red.py` for the smallest expected-red identity-mutation case.
- Add the complete matrix to `tests/test_run_intent_v2.py`.
- Keep `tests/test_trial_ledger.py` and `tests/test_reconcile_trial_ledger_cli.py` unchanged as V1 integration
  regression evidence.

`eng-write-tests` owns RI-U/RI-C test code. Static RI-S1 can be recorded by code review and E2E acceptance; it
must not introduce a new runtime scanner.

## 5. Coverage obligations

Protected core for this slice:

```text
src/qlib_peerlite/governance/trial_ledger.py
```

All lines and branches newly introduced for recursive normalization, freezing, V1/V2 construction and cached
identity require 100% line and 100% branch coverage. Existing unrelated ledger/reconciliation code stays under
the full regression suite but does not need artificial tests solely to inflate this slice percentage. No
`pragma: no cover`, broad exclusion or assertion-free execution substitutes are allowed.

## 6. Critical synthetic acceptance journey

One bounded journey is sufficient:

```text
mutable nested authority inputs
→ construct fully-bound M7 RunIntent
→ capture stable identity and read-only snapshots
→ mutate all caller aliases
→ verify identity/snapshot unchanged
→ construct a second semantically NFC-equivalent intent
→ verify identical identity
```

The journey ends at `RunIntent`. It must not create a journal, ledger event, fit, replay receipt, state product
or model output.

## 7. Exit criteria

- Every RI row passes with deterministic error type and stable oracle.
- Exact V1 hash and all existing trial-ledger/CLI tests remain green.
- New RunIntent code reaches 100% line/branch coverage under the protected profile.
- Full pytest and Ruff pass.
- No M7 event, budget count, replay, fit, PIT, real-data or OOS artifact is created.

## 8. Verdict

`PASS`: v50 has a complete, executable and bounded test portfolio with explicit fixtures, independent oracles,
failure branches, compatibility proof and a class-only acceptance journey. The router may proceed to expected
red; production implementation is not yet authorized by this document.
