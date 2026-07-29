# M6.5 v44 Independent Design Review

- Reviewer context: `/root/m65_v25_design_review`
- Independence: independent agent; read-only
- Subject SHA-256: `742723202a8ae3f4a7db2aab5e72006832b7a8c3d7fc88b6f7514a62a76914cd`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=5 / P2=1 / P3=0`

## Findings

1. Freeze a stable sidecar reconciliation lock that survives ledger inode replacement.
2. Bind the exact 8/60 budget authority into RunIntent, events and a fully typed recovery receipt.
3. Add a closed StaticM6ArchiveBinding with exact paths, hashes and both 4/29 and 6/44 byte prefixes.
4. Add a trusted replay binding for archive/source/runtime/dependency identity, all imported modules and a
   fail-fast fit guard.
5. Freeze one complete date per optimizer step and an exact sampler sequence.
6. Add deterministic refit, Gate row alignment, sidecar-lock and replay-binding test rows.

The T-known builder, exact 6/44 prefix, atomic replacement direction, CUDA 2×7 replay, Gate statistics,
screen-only semantics and architecture-v28 boundary otherwise pass.
