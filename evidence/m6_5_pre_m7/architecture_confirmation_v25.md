# M6.5 架构确认 v25 — 最小可部署的受控 archival-replay 控制面

状态：`DESIGN_ONLY / ARCHITECTURE_REPAIR`。本文件是对
`architecture_confirmation_v24.md` 的追加性替代：保留其中的 Pin 安装
DAG、Linux FD/OFD/no-replace 边界、raw worker mechanics-only 原则及 post-S5
archive continuation；只收敛 v20 两份独立 R3 审查和 protocol-graph 审计指出的
九项未闭合问题。它不创建 release、Pin、quality PASS、control slot 或 server
job；不执行 archival replay、训练、M7、PIT 或 final-OOS；不改 immutable M6
evidence、历史 worker 或 trial ledger。

本架构仅服务于 M6.5 的“重新证明历史 checkpoint replay 的控制链”。它不是常规
训练、回测或 Qlib 数据管线的运行时，也不新增数据库、常驻服务或交易接口。
在一个真实 Linux release 前，所有验证都必须使用 fake worker、fake namespace
launcher 和临时 control root；任何缺失的 Linux 原语都 fail closed。

## 1. 已核实的现状、范围和架构驱动

### 1.1 不可改变的事实

- 冻结 M6 close 的权威是逻辑账本前缀：
  `evidence/gates/M6_peerlite_gate.json` 固定 SHA-256
  `31a90d…1992de93`、6 个 candidate evaluation、44 个 model fit、上限
  27/60。当前 close snapshot 是 14,328 bytes、51 条换行终止 JSONL 记录；这些
  数值是 release closure 的输入，不是可由新控制面重写的输出。
- `trial_ledger.py` 以独立 dot-lock 的 `flock` 保护，并合法地用同目录
  `os.replace` 替换 ledger inode。因此历史/当前 `FileIdentityV1` 不能成为
  跨 append 的 ledger authority；它只能描述一次观测。
- 不可修改的
  `scripts/server/verify_m6_peerlite_archival_replay.py` 对所有输入/输出
  调用 `Path.resolve()`，要求输出目录起初不存在，用 pathname 创建目录，并在运行
  中才把 staged source 加入 `sys.path`。它会产生
  `qlib_peerlite_m6_archival_checkpoint_replay_v1 / PASS` raw receipt，
  但该 receipt 不是 official admission。
- 历史 `M6ArchiveSummary` 和 server raw receipt 是只读证据；它们没有 Context、
  role、slot、envelope、S5、S6 或 FinalIndex 语义。不得把它们重新包装为官方
  输出。

### 1.2 本次变更的唯一目标

在不改变上述历史语义的前提下，定义一个可部署的最小控制结构，使未来的
archival replay 能同时证明：

1. 实际拥有写权限的进程就是 Pin/Policy 指定的 runtime 和 Unix role；
2. P0、P1、P2 与 archive acceptor 的权限、FD、锁和崩溃恢复真实可执行；
3. legacy worker 实际读取的是冻结 source/ledger snapshot，而非 live package 或
   legacy 4/29 ledger；
4. worker-job 被清理后，archive 仍只靠 durable official evidence 重建结论；
5. 所有 normal deployment/configuration failure 都有确定的 reject、hold 或恢复路径。

### 1.3 架构决定与被拒绝方案

| 方案 | 决定 | 原因 |
| --- | --- | --- |
| P1 进程内 function-load raw worker | 拒绝 | raw worker 的 `.resolve()` 与已载入 live `qlib_peerlite` 不能证明 staged imports。 |
| 共享 worker-jobs 父目录加 ACL | 拒绝 | 同一 child identity 仍可能按已知 sibling 名称 traversal，且难以同时保证 legacy absolute path。 |
| 直接把 P0 的锁/token 给 archive acceptor | 拒绝 | topology lease 是 PID/actor-bound；跨 Unix identity 交接会破坏 writer matrix。 |
| 把 raw PASS 或 scratch 作为 archive input | 拒绝 | worker-job 可以 quarantine；raw receipt 无 official authority。 |
| 以 ledger inode 代表 M6 关闭态 | 拒绝 | 合法 `os.replace` 会改变 inode。 |
| 新增一个常驻调度/数据库服务 | 拒绝 | 对一次性 replay 没有必要；采用既有 trusted scheduler 下的 one-shot outer dispatcher。 |

## 2. 受信启动边界和物理 actor 图

### 2.1 角色与最小职责

`OuterDispatcher`（OD）属于既有 server-governance supervisor trust root。它是每一次
受控 replay 生命周期内的 one-shot 进程，不保存研究数据、不做模型计算、没有通用 RPC
或数据库。它只重新观察 sealed release inputs、发放一次性 permit、按固定 profile 启动
角色并 reaps 子进程。

```text
trusted scheduler
    |
    +-- OuterDispatcher (OD; pinned outer trust layer)
          |
          +-- ArchiveAcceptor[ADMIT]      result-publisher: E/C only, then exits
          |
          +-- P0 ReplaySupervisor         research-runner: S0..S5, H/O/envelope
          |      |
          |      +-- P1 Verifier           child-verifier: verifies P2, IPC attestation only
          |             |
          |             +-- P2 RawMechanics (fresh interpreter, same Unix uid as P1)
          |
          +-- ArchiveAcceptor[FINALIZE]   new result-publisher invocation: receipt/S6/index
```

- P0、P1、ArchiveAcceptor 必须是 Policy 固定的不同 Unix uid/gid/group profile。P2
  复用 P1 的 `child_verifier` Unix identity，但有单独的 `raw-mechanics` runtime
  profile；它是新鲜进程，且不继承 P1/P0 authority。这是比新增第四个 uid 更小的
  可部署方案。
- P0 是 S0--S5、H、OUTPUT_O、durable invocation、normalized result 和
  ChildReceiptEnvelope 的唯一 publisher；P1/P2 没有 official-root writer capability。
- `ArchiveAcceptor[ADMIT]` 是 E/C 的唯一 publisher。`ArchiveAcceptor[FINALIZE]`
  是 ArchiveReceipt、S6、FinalIndex 或 post-S5 rejection 的唯一 publisher。两次
  invocation 都持有自己的 actor capability 和自己的 OFD lease；它们永不接收 P0 token。
- P2 的 scratch 仅是 P1 的验证输入。它不是 slot，不能被 resolver、archive 或
  FinalIndex 直接读取。

### 2.2 唯一允许的 cross-identity launch mechanism

Policy 必须 pin 一个 native、reviewed 且不可通过 caller 参数泛化的
`m6_actor_exec` helper。它只能从 sealed descriptor FD 和 one-shot permit FD 读取
固定 profile；不接受 target uid、argv、path、cwd、environment 或任意 FD number 的 CLI
参数。它执行以下固定次序：

```text
validate sealed permit and descriptor digest
→ verify expected parent pid/start-ticks/role edge and monotonic deadline
→ initgroups + setresgid + setresuid to fixed profile
→ clear capabilities + no_new_privs + close_range(only fixed allow-list remains)
→ fexecve/execveat the policy-pinned interpreter and entrypoint
```

OD 维护仅在其进程生命期存在的 nonce table，并给每条边签发仅可消费一次的
`M6ActorPermitV1`。permit 绑定：

```text
{descriptor_digest, K, session_nonce,
 edge=(parent_role,parent_pid,parent_start_ticks -> child_role),
 target uid/gid/supplementary_groups,
 helper/interpreter/entrypoint/runtime-closure refs,
 fixed FD map, monotonic deadline, permit_nonce}
```

固定启动顺序为：

1. OD 验证 sealed anchor、Pin descriptor、Policy、evidence closure 和自身 runtime，
   启动 `ArchiveAcceptor[ADMIT]`；它取得新 lease，写 E/C，fsync 后退出并被 OD reap。
2. OD 用 P0 permit 启动 P0，并把仅供启动 P1 的 sealed P1 permit 交给 P0；P0 不获得
   OD 的 authority 或 permit nonce table。
3. P0 在取得 topology lease **之前** fork 一个 stub；stub 只能调用
   `m6_actor_exec` 消费那个 P1 permit，形成 P0→P1 的真实 parent chain。P1 设置
   `PR_SET_PDEATHSIG`，随后检查预期 parent PID/start tick。
4. P1 在 S3 后用已 pin 的 `m6_p2_view_exec` 启动 P2。P2 不需要 uid transition，
   但 helper 必须建立其私有 mount namespace、关闭输入 job FD，并以固定 interpreter
   exec fresh bootstrap。
5. OD 仅在 P0 已 exit 并被 reap 后，才使用新 permit 启动
   `ArchiveAcceptor[FINALIZE]`。它从 sealed descriptor 重建 context，独立取得新
   lease；没有对象、token 或 FD 从 P0 跨这个边界传递。

任何 helper hash/profile/parent/identity/permit/FD allow-list/deadline 不匹配都在
READY 前失败；不能降级为同 uid 运行、`preexec_fn`、generic `Popen`、传入 caller
argv，或共享 P0 lock。

## 3. Sealed release descriptor 与 runtime self-binding

### 3.1 终态安装 DAG

v24 的无环安装原则保持不变：先 freeze inner runtime closure 与 entrypoint，完成
M6.5 route closure，再写 Policy 到最终 sealed anchor，观察最终 anchor/policy identity，最后
由 OD 构造 Pin。Policy 不引用 Pin，inner entrypoint source 不编译 Pin bytes。

安装后 OD 从最终 anchor 以 no-follow FD 重新读取 Pin → Policy → evidence。它创建一个
写封闭的 `M6DispatchDescriptorV2` memfd（`F_SEAL_WRITE|GROW|SHRINK|SEAL`），而不是把
`compiled_pin` 或 caller path 传给角色。master descriptor 至少包含：

```text
K, release_id, descriptor digest, final-anchor D-v2,
Pin/Policy/evidence refs, Context and M6 ledger authority binding,
role graph and actor-launch profiles, runtime-closure/entrypoint refs,
root-relative slot topology, output topology, worker-view template,
LivenessProfileV1, device/job template and immutable release identifiers.
```

P0 与 ArchiveAcceptor 获得 master descriptor + sealed anchor FD；P1/P2 仅获得
role-scoped sealed views，含 master digest、自己的 profile、session/worker binding 与必要
stage refs，绝不含 control-root、slot、OFD lock 或 Policy writable capability。

### 3.2 必须由实际 actor 观测的 runtime

`ObservedRuntimeCandidateV1` 不能由 caller mapping 构造。每个有 authority 的 actor 在
READY 之前从自身进程重新计算并与 descriptor 精确比较：

```text
executable FileIdentity/hash; interpreter implementation/version;
entrypoint file/module/argv profile; sys.prefix; stdlib and dependency-closure manifest;
effective uid/gid/groups/capabilities; role; expected parent pid/start ticks;
descriptor/Pin/Policy/evidence digest set.
```

- P0 在其 observation 和 OD `ACK(P0)` 成功前，不得写 Bootstrap、S0--S5、H 或 O。
- `ArchiveAcceptor[ADMIT]` / `[FINALIZE]` 在自身 observation 成功前，不得写 E/C、
  receipt、S6、FinalIndex 或 rejection。
- P1 必须以其 runtime/profile observation 通过后才能发送 READY/ACK 或启动 P2。
- P2 由 neutral bootstrap 生成 `P2ObservedRuntimeReceiptV1`；P1 会验证该 receipt
  与 StageInventory/role-scoped descriptor 的精确等值。P2 的 receipt 没有 authority
  语义。

同一份有效 Pin 被传给错误 Python、旧 entrypoint、错误 venv/site-packages 或另一 release
runtime 时，所有写操作均 fail closed。

## 4. 模块边界与可机械检查的依赖方向

```text
m6_replay_identity.py
  DirectoryIdentityV2 / FileIdentityV1 / DirectoryChainV2 /
  SafePathComponent / PublicationSlotViewV1
        ↓
m6_replay_fs.py
  verified FD traversal / OFD lease / no-replace publication /
  ResolvedPublicationTarget
        ↑
m6_replay_authority.py
  SlotSpecV1 / policy / schema / role and writer semantics
        ↓
m6_replay_control.py
  SlotSpec validation → PublicationSlotViewV1 → FS operations
        ↓                         ↘
m6_replay_process.py / m6_replay_worker_adapter.py / m6_replay_lifecycle.py
```

`PublicationSlotViewV1` 是 identity/fs 层的 frozen dataclass，只带 root-relative parent
components、fixed leaf、expected parent D-v2 chain 和 immutable publication kind。它不包含
writer、role、K、schema 或业务语义。`SlotSpecV1.to_publication_view(binding)` 只能在
authority/control 已验证 Policy、Context、writer 和 slot schema 后调用。

`m6_replay_fs.py` 只接受 `PublicationSlotViewV1` 或自己的 opaque
`ResolvedPublicationTarget`，绝不接受 `Path`、`SlotSpecV1`、duck-typed mapping 或 caller
bytes。AST/import-graph check 必须证明 FS 不 import authority/control/lifecycle；所有
publication 前后重新比较 parent chain 与 leaf identity。

## 5. 6/44 账本权威、一次 snapshot 与 staged copy 的证据链

### 5.1 逻辑权威，不是 inode

`M6LedgerAuthorityBindingV1` 固定以下字段：

```text
logical_authority_id
family_id
authority_parent: DirectoryChainV2
ledger_leaf: "trial_ledger.jsonl"
legacy_writer_lock_leaf: ".trial_ledger.jsonl.lock"
writer_protocol: "trial_ledger_reconcile_v2_same_parent_atomic_replace"
m6_gate_ref
m6_close_prefix: {
  byte_length: 14328,
  sha256: "31a90d…1992de93",
  candidate_evaluations: 6,
  model_fits: 44,
  limits: {candidate_evaluations: 27, model_fits: 60},
  m6_journal_ref
}
```

在实际 release closure 中 SHA-256 必须使用 M6 gate 的完整 64 位 canonical value，
不能保存省略号。`authority_parent + fixed leaf + writer protocol + close prefix` 才是稳定
authority。一次 `ObservedLedgerSnapshotV1` 的 FileIdentity 只用于本次读取的 TOCTOU
证据，绝不可替代 logical authority。

### 5.2 P0 的受控 snapshot protocol

P0 在 dispatch 之前、未向 P1/P2 传递 live-ledger access 时执行：

1. 通过已验证 parent FD 打开 fixed ledger leaf；对既有 dot-lock 使用同一
   `flock` protocol 取得**共享读锁**。这只保护 legacy source 的读取/复制，绝不是
   official OFD topology lease。
2. 从同一 `O_NOFOLLOW` FD 读取完整 bytes `L`，对该 FD 前后 `fstat` 相同；记录
   ephemeral FileIdentity、长度、full SHA-256、line count 和计数。
3. 要求 `L[:14328]` 的 hash、行边界、JSONL 解析、6/44 计数、M6 journal relation 和
   authority parent 全部匹配 `M6LedgerAuthorityBindingV1`；完整 `L` 也必须是 append-only
   有效 JSONL，且未突破 27/60 上限。
4. 在仍持 source read lock 时，按 FD stream 将同一 bytes 复制到
   `stage/inputs/trial-ledger.jsonl`，fsync、设为 read-only，再比较 length/hash，要求
   `S == L` 的 bytes 摘要和长度完全相等。
5. 将 `ObservedLedgerSnapshotV1` 和 staged-copy equality 写入 H、
   `StagedMechanicsInvocationV1` 及 StageInventory；三者必须引用同一
   `snapshot_sha256`/`snapshot_length`。

合法 writer 的 `os.replace` 可以发生在 snapshot 之前或 source lock 释放之后，不会使
已封存的 H/S5 失效；archive 永不要求当前 live inode/hash 仍等于旧 snapshot。legacy 4/29
prefix、错误长度/line boundary/count、source/staged substitution、snapshot race 或缺失
authority parent 必须在 P1 dispatch 前拒绝。

## 6. P0 → P1 → P2 协议与 legacy worker 的可见路径

### 6.1 P2 private worker view

P2 只看见每 job 独有的 mount/pivot-root namespace：

```text
/m6p2/
  runtime/                         sealed read-only runtime closure
  program/p2_bootstrap.py          pinned stdlib-only neutral bootstrap
  program/verify_m6_peerlite_archival_replay.py
  program/p2-launch.cjson
  in/frozen-source-root/
  in/frozen-source-archive
  in/product/
  in/run/
  in/historical-verification.json
  in/trial-ledger.jsonl
  scratch/tmp/
  scratch/raw-output/              absent when P2 starts
```

`m6_p2_view_exec` 从 P1 验证过的 job FD 创建该视图后关闭 job FD；P2 不接收 P0↔P1
socket、control/root/slot/OFD/O/job FD 或 `/proc/self/fd` fallback。所有 raw arguments 是
固定的 `/m6p2/...` absolute paths，使旧 worker 的 `.resolve()`、pathname open 和
`mkdir(exist_ok=False)` 原样成立。若 namespace/pivot-root（或实证等价的仅此 job
visible view）无法建立，official dispatch 失败；不得退回共享父目录、caller path 或 ACL
猜测。

P2 的 `runtime`、`program`、`in` 都只读且无 symlink/hardlink；`scratch` 是唯一可写
目录。P1 保留经验证的 job FD、P2 pidfd 与 re-open 权限，以便 P2 exit/reap 后 no-follow
读取 scratch。P2 不会写任何 official slot。

### 6.2 fresh interpreter 与 import provenance

P1 不是 `python -m qlib_peerlite...`，也绝不 import `qlib_peerlite`。P2 以 Policy
pinned staged interpreter、`env -i`、cwd `/m6p2`、`-I -S -B` 启动。neutral bootstrap
初始只用 stdlib：

1. 检查 interpreter、`sys.prefix`、stdlib、runtime closure、StageInventory 和清空环境；
   拒绝 `PYTHON*`、`VIRTUAL_ENV`、`CONDA*`、`LD_PRELOAD`、`LD_AUDIT` 及 caller path。
2. 要求初始 `sys.modules` 没有 `qlib_peerlite`；从 sealed
   `RuntimeClosureManifestV1` 重建精确 `sys.path`，不使用 live site-packages、cwd、zip
   或 user-site。
3. 用 `importlib.util.spec_from_file_location()` 以私有非-`qlib_peerlite` 名称载入
   staged raw script；安装 import guard。
4. import guard 仅允许 `qlib_peerlite.*` 的精确 module-name → staged path → hash
   映射；每个延迟导入、extension、namespace package 或 shadow module 都必须属于
   StageInventory，否则拒绝。
5. raw `run()` 返回后，P2 将 non-authoritative
   `P2ObservedRuntimeReceiptV1` 写入 scratch。它含 runtime/source/module/native-map
   digests，但不含 `PASS`、slot 或 archive 语义。

P1 只在 P2 exit 且 pidfd/reap 确认后，才打开 scratch，验证 P2 receipt、raw receipt、
stage inventory、所有 staged module origins，以及 raw 的 14-fold / 0-fit / no-OOS /
no-ledger-mutation claims。raw receipt、P2 receipt 或 scratch 路径不能直接被 resolver 接受。

### 6.3 有凭据的 finite state machine

每个 packet 为 size-bounded canonical bytes，带
`{protocol, descriptor_digest, K, session_nonce, sequence}`。接收方启用 `SO_PASSCRED`，
拒绝 `MSG_CTRUNC`、重复/额外 FD、错误 uid/gid/pid/start-ticks、错误 nonce/deadline 或
非预期状态。`SCM_RIGHTS` 不被当作 identity 证明。

```text
P0 READY → OD ACK(P0)
P1 READY → P0 ACK(P1)
P0 fresh OFD lease → S0 → S1+O → H → Invocation → S2 → S3
P0 DISPATCH → P1
P2 READY → P1 ACK(P2) → raw mechanics → P2 RAW_DONE
P1 validates/reaps P2 → ATTEST(P1→P0)
P0 independently verifies scratch → FREEZE_REQUEST(P0→P1)
P1 closes job-write capability → FREEZE_ACK → P1 exit/reap
P0 reopens/recompares frozen scratch → Normalized → Envelope → S4 → Manifest → S5
P0 release lease/exit → OD reaps P0 → ArchiveAcceptor[FINALIZE] fresh lease
```

`ATTEST` contains the P2 identity/exit state, S3/nonce, staged invocation digest, raw receipt digest,
P2 runtime receipt digest, scratch inventory digest and normalized claims. P0 independently computes
the same facts. It sends `FREEZE_REQUEST` only after that comparison; P1 must close all job writable
handles, prove P2 reaped, send `FREEZE_ACK` and exit. P0 waits for P1 pidfd, then reopens scratch from
its own job FD and requires equality with the attested inventory before publishing any post-worker
durable result. This closes the late-write window without making scratch a long-term dependency.

## 7. Durable official evidence、post-S5 archive 与 resolver

### 7.1 固定 O topology 和 publication order

`OUTPUT_O` 是 P0 在固定 root-relative slot 中以 `O_EXCL` 创建的 directory。子 leaf 用
`OutputChildSlotSpecV1` 表示：其 parent 必须等于 O 中记录的 D-v2，leaf 固定，不能是
arbitrary path。P0 在 held lease 下以 immutable no-replace + file/parent fsync 发布：

```text
OUTPUT_O:             outputs/<K>.output/
HANDOFF_H:            registry/handoffs/<K>.cjson
INVOCATION:           O/staged-invocation.cjson
NORMALIZED:           O/normalized-result.cjson
CHILD_ENVELOPE:       registry/receipts/<K>.child-envelope.cjson
MANIFEST:             O/replay-output-manifest.cjson
```

唯一无环顺序为：

```text
S0
→ S1 + OUTPUT_O
→ H (LedgerAuthorityBinding + observed L + staged S equality)
→ INVOCATION (contains StageInventory)
→ S2 (binds O, H, Invocation)
→ S3 (P1 identity/session/nonce/Invocation)
→ P1/P2 attestation and freeze
→ NORMALIZED
→ CHILD_ENVELOPE
→ S4
→ MANIFEST
→ S5
→ ArchiveReceipt → S6 → FinalIndex
```

Binding requirements are fixed:

```text
Invocation → H + StageInventory + snapshot digest/length
Normalized → H + Invocation + raw-receipt digest + P2 receipt + scratch-inventory digest
Envelope → Invocation + Normalized + P1 credentials/attestation
Manifest → H + Invocation + Normalized + Envelope
S4 → Envelope + Normalized
S5 → Manifest + S4 + Envelope
```

After S5 and P1/P2 termination, worker-job/scratch may be quarantine/deleted. Archive only reopens
Context, S0--S5, H, O leaves and envelope; it never needs scratch, worker-job or current live ledger.

### 7.2 Fresh archive lease and deterministic recovery

P0 never transfers an OFD lease. It closes its lease after S5 fsync and exits. OD reaps P0 before
launching final ArchiveAcceptor, which self-observes its runtime/context, acquires a fresh lease and
revalidates all durable predecessors. The advisory `FREEZE` notification is not a capability; a P0
crash after S5 before notification is handled by re-observation, not a token handoff.

OD recovery after a P0 exit uses a fresh, Policy-authorized P0 recovery invocation and a fresh lease:

- valid S5, no late residue → `POST_S5_READY`, no pre-S5 terminal;
- incomplete S0--S4 after confirmed P1/P2 death → canonical pre-S5 terminal + job quarantine;
- late archive residue → no P0 terminal; ArchiveAcceptor resolves/rejects it;
- still-live holder or unknown child liveness → `BUSY`/`HARD_HOLD`, never promote.

ArchiveAcceptor can be relaunched after receipt-only or S6-only crash and resumes deterministically.

### 7.3 Resolver result semantics

| Observed condition | Writer action | Resolver result |
| --- | --- | --- |
| Valid live holder or full unique continuation | no terminal | `PENDING` |
| Valid verified pre-S5 failure after child death | canonical pre-S5 terminal | `REJECTED` |
| Valid S5, rejection absent, post-S5 defect | publish canonical rejection | `REJECTED` |
| Exact canonical rejection already exists | idempotent reject | `REJECTED` |
| Exact complete receipt/S6/index exists | idempotent acceptance | accepted result |
| Immutable rejection leaf occupied but malformed/wrong Context | never overwrite; quarantine diagnostic outside official root | `REJECTED_HARD_HOLD` |
| Prefix/authority/snapshot/O identity/context cannot be verified | do not dispatch/promote | `REJECTED_HARD_HOLD` |

`PENDING` is not a terminal status and is allowed only while there is one valid complete continuation;
a lost holder with incomplete S0--S4 must be terminalized after confirmed child death. `HARD_HOLD` is
not an automatic rejection and can never produce FinalIndex. An absent rejection leaf may publish a
canonical rejection; exact valid bytes are idempotent; occupied invalid bytes are never overwritten.

## 8. Liveness, cancellation and resource containment

`LivenessProfileV1` is inside the sealed Policy and descriptor. A production release must carry exactly
these finite values (fake releases may use separate pinned fake profiles):

```text
P0_READY=60s; P1_READY=60s; lease_acquire=60s; P2_READY=60s;
raw_completion=21600s; P1_verify=600s; freeze_and_reap=120s;
archive_finalize=600s; TERM_grace=30s; KILL_and_reap_grace=30s.
```

P0 observes P1/P2 using pidfd plus process-group/cgroup ownership. On timeout or lost IPC it sends
protocol CANCEL where possible, then TERM, waits the fixed grace, KILLs, and requires reaping before
writing a pre-S5 terminal. A late ATTEST/FREEZE after cancellation fails sequence/nonce/deadline
validation. P0 lock-acquire failure occurs before S3: it cancels/reaps P1 and writes no S3/S5. P0 death
cascades P1/P2 through PDEATHSIG; OD verifies/reaps or force-kills them before recovery. If reaping or
identity observation cannot be proven, the state is `HARD_HOLD`, not a guessed terminal. Archive timeout
or crash releases its fresh lease and OD relaunches only ArchiveAcceptor.

## 9. Enforcement, migration and verification obligations

The next bounded design must use this architecture without inventing a new actor, slot, runtime fallback
or permission model. It must implement in the following slices, each behind fake-provider tests before
any Linux integration attempt:

1. pure identity DTOs and one-way import graph;
2. FD/no-follow/no-replace/OFD provider and immutable slot views;
3. descriptor/permit/runtime observation and fixed actor-exec profiles;
4. P0/P1/P2 state machine, pidfd/liveness and private worker view;
5. logical ledger snapshot/staging/H binding;
6. O leaves/envelope/manifest, archive recovery and resolver;
7. Linux integration validation using non-production identities and fake raw worker.

Required architecture-level proofs include wrong/same uid and permit replay rejection; stray FD/env/path
rejection; actual P0→P1→P2 parent/PDEATHSIG/pidfd behavior; P2 inability to reach control/sibling paths;
raw `.resolve()` success only in `/m6p2`; live/staged import substitution rejection; 6/44 prefix and
legal append replacement handling; no-replace malformed-rejection HARD_HOLD; timeouts/cancel/reap;
job quarantine after S5; and receipt-only/S6-only recovery. These are behavioral obligations, not a
substitute for the router-selected test-design matrix.

The old M6 proof, raw worker, generic artifact writer and trial ledger remain untouched. Rollback before
release is deletion of an uninstalled candidate bundle; rollback after a sealed release is fail-closed
disablement of dispatch, never changing historical M6 evidence or an immutable official slot.

## 10. Architecture verdict

`PASS FOR ROUTING TO CHANGE-DESIGN` — the P0/P1/P2/Archive physical launch boundary, runtime
self-binding, logical 6/44 ledger authority, P2 staging namespace, durable output chain, immutable
decision semantics and liveness/recovery contracts are now explicit and mechanically testable. This is
only an architecture conclusion. It does **not** pass M6.5, authorize replay/M7/final-OOS, create a
release, or bypass the independent R3 change-design review, test-design, red-test, implementation,
green-test, code-review and E2E gates.
