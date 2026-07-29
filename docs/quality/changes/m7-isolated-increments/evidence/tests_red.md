# M7 Expected-Red Test Evidence

## Scope

This red tranche tests only the two isolated M7 engineering gaps approved by the
v2 design:

- CCC must use float64 population reducers with epsilon `1e-8` and reject
  non-finite inputs.
- The market-state Gate must reject an ordinary dataset and must never fall
  back to the legacy `market` channel.

It does not authorize a real-data fit, consume an M7 candidate evaluation, alter
the trial ledger, freeze cost or benchmark assumptions, or open final OOS.

## Controller command

```text
.venv/bin/python -m pytest -q tests/test_m7_expected_red.py
```

Expected result: exit code `1`.

Observed before production changes: five intended behavioral failures:

1. CCC returns `torch.float32` instead of contract-required `torch.float64`.
2. CCC does not reject `NaN`.
3. CCC does not reject positive infinity.
4. CCC does not reject negative infinity.
5. Gate training accepts a plain dataset and silently reads the legacy
   `market` channel instead of requiring verified `market_state` provenance.

There were no import, fixture, collection, environment, or harness failures.
As a green control, the existing PeerLite/model/market-state/panel-dataset
suite completed with `20 passed`.

## Boundary

Passing this quality stage authorizes only the bounded implementation stage.
Empirical screening remains blocked while `contracts/cost_spec.json` and
`contracts/benchmark_spec.json` are not frozen and the Gate input lacks a
verified PIT value/provenance binding.
