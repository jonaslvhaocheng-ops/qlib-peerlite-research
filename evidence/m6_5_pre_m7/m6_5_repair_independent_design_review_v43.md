# M6.5 v43 Independent Design Review

- Reviewer context: `/root/m65_v25_design_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject SHA-256: `04e1b8e1cdc1744e63afb4b3d5a0c3da09245c547ca8d31e54c89cf08d647016`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=6 / P2=1 / P3=0`

## Findings

1. The historical gate says implement/test while architecture v28 and v43 require design review first. Publish a
   new current gate version with the correct route.
2. The T-known allowlist conflicts with architecture v28 over trading/corporate-action inputs. Freeze one
   normalized exact allowlist and distinguish raw events from T-known states.
3. Self-contained specs still contain placeholder or inherited schema language for ledger and replay receipts.
4. Ledger crash safety requires the already-bounded whole-file temp, fsync, atomic-replace and directory-fsync
   mechanism plus concurrency tests.
5. CCC must use complete date sections with deterministic date batching and equal date weighting.
6. The 8/60 stage may yield only SCREEN_PASS/HOLD; deterministic refit needs an exact identity and purpose.
   Formal promotion and combination eligibility require the later five-seed confirmation CR.
7. Add import-graph, concurrency, prefix-tamper, archive-tamper, output-root-disjoint and static OOS tests.

The architecture-v28 scope correction, exact closure hashes, single-process replay boundary, M6 `6/44`,
M7 `NOT_RUN` and no-execution boundaries are otherwise preserved.
