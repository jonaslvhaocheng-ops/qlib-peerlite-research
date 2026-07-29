# M6.5 Implementation Slice V1

- Approved design: v48
- Test-plan IDs: `STATE-C1`, `LEDGER-U1`
- Expected red: unbound M7 initial-screen `RunIntent` was accepted.
- Changed production file: `src/qlib_peerlite/governance/trial_ledger.py`

## Behavior

- `QLIB_PEERLITE_M7_INITIAL_SCREEN_V1` now requires both
  `budget_limit_binding` and `market_state_authority_binding`.
- Supplying only one binding or a non-dictionary binding fails immediately.
- A bound intent hashes as RunIntent V2 and includes both authorities.
- Historical non-M7 intents with neither binding retain their V1 identity, preserving M6 evidence/tests.

## Fresh checks

```text
.venv/bin/python -m pytest -q tests/test_m65_expected_red.py tests/test_trial_ledger.py tests/test_reconcile_trial_ledger_cli.py
10 passed in 2.92s

.venv/bin/python -m ruff check src/qlib_peerlite/governance/trial_ledger.py tests/test_m65_expected_red.py
All checks passed!

.venv/bin/python -m pytest -q
62 passed in 7.88s
```

No test assertion was weakened. No replay, fit, PIT, real-data, budget or final-OOS action occurred.
Implementation source digest: `sha256:f5dfe81de7b711a9a91e64034eef29dd81e59e67eb61404b06ac67817dec3ddd`.
