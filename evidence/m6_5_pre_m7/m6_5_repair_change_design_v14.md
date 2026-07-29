# M6.5 R3 修复设计 v14 — Canonical reservation graph and durable handoff

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一 base 是
`m6_5_repair_change_design_v13.md` SHA-256
`fdba160c3e22680b3ba20844966fef0e673cbcb66b9ad1a3b51b0f283dba9e8a`。
v13 保留的 M6/PIT/Gate/genesis/authority/ACL/descriptor-v5/closure-v2/
seed+umask/publisher/test-order requirements 继续完整有效；本文件替换 replay
reservation 的 versions/relations/transaction，以修复 v13 独立对抗审查的
P1/P2。架构依据为 `architecture_confirmation_v17.md`。不授权 M7、server
replay、PIT certification 或 final OOS。

## 1. Versioned schemas and graph validator

New authoritative forms are `ReplayControlRootAnchor v1` (A),
`NamespaceParentBinding v2` (B), `FreshOutputReservation v3` (R),
`M6ReplayInputBinding v9` (V), `ReservationRegistry v1` (S),
`OutputReservationReceipt v3` (O), `ReplayHandoffAnchor v1` (H) and
`ReplayExecutionReceipt v8`. All use canonical duplicate-key-free closed JSON
and full typed `ArtifactRef`s. Legacy/unknown A/B/R/V/S/O/H/receipt forms,
digest-only edges and implicit upgrades are rejection-only.

Implementation must construct only:

```text
P + active profile → A → B → R → V → S → O → H → receipts
```

A is the pre-existing typed, immutable control-root producer stored outside its
identified mutable control-root inventory. Its content universe excludes future
B/R/V/S/O/H/output content. B alone owns canonical reservation coordinates;
R references B and never repeats policy, nonce or basename; V references full
P/A/B/R plus the unchanged full M6 replay inventory. This removes free output
authority and hash/self-reference ambiguity.

## 2. Mandatory relational validation

Implement one `validate_reservation_graph_v1()` and call it at freeze,
prelaunch, lock-held pre-create, post-create, child bootstrap and archive. It
must enforce the exact A/P/B/R/V equations from architecture v17, including:

```text
B.parent_relpath/components == P.parent_relpath/components
B.basename == CanonicalDerive(A.sha256, P.sha256, B.reservation_id, B.nonce_hex)
R.parent_binding_ref == Ref(B)
V.{A,P,B,R} == exact typed refs
R.required schema/profile == V.required schema/profile == 14 replay / 0 fit / OOS=false
```

The only accepted basename grammar is `^m6r-[0-9a-f]{52}$`; no implementation
may accept a generic path string. Parent resolution uses the exact anchored
`openat2` profile; `mkdirat`/reopen receive only that validated component.
Root, every parent-chain component and created root use complete FD-derived
`DirectoryIdentity v2` with opaque handle, ACLs and stable fields; output root
must match P's exact owner/gid/0700/access ACL/default-ACL-absent policy.

## 3. Durable reservation transaction

After V freeze and before any prelaunch work, acquire locks only in
`activation/profile → registry → namespace` order. First write the unique
`ISSUED` registry transition keyed by `R.sha256` through no-overwrite publish,
file fsync and directory fsync. Any duplicate is rejected; any later crash
burns R, so a retry requires a new nonce/B/R/V.

Under those locks, use an `O_PATH` witness FD only for identity and separately
open a matching `O_RDONLY|O_DIRECTORY` sync/operation FD. Never call `fsync` on
`O_PATH`. Re-resolve/compare A→B parent, validate the graph and absence, create
the root with `mkdirat(sync_fd, canonical_basename, 0700)`, immediately obtain
root witness/sync FDs, validate full root identity/ACL and emptiness, re-resolve
parent/leaf, then fsync root followed by parent.

Only then publish/fsync in this order: `RESERVED` S (V/B/R/root identity), O
(typed A/P/B/R/V/S/root identity), `RECEIPTED` S, H (all refs + sealed descriptor
and root identity), `HANDOFF_ANCHORED` S, FD transfer, child verified ACK, and
`HANDED_OFF` S. Locks release only after the ACK transition is durable. Every
publish uses same-dir temp → file fsync → atomic no-replace → directory fsync.
Missing capability fails closed.

Recovery under the same locks records `ABANDONED_BURNED` for ISSUED/no-root and
`QUARANTINED_UNPUBLISHED` for any root/incomplete later state. No burned or
quarantined reservation/root may be deleted, recreated, promoted or reused.
Archive repeats graph/identity/receipt/state equality under the same lock order
before acceptance.

## 4. Test-design commitments after independent PASS

Red/green/E2E design must cover malformed graph composites; B/R/P/A/V mismatch;
basename escape forms; canonical/duplicate/unknown/legacy encodings; same-ACL
final and intermediate parent swaps; root ACL/default-ACL drift; wrong FDs,
states or receipts; no-sync primitive; every crash/swap hook from create through
handoff/archive; mtime/nlink non-failure; and permanent no-reuse of an ISSUED,
burned or quarantined R. Tests remain synthetic and cannot create replay/M7/OOS
acceptance evidence.

Only a new independent PASS allows entry into test design, red tests and
implementation. M7/CCC/Gate/final OOS stay sealed.
