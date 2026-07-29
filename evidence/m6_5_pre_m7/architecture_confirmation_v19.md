# M6.5 架构确认 v19 — Closed M6 replay authority and pretransition recovery

状态：`ARCHITECTURE_READY / 待独立设计审查`。canonical base 为
`architecture_confirmation_v18.md` SHA-256
`690484697271b00795a26f9e22bc04704114617a567f840fc3293ef40241715b`。
本文件替换 v18 的 M6 replay authority graph、coordinate derivation and
R→V pretransition lifecycle；其他已保留的 M6 `6/44`、PIT, M7 seal,
descriptor/runtime/umask/ACL and final-OOS controls remain unchanged. It only
defines future archival-replay schemas; no actual authority, profile, replay,
training, PIT certification or OOS access is created here.

## 1. Closed M6 authority bundle and namespace materialization

Before any replay-only object, the single `m6_archive_acceptor` effective
identity emits an immutable **`M6ReplayAuthorityBinding v1` (E)** in a fixed
`O_EXCL` evidence slot. E has exact typed refs, by role, to: M6 execution spec,
M6 public gate, M6 close proof, M6 historical-verification receipt, verified
M6 `6/44` close-prefix receipt, and an independent
`M6_5_ENGINEERING_QUALITY_GATE v1 PASS` receipt. The latter is independent of
all future replay objects and exists only after the full quality route passes.
E also closes the only M6-only actor/ACL map, fixed evidence/policy/template/
namespace/profile slots, fixed control-store identity, and a closed allow-list
of permitted nested schema/role/path templates. It rejects every M7/QRC/Plan/
Authority/Profile schema or any nested ref outside the allow-list.

The only static, acyclic order is:

```text
M6 evidence + independent M6.5 PASS → E AuthorityBinding
→ T M6ReplayNamespaceTemplate v1 → C M6ReplayControlPolicy v3
→ P ReplayOutputNamespace v3 → F M6ReplayControlProfile v3
→ A M6ReplayControlAnchor v3 → B NamespaceParentBinding v4
→ R FreshOutputReservation v5 → V M6ReplayInputBinding v11
→ Q InputBindingFrozenReceipt v1 → S0…S6
```

`m6_archive_acceptor` is the **only** policy issuer and archive acceptor; there
is no separate policy-compiler role. E maps it, replay supervisor and child
verifier to exact UID/GID/groups/capabilities/ACLs. It alone writes E/T/C/P,
ArchiveAcceptanceReceipt and S6; replay supervisor alone writes F/A/B/R/V/Q,
pretransition terminals, S0/S1/O/S2/H/S3/S4,
`ReplayExecutionReceipt v10` and S5; child verifier writes only ChildReceipt.
Every record binds its role and effective identity and the validator rejects a
correct-looking record from another identity.

T is a canonical, E-bound namespace template containing the one allowed P slot,
strict parent components/resolver, allowed-output-schema typed ref, created-root
owner/gid/mode/access-ACL/default-ACL-absent spec, output-writer identity and
all allowed nested artifact refs. C contains exact E/T refs, the same P slot
and no mutable selector. P is materialized by the sole issuer at that exact slot
and contains exact E/T/C refs; every template field and nested ref must equal T
and comply with E's allow-list. P v1/v2 and implicit/template-inferred upgrades
are rejection-only.

F and A contain exact E/T/C/P refs and repeat no free M6 evidence. V contains
exact E/T/C/P/F/A/B/R refs plus its complete historical M6 input inventory; its
execution spec, public gate, close proof, historical verification and `6/44`
role refs must exactly equal their E counterparts. At freeze, claim, prelaunch,
every recovery/transition and archive, `validate_m6_replay_authority_v1()`
requires this full role-by-role equality, fixed slot ownership, control-store
identity, actor map and nested allow-list compliance. A configuration splice
between independently valid M6 evidence sets therefore fails before any output
claim.

## 2. Canonical coordinate key and R→V pretransition lifecycle

`DirectoryIdentity v2` is canonical closed data. Its only digest is derived,
never caller-supplied:

```text
ParentIdentityKey(B) = SHA256(CanonicalObject-v1({
  schema: "DirectoryIdentity v2", value: B.parent_identity
}))

K = SHA256(CanonicalObject-v1({
  domain: "qlib-peerlite/m6-replay-coordinate/v2",
  anchor_sha256: A.sha256,
  namespace_sha256: P.sha256,
  parent_identity_key: ParentIdentityKey(B),
  leaf_component: B.basename
}))
```

`B.parent_identity_digest` is not a schema field and an unknown such field
fails parsing. At every validation phase, the helper reconstructs the canonical
directory identity from the no-follow FD, recomputes `ParentIdentityKey` and K,
and compares them to R. Thus two B objects for the same real parent/leaf cannot
obtain different coordinate claims through a decorative digest.

R is the one durable coordinate claim, published `O_EXCL` at the fixed
A-rooted `registry/claims/<K>/reservation.cjson`; it binds exact E/T/C/P/A/B,
K, schema/ACL/profile equality and the fixed **V slot**
`registry/claims/<K>/input-binding.cjson`, but it never references V. V is
written only by replay supervisor to that slot with no-replace publish and
contains exact E/T/C/P/F/A/B/R refs; no generic V path is accepted.

Q is then written at the fixed pretransition slot
`registry/claims/<K>/input-binding-frozen.cjson`; it contains exact R/V refs,
the V-slot identity and full authority equality. S0 requires exact Q. If a
recovery sees R with no valid V, V with no valid Q, Q with no S0, any invalid
slot object, or a pretransition terminal, it appends the only fixed
`PretransitionTerminal v1` at
`registry/claims/<K>/pretransition-terminal.cjson` with state
`ABANDONED_BEFORE_V`, `ABANDONED_UNFROZEN_V`, or `ABANDONED_BEFORE_S0` as
appropriate. A terminal prohibits V/Q/S0 and burns R permanently; no deletion,
retry or reuse is permitted. This makes every crash point between claim and S0
deterministic without a R↔V cycle.

## 3. Linear execution lineage and transaction

After Q, the v18 fixed lineage remains authoritative:

```text
S0 → S1 → O → S2 → H → S3 → ChildReceipt → S4
→ ReplayExecutionReceipt → S5 → ArchiveAcceptanceReceipt → S6
```

Each transition repeats exact E/T/C/P/F/A/B/R/V/Q/K refs, fixed sequence/state,
typed immediate predecessor, writer role/identity and root identity/ACL when
applicable. Files use fixed `O_EXCL` paths under the K claim; scan validation
rejects unknowns, duplicate/gap/fork, stale/foreign predecessor, terminal
continuation, phase/receipt mismatch and mutable-current-head selection. Archive
rehashes exact S0…S5 with no terminal/future entry, writes its receipt, then
appends S6; neither receipt references its later state.

The A-anchored registry and transaction lock are resolved from strict components
and rechecked by FD identity at every phase. Under that lock, R claim and V/Q
freeze happen before root creation; output creation uses `O_PATH` only as an
identity witness plus equality-checked `O_RDONLY|O_DIRECTORY` sync FDs,
canonical leaf, no-follow root capture, ACL/emptiness verification and root-then-
parent fsync. It appends S1/O/S2/H/S3 before handoff. Every artifact publish is
same-directory temp write → file fsync → atomic no-replace → directory fsync;
unsupported primitive fails closed.

Mandatory synthetic tests add: canonical-parent-key tamper; same parent/leaf
with altered decorative digest; R-only/V-only/Q-only crash recovery terminals;
policy/profile/P/A/V cross-splice across two valid M6 evidence sets; early
pre-quality-pass issuance; P template/slot/nested allow-list mismatch; issuer,
execution-receipt and archive identity mismatch; as well as all retained
coordinate, lineage, path/FD/ACL/umask/crash tests. They cannot authorize replay,
M7, PIT certification or OOS.
