# M6.5 v43 Adversarial Design Review

- Reviewer context: `/root/m65_v24_adversarial_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject SHA-256: `04e1b8e1cdc1744e63afb4b3d5a0c3da09245c547ca8d31e54c89cf08d647016`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=1 / P1=4 / P2=2 / P3=0`

## Findings

1. **P0 — T-known product is not closed.** Add the architecture-required trusted server builder and source
   manifest, remove or explicitly prove future-conditioned eligibility flags, freeze the prediction clock,
   source identities, float64 aggregation and canonical digests, and test current-row revision poisoning.
2. **P1 — ledger crash oracle.** Bind whole-ledger atomic replacement or a bounded tail-recovery rule and
   crash-after-ledger-before-receipt idempotence.
3. **P1 — replay origin/runtime/CUDA.** Verify imported model blobs originate in frozen source, compare the
   frozen runtime identity, prove selected CUDA placement and define the v2 receipt fully.
4. **P1 — CCC/Gate numerics.** Freeze complete-date batching, equal-date epoch weighting and Gate ddof/dtype/
   serialization.
5. **P1 — screening formula.** Freeze referenced future inputs and exact IR, return, cost, fold-concatenation
   and threshold formulas.
6. **P2 — add the corresponding negative test rows.**
7. **P2 — stage wording.** Matrix rows are currently design inputs only; red execution follows a PASS review
   and routed test-design.

The old production control plane remains correctly excluded. M6 is `6/44`; M7, replay, fit, PIT rerun,
budget mutation and final OOS remain unauthorized.
