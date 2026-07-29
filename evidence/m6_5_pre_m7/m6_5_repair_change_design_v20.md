# M6.5 R3 修复设计 v20 — Linux control plane, release pin and authoritative archival admission

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一架构输入为
`architecture_confirmation_v24.md`（SHA-256
`d637bc6555a27898516271e831d519226a7539be7b11342c31ec5d0513daf2e9`）。本设计替代
v19，映射 v24 的全部边界到最小可实施的 Python 3.11/Linux control plane；不创建真实
release bundle/Pin/PASS/E/C/P/F/A/B/Q/R/V/state/receipt，不执行 archival replay、训练、M7、
PIT 或 final OOS，不修改 immutable M6 evidence、历史 raw worker 或 trial ledger。

## 1. Problem, scope and non-goals

M6.5 需要在第七步 M7 之前证明未来增量不会把普通路径、future data 或历史 replay 的机械
输出误当成正式研究结果。v19 已被独立审查退回：pre-E policy 没有物理根、fork 后 OFD lock
不安全、control chain/ChildReceipt/archive recovery 未闭合，且 legacy worker 是 path-only。
v20 的唯一目标是实现 v24 所定义的合成可测 control plane，使将来唯一的 official archival
result 只能来自：

```text
observed Pin/Policy/Evidence → Bootstrap/PASS → E/C → P/F/A/B/Q/R/V
→ locked lifecycle → verified child envelope + official output manifest → S5
→ archive receipt/S6/FinalIndex
```

非目标：修改 Qlib/PeerLite/M6 模型、做真实 fit/replay、读取 2025+、消费试验预算、改变
M6 history、把 raw worker 升级为 authority、实现 daemon/database、支持 macOS production，
或对 hostile host/native injection 做出未承诺的防御。

生产目标固定为 Linux + CPython 3.11 server。开发机 macOS 只运行 synthetic provider/fake
worker 测试；它的 skip 不构成 Linux pass。任何 Linux capability、filesystem、ACL、identity
或 deployment predicate 缺失都拒绝 dispatch，不降级。

## 2. Repository evidence and selected approach

现有边界必须保留：

- `m6_archive.py` 是只读历史 M6 proof，返回 `M6ArchiveSummary`；它不能写 control slot 或被
  official resolver 接受。
- `trial_ledger.py` 是独立预算 ledger，使用 pathname `flock`/replace 语义；不能成为本变更
  的 OFD lock 或 authority source。
- `artifacts.atomic_write_json` 是通用 Path/replace helper；不能用于 immutable control slot。
- `scripts/server/verify_m6_peerlite_archival_replay.py` 接 caller paths、会 `.resolve()`、要求
  output directory 不存在并写 raw PASS receipt；它完全不改，保持 mechanics-only。

比较的方案：

| 方案 | 结论 |
| --- | --- |
| 修改 raw worker，使其接收 Context/FD 并直接写 ChildReceipt | 拒绝：会改冻结历史脚本和已有 receipt 语义，且把 mechanics 与 authority 混合。 |
| 在 `m6_archive.py`/`trial_ledger.py` 上叠加控制逻辑 | 拒绝：会把历史 proof、预算账本和 official admission 互相耦合，现有锁/Path API 不满足 v24。 |
| 采用独立、六层 Linux control plane + 一个 narrow adapter（选择） | 选择：新增最小模块，旧代码只作为只读或 mechanics input，所有 official writes 有同一 FD/lock/slot 边界。 |

## 3. Target modules and dependency rules

新增文件如下；`governance/__init__.py` 保持不导出可写 capability，旧模块不改。

```text
m6_replay_identity.py      pure identity/ref/actor value types; no syscalls to higher modules
          ↓
m6_replay_fs.py            Linux FD traversal, stat/handle observation, no-replace/OFD primitives
          ↓                 ↘
m6_replay_process.py       process generation, at-fork poison, P1 launcher, pidfd/credential transport
          ↓                  \
m6_replay_authority.py     pure canonical Pin/Policy/Context/schema derivation
          ↓                  /
m6_replay_quality.py       observed release/evidence and Bootstrap/PASS issuance
          ↓
m6_replay_control.py       SlotSpec resolver, locked topology, E/C and P-through-Q recovery
          ↓                 ↘
m6_replay_worker_adapter.py staging, fixed legacy call and normalized mechanics verification
          ↓                 ↙
m6_replay_lifecycle.py     S0–S6, envelope/O/S5, archive recovery and official resolver
          ↓
m6_replay_worker_session.py P1 executable module only; imports adapter/process, never control
scripts/server/validate_m6_replay_authority.py          validate-only wrapper
scripts/server/run_authorized_m6_archival_replay.py     future capability-only wrapper
```

No lower module imports a higher one. `m6_replay_worker_adapter.py` receives a `WorkerJobHandle`
protocol supplied by control rather than importing control. `m6_replay_worker_session.py` is started by
module name and has no import path back into lifecycle. All durable publisher methods are package-private
or accept opaque capabilities; there is no generic `publish(path, bytes)`, raw mapping observer or
Path-taking authority API.

## 4. Shared schemas, error model and release build contract

`m6_replay_authority.py` is pure canonical parsing/derivation. Every parser requires canonical JSON
bytes (`canonical_json_bytes(parsed) == raw`), exact schema/version and content hash; it does no file
I/O. It owns these immutable DTOs:

```text
DirectoryIdentityV2, FileIdentityV1, DirectoryChainV2, TypedArtifactRef
M6QualityReleasePinV1, M6QualityGateReleasePolicyV2, QualityReleaseTopologyV1
QualityEvidenceItemV1, M6QualityRouteClosureV1
M6ReplayAuthorityBootstrapV1, M6EngineeringQualityGatePassV1
M6ReplayAuthorityContextV1, M6ReplayAuthorityBindingV3, M6ReplayControlPolicyV5
SlotSpecV1, ReplayInputPrecommitV1, ClaimR, BindingV
StagedMechanicsInvocationV1, ChildMechanicsAttestationV1, ChildReceiptEnvelopeV2
NormalizedMechanicsResultV1, ReplayOutputManifestV1, ReplayExecutionReceiptV1
ArchiveAcceptanceReceiptV1, ArchiveAcceptanceRejectionV1, S0…S6, FinalIndexV1
```

`M6QualityReleasePinV1` carries the v24 final-install fields: `release_id`, outer dispatcher ref,
inner authorized-entrypoint ref, resolver profile ref, sealed-anchor contract/ref/D-v2,
release-policy slot parent chain/leaf/schema, policy `FileIdentityV1`, policy typed ref and canonical
SHA-256. `PolicyV2` carries `RuntimeClosureRef`, `AuthorizedEntrypointRef`, topology and the ordered
closed evidence inventory, but never Pin. `M6QualityRouteClosureV1` contains exact stage-result refs
plus immutable ledger **prefix** `{identity, byte_length, sha256}`; no mutable head, Pin, Bootstrap or
PASS can enter that closure.

The runtime never builds these structures from a public mapping. Observer factories return opaque
`VerifiedReleasePolicy`, `ObservedQualityEvidenceInventory`, `VerifiedQualityInputs`,
`ActorCapability`, `LockedVerifiedControlTopology` and `WorkerJobHandle` tokens with module-private
construction sentinels. This is a normal-failure boundary, not a claim against arbitrary in-process
malicious code.

All expected failures use a finite error family, not exception text as protocol data:

```text
M6_REPLAY_LINUX_PRIMITIVE_UNAVAILABLE
M6_REPLAY_IDENTITY_OR_ACL_MISMATCH
M6_REPLAY_BUSY
M6_REPLAY_RELEASE_OR_EVIDENCE_REJECTED
M6_REPLAY_CONTROL_CHAIN_REJECTED
M6_REPLAY_CHILD_ATTESTATION_REJECTED
M6_REPLAY_INCOMPLETE_POST_S0
M6_REPLAY_ARCHIVE_REJECTED
M6_REPLAY_LEGACY_MECHANICS_REJECTED
```

The offline installer is not implemented as a runtime writer in this repository. Its required contract
is validated by schemas and synthetic fixtures. To avoid a hidden identity cycle, its exact sequence is:

```text
freeze runtime candidate → finish quality route
→ install final empty anchor skeleton/slot parents and final ACLs
→ install read-only EvidenceBundle and observe its final identities
→ build PolicyV2 from those final parent/evidence identities (Policy has no self FileIdentity/Pin)
→ write PolicyV2 to its final slot and observe its final FileIdentity/bytes
→ construct outer-dispatcher Pin → descriptor-pass Pin to inner entrypoint
```

A later copy/mount/ACL replacement fails observation. This refines the v24 topology-template step into a
deployable order, keeps the release DAG acyclic, and avoids a new deployment service.

## 5. `m6_replay_identity.py` and `m6_replay_fs.py`

### 5.1 Identity and actors

`m6_replay_identity.py` defines only value types/protocols and actor verification inputs. `DirectoryIdentityV2`
retains device/inode/mount/btime/opaque-handle/owner/mode/ACL fields; `FileIdentityV1` retains exact
regular-file identity. `VerifiedDirectoryChain` owns its directory FDs and canonical identity sequence.
`authenticate_actor()` compares observed effective uid/gid/sorted groups/capabilities/process identity
and parent FD ACL against the fixed writer-matrix entry before returning opaque `ActorCapability`.

### 5.2 Linux filesystem provider

`m6_replay_fs.py` supplies `LinuxReplayFilesystem` plus a test-only fake provider. Production creation
first runs `probe_linux_replay_capabilities()` and requires CPython 3.11/Linux, no-follow directory FD
traversal, statx/name-to-handle identity, `F_OFD_SETLK`, `renameat2(RENAME_NOREPLACE)`, fsyncable
directories, `AF_UNIX/SOCK_SEQPACKET`, `SO_PASSCRED` and `pidfd_open`. Failure is a stable reject.

Its only root traversal APIs accept `root_fd` + validated root-relative components:

```python
open_directory_chain(root_fd, components) -> VerifiedDirectoryChain
open_regular_file(parent_fd, fixed_leaf, flags) -> OpenedRegularFile
observe_directory_v2(fd) -> DirectoryIdentityV2
observe_file_v1(fd) -> FileIdentityV1
publish_immutable_cjson(parent_fd, fixed_leaf, canonical_bytes, expected: SlotSpecV1) -> TypedArtifactRef
acquire_ofd_lease(lock_parent_fd, fixed_leaf) -> OFDLease
```

Every component uses `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, compares device/mount and full expected D-v2
chain, rejects symlink/ancestor replacement/xdev drift, and never receives `Path`/cwd. Immutable publish
uses same-parent temp `O_EXCL` → file fsync → `renameat2(RENAME_NOREPLACE)` → parent fsync. Existing
leaf must be re-opened and exactly equal only for an explicit idempotent read; it is never overwritten.
OFD lease uses a reviewed `ctypes` native `struct flock` ABI on an `O_RDWR|O_NOFOLLOW|O_CLOEXEC` FD;
`EAGAIN/EACCES` returns `BUSY`. No `flock`, `os.replace`, `O_PATH` or portable fallback is allowed.

## 6. `m6_replay_process.py`: fork, P1 and credential transport

`ProcessGenerationGuard` records creator PID/generation for each live topology token and installs
`os.register_at_fork(after_in_child=...)`. In the child callback it closes registered control FDs, marks
tokens poisoned and increments local generation. Every topology method validates PID/generation/FD liveness
before doing anything; mismatch never writes or unlocks a parent-owned state.

`CleanWorkerSession.start_idle()` is called **before** P0 acquires a topology lock. It launches
`python -m qlib_peerlite.governance.m6_replay_worker_session` with `close_fds=True`, a single explicit
socket FD, minimal `env -i`, expected P0 PID and no other descriptor/path. P0 opens a pidfd for P1 and
captures P1 PID, `/proc` start ticks, uid and gid. P1, after exec, calls Linux `prctl(PR_SET_PDEATHSIG)`
through the reviewed wrapper and immediately rechecks `getppid()`; any failure exits before dispatch.

P0 uses one `AF_UNIX/SOCK_SEQPACKET` channel. It sends exactly one dispatch packet plus the private
`WORKER_JOB` FD with `SCM_RIGHTS`; P1 rejects truncated/extra/missing descriptors, makes the FD
non-inheritable and re-observes it. P0 sets `SO_PASSCRED` on its receive side. P1 sends exactly one
attestation packet; P0 requires kernel-attached `SCM_CREDENTIALS`, exact PID/uid/gid/start ticks, S3
nonce/H/context match, no `MSG_CTRUNC`, no returned FD and no second message. `SO_PEERCRED` is never
used as a socketpair child-identity oracle. P1 has no control-root/slot/lock/O FD and no durable writer
method.

P1 uses the received job FD to `fchdir` into the private directory and calls the staged raw-worker
`run()` function in the P1 process; it does not exec a third raw-worker child. P1 can therefore wait,
verify scratch and send its attestation; P1 death also stops the raw function. P0 holds the same OFD
lease from S3 through P1 completion, attestation verification, envelope/S4 and S5. A competing recovery
gets `BUSY`; after P0 death the child cannot publish and a new holder follows pre-S5 recovery.

## 7. `m6_replay_quality.py` and `m6_replay_control.py`

### 7.1 Observed release and quality issuance

`m6_replay_quality.py` exposes no `policy: Mapping` or `raw: bytes` publication API:

```python
observe_verified_release_policy(sealed_anchor_fd, compiled_pin, fs) -> VerifiedReleasePolicy
observe_quality_evidence_inventory(policy, fs) -> ObservedQualityEvidenceInventory
issue_bootstrap(policy, quality_issuer) -> ObservedArtifact
issue_quality_pass(policy, inventory, bootstrap, quality_issuer) -> ObservedArtifact
observe_verified_quality_inputs(policy, inventory, archive_acceptor, fs) -> VerifiedQualityInputs
```

Each call reopens and compares Pin/policy/topology/evidence parents before and after observation. The
issuer writes only fixed Bootstrap/PASS leaves through `publish_immutable_cjson`; it has no policy/evidence
write ACL. PASS is uniquely derived from observed Policy/Inventory/Bootstrap and must bind exact refs,
gate, issuer/ACL/runtime/family/profile/root/topology values. E/C can consume only the final opaque
inputs.

### 7.2 Locked slots and control-chain recovery

`m6_replay_control.py` creates a `SlotResolver` from the observed binding and has no generic open/write
method. `acquire_locked_verified_topology()` resolves all required root-relative slots, acquires the
exact OFD lease, then reopens and re-compares every root/parent/lock identity. Its token is mandatory for
all mutable control/lifecycle methods.

Two explicit APIs eliminate implementation-time ordering choices:

```python
ArchiveAuthorityIssuer.ensure_e_and_c(locked, inputs) -> tuple[E, C]
ReplayControlMaterializer.ensure_p_through_q(locked, e, c, k) -> tuple[P, F, A, B, Q]
ReplayReservationRegistry.claim_and_bind(locked, q) -> tuple[ClaimR, BindingV]
ReplayReservationRegistry.recover_pre_s0(locked, k) -> RecoveryDecision
```

`ensure_e_and_c` writes E then C, or only fills missing C after a byte-identical E; C without E or any
mismatch returns `CONTROL_CHAIN_REJECTED`. `ensure_p_through_q` uses C template bytes as the single
source of truth: P/F may be independently absent but are committed in fixed P then F order; A derives
from C/P/F; B only after re-observing A's `FinalParentSnapshot`; Q only after B/D/K exact validation.
At any partial frontier it may fill only the uniquely missing next object; gap/mismatch/ACL/root drift
never causes replacement, alternative choice or generic repair. R/V holds one token and emits R→V or
R→pre-S0 terminal, never both.

## 8. `m6_replay_worker_adapter.py`: frozen legacy call and output normalization

`FrozenMechanicsWorkerAdapter` is the sole bridge from verified FDs to the unchanged worker. Under the
held topology it allocates one `WORKER_JOB` directory through control, copies/reflinks verified inputs,
and records a recursive `StageInventoryV1`. Every staged regular file has source/staged identity/hash,
mode and fixed job-relative location; symlink, hardlink, unexpected entry, mutable import directory or
digest mismatch rejects. Stage is read-only to P1, scratch is the only P1-writable subtree, and the
supervisor-only job parent is not searchable by P1.

`StagedMechanicsInvocationV1` freezes all named arguments of the unchanged `run()` API:

```text
frozen_source_root, frozen_source_archive,
expected_frozen_source_archive_sha256, expected_revision,
product_dir, run_dir,
historical_verification, expected_historical_verification_sha256,
ledger_path, output_dir, device
```

Their values are exact paths derived after P1 `fchdir` from the verified job FD; P1 invokes the staged
script file so `__file__` and receipt path fields are the expected staged absolute paths. The invocation
also fixes interpreter/runtime/script hashes, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`,
`TMPDIR=scratch/tmp`, source archive hash/revision and device. `scratch/raw-output` is absent before
call, satisfying old-worker `mkdir(exist_ok=False)` behavior. No O/control-root/live-ledger FD or path
is passed.

The staged ledger is a read-only snapshot. H separately contains the observed live ledger identity and
immutable prefix and an explicit `live_ledger_access=NOT_PASSED_TO_P1`; raw receipt `mutated=false`
therefore proves only the snapshot was unchanged, never that all live ledger writers were frozen.

P1 reopens scratch no-follow and accepts exactly `archival_replay_receipt.json`, no temp/symlink/extra
file. It validates raw schema/status, expected staged paths/hashes, fourteen checkpoint replays, zero
fits/OOS/backtests and no staged-ledger mutation. It emits `ChildMechanicsAttestationV1`. P0 repeats the
scratch/inventory verification and uses a pure normalizer to construct `NormalizedMechanicsResultV1`;
the normalizer retains approved numerical/hash claims and raw receipt digest/schema but removes mutable
paths and never treats a generic PASS as authority.

P0 writes `ChildReceiptEnvelopeV2` (attestation bytes/hash, P1 credentials, invocation/raw/scratch
bindings and supervisor identity) and then one supervisor-owned `ReplayOutputManifestV1` in O. The
manifest binds Context/H/envelope/invocation, normalized result and raw/scratch digests; it contains no
scratch path or traversal. `ReplayExecutionReceiptV1`/S5 reference that manifest. Archive acceptance
later reopens only O and recomputes these canonical bindings; worker scratch is forensic-only and never
a prerequisite for resolving an official result.

## 9. Lifecycle, archive recovery and official admission

`M6ReplayLifecycle` is the only post-V mutator. Its public orchestration creates P1 before lock, then
under one `LockedVerifiedControlTopology` token performs:

```text
enter S0 → S1/O/S2 → allocate/stage worker job → H → S3(P1 identity + nonce)
→ dispatch P1 → verify attestation/scratch → ChildReceiptEnvelope → S4
→ ReplayOutputManifest + ReplayExecutionReceipt → S5
```

No API accepts arbitrary state/output paths or an arbitrary child receipt. `recover_pre_s5(locked, k)`
returns `BUSY` for a live holder. If no archive-role artifact exists, a successfully acquired lock turns
any S0–S4 incomplete/gap/malformed envelope/unexpected O into one canonical
`POST_S0_TERMINAL(INCOMPLETE_CHILD_OR_HANDOFF)` with no rerun, rewrap or scratch reuse. A valid S5 is
handed exclusively to archive acceptor. If any archive receipt/S6/FinalIndex/rejection slot exists but
S5 is absent or invalid, supervisor writes no terminal; it hands the residue to archive acceptor so the
canonical post-S5 rejection branch, rather than a terminal that could coexist with S6, handles it.

`ArchiveAcceptor.accept_or_resume_post_s5(locked, k)` has only these outcomes after revalidating
Context, S0–S5, O/H/manifest and all slots:

| Observed late chain | Action |
| --- | --- |
| valid S5, no receipt/S6/index/rejection | publish receipt → S6 → FinalIndex |
| valid receipt only | publish S6 → FinalIndex |
| valid receipt + S6 only | publish FinalIndex |
| valid receipt + S6 + FinalIndex and no rejection | idempotent accepted result |
| existing valid rejection | idempotent reject |
| malformed/gap/wrong binding/terminal/final conflict | publish one canonical `ArchiveAcceptanceRejectionV1`, never promote |

The rejection payload is exactly `{schema,K,Context ref,reachable S5 ref-or-absence,reason_code,
sorted offending role→digest/ref,expected predecessor relation}`: no exception text, timestamps, PID,
random or path. Resolver opens rejection first, then fixed FinalIndex; any rejection/final coexistence
or inconsistent chain rejects. `POST_S0_TERMINAL` is never created after reachable valid S5.

`OfficialArchiveResolver.resolve(k)` receives only sealed topology/capability context, opens the fixed
rejection/index slots, and accepts only a rejection-free exact chain:

```text
FinalIndex → S6 → ArchiveAcceptanceReceipt → S5 → ReplayOutputManifest/Envelope/H/Context
```

It rejects raw worker receipt, `M6ArchiveSummary`, generic PASS, worker scratch, O directories,
caller-selected paths and mutable heads. New server wrappers accept a single sealed descriptor/capability
from the outer dispatcher; they do not expose individual legacy paths and are not executed during this
change.

## 10. Compatibility, rollout, observability and resource bounds

No historical file/receipt/schema changes: raw worker, M6 archive proof and trial ledger remain regression
gates. New modules are dormant unless a VerifiedQualityInputs capability and Linux capability probe both
succeed; therefore rollout is opt-in by sealed dispatcher, not a config flag that can grant authority.
Rollback means stop issuing new release bundles/dispatches; immutable control objects are retained and
never deleted.

Diagnostic manifests contain stable role/stage/error codes, typed refs, identity hashes and
`replay_started` state; they omit raw handle bytes, input data, checkpoint payloads and secrets. Staging
copies can be expensive, but this is a single-worker archival control path, not model training; bounded
inventory streaming/reflink-if-available followed by full digest verification is accepted. Unsupported
reflink falls back to a verified ordinary copy, never a symlink/hardlink shortcut.

## 11. Verification obligations for the later test-design stage

The next selected test-design skill owns the detailed matrix. It must cover synthetic schema/identity
paths on every platform and Linux-only integration receipts on the server. Required seams include fake
filesystem/identity provider, fake OFD/process transport, fake mechanics protocol/session, staged job
fixture and deterministic clock-free canonical serializers. The later implementation must add isolated
test files for identity, filesystem, authority, quality, control, worker adapter, lifecycle and
authorized scripts; preserve existing M6 archive, ledger and raw-worker tests.

Linux integration tests must be explicitly marked and run on the server; local macOS skips must remain
visible rather than counted as a pass. All test data stays synthetic; no command may fit a model, invoke
the real worker, mutate a real ledger, access PIT/final OOS or consume budget.

## 12. Ordered implementation plan

1. Add pure identity/authority schemas and canonical validators; include release build prefix semantics.
2. Add Linux filesystem capability probe, FD identity traversal, durable no-replace publisher and OFD
   lease; do not touch generic artifacts/ledger.
3. Add process generation/fork poison, P1 launcher, pidfd and per-message credential transport.
4. Add observed Pin/Policy/evidence reader and deterministic Bootstrap/PASS issuer/reader.
5. Add SlotSpec resolver, locked topology, E/C and P-through-Q/recovery APIs.
6. Add worker job staging, fixed legacy-call adapter, P1 session and mechanics normalizer.
7. Add lifecycle S0–S5/envelope/O/terminal, archive continuation/rejection and FinalIndex resolver.
8. Add capability-only server wrappers while leaving the raw script unchanged.
9. Enter test-design, red tests, implementation, green tests, independent code review and E2E only via
   the quality router; no real archival dispatch/M7/OOS remains authorized before those gates pass.

## 13. Open decisions

None. Linux-only production capability, two-process P0/P1 model, `SO_PASSCRED` attestation, no-replace
publication, release installer DAG, legacy-worker adapter, output normalization and rejection precedence
are fixed by this design. If deployment cannot supply any required OS identity/ACL/kernel primitive, the
correct outcome is fail-closed `HOLD`, not a local compatibility fallback.
