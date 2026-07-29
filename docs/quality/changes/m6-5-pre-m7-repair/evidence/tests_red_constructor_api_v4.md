# Tests Red V4 — RunIntent Constructor Type Contract

- Review finding:
  `RUN_INTENT_V2_CONSTRUCTOR_TYPE_CONTRACT_MISMATCH`
- Product code changed in this red stage: `no`
- Verdict: `EXPECTED_RED`

## Command

```text
.venv/bin/python -m pytest -q \
  tests/test_run_intent_v2.py::test_constructor_declares_exact_dict_inputs_and_exposes_read_only_mappings
```

## Result

- Exit code: `1`
- Failure: the constructor advertises `Mapping[str, Any] | None`, while v50 and runtime require
  `dict[str, Any] | None`.
- Ruff on the updated test file passes.

The test also requires the post-construction authority attributes to be typed read-only properties. It is a
pure reflection/API test and performs no journal, ledger, replay, fit, PIT, data, budget, CCC, Gate or OOS
operation.
