# Implementation Repair — RunIntent Constructor Type Contract

- Finding: `RUN_INTENT_V2_CONSTRUCTOR_TYPE_CONTRACT_MISMATCH`
- Scope: `RunIntent` representation only
- Verdict: `PASS`

## Change

`RunIntent` now uses a bounded custom initializer:

- constructor parameters are explicitly `dict[str, Any] | None`, matching v50 and runtime rejection;
- normalized snapshots live in private Mapping fields;
- public `budget_limit_binding` and `market_state_authority_binding` are read-only
  `Mapping[str, Any] | None` properties;
- frozen dataclass equality remains content-based;
- V1/V2 payloads, normalization, cached bytes and cached identity are unchanged.

No caller, event V3, replay, fit, PIT, data, budget, CCC, Gate or OOS surface changed.

## Verification

- API regression: `1 passed`.
- Focused RunIntent/ledger/CLI suite: `34 passed`.
- Full repository suite: `86 passed`.
- Ruff: `PASS`.
- Instrumented RunIntent V2 suite and edge probes: `27 passed`.
- Protected ranges `69–138` and `180–330`: 100% line and branch coverage.
