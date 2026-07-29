# M6.5 架构确认 v17 — Canonical replay reservation graph and durable transaction

状态：`ARCHITECTURE_READY / 待独立设计审查`。canonical base 为
`architecture_confirmation_v16.md` SHA-256
`4a245590e8cc2a30610376167c67cbf3054d039a70fa2c7d410711f4d05992a4`。
除本文件完整替换的 M6 replay-output reservation contract 外，v16 保留的
M6 `6/44`、PIT/state、public Gate、actor ACL、one-way authority、descriptor
v5/closure v2、effective seed/umask、M7 publisher、Linux authoritative
platform 和 M6 replay input/runtime controls 全部继续有效。本文件不授权
M7、M6 replay、PIT certification、OOS 或历史证据修改。

## 1. Canonical bytes, typed references and one acyclic graph

All new replay-control objects use `CanonicalObject v1`: UTF-8 without BOM;
recursive duplicate-key rejection; closed schema and unknown-field rejection;
ASCII byte-lexicographic object-key order; no whitespace, float, NaN, Infinity
or `-0`; fixed-order arrays (set-like arrays sorted and duplicate-free); and
canonical reserialization whose bytes must equal supplied bytes. `sha256` is
over those exact bytes. A typed `ArtifactRef` is always the complete tuple
`(role, relative_path, schema_version, sha256, bytes)`, never a bare digest.
Legacy, same-name/different-schema, unknown-field and implicit-upgrade objects
fail closed.

Let existing immutable `ReplayOutputNamespace v1` policy be **P**. The only
allowed dependency graph is:

```text
P + activated replay-control profile
        ↓
ReplayControlRootAnchor v1 (A)
        ↓
NamespaceParentBinding v2 (B)
        ↓
FreshOutputReservation v3 (R)
        ↓
M6ReplayInputBinding v9 (V)
        ↓
ReservationRegistry v1 transition records (S)
        ↓
OutputReservationReceipt v3 (O)
        ↓
ReplayHandoffAnchor v1 (H)
        ↓
child receipt / ReplayExecutionReceipt v8 / ArchiveAcceptanceReceipt
```

`A` is the sole typed replacement for the former ambiguous control-root digest.
The governance supervisor creates it atomically/no-overwrite in the immutable
control-evidence store selected by the already-active replay-control profile,
before B/R/V and outside the mutable control-root inventory it identifies.
Its closed content universe is only existing profile/policy refs, P, the
control-root and metadata-registry identities/ACLs, resolver profile and writer
identity. It explicitly excludes B/R/V/S/O/H, staging, output roots and any
tree inventory. Thus no edge can point backwards or form a hash cycle.

`A` contains: activation-profile and control-plane-policy typed refs; typed P;
control-root `DirectoryIdentity v2`; metadata-registry relative path and
identity; strict resolver profile; and `writer=governance-supervisor`.
No parser may substitute a mutable registry head or a whole-tree hash for A.

`DirectoryIdentity v2` is FD-derived and contains only:

```text
type=directory; dev_major; dev_minor; ino; statx_mnt_id; btime_ns;
opaque_file_handle_sha256 from name_to_handle_at(AT_EMPTY_PATH);
uid; gid; mode_octal; access_acl_sha256; default_acl_sha256
```

It deliberately excludes `mtime`, `ctime` and `nlink`. The authoritative Linux
x86_64 helper must obtain all listed `statx`, opaque-handle and canonical
FD-ACL facts; unsupported filesystem/API, low-fidelity identity, resolver
fallback, symlink, `..`, absolute/magic-link path or cross-mount resolution
fails closed. Synthetic adapters may exercise the protocol but never issue
acceptance evidence.

## 2. One source of truth for coordinates and exact graph equations

Only **B** carries reservation coordinates. Its closed fields are typed refs to
A and P; P's strict parent component list and canonical relative path; exact
`linux_openat2_v1` resolver; root/final-parent identities and the complete
root→parent component identity chain; and:

```text
reservation_id (canonical UUID form)
nonce_hex (exactly 32 random bytes in lowercase hex)
derivation_version = ReplayLeafDerive v1
basename
```

The sole valid basename is:

```text
"m6r-" + lowercase_hex(SHA256(CanonicalObject-v1({
  domain: "qlib-peerlite/replay-output-leaf/v1",
  control_root_anchor_sha256: A.sha256,
  namespace_policy_sha256: P.sha256,
  reservation_id: B.reservation_id,
  nonce_hex: B.nonce_hex
})))[0:52]
```

It must match exactly `^m6r-[0-9a-f]{52}$`. Therefore it is a single pathname
component and rejects empty, `.`, `..`, slash, backslash, NUL, absolute,
Unicode-normalization and multi-component values before any `*at()` call.
`mkdirat` and reopen receive only this verified component.

**R** contains no duplicate policy/name/nonce fields and no future-output hash.
It is an existing immutable metadata artifact, not the future output root:

```text
FreshOutputReservation v3 =
  parent_binding_ref = Ref(B)
  must_be_absent = true
  required_output_schema_ref
  required_profile = { replay_count: 14, model_fit_count: 0,
                       final_oos_opened: false }
```

**V** preserves the complete v16 M6 input inventory: transfer/archive/tree;
M6 immutable spec/gate/close proof/historical verifier source; M3 product and
every consumed partition; run/candidates/14 fold receipts/checkpoints/
predictions/K16 refit; read-only legacy ledger; verifier/FD helper/bootstrap/
runtime/startup/process/fixed argv-cwd-import; plus typed P, A, B and R. It has
no caller-selected source, product, run, checkpoint, prediction, ledger,
output, runtime, interpreter, root or parent path.

At freeze, prelaunch, under namespace lock, post-`mkdirat`, handoff and archive,
the verifier must enforce all equations (not merely compare local hashes):

```text
A.namespace_policy_ref == Ref(P)
B.control_root_anchor_ref == Ref(A)
B.namespace_policy_ref == A.namespace_policy_ref == V.namespace_policy_ref == Ref(P)
B.parent_components / B.parent_relpath == P.parent_components / P.parent_relpath
B.resolver_profile == A.resolver_profile == P.resolver_profile
B.basename == CanonicalDerive(A.sha256, P.sha256, B.reservation_id, B.nonce_hex)
R.parent_binding_ref == Ref(B)
R.required_output_schema_ref == V.required_output_schema_ref
R.required_profile == V.required_profile == {14 replay, 0 fit, OOS=false}
V.control_root_anchor_ref == Ref(A); V.parent_binding_ref == Ref(B); V.reservation_ref == Ref(R)
```

For each of those phases, resolving from A's trusted root FD must also prove:

```text
Observe(root_fd) == A.control_root_identity
Resolve(root_fd, B.parent_components) == B.parent_chain
Observe(final_parent_fd) == B.parent_identity
leaf == B.basename
```

## 3. Durable no-reuse reservation transaction

`ReservationRegistry v1` is supervisor-only metadata rooted and identity-bound
by A. It is not part of A's content universe. Its records are canonical,
append-only/no-overwrite transition artifacts keyed by `R.sha256`; a same-R
second issue is always rejected. State is monotonic:

```text
ISSUED → RESERVED → RECEIPTED → HANDOFF_ANCHORED → HANDED_OFF
       → EXECUTED → ACCEPTED
any nonterminal state → QUARANTINED_UNPUBLISHED
ISSUED with no root after recovery → ABANDONED_BURNED
```

After V is frozen and before any prelaunch attempt, the supervisor acquires
locks in the sole order `activation/profile → registry → namespace`. It creates
the durable `ISSUED` record containing exact typed V/B/R refs with no-overwrite,
fsyncs the record and registry directory, and only then examines or creates an
output root. Thus a crash or rejection after issue burns R permanently; a new
attempt needs a new nonce → B → R → V.

`O_PATH` FDs are identity witnesses only and are never used for `fsync`. While
holding all three locks, the supervisor executes this exact transaction:

1. Resolve A root→B parent using the pinned `openat2` profile into an
   `O_PATH|O_DIRECTORY` witness FD; separately resolve a
   `O_RDONLY|O_DIRECTORY` sync/operation FD and immediately compare both full
   identities/ACLs to A/B/P.
2. Re-resolve and compare the full chain under namespace lock; validate every
   graph equation and `fstatat(parent_witness_fd, B.basename,
   AT_SYMLINK_NOFOLLOW) == ENOENT`.
3. Call `mkdirat(parent_sync_fd, B.basename, 0700)`, then immediately obtain
   no-follow witness and sync FDs for the created root. Verify its complete
   `DirectoryIdentity v2`, empty inventory, expected owner/gid/mode and exact
   access ACL/default-ACL absence required by P.
4. Re-resolve A root→parent and canonical basename, prove it still names the
   captured root identity, then `fsync(root_sync_fd)` followed by
   `fsync(parent_sync_fd)`.
5. No-overwrite publish and fsync `RESERVED` S with exact V/B/R refs and root
   identity; no-overwrite publish/fsync O with typed A/P/B/R/V/S refs and the
   same identity; then publish/fsync `RECEIPTED` S.
6. No-overwrite publish/fsync H with typed A/P/B/R/V/S/O refs, sealed
   descriptor identity and created-root identity; publish/fsync
   `HANDOFF_ANCHORED` S; only then transfer sealed root FD, read-only parent
   identity FD and descriptor FD to the child.
7. Child bootstrap re-verifies the full graph and FDs, emits its typed receipt,
   supervisor verifies it and publishes/fsyncs `HANDED_OFF` S before releasing
   namespace/registry locks.

Every durable publish is same-directory temp write → file fsync → Linux atomic
no-replace publish → parent-directory fsync. Missing no-replace, sync or
identity primitives fails closed. A crash at any step is recovered under the
same locks: root absent after ISSUED becomes `ABANDONED_BURNED`; root present
without complete later records becomes `QUARANTINED_UNPUBLISHED`; neither is
deleted, recreated, promoted or reused.

## 4. Typed receipts, archive acceptance and required tests

O, H, child receipt, `ReplayExecutionReceipt v8` and
`ArchiveAcceptanceReceipt` all contain complete typed refs for A/P/B/R/V/S/O/H
as applicable, strict schema/role/version/byte equality, and the full
created-root `DirectoryIdentity v2` including ACLs. No receipt accepts legacy,
unknown, partial, defaulted or digest-only forms. Archive reacquires locks in
the same order, validates the full graph, re-resolves A root→parent and B leaf
with no-follow/no-xdev semantics, requires equality of the root identity in all
receipts and S, rehashes final inventory, and only then may record ACCEPTED.

Mandatory synthetic tests must reject: any B/R/V/P/A ref or profile mismatch;
duplicate-key/unknown/legacy object; malformed or escaping leaf; same-ACL final
parent or intermediate-chain replacement; wrong FD/receipt/state; root ACL or
default-ACL drift; unsupported identity/sync primitive; and every crash/swap
hook from `mkdirat` through handoff and archive. They must prove `O_PATH` is
never fsynced, ordinary `mtime`/`nlink` changes do not falsely fail, and a
burned/quarantined R cannot be reused. They remain synthetic only: no server
replay, M7 fit, PIT certification or final-OOS access.
