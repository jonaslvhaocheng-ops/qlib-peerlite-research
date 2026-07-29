# Implementation Evidence — RunIntent V2 Immutable Snapshot

- Change: `m6-5-pre-m7-repair`
- Design: `evidence/m6_5_pre_m7/m6_5_repair_change_design_v50.md`
- Scope: `RunIntent` class seam only
- Result: `PASS`

## Production change

Only `src/qlib_peerlite/governance/trial_ledger.py` changed:

- recursively validates exact JSON-shaped V2 values;
- NFC-normalizes keys and string values;
- rejects normalized-key collisions, cycles, unsupported objects and nonfinite floats at construction;
- takes an owned recursively read-only Mapping/tuple/scalar snapshot;
- caches per-binding canonical bytes and the full V2 identity;
- returns the cached identity on every access;
- preserves the exact V1 schema, payload and serializer path.

No M7 caller, journal/event V3, replay, fit, PIT, real-data, budget mutation, CCC, Gate or final-OOS path was
added.

## Verification

```text
.venv/bin/python -m pytest -q \
  tests/test_m65_expected_red.py \
  tests/test_run_intent_v2.py \
  tests/test_trial_ledger.py \
  tests/test_reconcile_trial_ledger_cli.py
```

Result: `33 passed in 2.81s`.

```text
.venv/bin/python -m ruff check \
  src/qlib_peerlite/governance/trial_ledger.py \
  tests/test_m65_expected_red.py \
  tests/test_run_intent_v2.py
```

Result: `All checks passed`.

```text
.venv/bin/python -m pytest -q
```

Result: `85 passed in 6.04s`.

## Coverage harness note

Two exploratory coverage invocations failed during collection because coverage instrumentation caused the
installed NumPy extension to report `cannot load module more than once per process`. The same tests pass without
instrumentation, so this is recorded as a coverage-harness issue, not a product failure or a coverage claim.
The router-selected tests-green stage owns a protected, reproducible coverage receipt; no percentage is claimed
here.

## Frozen boundaries

- M6 close remains SHA256
  `31a90d1ff506d9dfae48ab8bd191bf8ee9bbcbdc261c8f1acde9c3741992de93`,
  14,328 bytes, 6 candidate evaluations and 44 fits.
- M7 remains `NOT_RUN`; future ceiling remains 8/60.
- No training, replay, database, PIT, budget or OOS artifact was touched.
