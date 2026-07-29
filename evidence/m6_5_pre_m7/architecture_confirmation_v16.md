# M6.5 架构确认 v16 — Bound replay namespace parent

状态：`ARCHITECTURE_READY / 待独立设计审查`。本文件的 canonical base 是
`architecture_confirmation_v15.md` SHA-256
`f6dd3a7d92007cfdc8a2b863be95b9c2bd3204305d63ee5ae849f3d22776fafd`。
除本文件明确替换的 replay-output reservation 语义外，v15 保留的 M6
`6/44`、PIT/state、public Gate、actor ACL、one-way authority、descriptor
v5/closure v2、effective seed/umask、M7 publisher 和所有 M6 replay
controls 均继续有效。本文件不授权 M7、M6 replay、OOS 或任何历史证据修改。

## 1. Frozen namespace-parent witness

`ArtifactRef v1(role,relative_path,schema_version,sha256,bytes)` 仍只表示已有、
测量过的内容；尚不存在的 replay output root 绝不是 `ArtifactRef`。

为了把“冻结时看到的父目录”与后续执行绑定，replay supervisor 在受控的、
sealed control root 下创建不可变的 **`NamespaceParentBinding v1` ArtifactRef**。
它是反替换 witness，不是可变 inode 的永久 authority link，且在最终
`M6ReplayInputBinding v8` 之前写入，因此不会形成 binding-hash 环。其 closed
fields 为：

```text
namespace-policy ArtifactRef (digest, schema, control-root-relative parent path)
reservation_id + frozen nonce + derived basename
control-root binding digest
parent_relpath (strict relative, no caller input)
resolver = linux_openat2_v1:
  RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV
  O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC
root identity, complete component identity chain from control root to parent,
and final parent identity
```

Every identity uses only stable, semantically relevant fields:

```text
type=directory; dev_major; dev_minor; ino; statx_mnt_id; btime_ns;
uid; gid; mode_octal; access_acl_sha256; default_acl_sha256
```

`mtime`、`ctime` 和 `nlink` are deliberately excluded because creating the
output entry changes directory metadata. The authoritative Linux x86_64 helper
must obtain `statx_mnt_id` and `btime_ns`, and ACL fingerprints, from the
no-follow FD-resolved objects; unavailable facts, a resolver fallback, a
symlink, `..`, an absolute/magic-link path or a cross-mount resolution fail
closed. A synthetic adapter may exercise these rules but can never issue
acceptance evidence.

## 2. M6 replay binding v8 and fresh output reservation v2

`M6ReplayInputBinding v8` is frozen before replay. Its exact existing
`ArtifactRef` inventory is:

1. external transfer manifest, source archive, internal manifest, single root
   and complete archive-tree inventory;
2. immutable M6 execution spec, public gate, close proof, historical
   verification receipt and approved frozen verifier source;
3. M3 product manifest and every consumed partition;
4. M6 run manifest, candidate list, all 14 fold receipts, every checkpoint
   `metadata.json` and `state_dict.pt`, every candidate prediction partition,
   and K16 deterministic-refit receipt/reference score;
5. legacy read-only ledger plus before/after identity;
6. sealed-root verifier v3, FD-exec helper, bootstrap, `ReplayRuntimeClosure
   v3`, `PythonStartupPolicy v1`, `ProcessStartupState v1` and the fixed
   argv/cwd/import policy;
7. immutable `ReplayOutputNamespace v1` policy ArtifactRef and the immutable
   `NamespaceParentBinding v1` ArtifactRef above; and
8. the separate `FreshOutputReservation v2` below.

`FreshOutputReservation v2` is a closed non-content record embedded in v8:

```text
reservation_id + binding-frozen nonce + derived basename
namespace-policy ArtifactRef digest
NamespaceParentBinding ArtifactRef digest
must_be_absent=true
required output schema + exact 14 replay / 0 fit / OOS=false profile
```

It has no SHA/bytes for future output and accepts no caller path. The v8 binding
fixes `14 replay / 0 fit / OOS=false`; no caller may select source, product,
run, checkpoint, prediction, ledger, output, runtime, interpreter root or
namespace parent. v7/v1 reservation and v7 binding are rejection-only for a
new replay; no implicit migration is allowed.

At freeze, supervisor opens the trusted control-root FD, resolves the strict
parent path with the exact resolver above, validates the namespace policy and
all chain/parent facts, verifies `fstatat(parent_fd, basename,
AT_SYMLINK_NOFOLLOW) == ENOENT`, writes and hashes `NamespaceParentBinding v1`,
then freezes reservation v2 and binding v8. The absence observation is a
precondition, never a claim that future output already has content.

## 3. Execution, handoff and acceptance equality

Before launch, the replay supervisor reopens the control root and resolves the
parent again without following links. It derives a fresh parent witness and
requires byte-for-byte equality with the frozen `NamespaceParentBinding v1`
and its digest in reservation v2/v8. It takes the namespace lock by verified
FD, resolves and compares a second time under that lock, rechecks basename
absence, and calls `mkdirat(parent_fd, derived_basename, 0700)`. Successful
`mkdirat` is the sole linear reservation point.

The supervisor then reopens the child by FD/no-follow, verifies exact owner and
mode, derives and compares the parent witness a third time, fsyncs parent and
root, and writes `OutputReservationReceipt v2` containing the exact v8,
reservation-v2 and parent-binding digests; pre/post parent observations;
created-root stable identity; empty inventory; owner/mode; and supervisor
identity. `EEXIST`, a substitution, a wrong type/ACL/owner/mode, a non-empty
root, a stale receipt, or any equality failure rejects before `mkdirat`; an
equality failure after it makes the root `QUARANTINED_UNPUBLISHED`.

The sealed handoff descriptor contains only the pinned descriptor FDs and the
three digests (parent-binding, reservation and reservation receipt). The child
bootstrap re-fstats those descriptors, emits the same parent/root identities in
its child receipt, and accepts no path argument. `ReplayExecutionReceipt v7`
and the child receipt must agree exactly on v8, reservation v2,
`NamespaceParentBinding v1`, reservation receipt, root identity, runtime,
startup/process state, seed/umask, stage/checkpoint and prediction facts.

At archive acceptance, `m6_archive` again acquires the namespace lock,
re-resolves control-root → parent with the same resolver, and requires exact
equality to the frozen parent-binding artifact. It opens the derived basename
under that verified parent without following links and requires its stable root
identity to equal every receipt before hashing the final inventory. A parent or
intermediate-chain swap after execution therefore fails archive acceptance.
Only v8 + reservation-v2 + parent-binding + matching supervisor/child v7
receipts, a new output, and an unchanged legacy ledger can be accepted.

The lifecycle is:

```text
POLICY_VALID → PARENT_BOUND → RESERVATION_FROZEN → PRELAUNCH_REVALIDATED
→ RESERVED (mkdir linear point) → HANDOFF_VERIFIED → EXECUTED
→ ARCHIVE_REVALIDATED → ACCEPTED
```

Any mismatch before `RESERVED` is `REJECTED`; any mismatch/crash after it is
`QUARANTINED_UNPUBLISHED`. A quarantined root is never deleted, recreated,
promoted or reused under the same reservation.

## 4. Mandatory synthetic design evidence

Tests must reject: final-parent D0→same-owner/mode/ACL D1 replacement between
freeze and launch; intermediate-chain replacement; a replacement race before
`mkdirat`; a swap after `mkdirat`/handoff before archive; symlink, `..`,
absolute, magic-link and cross-mount resolution; wrong parent FD/binding/
reservation/receipt; ACL/owner/mode drift; pre-existing/foreign/caller output
roots; stale/reused reservation; and crash after `mkdirat`. They must also show
that ordinary `mtime`/`nlink` changes alone do not cause a false failure, while
missing `openat2`/`statx` facts fail closed. These are synthetic tests only:
they neither run a server replay nor train M7 nor open final OOS.
