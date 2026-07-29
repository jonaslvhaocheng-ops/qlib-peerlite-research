# M6.5 有界修复变更设计 v22

- 状态：`DESIGN_ONLY / READY FOR INDEPENDENT REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- 风险：`R3`
- 决策时限：无外部决策等待；所有实现前提已由冻结契约、M6.5 gate 与 v28 架构确认确定。

本设计只修复 M6.5 已登记的工程质量发现。它不使 M6.5 通过、更不授权 M7、CCC/Gate
真实训练、预算消耗、2025+ final-OOS 或交易。

## 1. 问题与范围

### 当前可观察行为

| 问题 | 现状 | 影响 |
| --- | --- | --- |
| 市场状态来源 | `data.market_state` 只接收已投影的 DataFrame；M3 `build_matrix()` 已按 label/execution/purge 条件筛行，旧 Qlib `market` 还包含 `label_open/label_close` | future-conditioned population 可伪装为合法输入；`market_gate=True` 可读旧 `market` 组 |
| 账本写入 | `LedgerPrefixBinding` 同时被用于 M6 历史前缀和新写入的起点；CLI 允许任意 run/prefix/cap flags；run ID 未绑定唯一 journal/output/event plan | stale head、第二 journal 或未注册 start 可被追加 |
| M6 checkpoint replay | raw worker 的 archive hash 与 source root 是独立输入；它期望的 source-manifest schema 与现有 transfer manifest 不同；没有完整 launcher | 不能证明实际 import 的 tree 来自已验 archive，也无法将产品/run 输入完整绑定 |
| package / Gate 路径 | package root eager-import PeerLite/Torch；当前模型仍允许 `market_gate=True` | governance CLI 不必要加载模型，且 M7 前存在一条可开启的泄漏入口 |

### 目标行为

1. 只能从 sealed raw snapshot 构建独立的 `market_state_population`，生成带 provenance
   manifest 的审计产品；它绝不从 M3 supervised matrix、Qlib Dataset 或 legacy `market` 读取。
2. 在 M7 仍未授权时，现有通用 `market_gate=True` 路径必须 fail-closed；M6 的
   `market_gate=false` checkpoint、配置和 frozen-source replay 保持兼容。
3. 所有未来真实 fit 的 journal start 必须经 immutable registration、M6 historical prefix
   与 exact current head 校验后原子写入唯一 ledger；M6.5 仅用 synthetic fixtures 验证该机制。
4. 新的 M6 archival launcher 必须从受验 transfer archive 临时解出唯一 source tree，绑定
   M6 gate/run/product/ledger/runtime，再让 mechanics-only raw worker 实际重放 14 fold。
5. 在 M6.5 内完成对既有 M7 v2 design/test matrix 的边界复核，但不创建 M7 derived contract
   或 M7 model runner。

### 非目标

- 不修改任何 immutable M6/M5/M3 contract、historical receipt、gate、ledger 行或 frozen source。
- 不重构 `scripts/server/build_pit_data_product.py`，也不从其 `build_matrix()` 的中间/输出对象
  导入 state；该函数已进入 label/execution logic。
- 不实现 CCC、M7 state wrapper、M7 runner、组合晋级、真实 fit、组合回测或 final-OOS。
- 不加入 v27 的 setuid helper、FD passing、namespace、cgroup、GPU ACL、服务进程或 hostile-host
  security claim。
- 不把 raw data、server paths、checkpoint 或 archive 提交 Git。

### 约束与假设

- 研究 server operator、OS、CUDA runtime、project checkout、frozen archive 和普通文件权限在
  M6.5 中受信任；hash/path/runtime mismatch 必须拒绝，但本阶段不防御敌对 root 或 kernel。
- Python 版本继续固定为 3.11；M6 raw replay 只允许显式 `cuda`，不得降级为 CPU。
- M6 close state 是 gate 中固定的 hash 与 `6/44`。其 JSONL byte boundary 由冻结 hash/计数在
  line boundary 上**导出**，而不是声称 immutable gate 已直接保存 byte count。
- `mkt_adjf`/corporate-action 的 T-known availability 不能由代码假设：若 PIT audit 不能证明，
  state product 保持 `INTEGRITY_BUILT_NOT_PIT_QUALIFIED`，M7 继续禁止。

## 2. Repository evidence 与当前流

### 证据边界

- `evidence/m6_5_pre_m7/architecture_confirmation_v28.md`：已通过的有界架构。
- `evidence/m6_5_pre_m7/m6_5_mainline_scope_review_v1.md`：v27 不选为 M6.5 主线。
- `evidence/m6_5_pre_m7/m6_5_remediation_independent_code_review.md`：当前 P0/P1/P2 发现。
- `src/qlib_peerlite/data/market_state.py`：无 I/O 的聚合 primitives。
- `src/qlib_peerlite/data/qlib_dataset.py`：legacy `market` 含 label 字段，M6 不得改变。
- `src/qlib_peerlite/governance/trial_ledger.py`、`m6_archive.py`：现有 ledger/history roles。
- `scripts/reconcile_trial_ledger.py`、`scripts/server/verify_m6_peerlite_archival_replay.py`：
  当前 loose CLI 与 raw mechanics surface。
- `evidence/m6_5_pre_m7/m7_change_design_v2.md`、`m7_test_plan_v2.md`、
  `m7_design_review_v2.md`：M7 design-only input，仍不授权 M7。

### 当前与目标流

```text
当前不安全的 state 候选：
sealed raw → build_matrix(label/execution/purge) → M3 supervised matrix
          → projection → market_state primitive → legacy market gate

M6.5 后的唯一 state 生产路径：
sealed raw snapshot (allowlist only)
  → build_market_state_product
  → population.parquet + daily_state.parquet + manifest
  → audit-only verified loader
  → [未来、M6.5 PASS 后的 M7 adapter；本次不实现]
```

```text
future run registration → cooperative run lease → fsynced journal snapshot
  → ledger lock: M6 historical prefix + exact current head + registration + limits
  → atomic replacement → no-replace reconciliation receipt

M6 gate/static history + transfer manifest + server-root binding
  → safe temporary extraction → fresh Python subprocess/raw worker
  → 14 exact fold replays → outer M6.5 archival receipt
```

## 3. 方案比较

| 方案 | 正确性 | 复杂度/可运维性 | 可测试性 | 结论 |
| --- | --- | --- | --- | --- |
| A. 继续 v27 特权 actor control-plane | 目标超出当前 threat model，且独立审查已证明正常启动图不可执行 | 高：新增 uid、helper、FD、namespace、cgroup/GPU 运行单元 | 测试矩阵与研究问题无直接关系 | 拒绝 |
| B. 保留当前 DataFrame/loose-CLI/raw-root 接口，仅补禁列或 hash | 无法识别“先按未来筛行、再投影”的数据污染；stale head 和 archive/root splice 仍存在 | 表面简单，实际保留 P0/P1 | 负对照无法证明来源/头部/树绑定 | 拒绝 |
| C. 选择：单仓库 data/governance + 普通 server composition roots | 每个已登记发现有一个可验证输入、失败规则与 receipt；不改变 M6 历史 | 中等，复用现有模块/lock/manifest，不新增服务 | pure/core unit、synthetic integration、一次只读 server E2E 可分层 | 采用 |

## 4. 提议设计

### 4.1 Import 与 M7 Gate 暂停边界

**修改面：** `src/qlib_peerlite/__init__.py`、`config.py`、`models/peerlite.py`、`cli.py`、
`data/dataset.py` 及对应测试。

1. package root 改为 metadata-only + lazy public export：
   `from qlib_peerlite import PeerLiteModel` 继续可用，但
   `import qlib_peerlite.governance.trial_ledger` 不得加载 Torch/PeerLite。
2. M6.5 时任何 public config/CLI/model constructor 请求 `market_gate=True` 都抛出稳定的
   `M7MarketStateNotAuthorized` 错误，发生在 dataset `prepare()`、journal、output 或 fit 前。
   这不是删除注册 candidate；它是将 unsafe legacy delivery path 暂停至 future M7-only adapter
   完成 PIT qualification 后。
3. `PanelDataset.market_state_columns` 若非空，必须恰好等于 `DAILY_STATE_COLUMNS` 的固定顺序，
   每列存在且与 feature/label/legacy market 不相交；空列表维持现有 M5/M6 synthetic compatibility。
4. `data/qlib_dataset.py` 的 `feature/label/market` 三组和 `MARKET_COLUMNS` 不变；M6 frozen
   archive 使用 frozen source，因而历史 no-gate replay 不受 live code 影响。

### 4.2 独立 market-state 产品

**新增面：**

- `src/qlib_peerlite/data/market_state_product.py`
- `scripts/server/build_market_state_product.py`
- `scripts/server/verify_market_state_product.py`（只验证 manifest/product/PIT evidence，不训练）

**保留/收紧：** `data/market_state.py` 仍为无文件 I/O 的 primitive，并在聚合前按
`(datetime, instrument)` 的 canonical sort 运行 float64 聚合，避免同日输入顺序影响 digest。

#### 输入与来源策略

`build_market_state_product` 只接收已验证 sealed snapshot root 与 immutable research-contract
binding；拒绝 `--product-dir`、M3 frame、Qlib Dataset、legacy `market` 或任意 projected
DataFrame 作为来源。它只打开下列 raw source 及其 manifest/hash：

- `mkt_equd`、`idx_cons_core`、`md_security`、`md_trade_cal`、`equ_inst_sstate`、`mkt_adjf`。

它不得打开 `mkt_limit`、`md_sec_halt`、任何 label/execution/purge/split artifacts，亦不得调用
`build_pit_data_product.build_matrix()`。该 script 可以拥有自己的窄 T-known source reconstruction；
不抽取/重构 M3 builder，以免改变已合格 M3/M6 路径。

固定的 `U_state(T)` 顺序谓词是：

1. CSI300∪CSI500 PIT membership 已公告且在 `[effective_from,effective_to)` 内；
2. 上市至少 60 个有效交易日，且 `delist_date` 未在 T 前生效；
3. T 存在 raw quote 时 `is_active=true`；缺 quote 计入每日 `missing_quote_count` 并作为
   inactive 排除，而不是被静默丢弃；
4. T-known special status 不是 forbidden/unknown；
5. raw price domain 有效；
6. mkt_adjf 驱动的 causal feature action-mask 有效；
7. 四个 state source 均有限。

`feature_eligible` 只代表上述 causal action mask；它不借用 M3 的全 50 feature finite、label
valid、label interval、execution、limit、halt 或 purge 条件。action availability 的证据不充分时
builder 可以完整构造 integrity artifact，但 verifier 绝不颁发 PIT-qualified result。

#### Artifact 与 API

一个新的、初始不存在的输出根通过 sibling temporary root 建造并原子 publish，只包含：

| 路径 | 内容 |
| --- | --- |
| `population.parquet` | 选中 `(datetime,instrument)`、四个 source 列；无 label/execution 字段 |
| `daily_state.parquet` | `DAILY_PRODUCT_COLUMNS`，一日一行 |
| `daily_population_audit.parquet` | 每日候选/逐谓词/缺 quote/最终 count 与 key digest，不含未来字段 |
| `market_state_manifest.json` | canonical self-hash、所有 source/partition hash、policy/code/runtime hash、schema/order、日期/行数/file hashes、OOS seal/status |

manifest 的 `source_kind` 必须为 `SEALED_RAW_SNAPSHOT`，状态初始为
`INTEGRITY_BUILT_NOT_PIT_QUALIFIED`，并明确 `final_oos_market_partitions_opened=false`。
所有路径相对输出根且 containment/hash/schema/row bounds 必须可验证。

`load_verified_market_state_product(root, purpose="audit")` 只返回通过文件、manifest、daily
digest 和 coverage 验证的产品；它不接受裸 DataFrame。未来 model-purpose loader 还必须要求
独立 PIT audit receipt 的 exact binding/status `PASS`，本 M6.5 变更不提供该 model capability。
`verify_market_state_product` 负责固定/behavior PIT evidence 的读取与验证；若 source clock 或
future-poison evidence失败，输出 `HOLD/FAIL`，不会把 integrity artifact 升格。

### 4.3 Ledger：历史前缀、exact head 与 run registration 分离

**修改面：** `src/qlib_peerlite/governance/trial_ledger.py`、
`scripts/reconcile_trial_ledger.py`，新 synthetic fixtures/tests。

#### 稳定数据契约

1. 现有 `LedgerPrefixBinding` 只保留为**历史前缀**契约，尤其是 M6 close `6/44`。它不得再
   被用作新写入的 current head。
2. 新 `LedgerHeadBindingV1` 表示一次 preflight 所见**整个** ledger：`sha256`、byte length、
   candidate/model-fit counts。任何有新增 event 的 reconciliation 必须在同一 ledger lock 内
   将 raw bytes 与其精确相等；未知 tail、stale head 或 line-boundary mismatch 均失败。
3. 新 `RunRegistrationV1` 是 immutable canonical JSON，含 `run_id`、family/spec content hash、
   authority ID、M6 historical-prefix binding、initial head、唯一 journal/output/receipt relative
   paths、caps、以及完整 allowed source-event semantic plan。plan 固定每一个 source event ID、
   type、evaluation/model/seed/fold/fit identity 和 canonical semantic digest；timestamp 是审计字段，
   不改变已冻结的 semantic plan。
4. ledger 首次写入同一 registration 时写一个不计预算的 `RUN_REGISTERED` record；之后同 run ID
   只有 content-hash、journal path、output root 和 plan 全同才可重试。第二 journal、第二 output
   root、不同 plan/payload 或未登记 event 一律拒绝。

#### 控制流与恢复

正式 reconciler CLI 改为只接受 `--authority-root --registration --expected-head`，从 registration
解析 journal/ledger/receipt 的相对位置；不再接受自由 `run-id/family-id/prefix/limits` flags。
在同一 authority root 下 path traversal、symlink escape、existing receipt 或不匹配 root 均拒绝。

在 global cooperative `exclusive_run_lease()` 下，future runner 的顺序固定为：注册→journal
append+fsync→snapshot head→reconcile→assert reconciled→才可 `fit`。M6.5 不实现该 runner，
但 library/CLI 的 registration/lease API 和 synthetic crash fixture 会验证这个顺序。reconcile
本身还持有短 ledger lock，以便即使误并发也只允许一个 exact head 成功。

在锁内依次：验证 M6 historical prefix、验证 current exact head、读取不可变 journal snapshot、
校验 registration/plan、检查 source/semantic uniqueness与 limits、把 registration+new events
用同目录 atomic replace + fsync 一起发布。receipt 使用 no-replace create，绑定 registration、
journal snapshot hash、head-before/after 和 appended IDs。

若 atomic replacement 失败，ledger 字节不变；若 replacement 成功但 receipt 进程崩溃，已启动
fit 仍安全计数，操作员必须以新 observed head 做 no-op recovery 并生成新的未占用 receipt。
缺 receipt 时 future runner 不得 fit。legacy M6 ledger events 仍可读取，但不被迁移或重写。

### 4.4 M6 archival replay：普通 verified launcher + raw mechanics

**新增面：**

- `src/qlib_peerlite/governance/m6_replay_binding.py`
- `scripts/server/run_m6_archival_replay.py`

**修改面：** raw `scripts/server/verify_m6_peerlite_archival_replay.py` 仅限输入-binding/manifest
适配；`governance.m6_archive` 保持只读 static historical verifier，不能承担 checkpoint replay。

#### Binding 与输入

`M6ReplayInputBindingV1` 从已验证的 M6 gate、run manifest、historical verification receipt、
M6 static archive summary 和现有
`m6_frozen_source_0af4572_manifest.json` 派生。它固定：

- M6 revision/spec/gate/verification hashes 与导出的 M6 ledger prefix；
- transfer manifest schema、archive filename/bytes/SHA、tree digest/file count；
- product manifest SHA/product ID/rows/date max；
- run/candidate/prediction/checkpoint expected identities；
- raw verifier code hash、expected 14 replay/0 fit/OOS=false profile；
- server-root-relative input locations和 fresh output root policy。

input binding 不是 M7 contract，也不允许自报新 archive/product/run hash。它将作为 M6.5
receipt 的输入，并可用 synthetic fixture 构造。`verify_archived_m6_evidence()` 必须先运行，
并在本机缺少 frozen Git objects 时 fail-closed。

#### Launcher sequence

1. 输出 attempt root 必须不存在；launcher 验 binding 与 static M6 evidence。
2. 只从 binding 的 server root 解析相对路径，校验文件 hash/size和 product/run identity。
3. 校验 archive SHA，安全解压到一次性 temporary directory，拒绝 absolute、`..`、symlink 和
   hardlink entry；按 canonical inventory 复算 tree digest/file count。
4. 以 fresh `python -I -B` subprocess、受控 cwd 和显式 allowlisted environment 启动 raw
   worker；父进程已导入的 `qlib_peerlite` 不能污染 child import。launcher记录 python/
   package/CUDA/device/argv digest；它不虚构 frozen environment hash，最终 exact score equality
   是运行兼容性的判据。
5. raw worker 只从 extracted tree import，读取 bound product/run/checkpoint/ledger，执行 14
   checkpoint exact replays，输出嵌套 raw receipt；显式传递 `--device cuda`，无 CPU retry。
6. launcher 再核对 raw receipt、ledger before/after、0 fit、OOS seal和 full fold coverage，写入
   no-replace outer `qlib_peerlite_m6_archival_replay_v2` PASS receipt。

现有 transfer manifest schema
`qlib_peerlite_m6_frozen_source_transfer_v1` 被设为唯一 accepted historical schema；不重写
historical archive 来伪造 raw worker 所期望的另一 manifest。raw verifier 通过外部 binding/transfer
manifest 验证 tree，而不是让调用者自由提供不相关 source root。历史
`m6_archival_replay_server_receipt*.json` 只作 regression evidence，不能用作本次 M6.5 PASS。

### 4.5 M7 design-only 对齐

本变更不修改 M7 execution spec、model budget 或候选。它只把下列规定作为以后 M7 的强制
依赖写清：

- `m7_change_design_v2.md` 的 CCC loss/early-stop/tie/singleton 语义、独立 Gate product 和
  conditional combination 规则仍是 design-only；
- `m7_test_plan_v2.md` 的 behavior-to-test matrix 被保留并由后续独立 design review 检查；
- 任何 M7 derived contract 只能在 M6.5 gate PASS 后，以 verified state PIT audit、new ledger
  registration schema 和 M6.5 archival receipt 为输入创建；
- future M7 adapter 必须单独消费 `PIT_QUALIFIED` state product，不能重新开启当前
  `PeerLiteModel.market_gate` 的 legacy `market` 路径。

## 5. 失败、并发、安全、资源与可观测性

| 类别 | 固定行为 |
| --- | --- |
| State 输入/时点不符 | 不 publish usable product；保留 failure/audit receipt，M7 remains blocked |
| State artifact 篡改/覆盖缺失 | loader/verify fail-closed；不返回 model-capable input |
| Ledger stale head/lock/plan/budget 错 | ledger 原字节不变；不写成功 receipt，不允许 fit |
| Ledger crash after publish | starts 保留并计数；只可 exact no-op recovery，不能重用 run ID |
| Archive/tree/product/run/runtime/checkpoint 不符 | 不写 PASS outer receipt；历史 M6 evidence/ledger 不变 |
| Replay GPU 不可用或结果不精确 | fail；不 CPU fallback、无训练/预算消耗 |
| 资源 | state/replay 都按日期/partition 流式读取；replay 逐 fold释放模型；不 materialize final-OOS |
| 可观测性 | manifest/receipt 记录相对 artifact IDs、hash、rows、date bounds、daily digest、head、run registration、runtime；不记录 raw values/secret |

## 6. 兼容、迁移、发布与回滚

- `LedgerPrefixBinding`、`verify_archived_m6_evidence()` 和所有 M6 immutable files 保持历史读取
  兼容；只新增 v1/v2/v3 schema，不迁移旧 JSONL 行。
- loose v2 reconciliation CLI/API 是未授权的新 M6.5 surface；替换为 registration-only interface，
  不能保留一个可绕过 exact-head 的兼容入口。
- `from qlib_peerlite import PeerLiteModel` 兼容；仅移除 governance import 的 eager Torch side effect。
- M5/M6 Qlib three-colset contract不变；frozen M6 source replay不依赖 live model gate code。
- 先在 synthetic fixtures 和 full test suite 完成 green evidence，再进入 independent code review；
  只有后续 E2E route 才可以发起一次只读 server archival replay。真实 state build/PIT verification
  失败仅使 M7 HOLD，不回滚/重写历史。
- 若新实现撤回，只删除新增 M6.5 attempt/artifact namespace；历史 gates、ledger、source archive
  与 final-OOS seal保持原样，M7 继续 `NOT_RUN`。

## 7. 验证义务（交由 test-design 细化）

1. future-conditioned M3 projection、label/execution/limit/halt/purge inputs、错误 source kind 或
   state manifest/path/hash/schema/digest 必须被 state path 拒绝；在 sealed synthetic snapshot 上，
   future poison 不得改变过去/同日 state。
2. state 的 canonical order、四公式、daily coverage、missing quote policy、date broadcast和
   audit-only/PIT-qualified boundary必须可验证；legacy M5/M6 groups不变。
3. public Gate 在 M6.5 时在读取 dataset 前 fail-closed，M6 false-gate checkpoint仍可加载；
   governance import不加载 Torch，public model import仍可用。
4. M6 historical `6/44` prefix 可在任意合法 append 后验证；exact-head、registration、journal
   snapshot、duplicate/mutated events、concurrent locks、atomic replace/no-replace receipt和 crash
   recovery 都必须有失败 oracle。
5. archive/transfer-manifest/tree/source import/product/run/checkpoint/key/score/runtime/output mutation
   必须无 PASS；fresh child import、14 fold/0 fit/ledger unchanged/OOS false 必须有完整 oracle。
6. 本次新增/实质变更的核心 module 要达到 100% line 与 branch coverage；coverage scope、原始
   command、source digest和例外（无）由 tests-green receipt记录。M6.5 不能用旧模块的低覆盖率
   或 historical receipt代替。

关键 E2E journey 是：synthetic sealed snapshot→audit-only state artifact；registered journal→
ledger recovery；以及在 code-review 后、受 binding 的一次 M6 read-only 14-fold server replay。
它们不包含 M7 fit或 final-OOS。

## 8. 实施计划（仅在后续 TDD 路由允许后）

1. **边界封口。** 使 package root lazy、暂停 public legacy Gate、收紧 `PanelDataset` state
   colset；以 M5/M6 regression确保未改变基线路径。
2. **State artifact。** 编写纯 artifact validation 与独立 raw snapshot builder/verification
   command；固定 population/state/audit/manifest schema和 temporary publish行为。
3. **Ledger v3。** 引入 head/registration schemas，移除 loose write API/CLI，实现在同一锁内的
   history+head+plan验证、atomic publish、no-replace receipts和 recovery semantics。
4. **Archive binding/launcher。** 实现 transfer manifest/tree validation、安全 temporary extraction、
   child import isolation、outer receipt；raw worker仅做必要的 binding schema适配。
5. **M7 design handoff。** 将本设计与 v2 M7 design/test-matrix作为独立 design-review subject；
   不生成派生契约或 runner。
6. **质量闭环。** 按 router 顺序完成 independent design review、test-design、expected-red、
   implementation、green coverage、independent code review和 E2E；任何失败回到其负责阶段。

## 9. Open decisions

无。corporate-action availability、server Git object/CUDA availability 和真实 raw snapshot
PIT audit 都是已定义的**证据结果**：不满足即 fail/HOLD，不需要在实现时另作产品/研究选择。

## 10. Verdict

`PASS FOR INDEPENDENT DESIGN REVIEW`。该设计将所有 M6.5 code-review findings 映射到现有
data/governance/script boundaries上的可实现契约，明确了失败、恢复、兼容和测试 seams，并保留
M7/final-OOS/M6 历史边界。它不包含未解决的架构或研究语义决定。

