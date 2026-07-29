# M6.5 v42 Adversarial Design Review

- Reviewer context: `/root/m65_v24_adversarial_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject: `m6_5_repair_change_design_v42.md`
- Subject SHA-256: `50fe02263d2cb0aa181aed97b217b4c742fa998b4a50d32172257041a4101978`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=5 / P2=2 / P3=0`

## Findings

1. **P1 — architecture conflict.** v42 expands the approved architecture-v28 single trusted replay command
   into a multi-process FD-passing, syscall-sandbox and multi-transaction control plane that v28 explicitly
   excluded.
2. **P1 — typed policy ref mismatch.** Capacity activation still accepts generic ArtifactRefV1 while replay
   requires a CanonicalJsonRefV1 targeting V5; strict schemas cannot contain the same ref.
3. **P1 — generated output cannot satisfy sealed-source admission.** Capacity's NORMAL mode is not a
   generated-payload reservation protocol.
4. **P1 — execution evidence is self asserted.** RuntimeClosureReceiptV5 and independent static/call-trace
   evidence are absent from the replay DAG.
5. **P1 — pipe order is not executable.** Closing the read end before observing EOF loses the EOF proof,
   and no exact frame/terminal schema distinguishes complete from truncated output.
6. **P2 — matrix gaps.** Add ref-type mismatch, generated-source misuse, close-before-EOF, missing runtime
   evidence, hash-cycle and generic default-deny cases if that architecture is retained.
7. **P2 — recursive Base claim is stronger than historical evidence.** Add an immutable closure manifest
   listing exact repository-relative paths and hashes instead of relying on older matrix prose.

## Mainline conclusion

The minimal repair is not another control-plane patch. Return to architecture v28: a trusted,
single-process archival verifier, read-only frozen inputs, and one previously absent output directory.
Treat the capacity, event-authority, FD-passing and syscall-sandbox protocols as deferred production
hardening unless a new architecture change is separately approved.

M6 remains `6/44`; M7, fit, replay, real data, PIT, budget mutation and final OOS are not authorized.
