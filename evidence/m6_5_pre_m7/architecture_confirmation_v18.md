# M6.5 架构确认 v18 — M6-only replay authority and linear reservation lineage

状态：`ARCHITECTURE_READY / 待独立设计审查`。canonical base 为
`architecture_confirmation_v17.md` SHA-256
`2079525e3f0c9e6746d2047da3dd201f3d2a360cbc7bcb6bb1db9759037620f8`。
本文件完整替换 v17 的 replay-control authority、namespace policy、reservation
claim 和 transition-lineage contract；v17 以及更早版本保留的 M6 `6/44`、PIT,
public Gate、M7 descriptor/closure、seed/umask、ACL、runtime and final-OOS
boundaries 不变。它只定义将来的 M6 archival replay schema，绝不创建或激活
任何 policy/profile，也不授权 M7、replay、training、PIT certification 或 OOS。

## 1. A replay-only, pre-M7 authority root

`M6ReplayControlPolicy v1` is the sole policy producer for archival replay. It
may be emitted only by the M6 archive acceptor after it re-verifies exact typed
refs to the immutable M6 execution spec, M6 public gate, M6 close proof,
historical archive-verification receipt and the verified `6/44` close prefix.
It has `mode=M6_ARCHIVAL_REPLAY_ONLY`, `14 replay / 0 fit / OOS=false`, an
explicit M6-only actor/ACL map (`policy_compiler`, `replay_supervisor`,
`archive_acceptor`, `child_verifier`), a fixed immutable control-evidence store
and fixed policy/profile slots. It rejects every `M7*` schema, role, path,
QRC, Plan, Authority, activation or profile reference. The policy compiler has
no caller-selected authority/root input and emits its slot with `O_EXCL` only
after all M6.5 engineering-quality gates pass.

`ReplayOutputNamespace v2` (**P**) is a new immutable typed artifact produced
from that policy; P v1 is rejection-only and cannot be inferred/upgraded. Its
closed fields are: `policy_ref`; strict parent component list and canonical
relative path; exact `linux_openat2_v1` resolver; supervisor writer identity;
full allowed-output-schema typed ref; `no_reuse=true`; and exact created-root
specification (owner UID/GID, mode `0700`, canonical access ACL and absent
default ACL). All path components use a strict one-component grammar and no
caller path is permitted.

`M6ReplayControlProfile v1` is the single fixed-slot, `O_EXCL` activation for
P. It is produced only by the M6 replay supervisor after policy validation and
contains typed policy/P/M6-close refs, M6-only actor identities/ACLs, immutable
control-store identity and `M6_ARCHIVAL_REPLAY_ONLY` mode. It cannot reference
M7 or select an alternate root/profile. `M6ReplayControlAnchor v1` (**A**) is
then created in the profile-selected immutable control-evidence store and
contains full typed policy/profile/P refs, actual supervisor identity,
control-root identity, registry component list and component chain/identity,
and one fixed transaction-lock component and identity. A's content universe
excludes B/R/V, registry state, receipts, staging, output roots and any mutable
tree inventory. A registry components and its lock component use the same
nonempty one-component grammar as P; they are resolved only below A's root FD
with the anchored resolver, never by a caller path or mutable registry head.

The only allowed static order is:

```text
verified M6 close/proof → M6ReplayControlPolicy v1 → P v2
→ M6ReplayControlProfile v1 → A v1 → B v3 → R v4 → V v10
```

All objects use `CanonicalObject v1` (duplicate-key rejection, closed schemas,
canonical bytes and complete typed `ArtifactRef`s); unknown/legacy/same-name
different-schema/digest-only forms fail closed.

## 2. Unique coordinate claim and graph equations

`NamespaceParentBinding v3` (**B**) preserves v17's FD-derived complete
control-root→parent identity chain, resolver and strict leaf derivation, but
references exact A/P. `FreshOutputReservation v4` (**R**) is the durable,
existing metadata claim itself; it is not the future output root and carries no
future-output hash. Its unique coordinate key is:

```text
K = SHA256(CanonicalObject-v1({
  domain: "qlib-peerlite/m6-replay-coordinate/v1",
  anchor_sha256: A.sha256,
  namespace_sha256: P.sha256,
  parent_directory_identity_digest: B.parent_identity_digest,
  leaf_component: B.basename
}))
```

R is published at the fixed A-rooted path
`registry/claims/<K>/reservation.cjson` using `O_EXCL`, validated root→registry
FD resolution and fsync. Its payload binds exact A/P/B refs, K, the expected
output schema and created-root ACL spec, and the fixed `14 replay / 0 fit /
OOS=false` profile. A second R for the same K, even if it has a different R or
V hash, is rejected and permanently burns that coordinate. R has no V ref;
thus K contains neither R nor V hashes and no cycle exists.

`M6ReplayInputBinding v10` (**V**) preserves the full v17 M6 inventory and
contains typed A/P/B/R refs plus required output schema/root ACL spec/profile;
it contains no output-root identity, transition, receipt or current-head ref.
Every phase enforces exactly:

```text
P.policy_ref == Profile.policy_ref == A.policy_ref
A.profile_ref == Ref(Profile); A.namespace_ref == Ref(P)
B.anchor_ref == A.ref; B.namespace_ref == P.ref
B.parent_components/relpath == P.parent_components/relpath
B.resolver == P.resolver; B.basename == CanonicalDerive(A,P,B.id,B.nonce)
R.{anchor,namespace,parent_binding} == {A,P,B}; R.coordinate_key == K
R.output_schema == P.allowed_output_schema == V.required_output_schema
R.root_acl_spec == P.created_root_spec == V.expected_root_acl_spec
R.profile == V.profile == {14 replay, 0 fit, OOS=false}
V.{anchor,namespace,parent_binding,reservation} == {A,P,B,R}
A.supervisor_identity == Profile.authorized_supervisor == P.writer_identity == effective supervisor
```

At freeze, claim, prelaunch, every transition/recovery and archive, resolver
checks also require: `Resolve(A.control_root, A.registry_components) ==
A.registry_chain/identity`, `Resolve(registry, A.transaction_lock_component) ==
A.transaction_lock_identity`, actual profile/store identity equals A, and the
existing B parent-chain/ACL identity checks. No registry path, lock or writer
is selected from a caller value.

## 3. Fixed, acyclic transition and receipt lineage

One A-anchored transaction lock serializes claim creation and every transition;
it is never under the output root. Long verifier execution may release it only
after `S4`, and each later state reacquires/revalidates the same anchored lock.
For every R, files live only under `registry/claims/<K>/transitions/` with fixed
`%03d-<STATE>.cjson` names, `O_EXCL`, canonical bytes and fsync. A transition
contains exact A/P/B/R/V/K refs, fixed `sequence_no`, `state_kind`, the complete
typed predecessor ref (null only for S0), writer role/identity, and created-root
identity/ACL where applicable. Scan validation rejects an unknown entry,
duplicate/gap, wrong filename/sequence, wrong predecessor, role, ref, root
identity, branch or terminal continuation; it never reads a mutable current head.

The only nonterminal lineage and receipt matrix is:

```text
S0 ISSUED
→ S1 RESERVED (prev S0; created-root identity)
→ O OutputReservationReceipt v4 (refs S0,S1)
→ S2 RECEIPTED (prev S1; ref O)
→ H ReplayHandoffAnchor v2 (ref S2,O)
→ S3 HANDOFF_ANCHORED (prev S2; ref H)
→ ChildReceipt v2 (ref S3,H)
→ S4 HANDED_OFF (prev S3; ref ChildReceipt)
→ ReplayExecutionReceipt v9 (ref S4,ChildReceipt)
→ S5 EXECUTED (prev S4; ref ReplayExecutionReceipt)
→ ArchiveAcceptanceReceipt v2 (ref S5 and rehashed full S0…S5 lineage)
→ S6 ACCEPTED (prev S5; ref ArchiveAcceptanceReceipt)
```

Every object only points left. Archive first verifies exactly S0…S5 and no
terminal/future/forked record, writes its receipt, then appends S6; the receipt
never points to S6. A failure/recovery appends exactly the next allowed terminal
`ABANDONED_BURNED` or `QUARANTINED_UNPUBLISHED` with its immediate predecessor;
terminal records make every later transition/acceptance fail. This makes stale
receipt selection, state splice, future-reference and archive cycle fail closed.

Only P-authorized identities may write these phases: replay supervisor writes
S0/S1/O/S2/H/S3/S4 and S5; child verifier writes only ChildReceipt; archive
acceptor writes only ArchiveAcceptanceReceipt and S6. Each record carries that
role and effective identity, which must equal the policy/profile/A actor map;
the validator rejects a correct-looking record from any other role.

## 4. Reservation and output transaction

Under A's single anchored lock, the supervisor revalidates all §2 equations,
full registry/root/parent identities and leaf absence, publishes/fsyncs R by
`O_EXCL`, then freezes V. Before actual create it revalidates again, writes S0,
uses `O_PATH` only as an identity witness and a separately equality-checked
`O_RDONLY|O_DIRECTORY` operation/sync FD for `mkdirat`, captures no-follow root
witness/sync FDs, verifies full root identity/ACL/emptiness, re-resolves parent
and leaf, and fsyncs root then parent. It appends S1, O, S2, H and S3 in the
matrix order before FD handoff; after bootstrap it appends S4, after execution
receipt S5, and archive appends S6. Every publication is same-directory temp
write → file fsync → atomic no-replace publish → directory fsync. Unsupported
identity/sync/no-replace primitive fails closed.

Mandatory synthetic tests include M7-reference rejection; P v1/implicit-upgrade
rejection; P=R=V schema/ACL mismatch; same B/leaf claimed through two R/Vs;
registry/lock path substitution; all transition fork/splice/gap/duplicate/
future/cycle fixtures; receipt-phase mismatch; and all existing parent/ACL/
crash/swap/O_PATH/no-reuse tests. They are synthetic only and cannot authorize
server replay, M7, PIT certification or final OOS.
