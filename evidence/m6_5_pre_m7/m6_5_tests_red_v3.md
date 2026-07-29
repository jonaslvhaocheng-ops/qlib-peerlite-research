# M6.5 Tests Red V3 — Complete RunIntent V2 Matrix

- Stage: `tests-red`
- Design: `m6_5_repair_change_design_v50.md`
- Test plan: `m6_5_test_design_v2.md`
- Product code changed in this stage: `no`
- Verdict: `EXPECTED_RED`

## Command

```text
.venv/bin/python -m pytest -q tests/test_m65_expected_red.py tests/test_run_intent_v2.py
```

## Observed result

- Exit code: `1`
- Tests: `15 failed, 9 passed`
- Intended failures cover:
  - caller-owned nested mutation changing V2 identity;
  - mutable exposed snapshots;
  - absent recursive NFC and collision handling;
  - unsupported JSON values, non-string keys, cycles and nonfinite numbers not rejected at construction.
- Passing rows confirm:
  - M7 missing/partial/top-level type rejection already works;
  - valid ASCII V2 currently matches the independent known hash;
  - both authorities contribute to identity;
  - the historical non-M7 V1 known hash remains exact;
  - repeated non-cyclic children are accepted.

## Test-code quality

```text
.venv/bin/python -m ruff check tests/test_m65_expected_red.py tests/test_run_intent_v2.py
```

Result: `All checks passed`.

## Red-test validity and boundary

Every failure is an approved v50 product behavior, not syntax/import/environment/harness failure. All fixtures
are in-memory JSON-shaped values; no journal, ledger, replay, fit, PIT, real data, budget count, CCC, Gate or
OOS path is called.

This complete expected-red portfolio authorizes only the router-selected v50 implementation.
