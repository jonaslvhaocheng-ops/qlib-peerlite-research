# M6.5 架构确认 v11 — 单次授权、权威激活、终态发布与可执行运行时闭包

状态：`ARCHITECTURE_READY / 待新的独立设计审查`。质量变更：`m6-5-pre-m7-repair`；风险：`R3`。

本文件是在冻结的 `research_governance_threat_model_v1.md` 下作出的架构修复。它处理**普通**预 fork、重启、路径/环境误选、部分写入、错误服务参数和运行时漂移；不把恶意 runner 的任意 native-code execution、control root/host/kernel/ACL 被攻破或恶意 loader 注入当作本阶段可解决的对手。该边界一旦失效，相关证据无效，而不是由 Python 合同“继续可信”。

本文件不授权真实 M7、CCC/Gate、server replay、预算消费、最终 OOS 或改写 M6 history。

## 1. Canonical architecture composition and current evidence

下列组合是唯一的架构依据：

1. `architecture_confirmation_v9.md`，SHA-256
   `e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598` 的 §1、§2、§5 原样保留；
2. 本文件的 §3 **完整替代** v9 §3（plan / one authorized fit / terminal result）；
3. 本文件的 §4 **完整替代** v9 §4 和 v10 的全部 replay 段落；
4. v10（SHA-256 `e47c62a359a81b1c9f12c4946c8b1b2a4ea223f7b04b2fb76a9cf6fd87c4db13`）仅保留为 v11 取代前的审查历史，不是并行实现合同。

这一规则保留不可省略的 M6 `6/44` genesis、PIT/behavior/state input chain 和 v9 §5 的质量门，同时消除“多个部分补充互相覆盖却未说明”的歧义。

当前仓库的可核对证据是：历史 M6 静态/close evidence 由
`src/qlib_peerlite/governance/m6_archive.py` 和
`src/qlib_peerlite/governance/trial_ledger.py` 处理；现有 archive verifier 是
`scripts/server/verify_m6_peerlite_archival_replay.py`；M6-only public model 仍在
`src/qlib_peerlite/models/peerlite.py` / `src/qlib_peerlite/config.py` / `src/qlib_peerlite/cli.py`。
这些是本次增量的边界，不是已实现的 v11 行为。

## 2. Drivers, deployment topology, and ownership

M6.5 使用一个受信的单机治理 control root，不增加网络服务、数据库或新的研究进程类型。它有四个受控 Unix identity：

```text
governance-supervisor  owns control root, authority, admission and dispatch indexes
research-runner        reads one immutable job snapshot; writes only its unique staging root
result-publisher       reads control indexes/staging; owns final roots and terminal index
replay-supervisor      owns replay binding/staging/runtime closure and execution receipt
```

`research-runner` 不能写 authority、admission、dispatch、final 或 terminal index；
`result-publisher` 不能选择 caller-provided input roots；replay verifier 不能接收 source/product/run/checkpoint/prediction/ledger/output path flags。所有 control objects 位于由 supervisor 编译进配置的 control root 下，调用方只可以提供逻辑 `family_id` / `event_id`，不能提供 root、registry、activation、staging 或 final path。

依赖方向固定为：

```text
immutable contract / M6 close proof / certified input
    -> governance schema + supervisor                 (only owner of control indexes)
    -> frozen runner / replay bootstrap                (read-only execution mechanics)
    -> result publisher                                (only final/index writer)
    -> official resolver                               (read-only terminal lookup)
```

模型、Qlib Dataset、状态构建和 archive verification 不得反向写 control indexes；public model API 不得导出 Gate-capable M7 mechanics。这个边界可由 package-export tests、strict schemas、CLI flag rejection、Unix ownership/mode checks 和 public synthetic E2E 机械验证。

## 3. Authoritative plan, fork-safe single fit, and terminal publication

### 3.1 External-anchor authority activation

权威图严格单向且无环：`M7AuthorizationPlan v1`（禁止引用 QRC/registry/grant/activation）→ frozen QRC（精确引用 plan + control policy）→ `RunAuthorityRegistry v1` → `RunAuthority v1` → `RunAuthorityGrant v1` → `AuthorityActivationReceipt v1` → write-once `M7RunControlProfile v1`。`AuthorityRegistryRoot v1` 是 control root 内、由 supervisor 唯一解析的 immutable registry。其闭合 schema 列出每个允许的 `family_id` 对应的：frozen QRC content digest / contract ID、`M7AuthorizationPlan v1` digest、`M6CloseArchiveProof v1` digest、`LedgerAuthorityGenesis v2` digest、预算上限、完整 `EventPlan v1` digest、policy version 和 authoritative namespace ID。它不接受相对或绝对的 caller path。

`M7AuthorizationPlan v1` 必须反向绑定同一 QRC 与 family、预算、可计数 event 的完整有序集合和每个 event 的 `candidate_evaluation` / `model_fit` 标志。所有哈希引用形成无环 DAG；重复 event ID、重复 fit/evaluation semantic ID、错误计数、缺节点或不同 QRC/plan/family 均拒绝。

在 registry lock 内，supervisor 验证 M6 close proof / new ledger genesis / QRC / plan / registry / authority / grant 的上述双向关系后，write-once 建立 `AuthorityActivationReceipt v1`：

```text
registry root + exact QRC + exact plan + exact genesis + event-plan
    -> activation_id (content derived), activation_nonce, registry_generation
    -> control-root ActiveAuthorityIndex entry
```

activation receipt fsync 后，supervisor 以 `O_EXCL` write-once 建立 `M7RunControlProfile v1`（exact QRC/plan/policy/activation hashes、fixed deployment slot、actor identities、control-root identity），再将它 seal 成 `ACTIVE`。`ActiveAuthorityIndex` / profile 是 activation 的唯一外部锚：它由固定 control-root-relative path 解析、原子 fsync 写入且不可 caller 替换。没有 sealed profile 的中断安装不得启动 runner；每个 `(family_id, qrc_digest, plan_digest)` 只能有一个未关闭 activation。替换必须先有明确 `CLOSED` record，再建立新的 generation，旧 activation 不再可 dispatch。admission 和 resolver 都以 profile/index 中的 exact activation digest 为准，不能以“内部自洽”的 authority JSON、旧 registry snapshot 或启动参数为准。

### 3.2 Admission and one-use dispatch permit

在任何 admission 前，supervisor 先在 authority ledger 的稳定 lock 中把计划 event 写为 `START_RETAINED`，所以 crash-before-fit 也保守计费。`FitAdmissionDescriptor v3` 是 supervisor 从当前 activation 与一个 event **确定性**派生的不可变对象，至少绑定：

- activation/registry generation、authority namespace、QRC/plan/event-plan/genesis/ledger-head digests；
- event ID、exact event-plan-entry hash、唯一 evaluation/fit semantic IDs、retained-ledger-record hash / before-and-after logical head、预算 flags、状态/PIT/behavior/join/candidate/input-snapshot digests；
- fold/segment/date/schema、frozen runner revision/runtime descriptor；
- descriptor-derived、此前不存在的 staging 和 final root identities。

Supervisor 以 event 为键在 `AdmissionIndex` 中 write-once 记录 descriptor digest；只能从该 index 读取 descriptor。重复或冲突的 admission、过期 activation、非计划 event、错误 ledger head、错误 snapshot 或已存在 root 均在任何 runner 启动前失败。永久身份使用 namespace/genesis/logical head；瞬时 FD device/inode 仅用于 lease/admission 再核验，不能作为会被 atomic replace 改变的 ledger 永久身份。

`FitDispatchClaim v2` 不是单独的 `O_EXCL` 文件：在 supervisor event lock 中，它将 admission、stable lease、claim nonce、expected direct-exec worker 和 `DISPATCHED` durable record 绑定。runner 以 governance-owned claim directory 的 `O_CREAT|O_EXCL` 创建 immutable claim，随后 supervisor 直接以 `close_fds=True` fresh `exec` 一个单 worker command；pool / daemon / pre-fork worker 模式禁止。`ProcessIdentity v1` 为 `boot_id + pid + /proc/<pid>/stat start_ticks + runner_instance_nonce`。actual child 向 supervisor 的 Unix-domain control socket 请求一次性 `FitDispatchPermit v1`；supervisor 以 peer credentials 和该 process identity 验证它就是 direct-exec worker，并在同一短事务中把 permit 标记为 `CONSUMED`、持久化 `FIT_STARTED`、fsync 后才答复允许调用 `model.fit()`。

runner 内部的 `FitDispatchGuard` 只允许一次 permit consume；它在 `fork` child 中通过 `os.register_at_fork` poison admission/lease/ledger/snapshot descriptors，所有这些 FDs 设置 `CLOEXEC`，并在每次 `fit` 前检查当前 ProcessIdentity。因而正常的 fork-after-claim、继承 FD、pre-fork pool、父子同时尝试、重复 API 调用和重启竞争都会在 `model.fit()` 之前拒绝。claim 一旦存在绝不回收/重命名/再授权；若 permit 已消耗而 worker 崩溃，event 已保守计费，恢复不重用 claim/permit，必须使用 plan 中单独的 contingency event。该机制的保证上限是“冻结、受信 runner 的正常进程模型下每个 retained event 至多一个 `fit`”，并不声称阻止恶意 raw syscall runner。

### 3.3 Prepared-to-terminal result transaction

runner 只能在 descriptor 的 staging root 写 regular output files，再写 `PreparedResultReceipt v1`。它绑定 activation、event、descriptor、claim、dispatch receipt、worker identity、exact input snapshot/state digests、completion class、complete staging inventory and tree hashes。它没有 final/index 权限。

publisher 不接收 staging/final/receipt path 参数。它仅从 `ActiveAuthorityIndex -> AdmissionIndex -> DispatchIndex` 按 logical event lookup 期望的 descriptor、claim、staging root 和 final root；每一层的 activation/event/descriptor digest 必须相同。它以 FD/openat/type/owner/mode/nlink/hash 重新读取 staging，拒绝 symlink、extra file、错 job、旧 receipt、错 state/snapshot、非 `DISPATCHED` claim 或非成功 prepared terminal class。

通过验证后 publisher 将 output copy/seal 到 publisher-owned unique prepared root，fsync inventory，再用 atomic **no-replace** move 到 descriptor-derived、此前不存在的 final root（若平台不能证明 no-replace，直接失败，不能退回可覆盖 `rename`）。只有 final root hash 已稳定后，publisher 才在独占 event lock 下以 `O_EXCL` 原子追加 `TerminalPublicationReceipt v1` / `TERMINAL_PUBLISHED` 到 controlled `TerminalPublishIndex`。receipt 绑定 admission/activation/event/claim/dispatch/prepared receipt、all inventory hashes、final root identity、publisher generation 和 index sequence。`OfficialResultResolver` 只能由 `(activation_id,event_id)` 反查 terminal index，并重新验证 receipt / final inventory；它不接受路径发现、staging、checkpoint、prepared output 或 final-without-index。

崩溃处理固定如下：任何 `PREPARED` 前失败、prepared root 与 descriptor 不匹配、rename 后但 index 前的 root、index 后 hash 不匹配或不完整文件，均写入 quarantine（或保留为 forensic-only）并永不自动 promote/reuse。已 `TERMINAL_PUBLISHED` 的 final tree 由 publisher owner/mode 固化；resolver 每次读取仍验 hash。如此普通错误的 publisher 参数、stale receipt、错误 staging root、final-root reuse 和 crash residue 不会成为 official result。

## 4. Archive replay: sealed inputs plus complete executable runtime closure

### 4.1 Frozen input and runtime objects

`M6ReplayInputBinding v4` 在任何 replay 前冻结。除 v10 已列的 archive / M3 product partitions / M6 run-candidate-fold-checkpoint-prediction / legacy read-only ledger / output policy 全部精确 inventory 外，它必须引用一个 `ReplayRuntimeClosure v1` 和 `ReplayBootstrap v1`。每项含 logical role、control-root-relative path、SHA-256、bytes、schema/format、owner/mode constraints；binding 不允许自由 source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter path。

`ReplayRuntimeClosure v1` 是 supervisor-owned、content-addressed、只读的执行根，至少包含：

- exact Python interpreter executable（SHA/bytes、ELF build-id、CPython version/ABI/SOABI）、`pyvenv.cfg`/prefix metadata、stdlib 和 `lib-dynload` tree；
- all trace-observed site packages / pure Python files / extension modules for bootstrap、verifier and imported frozen source; the required minimum is `numpy`、`pandas`、`torch`、`pyarrow`, while `qlib` or any other dependency enters only if the closure construction import trace requires it；
- exact `sys.path` order, allowed built-in/frozen modules, module-name → origin/hash map, extension-module map and allowed namespace-package roots；
- dynamic-loader / platform baseline identity plus every loaded shared library allowed for this closure (canonical path, hash, type and ABI identity); a different server image/baseline is rejected rather than silently accepted;
- a read-only closure tree digest and a closure-construction receipt that records the interpreter's own version/ABI, platform and reproducible import probe；
- M6 的 exact CUDA/device profile：GPU UUID/model/compute capability、driver/CUDA/cuDNN/cuBLAS identities、`CUBLAS_WORKSPACE_CONFIG=:4096:8` 与既有 deterministic switches。GPU driver/kernel 不是复制进 Python tree 的对象，但它们是受信 host ABI profile 的显式契约；不匹配即拒绝。

这不是要求解决 hostile host：受信 control root 可以托管该 runtime root；但它使普通的 interpreter、venv、wheel、`sitecustomize`、cwd、`sys.path` 或 native library 选错在执行前/后可检测，而非产生“自洽却错误”的 replay。

### 4.2 Bootstrap-before-verifier execution path

权威 M6 replay 的平台固定为 `Linux x86_64 + CUDA`；macOS 只可运行 synthetic tests，绝不能产生 authority replay receipt。Supervisor 先用 FDs 重哈希 binding 的所有 input，再把全部 replay data/source/verifier/bootstrap manifests 复制至新的 supervisor-owned input stage，fsync/tree-hash 并设为 runner read-only。runtime 必须 materialize 成真实的 immutable `stage/runtime/bin/python3.11` layout；一个 staged native exec helper 以 `execveat(AT_EMPTY_PATH)` / `fexecve` 执行已测量的 interpreter FD，同时给 CPython canonical staged `argv[0]`。bootstrap 验证 `sys.executable`、`sys.prefix`、stdlib/lib-dynload 都仍在该 staged runtime 内；若该 FD/layout invariant 无法验证，直接 fail closed，不能退回 pathname/PATH/当前 venv 执行。启动参数固定为 `env -i`、fixed cwd、fixed argv、`-I -S`，**入口是 bootstrap，绝不直接 import/execute verifier**。当前 verifier 的 `numpy`/`pandas` top-level imports 因而只能在 bootstrap 已建立/验证封闭 runtime 后发生。

bootstrap 使用 closure manifest 建立唯一允许的 `sys.path`，拒绝任何 deployment, cwd 或 user site path；先验证其自身 / staged verifier / frozen source origins，再用受控 loader 运行 verifier。执行期间它记录全部 `sys.modules` 的 origin（built-in/frozen 为显式 allowlist；其余模块必须映射到 staged source 或 runtime closure的 exact relative path/hash）。verifier 不得 spawn 未列入 closure 的 child；若一个允许 child 存在，它需同样 bootstrap、closure digest 和 receipt。

在 verifier 导入前、CUDA preflight 后和正常退出前，bootstrap / supervisor 采集实际 loaded Python-module closure 和 Linux `/proc/<pid>/maps` 中的 native library map，逐项对照 runtime closure；这样 lazy Torch/CUDA library 也在最终 map 中出现。错误 interpreter、stdlib/site-package/wheel、module shadow、extension、native map、ABI、GPU/CUDA/determinism profile、closure tree、bootstrap 或 import policy 都使 execution receipt 为失败，且不会产生可接受 replay。`PYTHON*`、`VIRTUAL_ENV`、`CONDA*`、`LD_PRELOAD`、`LD_AUDIT`、`LD_DEBUG`、`DYLD_*` 和未批准的 loader search variables 均拒绝。

`ReplayExecutionReceipt v3` 由 supervisor 写在 verifier 外，绑定 v4 binding、runtime closure / bootstrap / native-exec-helper digests、interpreter FD dev/inode/mode/hash/build-id and observed executable identity、stage tree digest、fixed argv/cwd/env digest、PID/start/exit、prebootstrap flags/sys.path digest、observed module/native closure digest、host ABI/GPU/determinism profile、output identity、legacy ledger before/after。child receipt 重复 binding/runtime/bootstrap/stage identities、exact 14 checkpoints/predictions、14 replay/0 fit/OOS=false and observed closure digest。`m6_archive` 只接受 binding + supervisor receipt + child receipt 的三方相等，且 output 必为新 root；任何 ledger mutation、pre-existing output、extra input 或 closure mismatch 均失败。

## 5. Enforcement, migration and decisions

实现增加的是单机 control-root schema/CLI/library boundaries，不引入网络 RPC、数据库或生产交易系统。新实现落在治理包、严格 schema、server launcher 和 synthetic test fixtures；现有 M6 immutable contracts/history 与 final-OOS partitions 不修改。迁移顺序是：先 M6-only Gate public denial；再 genesis/authority/ledger；然后 snapshot/admission/dispatch/publisher；最后 replay binding/runtime/bootstrap。每个新 writer 使用 temp+fsync+atomic replace/rename+parent-dir fsync，失败保留旧权威对象或 quarantine，新对象绝不覆盖历史。

被拒绝的替代方案：

- 仅保留 `O_EXCL`：不能识别 fork 继承或 double `fit`；
- 让 runner/publisher 接收 root 或 receipt path：错误但自洽的对象可被提升；
- 仅 hash `qlib_peerlite` 或依赖 `-I -S`：不能闭合 interpreter、wheel/C extension/native library；
- 直接采用 OCI/容器作为唯一方案：可以作为后续生产化选择，但为当前单机研究环境添加不可证实的运维依赖；v11 先使用封闭 interpreter/runtime root + host-baseline manifest。

实施前必须有 behavior-to-test matrix；至少覆盖 activation substitution/stale/cycle、fork/FD/restart/crash、publisher substitution/final swap、runtime interpreter/package/native/cwd injection 和 archive three-receipt agreement。所有证据先在 synthetic root 上产生；server replay、真实 M7、CCC/Gate 和 final OOS 继续禁止，直到后续质量 stages 全部通过。
