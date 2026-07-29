# M7 complete engineering expected-red evidence

- Command:
  `.venv/bin/python -m pytest -q tests/test_m7_complete_red.py`
- Exit code: `1`
- Expected failure:
  `ModuleNotFoundError: No module named 'qlib_peerlite.m7'`
- Classification: missing approved product package, not syntax, fixture,
  assertion or environment failure.
- Test-plan IDs represented: `S1`, `R3`, `K3`.

The test collected and executed normally, then failed at the first approved
public M7 package boundary. This is the intended pre-implementation red state.

Verdict: `PASS` for `tests-red` only.

