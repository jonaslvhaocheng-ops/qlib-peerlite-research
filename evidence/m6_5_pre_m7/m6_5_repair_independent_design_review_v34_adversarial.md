# M6.5 v34 adversarial R3 design review

- Reviewer context: `/root/m65_v24_adversarial_review`
- Mode: independent, read-only
- Subject SHA256:
  `611800375ad7c7700613fcf7367cd688cf39801917badcb45b6824c8428f1b64`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=4 / P2=4 / P3=0`
- M7 v12: `NEEDS_CHANGES / NOT_AUTHORIZED`

## Blocking findings

1. `P1 CAPACITY_INODE_AND_ENTRY_EXHAUSTION`: byte-only limits allow many zero-byte entries.
   Add per-attempt and aggregate file/directory entry caps, filesystem inode floor, `f_favail`
   admission, inventory counts, and extraction-time enforcement.
2. `P1 CROSS_GENERATION_BUDGET`: registry must mechanically enforce one CCC then one Gate,
   exact `6/44` head, cumulative maximum `8/60`, and count FAILED/CLAIMED_INTERRUPTED without
   replacement.
3. `P1 CCC_QUALIFICATION_CONFLICT`: both CCC and Gate must bind complete PASS qualification
   before any candidate/fit first event; the current CCC purpose row conflicts with retained
   M7 first-event admission.
4. `P1 PRE_LIST_SEMANTICS`: freeze a pre-list rule for the full security/date Cartesian axis:
   before the listing observation is available, LIST/DELIST coverage is not required and fixed
   flags are false with zero listed sessions.
5. `P2 INODE_PREDICATE`: define exact `(st_dev, st_ino)` hardlink compatibility and all
   transaction object schemas.
6. `P2 PRIVATE_TEMP_RECOVERY`: fixed attempt/slot-derived temp names, exact allowed leftovers,
   inode/byte validation and cleanup rules are required; unknown entries HOLD.
7. `P2 TYPED_NUMERIC_CANONICALIZATION`: freeze number grammar/algorithm for negative zero,
   exponent and trailing zeros; bind parser as a locatable ArtifactRef.
8. `P2 OBSERVATION_INTERVAL_AND_ISSUER_TIME`: freeze half-open intervals, same-time conflict
   rejection, selection tie rules, and the trusted time used to validate issuer validity.

## Confirmed closures

- Active 0700 to released 0550, derived roots, dual-hash ArtifactRefs and oversized-orphan HOLD
  are effective.
- The main future-delist leak is closed: a 2023 delist is not applied in 2020.
- Replay remains two merged expected plus fourteen per-fold artifacts; M6 prefix remains 6/44.
- M6 is PASS, M6.5 needs changes, M7 is NOT_RUN; no fit, replay, real-data, budget or final-OOS
  authority exists.

The review edited no files, did not call the quality ledger, and ran no execution workflow.
