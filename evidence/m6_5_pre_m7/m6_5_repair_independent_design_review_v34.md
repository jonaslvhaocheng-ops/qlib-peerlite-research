# M6.5 v34 independent R3 design review

- Reviewer context: `/root/m65_v25_design_review`
- Mode: independent, read-only
- Subject SHA256:
  `611800375ad7c7700613fcf7367cd688cf39801917badcb45b6824c8428f1b64`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=3 / P2=2 / P3=0`

## Blocking findings

1. `P1 CAPACITY_EXPECTED_UNDERREPORT`: NORMAL RESERVED only requires expected bytes at or
   below cap. It must require equality to independently recomputed sealed-source logical bytes,
   revalidate the source before MATERIALIZING, and stop/abort before or after each write that
   would make `actual > expected` or `actual > cap`.
2. `P1 CROSS_PROTOCOL_EQUALITY_AND_REF_SLOTS`: capacity and nested transaction objects do not
   freeze exact equality of attempt, target, policy and inventories. Reservation-local,
   upstream-policy and target-derived ArtifactRef slot classes must be separate and exact.
3. `P1 DURABLE_AUTHORITY_ACTIVATION`: authority generation lacks fixed registry paths, global
   lock, atomic no-replace publication, fsync, contiguous generation validation, gap/duplicate
   rejection, unique activation point, and crash/retry rules.
4. `P2 RECEIPT_AND_TRANSACTION_CLOSED_SCHEMAS`: ABORT_ABSENCE, CLEANUP, PREPARED,
   PUBLISH_COMPLETE and sibling COMMITTED need full strict JSON schemas, hash domains, slots,
   nullability, and exact inode predicate.
5. `P2 LIFECYCLE_RECORD_HASH_AND_RECONCILIATION`: a JSONL record cannot use an ambiguous
   `evidence_record_file_sha256`. Freeze artifact-file plus record ID plus record-canonical hash,
   observation selection, source-to-latest equality, security equality, and clock ordering.

## Confirmed closures

- Active directories are 0700 and seal to 0550 only after durable RELEASED and zero staging.
- Fixed roots and attempt-derived paths exist; oversized orphan is permanent HOLD.
- PREPARED recovery is fail-closed in principle; semantic poison and historical null-to-date
  delist behavior are materially improved.
- Replay grain remains exactly two merged expected artifacts plus fourteen singleton-fold
  artifacts.
- No M7, fit, replay, real-data, PIT or final-OOS authority exists.

The review edited no files, did not call the quality ledger, and ran no execution workflow.
