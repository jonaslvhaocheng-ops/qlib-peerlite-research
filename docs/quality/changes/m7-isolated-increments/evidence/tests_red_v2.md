# M7 first-tranche repair expected-red evidence

## Command

```text
.venv/bin/python -m pytest -q tests/test_m7_expected_red.py
```

Expected and observed result: exit code `1`, with exactly two current
contract failures and five already-repaired cases green.

1. A caller-defined subclass with a no-op integrity method is accepted by the
   intermediate Gate boundary, so `fit()` does not raise before `prepare()`.
2. The CCC trainer invokes gradient clipping with
   `error_if_nonfinite=False`; the injected non-finite norm stops the call,
   but the required guard flag is absent. The optimizer step count remains
   zero in the fixture.

No import, collection, fixture, optional-Qlib, environment or harness failure
occurred. The adjacent existing model/data suite remains green with
`20 passed`.

This red evidence authorizes only deletion of the spoofable marker,
unconditional dataset-level Gate denial, and activation of the pre-step
non-finite-gradient guard. It does not authorize a concrete Gate factory,
checkpoint binding, prerequisite validator, state machine, candidate event,
real fit or final OOS access.
