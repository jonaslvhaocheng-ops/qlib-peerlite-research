# M6.5 架构确认 v22 — Quality issuance, complete slot topology and official replay admission

状态：`ARCHITECTURE_READY / 待变更设计`。本文件以
`architecture_confirmation_v21.md`（SHA-256
`7e14a5b8a5cbdb1d1bc3e44fa7bb623ce9c5c8bba20cd1efe8ca418618b66881`）为直接
基线，并逐项解决 v18 两份独立 R3 审查与 reservation/official-result 审计的所有
P1/P2。v21 的完整 Context key、DirectoryIdentity v2（含 opaque handle）、K v4、
C→{P,F}→A、Q-before-R、pre-S0 terminal 和 M6/M7/OOS boundaries 保留。本文件
`DESIGN_ONLY`：不创建真实 quality pass、Bootstrap、E/C/P/F/A/B/Q/R/V、states 或
official result；不运行 replay、训练、PIT、M7 或 final OOS。

## 1. Pre-E quality issuance and observed-byte trust chain

唯一的 pre-E trust root 是冻结 M6.5 quality release policy，而不是调用方提供的
path/ref：

```text
M6QualityGateReleasePolicy v1 (fixed in the reviewed M6.5 release closure)
  = {
      sealed_control_anchor_contract,
      control_root_component = ["m6-replay-control"],
      quality/bootstrap slot = ["quality", "m6-replay-authority-bootstrap-v1.cjson"],
      quality/pass slot = ["quality", "m6-engineering-quality-gate-pass-v1.cjson"],
      quality_gate_issuer effective identity/ACL,
      allowed quality-pass and Bootstrap schemas,
      no-follow/no-xdev resolver profile
    }
```

该 policy 是冻结 runtime/release closure 的一部分，不能由 CLI、环境、cwd、配置文件或
Bootstrap 自己选择。`quality_gate_issuer` 是明确独立的 effective identity；它只可在
上述 two quality slots 发布，且顺序固定为：

```text
quality_gate_issuer publishes Bootstrap (O_EXCL, durable)
→ validates all M6.5 engineering evidence
→ quality_gate_issuer publishes M6EngineeringQualityGatePassV1 (O_EXCL, durable)
   whose replay_issuer_bootstrap_ref == Ref(Bootstrap)
```

Bootstrap 是 pre-E release input，不是 replay authority；只有 PASS 的实际 bytes 证明
它已完成 M6.5 quality route。它不能引用 E/C/P/F/A/B/Q/R/V、state、receipt、output、
time、PID 或 random。PASS 也不能引用任何 future replay object。

`archive_acceptor` 只能通过 `VerifiedQualityInputs` 取得这两个对象。该 capability 由
固定 release policy 的 sealed anchor FD 创建，且只在以下全部成功后出现：

```text
1. no-follow resolve root and quality parent from the policy; compare full D v2 chains.
2. open both fixed slots; compare observed canonical bytes to their complete typed refs.
3. parse M6ReplayAuthorityBootstrapV1 and M6EngineeringQualityGatePassV1 exactly.
4. require PASS.status=PASS, PASS.gate_id=M6.5-PRE-M7-ENGINEERING-QUALITY,
   PASS.replay_issuer_bootstrap_ref == Ref(observed Bootstrap), and all policy
   issuer/slot/schema/ACL/root/runtime/family/profile values equal Bootstrap.
5. retain observed bytes, typed refs and parent FD identities in VerifiedQualityInputs.
```

No API may construct `VerifiedQualityInputs` from a `TypedArtifactRef` alone or
by arbitrary repository path. `E` construction consumes only this capability,
not raw Bootstrap/PASS mappings. This makes the equality
`QualityPass.replay_issuer_bootstrap_ref == E.replay_issuer_bootstrap_ref` an
observed-byte proposition rather than a caller claim.

## 2. One exhaustive writer/identity/slot matrix

All writer roles, effective identities, ACL expectations and slots are closed in
Bootstrap and copied byte-for-byte into Context. The actual publisher verifies
the current peer/FD ACL and normalized `{uid,gid,groups,capabilities,process
identity}` before every write; a role string is never sufficient.

| Durable artifact / transition | Sole writer role | Root-relative fixed slot role |
| --- | --- | --- |
| Bootstrap, QualityPass | `quality_gate_issuer` | `QUALITY_BOOTSTRAP`, `QUALITY_PASS` |
| E `M6ReplayAuthorityBinding v3`, C `M6ReplayControlPolicy v5` | `archive_acceptor` | `AUTHORITY_E`, `CONTROL_POLICY_C` |
| P, F, A, B, Q, R, V; pre-S0 terminal; S0/S1/O/S2/H/S3/S4; ReplayExecutionReceipt/S5; post-S0 terminal | `replay_supervisor` | respective `SUPERVISOR_*` slots |
| ChildReceipt | `child_verifier` | `CHILD_RECEIPT` |
| ArchiveAcceptanceReceipt, S6, final index | `archive_acceptor` | `ARCHIVE_RECEIPT`, `S6`, `FINAL_INDEX` |

No writer is allowed to emit a role assigned to another row. In particular:

```text
quality_gate_issuer  cannot write E/C/R/V/states/output/archive;
archive_acceptor     cannot write Bootstrap/QualityPass/P/F/A/B/Q/R/V/S0-S5;
replay_supervisor    cannot write Bootstrap/QualityPass/E/C/ArchiveReceipt/S6/index;
child_verifier       cannot write anything except ChildReceipt.
```

`archive_acceptor.issue_authority_and_control(VerifiedQualityInputs,
ActorCapability, LockedVerifiedControlTopology)` is the sole E/C durable
publisher. It checks Bootstrap→Context equality, `authority_context_key`,
archive-acceptor actual identity, all E/C slot parents and O_EXCL publication;
then publishes E before C. The registry/lifecycle API has no E/C method. The
replay supervisor can begin only by reopening published E/C and validating their
complete Context snapshot.

## 3. Complete root-relative normal form for every durable slot

There is one `ReplayControlRootBinding v2`, rooted at the release-policy-verified
`m6-replay-control` FD. Every durable object uses **only root-relative** component
lists; no list is registry-relative and no code may strip/add a `registry`
prefix. Each `SlotSpec v1` is closed:

```text
SlotSpec = {
  role, root_relative_parent_components, parent_directory_identity_chain,
  leaf_rule, expected_schema, writer_role, publication_mode=O_EXCL_DURABLE
}
```

`parent_directory_identity_chain` contains the full `DirectoryIdentity v2` of
every directory from the verified replay-control root to the slot parent. The
only permitted dynamic leaf variables are validated lowercase `K` or the
validated `B.basename`; no separator, absolute path, `.`, `..`, symlink or
caller-selected parent is accepted. The following roles are exhaustive:

| Role family | Root-relative parent / leaf rule |
| --- | --- |
| `QUALITY_BOOTSTRAP`, `QUALITY_PASS` | `quality/` + fixed leaf |
| `AUTHORITY_E`, `CONTROL_POLICY_C` | `authority/`, `policies/` + fixed leaf |
| `NAMESPACE_P`, `PROFILE_F`, `ANCHOR_A` | `namespaces/`, `profiles/`, `anchors/` + fixed leaf |
| `PARENT_B`, `PRECOMMIT_Q`, `CLAIM_R`, `BINDING_V`, `PRE_S0_TERMINAL` | `registry/parents|precommits|claims|bindings|pre-s0-terminals/` + `<K>.<role-version>.cjson` |
| `S0` … `S6`, `POST_S0_TERMINAL` | `registry/states/` + `<K>.<state-or-terminal>.cjson` |
| `OUTPUT_O`, `HANDOFF_H` | `registry/outputs/`, `registry/handoffs/` + `<K>.<role>.cjson` |
| `CHILD_RECEIPT`, `EXECUTION_RECEIPT`, `ARCHIVE_RECEIPT` | `registry/receipts/` + `<K>.child|execution|archive.cjson` |
| `FINAL_INDEX` | `registry/final-index/` + `<K>.accepted.cjson` |
| actual output root | `outputs/` + validated `B.basename`; B's full D v2 must equal this `outputs/` parent identity |

The transaction lock has exactly one root-relative spec:

```text
LOCK = root / registry / locks / m6-replay-transaction.lock
```

Its **entire** directory chain and `FileIdentity v1` are carried by the binding.
All role parents—including quality, authority, policies, namespaces, profiles,
anchors, every registry subtree, receipts, states, final-index and outputs—are
reopened no-follow and compared before use. This closes same-ACL replacement in
any subtree, not only claims/bindings. E/C slots are outside the registry but are
still subject to the same root binding and lock-protected publication protocol.

## 4. Locked capability and all lifecycle mutation

`acquire_locked_verified_topology(anchor_fd, authority_or_bootstrap, actor)` is
the only API that can return an opaque `LockedVerifiedControlTopology`. It:

```text
resolve + compare root and every applicable SlotSpec parent chain
→ open exact LOCK from root-relative components
→ acquire an `F_OFD_SETLK` exclusive lock with CLOEXEC (unsupported primitive fails closed)
→ re-open and compare root, lock and all applicable parents after lock acquisition
→ return an unforgeable in-process capability owning the lock FD
```

The capability cannot be reconstructed from a dataclass/mapping, cannot cross
fork/exec, and is closed on failure. Every mutable operation requires it and
rechecks terminal/predecessor/slot absence immediately before publish. Lock loss,
actor mismatch, fork/exec, a changed FD identity or a failed publish writes
nothing and forces a fresh root→lock acquisition.

Under one held capability, the registry makes exactly one decision for a claimed
K: `(R → V)` or `(R → PreS0Terminal)`, never both. A recovery scan holds the same
capability through inspection and terminal publication; it never races a V
publisher. The sequence is:

```text
validate Context/D/K → Q
→ acquire LockedVerifiedControlTopology
→ revalidate Q/D/K/no terminal
→ publish R
→ recheck terminal/no V; publish V=CanonicalComplete(Q,Ref(R))
→ publish S0 only if no terminal
```

If a process crashes after R, the kernel releases the lock; the successor must
reopen/revalidate every chain before deciding V or terminal. No O_EXCL on a
separate file substitutes for the held-state-machine lock.

## 5. Complete S0…S6 lifecycle and official-result admission

`M6ReplayLifecycle` owns the whole post-V sequence and exposes only these stable
operations, each requiring `LockedVerifiedControlTopology`, a validated Context
snapshot and the prescribed actor capability:

```text
enter_s0(V) -> S0
prepare_output(S0, B) -> S1, O, S2
seal_handoff(S2, output_FDs, launch_contract) -> H, S3
record_child(ChildReceipt) -> S4
finalize_execution(S4, child_receipt) -> ReplayExecutionReceipt, S5
accept_archive(S5) -> ArchiveAcceptanceReceipt, S6, FinalIndex
recover_post_s0(K) -> {ARCHIVE_MAY_ACCEPT_S5, QUARANTINED_POST_S0, REJECT}
```

Every transition contains E/C/P/F/A/B/Q/R/V/K, complete Context snapshot,
immediate predecessor, writer identity, fixed role slot and observed FD/root
identities. The caller cannot provide a next-state path or mutable head. Output
creation is impossible before S0; `O` records the created output-root D v2 and
the final parent/leaf comparison. H captures only sealed FD descriptors and the
fixed launch contract; child receives no control-root writer capability.

Post-S0 recovery is conservative: under the held topology lock, a complete S5
with no later artifact may be handed to `archive_acceptor`; any incomplete,
forked, gap, unexpected output, wrong writer or crash-ambiguous S0…S4 sequence
causes one fixed `POST_S0_TERMINAL` published by replay supervisor and permanently
blocks execution/acceptance for K. S6/FinalIndex can never coexist with a
terminal. This adds no back-edge: terminals reference only prior objects.

`AuthorizedArchivalReplayLauncher` is a subcomponent of lifecycle and the only
route that may invoke the existing `verify_m6_peerlite_archival_replay.py`
mechanics worker. The launcher uses Context's fixed runtime/argv/cwd/import
contract and `env -i`, passes only verified immutable inputs plus a sealed
staging/output FD, then binds the child's raw mechanics receipt into
ChildReceipt/ReplayExecutionReceipt. The existing worker's caller paths and
`qlib_peerlite_m6_archival_checkpoint_replay_v1` PASS receipt remain
**MECHANICS_ONLY**: a direct CLI run cannot create a valid Context-bound
control-slot chain and its raw receipt is explicitly rejected by lifecycle/
acceptance parsers.

`OfficialArchiveResolver` is the sole reader for official archival result. It
reopens the root/topology, resolves only the fixed `FINAL_INDEX` slot, and accepts
only a matching Context-bound `S6 + ArchiveAcceptanceReceipt + S5` chain written
by archive acceptor. It rejects raw worker receipts, `M6ArchiveSummary`, generic
`status=PASS`, staging directories, caller paths and any mutable-current-head
selection. Therefore a normal direct replay can be useful forensic evidence but
cannot become an official result.

## 6. Retained acyclicity, scope and decision

The complete directed graph is now:

```text
frozen M6.5 release policy
→ Bootstrap → QualityPass → VerifiedQualityInputs
→ E → C → {P,F} → A → B → Q → R → V
→ S0 → S1 → O → S2 → H → S3 → ChildReceipt → S4
→ ReplayExecutionReceipt → S5 → ArchiveAcceptanceReceipt → S6 → FinalIndex
```

`POST_S0_TERMINAL` may reference only a predecessor; it never points forward.
No Context key includes a future object. Legacy worker and `m6_archive.py` remain
read-only/mechanics-only evidence and do not enter official resolution. This is
still one local Python control-plane, not a service/database expansion; it adds
only the minimum issuer, slot, lock, lifecycle and resolver boundaries needed to
make the frozen ordinary-failure model mechanically testable.

The next required action is a v19 change design that maps these roles and APIs to
code. A fresh independent R3 design review must pass before test design, red
tests, implementation, code review, archival replay, M7, CCC/Gate or final OOS.
