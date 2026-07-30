# M10 implementation evidence

Implemented:

- strict `SHADOW_ONLY/SYNTHETIC/paper` policy and M9 authorization;
- pinned session calendar and deterministic due-time decision;
- bounded, no-follow, single-read Parquet capture;
- one-cross-section signal validation and local monitoring;
- deterministic paper intents;
- reservation, terminal commit, replay, crash repair and corruption gates;
- terminal self-hash and exact artifact verification;
- mutation-free preflight errors and transactional halted alerts;
- `shadow-preflight` and `shadow-cycle` public CLI commands;
- committed synthetic-only policy, calendar and runbook.

No model, training, Qlib, PIT, final-OOS or live execution path was changed.

Focused tests: 17 passed. Full suite: 208 passed. Ruff: pass.
