# M6.5 Expected-Red Evidence V1

- Plan IDs: `STATE-C1`, `LEDGER-U1`
- Test: `tests/test_m65_expected_red.py::test_unbound_legacy_run_intent_is_rejected_before_any_trial_event`
- Command:

```text
.venv/bin/python -m pytest -q tests/test_m65_expected_red.py
```

- Exit code: `1`
- Expected reason: current `RunIntent` accepts the legacy three-field construction and therefore omits both
  `BudgetLimitBindingV2` and `MarketStateAuthorityBindingV1`.
- Observed failure:

```text
Failed: DID NOT RAISE <class 'TypeError'>
tests/test_m65_expected_red.py:11
1 failed in 1.17s
```

Verdict: `PASS_EXPECTED_RED`. The failure is the intended missing product behavior, not a syntax, import,
environment or harness failure. No production code was changed and no replay, fit, PIT, budget or OOS action
occurred.
