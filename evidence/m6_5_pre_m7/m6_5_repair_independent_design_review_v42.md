# M6.5 v42 Independent Design Review

- Reviewer context: `/root/m65_v25_design_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject: `m6_5_repair_change_design_v42.md`
- Subject SHA-256: `50fe02263d2cb0aa181aed97b217b4c742fa998b4a50d32172257041a4101978`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=4 / P2=1`

## Findings

1. Execution and PairReceipt exact schemas omit the RuntimeStoragePolicyV5 field that the plan requires
   them to repeat.
2. Capacity admission requires a sealed source inventory before materialization, but replay output does not
   exist yet. A separate bounded scratch reservation or a different scoped output protocol is required.
3. The fixed ReplaySupervisorLease lacks a crash-recovery state machine and exact failure receipt.
4. ExecutionReceipt does not reference the trusted RuntimeClosureReceiptV5 that proves same-FD output,
   worker reaping and pipe EOF.
5. Canonical JSON inputs need the same no-follow, same-open-FD validate-and-consume rule as raw inputs.

## Closed items

V5 adoption, input/output transaction role separation, deterministic invocation identity, fixed output
payload, sibling transaction paths, supervisor-only filesystem write direction, default-deny opcodes,
same-FD output finalization direction, V3 pair coverage and all no-execution boundaries remain intact.
