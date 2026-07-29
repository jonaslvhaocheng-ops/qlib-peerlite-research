# M6.5 v46 Adversarial Design Review

- Reviewer context: `/root/m65_v45_adversarial_retry`
- Independence: independent agent; read-only
- Subject SHA-256: `05f21bf9b15497e85b16538c8497495440d6216246642af318b113f2e55df37f`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=3 / P2=1 / P3=0`

## Findings

1. Define an exact reconciliation-snapshot slot preimage, directory and filename.
2. The budget authority must itself freeze candidate evaluation IDs and event purposes before the reconciler
   can enforce them.
3. Make no-fit reference discovery generic over all reachable Python object references, including defaults,
   callable instances, descriptors and containers.
4. Reject source timestamps with precision finer than microseconds before eligibility comparison and
   canonical encoding.

The v4 hashes, static source anchor, semantic checkpoint digest, signed-zero normalization, finite-overflow
failure and bounded lock injection otherwise pass. No state was mutated.
