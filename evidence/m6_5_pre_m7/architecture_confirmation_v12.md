# M6.5 架构确认 v12 — 可计算 authority 图、线性化 dispatch 与统一执行闭包

状态：`ARCHITECTURE_READY / 待独立设计审查`。风险：`R3`。本文件在
`research_governance_threat_model_v1.md` 的受信 supervisor/control root/host/ACL 边界内处理普通配置、并发、fork、崩溃、路径和运行时误选；它不声称解决 hostile runner 的 arbitrary native-code execution 或 host/control-root compromise。M7 实证、CCC/Gate、archive replay、final OOS 和 M6 history mutation 继续不被授权。

## 1. Canonical composition and retained invariants

唯一架构组合是：

1. `architecture_confirmation_v9.md` SHA-256
   `e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598` 的 §1（M6 `6/44` genesis）、§2（PIT/behavior/state chain）和 §5（quality gate）原样保留；
2. 本文件 §2–§6 完整替代 v9 的原 §3/§4、v10 的全部 replay amendment 和 v11 的全部 replacement；
3. v10/v11 保留为审查历史，不是可并行选择的合同。

因此 legacy server `4/29` 仍绝不是 authority，M6 close `6/44` proof/genesis 不可改写，`VERIFY`/synthetic state 不得成为 production model input，public M6 model 继续不暴露 Gate/raw market state，且一切新治理行为先在 synthetic root 验证。

## 2. Single-host control plane, identities and ownership

M6.5 不增加数据库、网络服务或生产交易单元。受控 control root 内有四个**非 root、pairwise non-alias** Unix writer identities：

```text
governance-supervisor  authority / activation / admission / dispatch control indexes
research-runner        immutable snapshot reader; own-event claim and staging writer only
result-publisher       publisher-prepared / final / terminal-index writer only
replay-supervisor      archive stage / runtime / replay receipt writer only
```

`OfficialResultResolver` 是 governance-supervisor 的 read-only capability，而不是共享给 research scripts 的 Path API：policy 只给 supervisor read/search final/index ACL，不给它 final/index write ACL。它只接受 `(activation_id,event_id)` 并由 terminal index 反查。research-runner 没有 final/index 的 read/write/search ACL；result-publisher 没有 authority/admission/dispatch 的写 ACL；replay-supervisor 没有 M7 authority/final/index 写 ACL。

`M7ControlPlanePolicy v1` 是 QRC 精确引用的 immutable policy，含四个 actor 的 numeric UID/GID、允许 supplementary groups/capability set（默认空）、control-root identity、socket peer allowlists 和 closed object-class ACL matrix：

| Object class | Owner / permitted writer | Other permitted access |
|---|---|---|
| policy, registry, activation, profile, admission, dispatch | governance-supervisor | runner/publisher no write; only explicitly needed FD read |
| event claim | research-runner | supervisor read/check only |
| job snapshot | governance-supervisor | runner read-only by sealed FD |
| runner staging | research-runner | publisher read/execute for sealing only |
| publisher prepared, final, terminal index | result-publisher | supervisor resolver read/search only |
| replay stage/runtime/receipt | replay-supervisor | verifier read-only by sealed FD |

No row may grant a shared writable group; every object is canonical relative to control root and opened via root FD/`openat`/`O_NOFOLLOW`, type/owner/mode/nlink/ACL/hash checks. Before activation, before permit, before publication and before resolution, the relevant policy/identity/ACL facts are rechecked. Actor UID/GID alias, unapproved supplementary group, shared group write, wrong socket owner/mode/peer UID, or any runner write bit on final/index rejects the operation and prevents official output. This is a normal deployment correctness prerequisite, not a hostile-host claim.

## 3. One-way frozen authority graph and activation lifecycle

The only permissible content-hash DAG is:

```text
M7AuthorizationPlan v1  --no QRC reference-->
frozen QRC (exact plan SHA + exact M7ControlPlanePolicy SHA)
  -> RunAuthorityRegistry v1 (exact QRC SHA + exact Plan SHA + policy SHA + M6 genesis SHA)
  -> RunAuthority v1 -> RunAuthorityGrant v1
  -> AuthorityActivationReceipt v1
  -> M7RunControlProfile v1 (O_EXCL sealed external anchor)
```

The arrow from plan to QRC in the diagram is chronological only: `M7AuthorizationPlan` **never contains a QRC ID, digest, mutable selector or reverse reference**. It contains family/run semantics, exact event plan/budget/spec references, M6 `6/44` genesis reference, namespace/journal/output policy and separately enumerated contingency events. QRC binds plan and policy. Registry then proves both objects are the selected pair by exact digests and checks `Plan.family_id == QRC.family_id`; no second Plan→QRC hash edge exists. Placeholder/self-hash/cycle, same ID with different bytes, old QRC/new plan, new QRC/old plan and any mutable selector fail.

Under control-root + authority locks, supervisor validates the full graph and M6 genesis, creates `AuthorityActivationReceipt` with activation nonce/generation/issuer/current logical ledger head/actor policy/root identities, then `O_EXCL` creates its fixed-slot `M7RunControlProfile`. The profile repeats QRC/plan/policy/activation/actor identities and deployment slot. It is the only external anchor; no runner or publisher receives a root/authority/plan/profile selection CLI.

Activation state is linearized by one activation lock:

```text
INSTALLING -> ACTIVE -> CLOSING -> CLOSED
```

Only `ACTIVE` may issue a dispatch permit. Transition to `CLOSING` takes the same lock as permit consumption, marks every `ADMISSION_ISSUED` / `RUNNER_STARTED` / `CLAIMED` but not-yet-dispatched event `ABANDONED_BEFORE_DISPATCH`, and fences all later permits. Existing `DISPATCHED` events may finish to terminal/quarantine; only then is `CLOSED` written. An interrupted install with no sealed profile starts nothing. Any new activation requires a new run/plan/QRC/namespace; stale profiles/activations never regain `ACTIVE`.

## 4. Event admission and at-most-once `fit` boundary

### 4.1 Immutable descriptor and exact state machine

For a plan event, supervisor holds the authority + ledger lock, rechecks the active profile and current logical ledger head, writes `START_RETAINED`, materializes/re-hashes/fsyncs the job-private certified snapshot, then `O_EXCL` writes `FitAdmissionDescriptor v4`. Descriptor fields include activation/profile generation, QRC/plan/registry/authority/grant/genesis/policy digests, exact event-plan entry hash, retained ledger record plus before/after logical head, evaluation/fit semantic IDs, fixed/behavior/state/join/candidate/snapshot digests, fold/segment/date/schema, expected `RunnerExecutionClosure v1`, and unique claim/staging/final/terminal-index identities.

The event state machine is exactly:

```text
PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> RUNNER_STARTED
        -> CLAIMED -> DISPATCHED -> PREPARED -> PUBLISHING -> TERMINAL_PUBLISHED
                                      \-> QUARANTINED_*

any nonterminal crash after START_RETAINED -> ABANDONED_UNKNOWN / QUARANTINED_*
```

No state is reused. A retained event may only be retried by a different frozen contingency event with a different descriptor and every root identity different.

### 4.2 Fixed fresh-exec / claim / permit order

There is one schema and one order—`DispatchClaim v1`, `FitDispatchPermit v1`, `DispatchReceipt v2`:

1. supervisor stages and verifies `RunnerExecutionClosure`, descriptor and snapshot, then starts **one fresh direct-exec worker** with `close_fds=True` and an explicit minimal `pass_fds` list; it never uses a pool, daemon, pre-fork helper or existing Python process;
2. post-exec bootstrap proves the observed runner closure (see §5). Only that post-exec worker derives `ProcessIdentity v1 = boot_id + pid + start_ticks + runner_instance_nonce` and creates its own event-local `DispatchClaim v1` by `O_CREAT|O_EXCL`;
3. worker requests permit over the supervisor-owned Unix socket. `SO_PEERCRED`, ProcessIdentity, profile generation, descriptor, exact claim, sealed snapshot FD, expected/observed runner closure and current logical head are re-read under the **same activation/event lock**;
4. if and only if profile is still `ACTIVE`, supervisor atomically fsyncs `DispatchReceipt v2(state=DISPATCHED,FIT_STARTED)` and consumes the one-use permit before replying success;
5. only the replying ProcessIdentity may cross one instrumented `model.fit()` call boundary. `FitDispatchGuard` removes its local permit after that attempt.

`os.register_at_fork` poisons the descriptor/claim/ledger/snapshot/permit handles in child; all non-passed FDs are `CLOEXEC`. Thus a pre-permit fork, post-permit fork, inherited FD, second socket request, PID reuse, restart race or two direct workers cannot pass the same event's permit check. If CLOSING wins the shared lock, permit fails; if permit wins, the event is already `DISPATCHED` and is allowed only to complete/quarantine under that fixed activation. The control flow never creates a claim before exec and never asks a separate pre-existing launcher to own a worker claim.

## 5. Sealed `RunnerExecutionClosure` for every official M7 fit

M7 official output and M6 replay share one implementation family, `SealedPythonExecutionClosure v1`, with distinct `purpose = AUTHORITATIVE_FIT | ARCHIVAL_REPLAY`. `RunnerExecutionClosure v1` is the AUTHORITATIVE_FIT profile and must be bound in admission before runner launch. It contains exact interpreter/entrypoint/config/source bytes, real staged runtime layout, CPython ABI/stdlib/lib-dynload/site-package/extension inventory, ordered `sys.path`, module-origin allowlist, native library/host ABI/GPU profile, fixed cwd/argv/environment/umask and deterministic settings, and closure-construction probe/tree digest.

Supervisor FD-hashes the closure, creates a new root-owned immutable stage and starts the measured interpreter through approved Linux FD-exec helper (`execveat(AT_EMPTY_PATH)` / `fexecve`) with canonical staged `argv[0]`, `env -i`, `-I -S`, fixed cwd and no path/PATH fallback. A stdlib-only bootstrap runs **before any runner/model import**, validates interpreter/prefix/path/origins, installs the only allowed import roots, rejects `PYTHON*`, venv/conda variables, site customization, cwd/deployment shadow and unapproved loader variables, then records actual Python module and native-map closure. It must finish this validation before the worker can create a claim or read a snapshot.

`RunnerExecutionReceipt v1` binds expected and observed closure digests, FD executable identity, staged tree, argv/cwd/env/umask/determinism, ProcessIdentity, module/native map and bootstrap digest. `DispatchClaim`, `DispatchReceipt`, `PreparedResultReceipt`, `TerminalPublishedReceipt` and resolver result descriptor all repeat the expected/observed closure digest and require equality. An executable/venv/module tree/config/CUDA/ABI/environment swap, wrong compatible stale runner, missing bootstrap or observed mismatch fails before permit; publisher refuses a prepared result with mismatched runner execution receipt. If target Linux/CUDA cannot meet FD-exec/bootstrap/import/native-map invariants, official M7 fit fails closed.

## 6. Publisher transaction and replay specialization

Publisher accepts only `(activation_id,event_id)`, resolves the sealed profile → descriptor → claim → dispatch sequence, reopens every object by FD and validates all bindings including runner execution receipt. It reads only the descriptor-derived staging root, requires exact regular-file inventory and receipt equality, seals a publisher-owned copy, uses atomic no-replace transition to a never-existing descriptor final root, then `O_EXCL` writes `TerminalPublishedReceipt v2` to terminal index. `OfficialResultResolver` only reads that index and rehashes final inventory; direct staging/checkpoint/final path discovery is absent. Any mismatched, incomplete or crash-residue root is forensic quarantine, never auto-promoted/reused.

For M6, `ReplayRuntimeClosure v2` is the ARCHIVAL_REPLAY specialization of the same closure implementation. `M6ReplayInputBinding v5` binds every archive/product/run/checkpoint/prediction/ledger input plus bootstrap/native helper/runtime closure. It is authoritative only on Linux x86_64 CUDA. Its fixed environment contains exact locale/timezone/PYTHONHASHSEED, CPU thread/affinity-related variables, CUDA visibility/GPU UUID, driver/CUDA/cuDNN/cuBLAS identities, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, relevant deterministic switches, stage-local temporary/cache roots and a restrictive umask; unlisted values are rejected. Bootstrap observes modules at preflight/CUDA-preflight/exit and `/proc/<pid>/maps` at preflight/final so lazy native libraries are bound. The three-way v5 binding + supervisor execution receipt + child receipt agreement remains 14 replay / 0 fit / OOS=false only.

## 7. Enforcement, migration and proof boundary

New code is limited to governance schemas/control-root access/authority/admission/dispatch/execution-closure/publication/replay modules plus approved server bootstrap/helper/verifier scripts. Existing M6 contracts, rows, git blobs and historical verifier remain immutable evidence. Implementation starts with strict parsers and synthetic fixtures, then identity/ACL preflight, graph activation, runner closure/dispatch, publisher, replay specialization. Every writer is temp+fsync+atomic no-overwrite/parent fsync; failures preserve old authority or quarantine new bytes.

Tests must demonstrate a concrete canonical Plan/QRC graph serializes without a cycle; profile close versus permit is linearized; post-exec-only claim works; runner/publisher UID alias or ACL mutation fails; correct descriptor plus wrong runner closure cannot become terminal; and M6 closure rejects interpreter/package/native/GPU/environment drift. These tests are later test-design obligations, not permission to run real data. Only after red/green/code-review/E2E quality stages can a separate read-only server replay be proposed. M7, CCC/Gate and final OOS remain later gates.
