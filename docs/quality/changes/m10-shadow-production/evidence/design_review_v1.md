# Independent design review v1

Reviewer: `/root/m10_independent_design_review`

Verdict: `NEEDS_CHANGES`

## Findings

### P1 — Exactly-once protocol incomplete

Two processes can observe a missing idempotency record, and a crash can leave a
published cycle without its index. The design must define reservation,
ownership, commit point, stale recovery and loser behavior.

### P1 — Signal time semantics incomplete

The design does not bind one score cross-section to its manifest timestamp,
cycle date and an allowed trading session. It must reject multiple timestamps,
non-session dates and schedule mismatches.

### P2 — Filesystem trust boundary incomplete

The design must constrain cycle IDs, prove state-root containment, reject
symlinks and hash the exact immutable bytes that are parsed.

### P2 — Synthetic and resource bounds incomplete

The design must enforce a synthetic instrument namespace and pre-parse byte,
row and instrument bounds.

No production code was changed. The absent broker/live adapter and M9 HOLD
boundary remain correct and should be preserved.
