# M6.5 v44 Adversarial Design Review

- Reviewer context: `/root/m65_v24_adversarial_review`
- Independence: independent agent; read-only
- Subject SHA-256: `742723202a8ae3f4a7db2aab5e72006832b7a8c3d7fc88b6f7514a62a76914cd`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=1 / P1=4 / P2=1 / P3=0`

## Findings

1. **P0 — pre-fit state identity.** Future derived contract and events must bind exact state product,
   source manifest, PIT parent, calendar and builder refs. Revision selection must choose the latest eligible
   revision at T-close and reject equal-time conflicts.
2. Use a stable sidecar lock and a receipt slot derived from run intent, journal and committed ledger-prefix
   identity, with unambiguous recovery after later journal commits.
3. Replay archive/runtime identities must come from a fixed external binding, verify full frozen tree and all
   imported project/dependency origins, and define the no-fit guard and nested receipt coverage.
4. Freeze one bit-deterministic float reducer and length-prefix instrument keys.
5. Freeze exact CCC date-to-optimizer-step and sampler semantics.
6. Add the corresponding external-anchor, lock recovery, transitive import, cancellation, date-packing and
   pre-fit state-substitution tests.

M6 remains `6/44`; M7, tests, implementation, replay, fit, PIT rerun, budget mutation and final OOS remain
unauthorized.
