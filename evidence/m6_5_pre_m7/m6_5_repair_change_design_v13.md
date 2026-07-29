# M6.5 R3 修复设计 v13 — Bound namespace-parent implementation amendment

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一 base 是
`m6_5_repair_change_design_v12.md` SHA-256
`4798192f857896147774e269900db72777ec01dd75fa1b82fc354262a12753f4`。
v12 保留的 M6/PIT/Gate/genesis/authority/ACL/descriptor-v5/closure-v2/
seed+umask/publisher/test-order requirements 继续完整有效；本文件只替换其
namespace/reservation 语义，以修复独立 review v12 的 P1。架构依据为
`architecture_confirmation_v16.md`。不授权 M7、server replay、PIT
certification 或 final OOS。

## 1. Exact contract migration

New authoritative replay contracts are `NamespaceParentBinding v1`,
`FreshOutputReservation v2`, `M6ReplayInputBinding v8`,
`OutputReservationReceipt v2`, and `ReplayExecutionReceipt v7`. New replay
acceptance rejects v7/v1 reservation/binding and v6 receipt forms; no parser may
silently upgrade them.

`NamespaceParentBinding v1` is a supervisor-owned, sealed-control-root,
immutable `ArtifactRef`. It records the exact namespace policy ref,
reservation id/nonce/basename, control-root digest, strict relative parent
path, required `linux_openat2_v1` resolver, root identity, every identity from
control root to final parent, and final parent identity. Every identity is
`directory + dev + ino + statx mount id + btime + uid/gid + mode + access/default
ACL digests`; it intentionally excludes `mtime`/`ctime`/`nlink`.

Reservation v2 embeds the exact parent-binding artifact digest alongside the
namespace-policy digest, nonce-derived basename, `must_be_absent=true`, output
schema and `14 replay / 0 fit / OOS=false`. v8 contains the full v12 input
inventory unchanged, plus the namespace policy artifact, parent-binding
artifact and reservation v2. No caller/verifier path is an input.

## 2. Required control flow

1. Supervisor resolves control-root → parent by pinned FD and exact `openat2`
   flags; unavailable `openat2`, `statx_mnt_id`, `btime` or FD-derived ACL facts
   fail closed.
2. It validates policy, complete identity chain and `ENOENT` for basename;
   writes/hashes parent-binding v1, then freezes reservation v2 and v8.
3. Before launch it resolves again and compares every stable parent-binding
   field. Under verified namespace lock it resolves and compares once more,
   rechecks absence and performs `mkdirat`.
4. After `mkdirat`, it verifies new-root identity/owner/mode, compares parent
   binding once more, fsyncs, and writes receipt v2.
5. The sealed descriptor carries only descriptor FDs plus exact parent-binding,
   reservation and receipt digests. Bootstrap and child receipt repeat those
   identities; neither accepts a path flag.
6. Archive re-resolves the full chain, compares parent-binding exactly, opens
   the basename no-follow, compares root identity to all receipts, then hashes
   inventory and accepts only exact v8/v2/v7 agreement.

Before `mkdirat`, failure is `REJECTED`; after it, any failure/crash is
`QUARANTINED_UNPUBLISHED`, never delete/recreate/promote/reuse. This must be
implemented with the pre-existing v12 requirements for PID/FD sealing, Python
startup, seed/umask, ACL and unchanged legacy ledger.

## 3. Test design required after independent PASS

Red/green/E2E tests must cover happy path; same-ACL final-parent replacement;
intermediate-chain replacement; pre-mkdir and post-mkdir race hooks; archive
revalidation; symlink/absolute/`..`/magic-link/cross-mount rejection; wrong
FD/digest/receipt; ACL/mode/owner drift; pre-existing output; no-reuse after
crash; and harmless parent `mtime`/`nlink` change. A synthetic adapter can
exercise failure behavior but cannot issue archive acceptance evidence.

Only after fresh independent PASS may the quality route enter test design, red
tests and implementation. M7/CCC/Gate/final OOS remain sealed throughout.
