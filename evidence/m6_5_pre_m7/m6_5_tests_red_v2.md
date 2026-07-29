# M6.5 Tests Red V2 — Mutable RunIntent Authority Identity

- Stage: `tests-red`
- Design: `m6_5_repair_change_design_v50.md`
- Test plan: `m6_5_test_design_v2.md`
- Product code changed in this stage: `no`
- Verdict: `EXPECTED_RED`

## Command

```text
.venv/bin/python -m pytest -q tests/test_m65_expected_red.py
```

## Observed result

- Exit code: `1`
- Tests: `1 failed, 1 passed`
- Intended failing test:
  `test_run_intent_v2_owns_an_immutable_nested_authority_snapshot`
- Failure: after mutating the original nested budget and market-state dictionaries, the same intent changed from
  SHA256 `5cabd6d0baf623c95694e6da4e9b34aa242ab15589ff75893d133b203109db8d`
  to `e1effc5bed5b40cff78112c9c43c77e4bd279a15a908d92198eb4df87007e280`.
- The pre-existing M7-unbound rejection test remained green.

## Red-test validity

The failure is the approved product gap, not an import, syntax, fixture, environment or harness error. The test
uses a valid fully-bound M7 intent, retains aliases to nested containers, mutates those aliases, and observes
identity drift. No journal, ledger, replay, fit, PIT, real-data, budget or OOS action occurs.

This red test authorizes only the router-selected bounded implementation repair.
