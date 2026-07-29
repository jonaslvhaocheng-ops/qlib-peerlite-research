# M6.5 v36 adversarial R3 design review

- Reviewer: `/root/m65_v24_adversarial_review`
- Subject: `sha256:291d9edca6b69bcc9004c51ddf4ffcfe59b6c196d2367bc9a648815ab1b728a7`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=6 / P2=4 / P3=0`
- M7 v14: `NEEDS_CHANGES / NOT_AUTHORIZED`

Findings:

1. `P1 PHYSICAL_BLOCK_CAPACITY`: logical bytes do not reserve filesystem allocation blocks.
2. `P1 LEASE_BOOTSTRAP_RACE`: creating per-attempt lease before capacity admission spends an inode
   before reservation.
3. `P1 PHASE_MUTABLE_INVENTORY`: mode seal and staging cleanup invalidate FINAL_PHYSICAL/nlink.
4. `P1 LEDGER_TRANSITION_AND_RESULT`: no closed STARTED/outcome transition chain or result→claim
   binding.
5. `P1 EXTERNAL_ISSUER_TRUST`: trust anchor has a hash cycle and no request-external registry root.
6. `P1 HISTORICAL_RESOLVER`: historical wrapper/row/resolver and full clock order remain open.
7. `P2 FIELD_REGISTRY_V3_SCHEMA`: V3 wrapper is not fully enumerated.
8. `P2 CHMOD_DURABILITY`: temp chmod needs a following file fsync before parent fsync.
9. `P2 REPLAY_DIGEST_PREIMAGES`: v36 omitted key/score/identity row preimages.
10. `P2 MATRIX_GAPS`: add explicit block, lease-storm, post-cleanup, ledger, anchor, resolver and
    chmod-crash fixtures.

Confirmed: logical bijection, source/staging/final subset prevention, post-admission control
arithmetic, temp branches, registration scan, permanent committed budget, dual qualification,
zero fractions, PIT history goal and pointer classification. Review was read-only; no execution.
