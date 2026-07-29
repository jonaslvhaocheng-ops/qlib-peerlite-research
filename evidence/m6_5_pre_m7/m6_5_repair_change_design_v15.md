# M6.5 R3 修复设计 v15 — M6-only control and linear reservation implementation

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一 base 是
`m6_5_repair_change_design_v14.md` SHA-256
`69e8373b847854e382ea4b3443eaecbeb52cca60d56210dd924173b59d2195a6`。
v14 保留的 M6/PIT/Gate/genesis/authority/ACL/descriptor-v5/closure-v2/
seed+umask/publisher/test-order requirements 继续完整有效；本文件替换 replay
control producer、namespace policy、claim and transition lineage，以修复 v14
双 P1。架构依据是 `architecture_confirmation_v18.md`。本阶段仅设计，不创建
M6 replay control object，不运行 replay/M7/PIT certification/OOS。

## 1. New authoritative forms and creation order

Implement strict, closed, canonical forms only:

```text
verified M6 close/proof
→ M6ReplayControlPolicy v1
→ ReplayOutputNamespace v2
→ M6ReplayControlProfile v1
→ M6ReplayControlAnchor v1
→ NamespaceParentBinding v3
→ FreshOutputReservation v4
→ M6ReplayInputBinding v10
→ S0…S6 / O v4 / H v2 / child v2 / execution v9 / archive v2
```

The policy compiler/activation are M6 archival-replay-only schemas with fixed
slots and typed M6 close/spec/gate/proof refs; they reject every M7 object or
reference. P v2 is mandatory and adds strict parent components/resolver,
allowed-output-schema ref and exact created-root ACL policy. P v1 and all
v17/v14 reservation/binding/receipt forms reject; no inferred migration.

## 2. One validator and one coordinate claim

Implement `validate_m6_replay_graph_v2()` for freeze, claim, prelaunch,
transition, recovery, child bootstrap and archive. It validates all typed
policy/profile/P/A/B/R/V equations from v18, including M6-only actor identity,
strict A-rooted registry/lock resolution, P=R=V output schema and root ACL,
and B's one-component derived leaf.

R v4 is written once with `O_EXCL` at the A-rooted coordinate path derived from
only A/P/B parent identity/leaf. It contains no V hash; a second R/V for the
same coordinate is rejected even when both metadata hashes differ. V v10 only
references pre-existing A/P/B/R and complete M6 inputs, never output identity,
state, receipt or mutable head.

## 3. Exact transition/receipt implementation

Use one A-anchored transaction lock; resolve and compare its registry/lock
components and identities at every use. Do not use a mutable current-head.
Create `ReservationTransition v1` records only at fixed paths with fixed
sequence/state, canonical predecessor ref, exact A/P/B/R/V/K refs, writer role
and root identity where applicable. Scan and reject any fork, gap, duplicate,
unknown file, wrong predecessor, state role, stale root identity or terminal
continuation.

Enforce P's actor map: replay supervisor alone writes S0/S1/O/S2/H/S3/S4/S5,
child verifier alone writes ChildReceipt, and archive acceptor alone writes
ArchiveAcceptanceReceipt/S6. Every phase record binds its role and effective
identity; a record from another identity fails even if its hashes are valid.

The only implementation order is:

```text
S0 → S1 → O → S2 → H → S3 → child receipt → S4
→ execution receipt → S5 → archive receipt → S6
```

Each arrow has the phase-specific reference matrix in v18; no object may point
right. Archive accepts only a rehashed S0…S5 chain with no terminal/future
record, writes archive receipt, then appends S6. A burned/quarantined terminal
is next-sequence-only and forbids every later record or acceptance.

## 4. Transaction and tests after design PASS

R claim and V freeze happen before any root creation. Create path uses separate
`O_PATH` identity and `O_RDONLY|O_DIRECTORY` sync FDs, validates parent/ACL,
calls `mkdirat` with the canonical leaf, captures and verifies root ACL/identity,
fsyncs root then parent, and appends S1/O/S2/H/S3 before handoff. All publishes
are no-replace durable writes; failures burn/quarantine without reuse.

The next test design must include policy/profile/P-version fixtures; M7 ref
rejection; P/R/V schema and ACL mismatch; duplicate-coordinate R claims;
anchored registry/lock substitution; all S0…S6 branch/splice/gap/future/cycle
fixtures; and retained path/FD/ACL/crash tests. Only a fresh independent PASS
allows test design, red tests and implementation; M7/CCC/Gate/final OOS remain
sealed.
