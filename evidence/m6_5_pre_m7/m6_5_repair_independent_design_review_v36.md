# M6.5 v36 independent R3 design review

- Reviewer: `/root/m65_v25_design_review`
- Subject: `sha256:291d9edca6b69bcc9004c51ddf4ffcfe59b6c196d2367bc9a648815ab1b728a7`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=4 / P2=2 / P3=0`

Findings:

1. `P1 CONTROL_SLOT_COUNT`: 21 controls are 4 directories plus 17 files, while policy says 18 files.
2. `P1 FINAL_MODE_AND_CONTROL_SCAN`: FINAL_PHYSICAL is recorded before 0550 seal and does not define
   exact exclusion of PUBLISH_COMPLETE from payload scan.
3. `P1 LEDGER_HEAD_UNBOUND`: event ledger heads lack artifact slots, entries and recurrence.
4. `P1 TRUST_ANCHOR_CYCLE`: anchor contract hash can cycle with derived contract and registry lacks
   external policy/root/head transition.
5. `P2 EVENT_ID_COLLISION`: source_event_id uniqueness or seq-bound event key is missing.
6. `P2 PARSER_RESOLVER_RESOURCES`: parser resources/I/O policy and historical snapshot resolver
   closure are not bound.

Confirmed: directory inode fix, 0.x grammar, fixed inventory slots, temp state table, committed
budget, unique registrations, payload bijection, historical fields, bundle hashes and replay
grain. Review was read-only; no execution or ledger mutation.
