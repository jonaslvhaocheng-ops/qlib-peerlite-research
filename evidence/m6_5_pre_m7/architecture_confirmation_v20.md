# M6.5 架构确认 v20 — Authority bundle, precommit and non-reconstructable claim

状态：`ARCHITECTURE_READY / 待独立设计审查`。canonical base 为
`architecture_confirmation_v19.md` SHA-256
`073f5b150a5d6ab5978a84ac1ef0d39793780688a3557479583081b0bcb1db52`。
v19 的 M6/PIT/M7/FD/ACL/umask/OOS boundaries remain intact. This document
replaces its authority materialization and R→V logic with an acyclic precommit
model. It is `DESIGN_ONLY`: no policy/profile/claim/replay/training/PIT/OOS
instance is created.

## 1. Exact M6 authority bundle and materialization DAG

`M6ReplayAuthorityBinding v2` (**E**) is an immutable closed record emitted in
one fixed `O_EXCL` slot by the sole `PolicyIssuer = archive_acceptor` effective
identity. E has exactly these typed evidence roles:

```text
m6_execution_spec
m6_public_gate
m6_close_proof
m6_historical_verification
m6_verified_close_6_44
m6_5_quality_gate_pass
```

The first five are frozen M6 evidence; the sixth is an independent M6.5
engineering-quality PASS receipt that cannot reference any future replay object.
E also contains the M6-only actor/ACL map, evidence/policy/namespace/profile
slots, immutable control-store identity and recursive exact nested-ref allow-list.
It rejects all M7/QRC/Plan/Authority/Profile schemas and any ref not on that
allow-list. No free authority, root or writer selector exists.

`E.m6_evidence_key` is a derived (never caller-supplied) canonical hash of the
six complete refs, family ID, frozen verifier/runtime-contract refs and scope
`M6_ARCHIVAL_REPLAY_ONLY`. C/P/F/A/Q/V each carry that same key only as an
index; the validator recomputes it from their six full role refs and rejects any
key mismatch or same-label/different-bytes evidence set.

Only this DAG is valid:

```text
six E evidence roles + PolicyIssuer
→ C M6ReplayControlPolicy v4
→ { P ReplayOutputNamespace v4, F M6ReplayControlProfile v4 }
→ A M6ReplayControlAnchor v4 → B NamespaceParentBinding v5
→ Q ReplayInputPrecommit v1 → R FreshOutputReservation v6
→ V M6ReplayInputBinding v12 → S0…S6 / receipts
```

For every `X ∈ {C,P,F,A,Q,V}`, `X.m6_evidence_roles` is required and equals
E's six complete typed refs role-by-role (schema, role, path, hash and bytes),
not merely an evidence-set digest. Each has `mode=M6_ARCHIVAL_REPLAY_ONLY`,
profile `{14 replay,0 fit,OOS=false}`, and the same E actor map. R carries the
same E role map as a redundant claim check. V additionally carries the full
historical M6 inventory, whose six corresponding roles must equal E exactly.

C contains E, its issuer identity/slot ACL and a closed **PTemplate**—not a P
hash. PTemplate fixes P slot, replay-supervisor output writer, parent components,
resolver, root ACL spec, output schema, profile and recursive allowed nested
refs. P is instantiated by replay supervisor from that template with only the
permitted `self_policy_ref=Ref(C)` substitution; all other fields must exactly
equal the template. F is independently materialized by replay supervisor from
C's fixed profile slot/template and cannot select a P or policy. A binds exact
C/P/F and proves both are the valid C-derived materializations. Thus C never
points to P content, P never points to F/A/V, and no policy/materialization cycle
is possible.

The writer matrix is immutable: archive acceptor writes E/C and archive receipt/
S6; replay supervisor writes P/F/A/B/Q/R/V, pre-S0 terminal, S0/S1/O/S2/H/S3/
S4, `ReplayExecutionReceipt v11` and S5; child verifier writes only ChildReceipt.
Every emitted object binds `writer_role + effective UID/GID/groups/capability /
process identity`, and validation compares it to E's map and actual peer/FD ACL.
In particular, `C.execution_receipt_writer == P.execution_receipt_writer ==
F.execution_receipt_writer == A.execution_receipt_writer ==
Q.execution_receipt_writer == V.execution_receipt_writer == replay_supervisor`;
the observed `ReplayExecutionReceipt v11` writer must equal that identity.

## 2. Canonical coordinate identity and complete V precommit

Let `D = B.final_parent_identity : DirectoryIdentity v2`. `D` is inline closed
canonical data observed through a no-follow FD (type, dev major/minor, inode,
mount ID, btime, uid/gid/mode, access/default ACL); it excludes mtime/ctime/
nlink/atime. No `parent_identity_digest` field exists. The coordinate uses D's
canonical bytes directly:

```text
K = SHA256(CanonicalObject-v1({
  domain: "qlib-peerlite/m6-replay-coordinate/v3",
  anchor_sha256: A.sha256,
  namespace_sha256: P.sha256,
  final_parent_identity_v2: D,
  leaf_component: B.basename
}))
```

At freeze, claim, prelaunch, recovery and archive, the validator requires
`Canonical(Observe(final_parent_fd)) == Canonical(D)` and recomputes K from
A/P/observed D/leaf. Unknown decorative digest fields fail parsing; same physical
parent and leaf therefore cannot form two coordinate keys.

Q is a canonical **complete V preimage** constructed before any claim. It binds
E/C/P/F/A/B, all V historical input/runtime fields, profile/schema/root ACL,
K, exact future V slot and no output/state/receipt/current-head/wall-clock or
random field. It contains neither R nor V. Its fixed path derives from A-rooted
registry and K, never Q/R/V hash.

R is the only `O_EXCL` K claim, published at a flat fixed slot
`registry/claims/<K>.reservation-v6.cjson`. It binds E/C/P/F/A/B/Q/K and declares
the fixed V and pre-S0-terminal slots, but never V content. V is valid only when
its raw canonical bytes equal `CanonicalComplete(Q, reservation_ref=Ref(R))` and
it is published no-replace at `registry/bindings/<K>.binding-v12.cjson`. Therefore
no choice remains between R creation and V freeze.

## 3. Pre-S0 crash state and linear execution state

The fixed pre-S0 terminal is `PreS0Terminal v1` at
`registry/pre-s0-terminals/<K>.cjson`, written only by replay supervisor under
A's anchored lock. Q alone is a lazy precommit, not a claim. Recovery is
conservative and unique:

```text
Q without R                         → no claim, no terminal
R without valid V                   → ABANDONED_BURNED_PRE_V
R + valid V without S0              → ABANDONED_BURNED_POST_V_PRE_S0
R + invalid/duplicate/partial V,
or output before S0                 → QUARANTINED_PRE_S0
existing PreS0Terminal               → reject V/S0/root/archive forever
```

R, V and terminal slots are flat fixed paths; crash residue is never removed or
reconstructed. When A root/lock cannot be revalidated, no substitute terminal
is written and the claim remains unavailable and unreusable.

Only after valid Q/R/V and absent terminal may the existing exact lineage run:

```text
S0 → S1 → O → S2 → H → S3 → ChildReceipt → S4
→ ReplayExecutionReceipt → S5 → ArchiveAcceptanceReceipt → S6
```

Each object repeats E/C/P/F/A/B/Q/R/V/K, exact immediate predecessor and
authorized writer. Fixed O_EXCL paths and scan validation reject gaps, forks,
splices, future refs, stale head selection, terminal continuation and receipt
phase mismatch. Execution receipt references only V + S4 + ChildReceipt +
observed runtime/output facts; S5 references it. Archive receipt references
S5 and rehashed S0…S5; only afterward can S6 be written.

## 4. Transaction and mandatory test evidence

Under A's resolved registry/transaction lock: validate E→V authority and D/K;
publish R; derive/publish V uniquely from Q+R; validate full graph; publish S0;
only then create future output with separate O_PATH witness and sync FD,
canonical leaf, no-follow root capture, ACL/empty checks and root-then-parent
fsync. All writes use temp → file fsync → atomic no-replace → directory fsync.

Synthetic tests must reject: any role-level C/P/F/A/Q/V evidence splice; E
without quality PASS; alternate P slot/template/nested ref; wrong issuer or
execution/archive writer; same parent/leaf with a decorative digest; Q/R/V
content mismatch; every pre-S0 crash combination; and all retained state,
coordinate, path, ACL, FD, umask and PIT boundary fixtures. They do not authorize
server replay, M7, PIT certification or OOS.
