# M6.5 架构确认 v28 — 有界研究质量修复

状态：`DESIGN_ONLY / ARCHITECTURE CONFIRMATION`  
范围：M6.5 允许的 T-known market state、trial-ledger reconciliation、M6 archival
checkpoint replay，以及 M7 的设计/测试边界。  
非范围：M7 real fit、final-OOS、交易或生产运行时安全。  

本文件取代 v27 作为 M6.5 主线的 architecture input。v27 和其失败审查保留为未来
production hardening 的候选，但不再是 M6.5 的依赖，理由见
`m6_5_mainline_scope_review_v1.md`。

## 1. 当前状态与架构驱动

当前仓库是一个 Python 3.11 单仓库、单 research-server 运行模型：库代码位于
`src/qlib_peerlite`，server-only composition roots 位于 `scripts/server`，测试位于
`tests`。M6.5 面对的是三个已审查的工程缺口，而不是新的服务或部署系统：

1. Gate 不得从带 label/execution 条件的 supervised matrix 派生 state；
2. 任何已启动 fit 都必须可幂等地进入唯一 ledger，并保持 M6 关门时 `6/44` 历史前缀；
3. M6 的“逐折 checkpoint replay”必须由新的只读 archival verifier 实际验证。

主要驱动是：PIT 正确性、历史证据不可变、追加账本的 crash/concurrency 安全、可复现性、
以及最小运行复杂度。不是 hostile-host resistance、实时交易或 GPU multi-tenant isolation。

## 2. 目标模块边界与数据所有权

| 所有者 | 职责 | 允许依赖 | 禁止依赖/职责 |
| --- | --- | --- | --- |
| `data.market_state` | 纯函数式选择 `U_state(T)`、日聚合、state 校验和按日期广播 | `data.schema`、NumPy、Pandas | Qlib、模型、文件 I/O、M3 supervised matrix、label/execution/purge 语义 |
| server market-state builder | 从 sealed raw/PIT inputs 抽取 allowlisted 输入，写 product + source manifest | `data.market_state`、已有 PIT artifact helpers | 直接以 label/执行/未来条件筛选 state；写训练/预测结果 |
| `governance.trial_ledger` | JSONL prefix 验证、run intent、锁保护的 started-event reconciliation、幂等读取 | stdlib、`governance.artifacts` | 模型训练、Qlib、指标计算、变更历史 M6 bytes |
| `governance.m6_archive` | 历史 M6 static chain、frozen code 和 ledger-prefix 的只读验证 | stdlib、`artifacts`、`trial_ledger` | 写 ledger、加载模型、发起训练 |
| archival replay server command | 在固定 archive/runtime 下实际加载 checkpoint 并逐 fold 比较 key/score；写新的唯一 receipt | frozen source tree、受控 Python/CUDA runtime、read-only M6 input、输出目录 | `fit`、2025+ data、portfolio/backtest、修改历史 M6 evidence/ledger |
| M7 contract/design artifacts | 预先声明 CCC checkpoint 语义、组合触发和预算；定义行为—测试矩阵 | immutable research contract、上述产品契约 | M7 implementation/real fit、结果驱动参数选择 |

`scripts/**` 是 composition root，不得被 library modules import。`market_state` 与
`governance` 是不依赖模型的低层模块。为使这个依赖方向可执行，M6.5 变更设计须使
`qlib_peerlite` package root 保持 import-light：治理/数据 CLI 不得因 package import
隐式加载 PeerLite/Torch；模型的 public import 只能保留在模型专属边界或延迟暴露。

## 3. 稳定公共契约

### 3.1 Market state

输入是具有唯一 `(datetime, instrument)` 键的严格 allowlist：历史 universe、上市/交易
状态及四个因果 feature source。输入中任何 `label*`、`execution*`、`limit*`、停复牌、
corporate-action crossover、purge/embargo 或额外列均为错误。输出是一行一个日期的四维
state，加 population count、keyset digest 与 state digest；它只能按 exact-date join/broadcast
给 model rows。产品源 manifest 必须绑定 sealed input identity、日历、allowlist、builder
code hash、日期范围和输出 hashes。

### 3.2 Trial ledger

`LedgerPrefixBinding` 是历史 closed state 的只读契约。M6 的 close prefix 固定为
`6 candidate evaluations / 44 model fits`，精确 byte boundary 与 digest 从 immutable/M6 gate
证据读取，不能以“当前 ledger 文件整体 hash”代替。`RunIntent` 是 journal source identity；
每个 `*_STARTED` event 在 fit 前写入 run-local journal，并由
`reconcile_started_events(...)` 在 ledger lock 内验证、去重、追加和 fsync。失败/中断的
start 仍计入预算；相同 source event 重跑必须 no-op，冲突 identity 必须 fail closed。

### 3.3 M6 archival replay

archive verifier 有两层，职责不能混淆：

- `verify_archived_m6_evidence(...)` 验证 historical gate、frozen code、run journal 和
  live-ledger 中的历史 prefix；
- `verify_m6_peerlite_archival_replay.py` 仅从已校验的 frozen source archive 和 M6
  pre-final-OOS product 读取，加载 14 个 checkpoint，重建 frozen folds，逐 fold 比较
  checkpoint inventory、keys 与 exact score bytes。

replay 的唯一可写目标是一个**不存在的** output directory 中的新 receipt；历史 M6
gate/receipt、ledger、product、checkpoint 和 source archive 都只读。固定 launcher record
必须记录 Python/CUDA/Torch versions、argv、selected device、archive/content hashes 和输出
root；`env -i`/pinned argv 是可复现 launcher hygiene，不是 security sandbox。若 GPU/runtime
不符合冻结环境，job 失败且不输出 PASS receipt；不以 CPU fallback 代替 CUDA replay。

## 4. 运行、信任与失败边界

M6.5 使用一个受信任 research-server operator 执行单个受控 replay command；普通文件权限、
lock、immutable hashes、原子 write 和显式 manifests 共同防止**意外**写入和证据错配。
本架构不对敌对本机用户、root、kernel、恶意 native library 或恶意 runner 作安全承诺。
如出现 archive/hash/runtime/ledger/product 不匹配、输出目录已存在、journal malformed、并发
锁冲突或任何 fold 不等，job 必须停止且不产生通过 receipt。

没有 OD/QI/AA/P0/P1/P2 服务、setuid helper、FD capability passing、mount namespace、
cgroup、GPU ACL、跨 uid scratch 或 background resolver。它们不是本阶段的运行单元，也
不能以“额外保护”为由成为 M7 的前置条件。

## 5. 可机械执行的约束

1. `data.market_state` 的 import graph 只能指向 `data.schema` 和数值依赖；测试用
   import/static inspection 强制这一点。
2. market-state builder 只调用 allowlisted input adapter；future-poison mutation 必须不改变
   已产生的日期 state，或在非法字段进入时明确拒绝。
3. ledger 写路径只能由 reconciliation composition root 调用；它在锁中复核 prefix、source
   identity、limits 与 JSONL boundary。M6 historical bytes 从不写回。
4. archival raw script 不得出现 `fit(`，不得接受 final-OOS product，且保存 receipt 前后
   ledger sha256 必须相同。
5. server-only scripts 必须在 `tests` 的 fake filesystem/subprocess seam 下可测；真实 CUDA
   archival replay 是后续 E2E acceptance action，不是 unit-test substitute。
6. M7 设计文档和 test matrix 是 M6.5 的 required artifacts，但不会调用 M7 model runner。

## 6. 增量迁移与回滚

1. 保留所有 M6 immutable files、historic receipts 和 v27 failure evidence；不覆盖旧 verifier。
2. 以现有 unreviewed M6.5 worktree surfaces为候选实现，而非既成通过事实：
   `data/market_state.py`、`governance/trial_ledger.py`、`governance/m6_archive.py`、
   `scripts/reconcile_trial_ledger.py`、archival replay script 及其 tests。
3. 下一阶段把每个公共契约写成实现就绪 change design，并明确每一项旧 finding 的闭合
   证据；只有独立 design review 通过后才进入 test design/red tests。
4. 若设计或测试证明现有 surface 不能满足契约，只撤回相应新代码/新 receipt，不回写或
   删除 M6 历史证据。M7 保持 `NOT_RUN`。

## 7. 架构决策与被拒绝替代方案

**决定：** 选择单仓库、纯 library + server composition-root 的有限修复，以现有研究
server 的受信任运行边界生成可审计 evidence。

**拒绝：** v27 的特权 multi-actor control plane。它既不在批准 CR 的必要产物内，也未能
通过独立可执行性审查；将它实现会增加部署单元、OS 特权和测试矩阵，却不直接闭合 Gate
的 market-state、ledger、archival verifier 或 M7 test-matrix finding。

**未来：** 若项目进入生产化、跨租户执行或 hostile-host security claim，须另立 production
CR，再评估 v27 的 namespace/cgroup/device isolation 思路；它不能回溯成为当前 M6.5 的
隐含验收条件。

## 8. Architecture verdict

`PASS FOR ROUTING TO CHANGE-DESIGN`。当前仓库已有能容纳这四个有界修复的 data、governance
与 script boundaries；目标依赖方向、数据所有权、运行边界、失败规则与临时债务均已明确。
这是 architecture-only 结论：不等于 M6.5 PASS，未授权 replay、M7、任何真实 fit 或
final-OOS access。

