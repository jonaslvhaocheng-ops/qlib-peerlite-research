# M6.5 v37 independent R3 design review

- Reviewer: `/root/m65_v25_design_review`
- Subject: `sha256:ab3d455f308d108b86a9ced8dd6b4db27eba354d6ace94d5d438e2126ff74bb5`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=6 / P2=1 / P3=0`

Findings: hardlink block scan needs inode dedupe; LeaseBinding/RESERVED two-final bootstrap is not
crash closed; post-cleanup nlink assumes unique staging inodes; result payload schemas/slots and
event-kind mapping are open; issuer registry objects/publication and parent authorization are not
closed; LIST/DELIST share one conflicting vendor clock; historical digests and Evidence V3 need
closed schemas.

Confirmed: 4+19 control count, three inventory phases, sibling completion, run-ledger recurrence,
event-key uniqueness, parser resource/I/O closure, no derived-contract cycle, committed budget,
replay digest preimages and 2+14 grain. Review was read-only and executed nothing.
