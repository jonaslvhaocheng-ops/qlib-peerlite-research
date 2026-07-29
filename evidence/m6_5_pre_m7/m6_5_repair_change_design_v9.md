# M6.5 R3 修复设计 v9 — 可验收的研究治理控制面

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
Owner：M6.5 pre-M7 quality track  
Risk：`R3`  
Requirement：修复 v8 独立审查的 four P1：无环 Plan/QRC authority、post-exec claim 与 close/permit 线性化、M7 actual execution closure、non-alias Unix identity/ACL policy。

本文件不授权真实 M7 QRC freeze/fit、CCC/Gate、server replay、final OOS、生产交易或 M6 immutable/history mutation。

## Canonical incorporation

这是该 change 的唯一 canonical design artifact：它逐字纳入
`m6_5_repair_change_design_v6.md` SHA-256
`2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78` 的 §1、§2、§3、§4、§7；本文件 §5 完整替代 v6 §5，§6 完整替代 v6 §6。v7/v8 是历史设计，不是并行实施来源。架构依据是 `architecture_confirmation_v12.md`，威胁边界固定为 `research_governance_threat_model_v1.md`。

这条 incorporation rule 保留 M6-only Gate denial、M6 `6/44` genesis、PIT/behavior/state handoff、synthetic-only boundary、full coverage/lint/type/E2E/code-review sequence；实现不得只挑选本文件一个段落而遗漏 hash-bound base。

## Problem and scope

### Current evidence

`src/qlib_peerlite/governance/trial_ledger.py` 和 `m6_archive.py` 提供 M6 prefix/reconcile/archive evidence，但 `flock` 只能是短期协调，不能成为跨 fork 的 one-use fit authorization。`scripts/server/verify_m6_peerlite_archival_replay.py` 在 top level 导入 `numpy`/`pandas`，后续 frozen source 需要 `torch`，parquet stack 会加载 `pyarrow`；故 “only qlib_peerlite origin” 不能证明执行闭包。现有 public PeerLite/config/CLI 仍是 v6 §2 的 M6-only closure target。当前没有 authority control profile、actor ACL policy、runner execution receipt 或 descriptor-bound publisher control plane。

### Desired behavior

1. 一个 retained event 在冻结、受信 runner 的普通 fork/restart/crash 环境中最多跨过一次 `model.fit()`；不确定 crash 保守计费，重试只能用另一个预注册 contingency event。
2. authority 只能沿唯一可计算 DAG 从 plan/QRC 到 sealed control profile 激活；错误但内部自洽的 graph、stale activation 或 profile replacement 在 journal/claim/fit 前拒绝。
3. 每次 official M7 fit 和 M6 replay 都在 FD-measured, staged, bootstrap-verified Python/native runtime 中执行；wrong executable/venv/import/env/ABI 不能生成 terminal output。
4. terminal result 只由 ACL-separated publisher transaction 创建；同 UID 服务误配、shared write group、wrong socket peer 或 direct path 都不能使 staging/checkpoint/nonterminal output official。

### Non-goals and assumptions

- trusted control root, supervisor, host/kernel/ACL and frozen approved code remain assumptions; arbitrary native-code runner or host/control-root compromise invalidates evidence rather than being solved here;
- no new DB/RPC/microservice/container platform; this is a single-host file-backed control plane;
- authority replay acceptance is Linux x86_64 CUDA only; macOS remains synthetic-test-only;
- M6 historical source/contracts/rows/gate and final-OOS partitions remain untouched and sealed.

## Repository boundary and options

| Surface | v9 responsibility |
|---|---|
| `governance/schema.py`, `control_root.py` | closed schemas, ArtifactRef, root-FD/ACL/identity primitives |
| `authority.py`, `admission.py`, `dispatch.py` | graph/profile, descriptor, post-exec claim/permit lifecycle |
| `execution_closure.py` | shared staged Python closure/bootstrap/observed receipt for M7 and replay |
| `publication.py` | prepared inventory, publisher no-replace transaction, resolver |
| `replay_binding.py`, `m6_archive.py` | M6 v5 binding and three-receipt validation |
| server bootstrap/FD-exec helper/v3 verifier | Linux sealed execution only; historic verifier stays an evidence input |

Rejected alternatives:

- `flock`/lease/`O_EXCL` alone: cannot distinguish forked/inherited process or enforce actual code bytes;
- runner/publisher caller paths: allow self-consistent wrong roots;
- hash a Python path then execute it by path: ordinary deployment rotation can run different bytes;
- OCI-only solution: defer a separate container/runtime operator dependency; use content-addressed staged runtime plus ABI profile now.

## Proposed design

### Common schemas and safe IO

All cross-object references use strict canonical `ArtifactRef v1`:

```json
{
  "role": "logical_role",
  "relative_path": "root-relative/path",
  "schema_version": "schema_vN",
  "sha256": "64-lowercase-hex",
  "bytes": 0
}
```

Unknown fields, absolute/`..`/symlink paths, devices/FIFOs/sockets, wrong type/owner/mode/ACL/`nlink`, duplicate IDs and digest/byte mismatch fail. Readers use a trusted root FD, `openat`, `O_NOFOLLOW`, `fstat` and SHA; writers use temp+file fsync+atomic no-overwrite publication+parent fsync. Long-lived authority links use content digests and logical ledger heads, not an inode which may change after atomic replacement.

### Control-plane identity and ACL contract

`M7ControlPlanePolicy v1` is immutable and QRC-bound. It names numeric UID/GID, allowed supplementary groups (empty unless exact justified), zero unexpected Linux capabilities, control-root identity and socket peer rules for four non-root, pairwise distinct writers: `governance-supervisor`, `research-runner`, `result-publisher`, `replay-supervisor`. It contains a closed ACL matrix:

```text
supervisor write: policy/registry/activation/profile/admission/dispatch
runner write: own claim + own staging only
publisher write: publisher-prepared/final/terminal-index only
replay supervisor write: replay stage/runtime/receipt only
```

`OfficialResultResolver` is a read-only supervisor capability, accepts only `(activation_id,event_id)`, and has read/search—not write—ACL to final/index. No object grants shared writable group access. `research-runner` cannot read/write/search final/index; publisher cannot write authority/admission/dispatch; replay supervisor cannot write M7 authority/final/index. Activation preflight validates UID/GID nonalias, groups/capabilities, all directory/file ownership/mode/POSIX ACL and Unix socket owner/mode plus `SO_PEERCRED` allowlist. Relevant ACL facts are revalidated before permit/publish/resolve. Any alias, shared writable group, wrong socket peer/owner or ACL mutation fails closed.

### §5 replacement — authority, one fit and official publication

#### 5.1 Calculable one-way authority graph

The graph has exactly this digest direction:

```text
M7AuthorizationPlan v1 (no QRC / registry / grant / activation reference)
  -> frozen QRC (plan SHA + M7ControlPlanePolicy SHA)
  -> RunAuthorityRegistry v1 (QRC SHA + Plan SHA + policy SHA + M6 genesis SHA)
  -> RunAuthority v1 -> RunAuthorityGrant v1
  -> AuthorityActivationReceipt v1 -> M7RunControlProfile v1
```

The first arrow is creation order, not a Plan→QRC field. `Plan` includes family/run semantics, exact ordered event entries/budget/spec, M6 `6/44` genesis, namespace/journal/output policy and distinct contingency events; it has no QRC ID/digest/selector/placeholder. QRC references plan and policy exactly. Registry validates `QRC.plan_sha == sha256(plan)`, same family ID and repeats both digests. Downstream objects repeat exact QRC/plan/policy/genesis/budget/spec/event-plan/namespace values. Placeholder/self-hash/cycle, same ID/different bytes, mixed QRC/plan, legacy `4/29`, wrong head or mutable selector are rejected.

Under control-root/authority locks supervisor validates the entire graph/genesis/identity policy, records `AuthorityActivationReceipt` (activation nonce/generation/issuer/heads/roots/actor policy), then creates fixed-slot `M7RunControlProfile` via `O_EXCL` and fsync. Profile is the sole external anchor; runner/publisher receive no authority/root/plan/profile choice flag. Lifecycle is:

```text
INSTALLING -> ACTIVE -> CLOSING -> CLOSED
```

`CLOSING` takes the same activation lock as permit consumption, marks every not-yet-dispatched admission `ABANDONED_BEFORE_DISPATCH`, forbids later permits, lets already `DISPATCHED` events terminal/quarantine, then writes `CLOSED`. A new activation always uses new run/plan/QRC/namespace; no stale profile reactivates.

#### 5.2 Admission, post-exec claim and permit linearization

With authority+ledger locks, supervisor verifies profile is `ACTIVE`, plan membership and logical ledger head; writes `START_RETAINED`; materializes exact certified snapshot; then `O_EXCL` writes `FitAdmissionDescriptor v4`. Descriptor binds profile/activation/QRC/plan/registry/authority/grant/genesis/policy, event-plan entry hash, event/evaluation/fit semantic IDs, retained record and before/after head, state/PIT/behavior/join/candidate/snapshot input, fold/date/schema, expected `RunnerExecutionClosure`, and unique claim/staging/final/terminal-index roots.

The sole event ordering is:

```text
PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> RUNNER_STARTED
        -> CLAIMED -> DISPATCHED -> PREPARED -> PUBLISHING -> TERMINAL_PUBLISHED
                                      \-> QUARANTINED_*
```

1. Supervisor measures/stages the execution closure, descriptor and snapshot; it starts one fresh direct-exec worker with `close_fds=True` and only a minimal audited `pass_fds` set. No pre-fork pool/daemon/existing Python launcher is permitted.
2. External stdlib bootstrap validates observed closure before any runner/model import, snapshot read or claim action. The post-exec worker derives `ProcessIdentity v1 = boot_id + pid + start_ticks + runner_instance_nonce` and creates one `DispatchClaim v1` via `O_CREAT|O_EXCL` in its event-only directory.
3. Worker requests `FitDispatchPermit v1`. Under the same activation/event lock, supervisor reopens active profile generation, admission/claim, peer `SO_PEERCRED`, ProcessIdentity, snapshot FD, current head and expected/observed runner execution receipt.
4. If profile remains `ACTIVE`, it atomically fsyncs `DispatchReceipt v2(state=DISPATCHED,FIT_STARTED)` and consumes permit before reply. If CLOSING/CLOSED won the lock it rejects; a dispatched event may only finish/quarantine.
5. `FitDispatchGuard` lets only the responding ProcessIdentity call an instrumented `model.fit()` once, then destroys local permit state. `os.register_at_fork` poisons all control handles in children and all non-passed FDs are `CLOEXEC`.

Claim/dispatched/crashed events never retry/reclaim/reuse. They stay conservatively spent and require a separately frozen contingency event. Parent/child fork, inherited FD, duplicate socket request, PID reuse, stale profile, supervisor restart or ACL/closure alteration cannot yield a second fit or a post-close `FIT_STARTED`.

#### 5.3 Unified executed-bytes closure

`SealedPythonExecutionClosure v1` supplies two purpose profiles: `AUTHORITATIVE_FIT` (`RunnerExecutionClosure v1`) and `ARCHIVAL_REPLAY` (`ReplayRuntimeClosure v2`). Authoritative fit closure includes exact interpreter/entrypoint/config/source bytes, real staged CPython layout, ABI/stdlib/lib-dynload/site-package/extension inventory, frozen `sys.path`, module-origin allowlist, native library/host ABI/GPU profile, fixed argv/cwd/environment/umask and deterministic configuration. It contains an explicit key→value environment map, not merely a digest: `TZ`, `LC_ALL`, `LANG`, `PYTHONHASHSEED`, OMP/MKL/OpenBLAS/NumExpr thread/dynamic settings, CUDA visibility/GPU UUID, CUDA/cuDNN/cuBLAS identities, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, stage-local temp/cache paths and all model deterministic flags. Any future M7 profile must freeze every listed value before activation; unknown/unlisted values are rejected.

Supervisor FD-hashes then stages closure, invokes the opened interpreter through the approved Linux FD-exec helper (`execveat(AT_EMPTY_PATH)` / `fexecve`) with canonical staged `argv[0]`, `env -i`, `-I -S` and fixed cwd. A hash-bound stdlib-only bootstrap runs first; it validates executable/prefix/sys.path/initial modules, installs allowed roots and import guard, rejects `PYTHON*`, venv/conda, sitecustomize, cwd/deployment shadows and unapproved loader variables, then records Python origins and `/proc/<pid>/maps` native map before the worker may claim/read snapshot. It records again after GPU preflight and on exit to catch lazy loads.

`RunnerExecutionReceipt v1` binds closure expected/observed digest, bootstrap/source/config/executable FD identities, stage tree, argv/cwd/env/umask/determinism, ProcessIdentity, imports/native maps and host ABI/GPU values. Descriptor, claim, dispatch, prepared, terminal and resolver objects all repeat expected+observed digest and require equality. A correct descriptor plus wrong/stale runner, swapped venv/module/config, wrong `PYTHONPATH`/cwd/site, ABI/CUDA/env drift or missing bootstrap fails before permit; publisher refuses mismatch. Unsupported FD-exec/native-map invariants fail official M7 fit closed.

#### 5.4 Publisher transaction and resolver

Runner writes only descriptor staging regular files, exact `OutputInventory v1` and `PreparedResultReceipt v2` binding activation/admission/claim/dispatch/runner execution receipt/state/snapshot/model identities, expected staging root and success outcome. Publisher takes only `(activation_id,event_id)`, resolves profile/indexes/expected roots itself, exact-compares all identities and inventory, rejects extra/missing/symlink/hardlink/owner/mode/hash/stale/foreign/preexisting objects, copies/seals to publisher-owned prepared root, fsyncs and uses atomic no-replace final move. It then `O_EXCL` writes `TerminalPublishedReceipt v2` with all bindings and publisher identity/index sequence.

Resolver accepts only terminal index lookup and rehashes final inventory. Fit-without-prepared, prepared-before-move, move-before-index, final swap and every nonterminal crash are quarantine/forensic only; no automatic promotion, reuse or directory discovery exists.

### §6 replacement — sealed M6 archive replay

`M6ReplayInputBinding v5` binds all v8 historical input roles (transfer/archive/internal manifest/M3 consumed partitions/M6 run-candidates-14-fold-checkpoints-predictions/K16 receipt/read-only ledger/new output) plus approved v3 verifier, bootstrap, FD-exec helper and `ReplayRuntimeClosure v2`. It takes no caller source/product/run/checkpoint/prediction/ledger/output/runtime path flags.

Replay runtime is the `ARCHIVAL_REPLAY` closure profile and authoritative only on Linux x86_64 CUDA. It contains interpreter/CPython/runtime tree/package/extension/native inventory and trace-observed minimum `numpy,pandas,torch,pyarrow`, plus exact locale/timezone/hash/thread/CUDA/GPU/driver/determinism/cache/umask environment. Supervisor FDs verify all inputs, stage immutable runtime/data/source/verifier, launch bootstrap before verifier imports, enforce module/native map equality at preflight/GPU-preflight/exit and writes `ReplayExecutionReceipt v4`. Child receipt repeats binding/stage/runtime/closure/14-checkpoint/14-prediction/14 replay-0 fit-OOS=false values. `m6_archive` only accepts exact three-way agreement, new output and unchanged legacy ledger. macOS emits only synthetic non-authoritative evidence.

## Failure, migration, observability and resource bounds

All new objects are versioned and additive; no legacy M6 evidence changes. A failed activation never seals profile; a failed closure never starts worker; every nonterminal output is quarantined and no budget rollback occurs after `START_RETAINED`. Receipts expose correlation `(activation,event,descriptor,claim,ProcessIdentity)`, logical ledger heads, expected/observed closure digests, actor/ACL policy digest, state transition, tree hashes and quarantine reason. Rollback before M7 is disabling a not-yet-sealed activation or closing it; it never overwrites history. Runtime staging has explicit tree/file/byte limits in closure policy and uses one direct worker per event; no unbounded queue/pool is allowed.

## Verification obligations

The subsequent test-design stage must cover public synthetic behavior for:

- serializable no-cycle Plan/QRC graph, all graph substitutions and profile installation/close races;
- UID/GID alias, shared write group, ACL/socket change and forbidden direct writer/resolver access;
- post-exec-only claim, fork/inherited FD/pre-fork pool/PID reuse/duplicate permit/restart/close-versus-permit boundaries with at most one fit and no post-close fit;
- executable/runtime/config/module/native/GPU/env mutation and correct descriptor + wrong runner closure rejection;
- publisher/root/receipt/inventory/final/index substitution, no-replace race and every crash boundary;
- v5 archive input/runtime/receipt agreement proving 14 replay / 0 fit / OOS=false only.

Later red/green stages retain v6 §7 frozen include-list coverage, full suite/lint/type and synthetic E2E. No test or code stage authorizes real M7/replay/OOS.

## Ordered implementation plan

1. Implement strict schemas, root-FD reads and identity/ACL preflight fixtures.
2. Finish v6 M6-only public Gate denial without exposing M7 mechanics.
3. Implement read-only M6 genesis/logical-head validation and one-way authority graph/profile installer.
4. Implement shared sealed execution-closure staging/bootstrap/receipts before any runner dispatch.
5. Implement snapshot/admission/post-exec claim/linearized permit/close state machine with fit spy seam.
6. Implement publisher prepared/final/terminal transaction and resolver-only lookup.
7. Specialize shared closure for M6 v5 replay/binding/archive validation and approved server scripts.
8. Update constrained CLI/manifests/synthetic E2E, then run router-selected red/green/code-review/E2E gates.

## Open decisions

None. A server lacking Linux FD-exec, ACL identity or closure-observation invariants is `BLOCKED` for authority replay/fit; it may still run synthetic tests but must not weaken execution semantics.
