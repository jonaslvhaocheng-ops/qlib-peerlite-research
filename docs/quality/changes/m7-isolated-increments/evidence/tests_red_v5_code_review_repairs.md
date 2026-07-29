# M7 code-review repairs expected-red

- Command:
  `.venv/bin/python -m pytest -q tests/test_m7_review_repairs_red.py`
- Exit: `1`
- Intended failure:
  `ModuleNotFoundError: qlib_peerlite.m7.adapter`
- Harness: collected and executed normally.

The test fixes the required repaired public surface: no empirical lease
factory, persisted-evidence recovery and a protected M7 adapter module.

Verdict: `PASS` for `tests-red`.

