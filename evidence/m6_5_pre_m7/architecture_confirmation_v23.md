# M6.5 架构确认 v23 — Pinned quality root, process-safe lifecycle and sealed mechanics adapter

状态：`ARCHITECTURE_READY / 待变更设计`。本文件以
`architecture_confirmation_v22.md`（SHA-256
`389ccd530c7705244e9025ef72efd891527a55a97286f14293e4912f12af49e9`）和
`m6_5_repair_change_design_v19.md`（SHA-256
`c6788d62318141b3a5f16e09f69e185303247910946582cb6501fad6b7b963a0`）为基线，
逐项修复 v19 两份独立 R3 设计审查及只读专项审计提出的六类普通故障路径。

本文件仍是 `DESIGN_ONLY`：不创建真实 release pin、policy、quality evidence、
Bootstrap、PASS、E/C/P/F/A/B/Q/R/V、states、receipt 或 official result；不运行
archival replay、训练、PIT、M7 或 final OOS；不修改 immutable M6 evidence、历史 raw
worker 或 trial ledger。所有后续测试仅可使用合成 FD、字节和 fake worker。

v22 已正确建立的内容保留：完整 Context key、`DirectoryIdentity v2`（含 opaque
handle）、K v4、`C → {P,F} → A`、Q-before-R、FinalIndex-only 官方读取和 M6/M7/OOS
边界。v23 只收紧其 release-root、进程生命周期、物化/恢复和 legacy worker 边界。

## 1. 在 Bootstrap 之前闭合的质量 release 根

### 1.1 不可由调用方替代的 pin

`M6QualityReleasePinV1` 是 frozen authorized entrypoint / release closure 的编译时
canonical 常量；它不是 CLI 参数、环境变量、cwd、配置文件、Bootstrap 或任意 Python
mapping。它只包含以下 closed fields：

```text
schema
release_id
authorized_entrypoint_ref
resolver_profile_ref
sealed_anchor_contract_ref
sealed_anchor_identity: DirectoryIdentityV2
release_policy_slot: {
  from_anchor_components,
  directory_identity_chain,
  fixed_leaf,
  expected_schema
}
policy_file_identity: FileIdentityV1
policy_typed_ref
policy_canonical_sha256
```

`release_policy_slot.directory_identity_chain[0]` 必须是 sealed anchor，且 chain length
精确等于 components length + 1。所有 component 均是 anchor-relative、no-follow、no-xdev，
拒绝绝对路径、`.`、`..`、separator 和 caller-selected parent。Pin 固定 policy 的 bytes/ref/
file identity；Policy 本身**不得自引用**，因而不存在 hash cycle。

唯一入口为：

```python
observe_verified_release_policy(
    sealed_anchor_fd: int,
    compiled_pin: M6QualityReleasePinV1,
    provider: FdIdentityProvider,
) -> VerifiedReleasePolicy
```

它先比较 anchor D-v2、policy parent full D-v2 chain、policy file identity、canonical
bytes/hash/ref，随后重新打开并比较 parent/root。任何 anchor、同 ACL 同名 parent、file
identity、hash、schema 或 pin 不一致都在任何 Bootstrap write、observed-quality capability
创建或 E/C 写入前 fail closed。

### 1.2 `M6QualityGateReleasePolicyV2` 与完整物理 topology

Pin 观察到的 canonical bytes 必须解析为 sealed
`M6QualityGateReleasePolicyV2`。其 observed typed ref 只保存在
`VerifiedReleasePolicy` 中，不能由 caller 构造。Policy 的 closed fields 是：

```text
schema, release_id, gate_id, canonicalization_profile
quality_route_contract_ref, runtime_closure_ref
quality_release_topology: QualityReleaseTopologyV1
exact_evidence_inventory: ordered closed role map
```

`QualityReleaseTopologyV1` 必须包含：

```text
schema, resolver_profile_ref, sealed_anchor_contract_ref, sealed_anchor_identity
release_policy_slot (byte-for-byte equal to pin.release_policy_slot)
replay_control_root_chain
quality_parent_chain
evidence_bundle_parent_chain
QUALITY_BOOTSTRAP slot, QUALITY_PASS slot
quality_gate_issuer effective identity and parent-ACL expectation
```

每个 chain 的唯一形式为
`{from_anchor_components, directory_identity_chain}`；每个 runtime slot 的唯一形式为
`{role, parent_components, parent_directory_identity_chain, fixed_leaf,
expected_schema, writer_role, publication_mode=O_EXCL_DURABLE}`。Bootstrap/PASS 只固定
parent D-v2、leaf、schema 和 writer/ACL；它们在尚未创建时不虚构 FileIdentity。

因此 Bootstrap 之前就已经由 Pin 固定并观察：sealed anchor、policy parent、control root、
quality parent、evidence-bundle parent 和两个 quality slot 的物理 topology。Bootstrap 后的
binding 只作再次验证，绝不反向认证其自身 parent。

### 1.3 精确 M6.5 质量 evidence closure

Policy 的 `exact_evidence_inventory` 是无 missing/extra/reorder 的 ordered role map。每一项
固定 evidence-bundle slot、expected schema、typed ref、file identity/hash 及 semantic
predicate。最小且完整的角色集合为：

```text
M6_5_CHANGE_REQUEST
M6_5_ARCHITECTURE_RESULT
M6_5_CHANGE_DESIGN_RESULT
M6_5_DESIGN_REVIEW_RESULT
M6_5_TEST_DESIGN_RESULT
M6_5_TESTS_RED_RESULT
M6_5_IMPLEMENTATION_RESULT
M6_5_TESTS_GREEN_RESULT
M6_5_CODE_REVIEW_RESULT
M6_5_E2E_RESULT
M6_5_ROUTE_CLOSURE
```

`M6_5_ROUTE_CLOSURE` 必须逐项引用前十项，并精确绑定 `change_id`、`gate_id`、ledger
snapshot、stage order、PASS/独立性/命令 receipts 等对应质量路由语义；它不得引用
Bootstrap、QualityPass 或任意 future replay object。Release builder 在离线封装阶段一次性
写 sealed read-only policy/evidence bundle，随后其 runtime ACL 对 quality issuer 只读。它不
是新的服务或 runtime publisher。封装发生在质量路由已闭合之后，且不改 product/test
source；开发/测试阶段只使用合成 pin 与合成 bundle，当前阶段不产生正式 pin 或 PASS。

只有 `VerifiedReleasePolicy` 能产生：

```python
observe_quality_evidence_inventory(verified_policy, provider) -> ObservedQualityEvidenceInventory
issue_bootstrap(verified_policy, issuer_capability) -> ObservedArtifact
issue_quality_pass(
    verified_policy, observed_inventory, observed_bootstrap, issuer_capability
) -> ObservedArtifact
observe_verified_quality_inputs(
    verified_policy, observed_inventory, provider, archive_acceptor_capability
) -> VerifiedQualityInputs
```

这些 API 不接收 raw policy/mapping/path，也不接收 caller-provided typed ref。实际顺序为：

```text
compiled Pin → observed PolicyV2/topology → observed exact evidence inventory
→ Bootstrap → QualityPass → VerifiedQualityInputs → E/C
```

QualityPass 必须携带并由 observed bytes 验证 policy ref、inventory ref、Bootstrap ref、
`status=PASS`、精确 gate id、issuer identity/ACL、runtime/family/profile/root/topology 值；
Bootstrap/PASS 现有时只允许 bytes 与此唯一构造值完全相等的幂等重读，任何不同 release
占用同一 leaf 都永久 fail closed。`VerifiedQualityInputs` 保存 observed policy/evidence/
Bootstrap/PASS bytes、refs、full parent identities，而 E/C 只接收该 opaque capability。

## 2. 闭合 writer、author 与 durable publisher 的边界

每项 durable slot 都有一个 physical publisher；语义作者与物理 publisher 不同时必须显式
编码，role string 从不等于授权。实际 `{uid,gid,sorted groups,capabilities,process identity}`
和 parent FD ACL 在每次写前都与 policy/context 比较。

| Object / transition | Semantic author | Sole durable publisher / lock owner |
| --- | --- | --- |
| sealed policy/evidence bundle | offline release builder | offline release builder；runtime read-only |
| Bootstrap, QualityPass | `quality_gate_issuer` | `quality_gate_issuer` |
| E, C | `archive_acceptor` | `archive_acceptor` with topology lock |
| P, F, A, B, Q, R, V; pre-S0 terminal; S0–S3; O; H; execution receipt/S5 | `replay_supervisor` | `replay_supervisor` with topology lock |
| `ChildMechanicsAttestationV1` | `child_verifier` | one-shot authenticated IPC only; never a control-root slot |
| `ChildReceiptEnvelopeV2`, S4 | `child_verifier` attestation + supervisor observation | `replay_supervisor` with topology lock |
| `ArchiveAcceptanceReceipt`, S6, FinalIndex, `ArchiveAcceptanceRejectionV1` | `archive_acceptor` | `archive_acceptor` with topology lock |
| raw mechanics receipt / worker scratch | raw worker | private non-official worker job only |

`child_verifier` has no control-root writer capability and cannot write `S4`, `ChildReceiptEnvelope`,
E/C, state, output or final index. `raw worker` cannot write any control-root slot. Conversely,
supervisor may publish an envelope only after validating a child-authored IPC attestation; it may not
invent a child author. This resolves the former contradictory “child sole writer + all durable writes
hold supervisor topology lock” rule.

All durable components remain root-relative `SlotSpecV1` objects. In addition to v22 roles, v23
defines:

```text
WORKER_JOB              registry/worker-jobs/<K>.job/        O_EXCL_DIR_DURABLE
CHILD_RECEIPT_ENVELOPE  registry/receipts/<K>.child-envelope.cjson
ARCHIVE_REJECTION       registry/archive-rejections/<K>.cjson
```

`WORKER_JOB` has a fixed verified parent and dynamic validated K-only leaf. Its private inner layout
is exactly `stage/…` and `scratch/raw-output`; no caller supplies an inner component. `raw-output`
must not exist at handoff. `ARCHIVE_REJECTION` is not `POST_S0_TERMINAL`: it records a malformed
post-S5 archival residue, blocks official admission, and can coexist only with an invalid/partial late
chain. A valid FinalIndex plus any rejection always fails closed in the resolver.

`registry/worker-jobs/` itself is supervisor-only `0700`; each job leaf is created `O_EXCL`, passed by
FD to the child session and given only the minimal child access required for its private contents.
The child has no search permission on the parent/root and no parent FD, so the received job descriptor
is not a reusable control-root traversal capability. Supervisor retains its own descriptor for later
no-follow re-observation.

## 3. Process-bound lock capability and clean child launch

`LockedVerifiedControlTopology` is an opaque, process-bound capability containing:

```text
owner_pid, process_generation, lock_fd, lock_file_identity,
verified root/slot FDs and identities, actor capability
```

The lock FD is opened no-follow `O_RDWR|O_CLOEXEC`; the only accepted primitive is an exclusive
`F_OFD_SETLK`. Acquisition resolves and compares every applicable SlotSpec parent, locks the exact
root-relative lock leaf, then reopens/recompares root, lock and parents. Every method first checks
current PID and generation, live FDs, actor identity/ACL, lock identity and terminal/predecessor
conditions. Failure closes/poisons the capability and writes nothing.

Because OFD locks survive fork through a copied open file description, `CLOEXEC` alone is insufficient.
The implementation must register a child-at-fork handler that immediately closes inherited control
FDs and poisons all inherited capabilities; each capability rejects PID/generation mismatch and may
never unlock parent-owned state. This is defense in depth, not a substitute for the launch protocol.

The launch protocol avoids creating a worker while a topology lock is held:

1. Supervisor creates an idle `CleanWorkerSession` **before** topology lock acquisition. It inherits
   only one `AF_UNIX/SOCK_SEQPACKET|CLOEXEC` endpoint and a minimal `env -i`; it has no control root,
   slot, lock, policy, or output FD.
2. Supervisor acquires the topology lock; materializes the verified worker job, H and S3; S3 records
   the one-shot nonce plus expected child PID/start identity/uid/gid.
3. Only after S3 is durable does supervisor send the job/stage/scratch descriptors and launch message
   through the socket with an explicit FD allow-list. The session uses `PR_SET_PDEATHSIG` and a
   parent-PID race check. It may send exactly one attestation message and cannot durable-publish.
4. Supervisor keeps the same topology lock from S3 through child wait, scratch re-observation,
   attestation validation, envelope/S4 publication and execution receipt/S5. A second recovery
   attempt while this holder is live returns `BUSY`, never timeout-terminalizes it.

If supervisor dies, the kernel releases its lock, the child loses its parent/session endpoint and exits;
it has no topology capability. A successor that later acquires the lock may quarantine the incomplete
job and publish the prescribed pre-S5 terminal, but can never promote a late scratch file.

## 4. Deterministic authority and control-chain materialization

Two typed, lock-held APIs replace all generic publication:

```python
ArchiveAuthorityIssuer.ensure_e_and_c(
    locked: LockedVerifiedControlTopology,
    inputs: VerifiedQualityInputs,
) -> tuple[E, C]

ReplayControlMaterializer.ensure_p_through_q(
    locked: LockedVerifiedControlTopology,
    e: E,
    c: C,
    coordinate: K,
) -> tuple[P, F, A, B, Q]
```

Every candidate bytestring is uniquely canonicalized from observed predecessor bytes and C's frozen
template. An existing slot must match the exact expected bytes/ref/identity, not merely semantic
equivalence. The materializer has no caller-selected P/F/A/B/Q value, path or alternate parent.

| Observed chain under the held lock | Only allowed action |
| --- | --- |
| E/C both absent | archive acceptor writes deterministic E, then C |
| valid E, C absent | archive acceptor derives and writes only C |
| C exists without E; E/C mismatch or invalid | `CONTROL_CHAIN_REJECTED`, no repair or alternate choice |
| valid C, P/F both absent | write canonical P, then canonical F; ordering serializes publication only, not a P→F semantic edge |
| exactly one valid P/F | compare it to derive(C), then write only the missing sibling |
| valid P/F, A absent | write `A = derive(C, Ref(P), Ref(F))` |
| valid A, B absent | re-observe A's fixed `FinalParentSnapshot` D-v2 and write only canonical B |
| valid B, Q absent | revalidate D/K and write only canonical Q |
| valid Q | verify full chain and return; only then can R/V begin |
| gap, wrong predecessor, bytes mismatch, root/ACL/D-v2 change, unexpected leaf | `CONTROL_CHAIN_REJECTED`, no delete, replacement or new choice |

`A` must contain a `FinalParentSnapshot` of root-relative components plus full D-v2 chain. B, Q, R,
V and acceptance compare that snapshot; recovery is never allowed to choose the directory that happens
to exist later at the same path. P/F/A/B/Q partial crashes therefore converge to byte-identical clean
chain output or fail closed.

## 5. Sealed adapter for the unchanged path-only mechanics worker

The historical `scripts/server/verify_m6_peerlite_archival_replay.py` is unchanged and remains
mechanics-only: it resolves caller paths, requires a nonexistent `output_dir`, creates it itself, and
writes only `archival_replay_receipt.json`. It has no Context, lock, slot, actor or ChildReceipt
contract. It must never be called directly by a new official path.

`FrozenMechanicsWorkerAdapter` is a small new lifecycle dependency, not a rewrite of that script. It
receives only verified FDs/context and produces a `StagedMechanicsInvocationV1` bound to:

```text
K, Context/H refs and launch nonce
frozen worker script/runtime/argv/env/cwd hashes
every staged input's observed ref, stage-relative path, identity and inventory hash
WORKER_JOB D-v2, fixed stage layout, scratch/raw-output leaf and receipt leaf
fixed device and env -i allow-list
```

Supervisor creates the private `WORKER_JOB` under the held lock, copies or reflinks all verified
immutable inputs into its stage tree, and verifies the copied inventory/ACL/FD identities again. The
adapter's child session `fchdir`s to the verified private job directory and invokes the unchanged worker
with **only fixed stage-relative paths**:

```text
stage/inputs/frozen-source-root
stage/inputs/frozen-source-archive
stage/inputs/product
stage/inputs/run
stage/inputs/historical-verification.json
stage/inputs/trial-ledger.jsonl
stage/program/verify_m6_peerlite_archival_replay.py
scratch/raw-output
```

No symlink, hardlink, `/proc/self/fd` path, inherited caller path, official O path or control-root path
is valid. `scratch/raw-output` is absent before launch, exactly matching old-worker semantics. The
worker may only write within private scratch; official O is supervisor-owned and receives only
canonical, re-observed verified output metadata after success. Scratch is forensic/quarantine material,
never an official output root.

After raw worker exit, the child verifier opens scratch no-follow, demands exactly the expected receipt
and no symlink/temp/extra output, validates schema/14 folds/no ledger mutation and matches all self-
reported hashes/paths to the staged invocation. It sends one canonical
`ChildMechanicsAttestationV1` through the authenticated socket. Supervisor independently reopens and
hashes the scratch inventory, checks `SO_PEERCRED`, nonce, PID/start identity, uid/gid, exit status and
attestation bytes, then publishes `ChildReceiptEnvelopeV2` and S4 under its held lock. A raw
`status=PASS` receipt is only an envelope input and is schema-rejected everywhere else.

## 6. Complete lifecycle and recovery table

The durable success path is:

```text
E → C → {P,F} → A → B → Q → R → V
→ S0 → S1 → O → S2 → H → S3
→ ChildMechanicsAttestation (IPC only)
→ ChildReceiptEnvelope → S4 → ReplayExecutionReceipt → S5
→ ArchiveAcceptanceReceipt → S6 → FinalIndex
```

`POST_S0_TERMINAL` may only be published before valid S5. It never coexists with valid S6/FinalIndex.
`ArchiveAcceptanceRejectionV1` is a separate fail-closed late archival branch and is never an official
result.

### 6.1 Supervisor-owned S0–S5 recovery

Under a successfully acquired same topology lock:

| Committed frontier | Deterministic recovery |
| --- | --- |
| live original supervisor still owns lock | `BUSY`, zero writes |
| S0/S1/O/S2/H/S3 with no valid envelope/S4 | publish one `POST_S0_TERMINAL(INCOMPLETE_CHILD_OR_HANDOFF)`; retain scratch only for forensics |
| valid envelope but no S4, or valid S4 but no valid S5 | same terminal; never rewrap, rerun or reuse scratch/K |
| gap, wrong writer, malformed envelope, unexpected official O | terminal if S5/S6/FinalIndex are absent |
| complete valid S5 and no later archive artifact | hand off only to archive acceptor |
| terminal already present | idempotent reject |

The parent holds the lock across the live child window, so recovery cannot race a normal S3→S5 path.
After parent death, a still-running child has no publisher capability and its private scratch cannot be
promoted; the terminal is consequently safe and deterministic.

### 6.2 Archive-acceptor post-S5 recovery

`ArchiveAcceptor.accept_or_resume_post_s5(locked, k)` is the only archive publication API. Before each
write it revalidates Context, S0–S5, O/H/output inventory and all slot/root identities.

| S5 | ArchiveAcceptanceReceipt | S6 | FinalIndex | Action |
| --- | --- | --- | --- | --- |
| valid | absent | absent | absent | validate, publish receipt, then S6, then index |
| valid | valid | absent | absent | revalidate receipt/S5/inventory, publish S6 then index |
| valid | valid | valid | absent | revalidate full chain, publish index |
| valid | valid | valid | valid and exact | idempotent accepted result |
| malformed, gap, wrong ref/hash, terminal, unexpected output or prior rejection | publish/return `ArchiveAcceptanceRejectionV1` if absent; never overwrite, fill a gap, or promote |

S5 therefore never leads to a post-S0 terminal. A crash after receipt or after S6 resumes to the exact
same bytes as the uninterrupted path. A malformed late object cannot be deleted or repaired into an
official result; resolver checks the rejection slot first and rejects any inconsistent combination.

`OfficialArchiveResolver` still opens only the fixed FinalIndex slot and accepts only a matching,
rejection-free Context-bound `FinalIndex → S6 → ArchiveAcceptanceReceipt → S5` chain. It explicitly
rejects raw worker receipts, M6ArchiveSummary, generic PASS, worker scratch, output directories,
caller paths and mutable heads.

## 7. Module boundaries, enforcement and migration

Target dependency direction is deliberately local and one-way:

```text
m6_replay_identity.py       FD identities, process/fork guard, actor capability
          ↓
m6_replay_authority.py      canonical schemas, Pin/PolicyV2/Context/refs
          ↓
m6_replay_quality.py        observed policy/evidence, Bootstrap/PASS, verified inputs
          ↓
m6_replay_control.py        SlotSpec, held topology, E/C and P-through-Q recovery
          ↓                 ↘
m6_replay_worker_adapter.py  private job staging and child attestation adapter
          ↓                 ↙
m6_replay_lifecycle.py      S0–S6, envelopes, archive recovery and official resolver
          ↓
scripts/server/*            capability-only validate/future authorized entrypoints
```

`m6_archive.py`, `trial_ledger.py`, data/models and the raw worker do not import the control plane;
the raw worker is injectable through a narrow mechanics protocol only. No service, database, daemon,
new research family, real replay, model fit, budget event, PIT certification or M7/OOS access is added.

Implementation must enforce no public generic slot writer, no Path-taking authority/quality API, no
raw mapping constructor for observed capabilities, no import cycle, and no child allow-list containing
control-root/lock/slot FDs. Existing v22/v19 documents remain immutable historical design evidence;
v23/v20 are new evidence, not retroactive alteration of them.

## 8. Required later verification seam (not tests yet)

The later test-design gate must cover, with synthetic artifacts only:

- Pin/policy/evidence topology substitution before and after observation, all missing/extra/reordered
  evidence roles, wrong gate/status/independence/ledger receipts, and wrong issuer ACL;
- real fork fixtures proving child poison/close, PID/generation rejection, no inherited topology FD,
  live-holder `BUSY`, parent-death recovery and explicit FD allow-list;
- every E/C/P/F/A/B/Q partial frontier, exact byte equality, FinalParentSnapshot replacement and no
  alternate choice;
- child IPC peer/nonce/identity failures, second message, forged/raw substitution, scratch inventory
  mutation, child crash and supervisor crash; none may create envelope/S4/S5;
- legacy worker existing-output behavior, stage/scratch path replacement, direct raw PASS and worker
  scratch never reaching FinalIndex;
- receipt→S6 and S6→FinalIndex crash windows converging exactly, plus malformed late chains producing
  rejection and no official admission.

These obligations are deliberately not implemented or executed in this architecture stage. A fresh
change design and independent R3 design-review PASS remain mandatory before test design, red tests,
implementation, code review, archival replay, M7, CCC/Gate or final OOS work.
