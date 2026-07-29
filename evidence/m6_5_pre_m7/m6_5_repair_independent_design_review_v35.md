# M6.5 v35 independent R3 design review

- Reviewer: `/root/m65_v25_design_review`
- Mode: independent, read-only
- Subject SHA256:
  `46add10c455daf6e9c705e18dd5d2357e58a4b143ea5fd805a82195866ecd1c4`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=4 / P2=2 / P3=0`

## Findings

1. `P1 PREPARED_DIRECTORY_INODE_IMPOSSIBLE`: PREPARED cannot freeze the OS inode of a final
   directory that does not yet exist. Freeze a device/inode-free logical payload manifest;
   completion records observed final inventory; only regular hardlinked files require inode
   equality.
2. `P1 FINITE_NUMBER_ZERO_FRACTION`: numeric grammar incorrectly rejects `0.5` and `-0.5`.
   Accept canonical zero-integer fractions while continuing to reject negative zero, exponent,
   leading zeros and trailing fractional zeros.
3. `P1 EVENT_LEDGER_DIGEST_UNCLOSED`: prior terminal and retained digests lack fixed event/claim/
   outcome/terminal schemas, paths and digest preimages, so budget/no-replacement cannot yet be
   independently recomputed.
4. `P1 ISSUER_TIME_SELF_ASSERTED`: receipt `verified_at` cannot prove when the receipt existed.
   Bind a trusted append-only authorization registration or drop the historical-time claim.
5. `P2 DERIVED_INVENTORY_SLOTS`: freeze exact source-revalidation, staging-inventory and
   payload-logical-manifest paths and whether they count toward capacity.
6. `P2 AUTHORITY_TEMP_RECOVERY`: after successful link, unlink temp and fsync parent; add exact
   recovery rules for valid/invalid known temps.

Confirmed: four-dimensional source reservations, inode floor, dual qualification, PRE_LIST,
record/source reconciliation in principle, unique activation, 6/44-to-8/60 policy ceiling and
two-merged-plus-fourteen-per-fold replay remain present. No execution was authorized or run.
