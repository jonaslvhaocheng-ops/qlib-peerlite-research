# M6.5 R3 修复设计 v16 — Closed M6 authority and pretransition recovery

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一 base 是
`m6_5_repair_change_design_v15.md` SHA-256
`b376d221fc2273d83db4aa608f031b8f8254789ea29ca6d10e6b3b34c23bc1b1`。
v15 保留的 M6/PIT/Gate/genesis/ACL/descriptor/closure/seed/umask/publisher
requirements 继续完整有效；本文件替换 replay authority and pretransition
contracts，以修复 v15 P1/P2。依据 `architecture_confirmation_v19.md`。本阶段
只设计：不得产生 E/T/C/P/F/A/B/R/V/Q 实例，不运行 replay/M7/PIT/OOS。

## 1. Authority implementation contract

Implement one strict `validate_m6_replay_authority_v2()` that expands E's exact
M6 execution-spec/gate/close-proof/historical-verification/6-44/M6.5-PASS refs
and requires role-by-role equality in C/P/F/A/V and V's historical inventory.
It enforces one `m6_archive_acceptor` policy-issuer/archive identity, E actor
ACL map, fixed E/T/C/P/F slots, M6-only nested allow-list and control-store
identity. No M7 object, alternate evidence set, alternate P slot/template,
implicit P upgrade, generic path or unlisted nested ref is accepted.

T is the pre-C namespace template. C binds E/T and P slot; P binds E/T/C and
field-equals T; F/A/V bind the same E/T/C/P. P=R=V schema, root ACL and profile
equality remains mandatory. `ReplayExecutionReceipt v10` is emitted only by
replay supervisor; archive acceptor emits archive receipt/S6; child verifier
only ChildReceipt.

## 2. Coordinate and pretransition implementation

Remove any `B.parent_identity_digest` input. Implement
`parent_identity_key(directory_identity)` as the SHA-256 of CanonicalObject-v1
`DirectoryIdentity v2`; recompute it from the no-follow parent FD whenever K is
used. K derives only from A, P, that recomputed key and B leaf. An unknown or
mismatching digest field rejects before R claim.

R v5 is the once-only O_EXCL K claim. It declares fixed V and Q slots but does
not refer to V. V v11 can be published only in R's V slot; Q then binds R/V in
the fixed Q slot; S0 requires Q. Under A's transaction lock, recovery maps every
pre-S0 combination to exactly one terminal: missing/invalid V,
missing/invalid Q, or Q-without-S0 becomes the fixed `PretransitionTerminal`
and burns R. A terminal rejects every future V/Q/S0; no retry/reuse/delete.

## 3. Retained linear transition implementation

After Q the sole lineage is S0→S1→O→S2→H→S3→ChildReceipt→S4→
ExecutionReceipt→S5→ArchiveReceipt→S6. Each state/receipt repeats E/T/C/P/F/
A/B/R/V/Q/K, exact predecessor and authorized writer. The scanner uses fixed
O_EXCL names and rejects all branch/splice/gap/future/terminal/current-head
forms. Output root transaction retains separate witness/sync FDs, ACL/empty/
identity checks, ordered fsync and no-replace durable publication.

## 4. Test design after independent PASS

Test design must include two-valid-evidence-set authority splice; early E issue
without quality PASS; policy/P template/slot/nested-ref mismatch; issuer/receipt
writer mismatch; canonical parent-identity-key tamper; R-only/V-only/Q-only
crash recovery; plus all retained state/coordinate/path/ACL/FD/umask fixtures.
Only fresh independent PASS permits test design, red tests or implementation.
M7/CCC/Gate/final OOS remain sealed.
