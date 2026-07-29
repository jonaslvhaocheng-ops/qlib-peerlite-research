# M6.5 R3 修复设计 v17 — Authority bundle and V precommit implementation

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一 base 是
`m6_5_repair_change_design_v16.md` SHA-256
`83e18a05f6f98fcde0b71302233cc6322c5757e5c45736b46dd3a602f739af98`。
v16 保留的 M6/PIT/Gate/genesis/ACL/descriptor/closure/seed/umask/publisher
controls continue unchanged. This amendment replaces authority materialization
and R→V semantics according to `architecture_confirmation_v20.md`; it creates
no real E/C/P/F/A/B/Q/R/V instance and authorizes no replay/M7/PIT/OOS.

## 1. Strict construction and validation

Implement only the v20 DAG E→C→{P,F}→A→B→Q→R→V. `E` has exactly six typed
M6 evidence roles and independent M6.5 PASS; C/P/F/A/Q/V expand and compare all
six role-by-role. C holds the closed PTemplate and slot, not P hash; P and F are
independent C-derived materializations; A unifies them. Validate nested refs
recursively against E allow-list, fixed slots/control store, M6-only mode,
actor map, derived evidence key and actual writer identity. No M7 object, alternate evidence bundle,
template, slot, policy, root or writer is accepted.

## 2. Precommit before claim

`DirectoryIdentity v2` is canonical inline data, not a caller digest. Derive K
directly from canonical A/P/D/leaf bytes and recompute it from the no-follow
parent FD at every phase. Q v1 freezes the complete V payload before R and has
no R/V/output/state/receipt/random field. R v6 is the once-only flat K claim;
V v12 must be the byte-exact `CanonicalComplete(Q, reservation_ref=R)` written
only at R's fixed V slot. This eliminates any post-claim V choice and R/V cycle.

## 3. Deterministic pre-S0 and execution lifecycle

Implement the flat `PreS0Terminal` slot and exact recovery table from v20.
R-without-V, R+V-without-S0 and invalid/pre-S0-output cases burn/quarantine R;
Q alone is inert. No terminal permits future V/S0/output/archive.

After V, retain the fixed S0→S6 receipt lineage. Every transition/receipt binds
E/C/P/F/A/B/Q/R/V/K, predecessor and authorized writer. Replay supervisor emits
`ReplayExecutionReceipt v11`, child only ChildReceipt, archive acceptor only
archive receipt/S6. Use anchored lock, O_EXCL paths, no mutable head, separate
witness/sync FDs and durable publication order.

## 4. Tests after independent PASS

Test design must cover all six-role authority splices, E quality-PASS absence,
template/slot/allow-list errors, writer mismatch, canonical D/K tamper, Q/R/V
byte completion, each pre-S0 recovery row and retained transition/path/ACL/FD/
umask/PIT fixtures. Fresh independent design PASS is required before tests or
implementation; M7/CCC/Gate/final OOS remain sealed.
