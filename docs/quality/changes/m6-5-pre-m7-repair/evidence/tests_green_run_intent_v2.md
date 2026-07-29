# Tests Green Evidence — RunIntent V2

- Change: `m6-5-pre-m7-repair`
- Mode: `green`
- Product source digest:
  `sha256:1f471d4195d93c27f1db31e2158205c97dc8dda371f3e46787c26d4c072779a7`
- Verdict: `PASS`

## Results

- Complete RunIntent V2 matrix plus two coverage-only edge probes: `26 passed`.
- Focused RunIntent/ledger/CLI regression: `33 passed`.
- Full repository regression: `85 passed`.
- Ruff on changed production and test surfaces: `PASS`.

## Protected coverage

Coverage was collected with `coverage run --branch` and pytest plugin autoload disabled, avoiding the local
pytest-cov/NumPy double-load conflict. Raw evidence is
`run_intent_v2_coverage.json`.

The verifier protects:

```text
trial_ledger.py lines 69–138   recursive V2 normalize/freeze helpers
trial_ledger.py lines 180–295  RunIntent V1/V2 construction and cached identity
```

Result:

```text
PASS: RunIntent V2 protected ranges have 100% line and branch coverage
```

The displayed whole-module percentage is intentionally not used: the focused command does not exercise
unrelated legacy reconciliation functions. Those functions remain covered by the full regression suite.

## Boundary

All tests are synthetic/in-memory or existing tmp-path ledger regressions. No M6 replay, model fit, PIT rerun,
database access, budget mutation, CCC/Gate execution or final-OOS access occurred.
