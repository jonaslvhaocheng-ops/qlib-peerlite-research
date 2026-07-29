# M6.5 v41 Adversarial Design Review

- Reviewer context: `/root/m65_v24_adversarial_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject: `m6_5_repair_change_design_v41.md`
- Subject SHA-256: `a9724a5dc98a27710f7724aa306e25dd710b3135fa12133a56b1bbf8ae3ead4f`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=4 / P2=2 / P3=0`

## Findings

1. **P1 — Capacity policy downgrade.** Replay V2 cannot use RuntimeStoragePolicyV2 while requiring the
   V11 capacity chain. Bind the current V5 schema and add a downgrade-substitution negative case.
2. **P1 — reservation invocation and input/output transactions are not closed.** A path-only invocation
   slot leaves the attempt-ID preimage mutable. Define an exact invocation object and separately bind
   closed input and output transaction chains in every pair receipt.
3. **P1 — CUDA-only and zero-fit are self assertions.** Add an external execution receipt binding
   launcher, code/runtime closure, argv, selected CUDA device, observed no-fit call closure, ledger prefix
   and input FDs.
4. **P1 — stale worker can retain a writable FD after flock loss.** A supervisor cannot atomically close
   another process's descriptors. The supervisor must exclusively own the lease and writable publication
   capabilities, mediate writes, confirm worker death and descriptor closure, then release the flock.
5. **P2 — raw input manifest has a validation-to-consumption gap.** Record root/device/inode/nlink and use
   the same no-follow-open file description for hashing, schema validation and replay consumption.
6. **P2 — the matrix needs corresponding policy, invocation, transaction, CUDA, stale-writer and raw-swap
   cases.**

## Closed items

Typed refs, event containment, acyclic checkpoint DAG, LP execution identity, receipt-root containment,
FD operation policy, output-root grammar, pair/model equality, aggregate coverage, reservation ordering and
lease digest remain closed. M6 is `6/44`; M7, fit, replay, real data, PIT, budget mutation and final OOS are
not authorized.
