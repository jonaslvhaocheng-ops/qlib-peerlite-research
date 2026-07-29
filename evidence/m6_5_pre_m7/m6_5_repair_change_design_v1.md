# M6.5 R3 修复设计 — 在 M7 前关闭数据来源、账本与历史重放缺口

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
质量变更：`m6-5-pre-m7-repair`  
风险：`R3`  
设计依据：`architecture_confirmation_v3.md`、独立代码审查
`m6_5_remediation_independent_code_review.md`、独立测试审计
`m6_5_independent_test_coverage_audit.md`。

## 1. 问题、目标、范围与非目标

### 当前可观察问题

1. 目前 market-state primitive 只检查调用时的列名；上游若已用 T+1 标签、执行限制或 purge
   过滤 M3 行后再投影列名，Gate 的当日横截面仍会被未来信息改变。
2. `LedgerPrefixBinding` 证明的是“历史 M6 前缀仍存在”，不是“某次 M7 run 从此刻的唯一账本头
   启动”；同一 run ID 也可换 journal 继续追加。
3. M6 checkpoint replay 虽然 14/14 score 精确相等，但 verifier 可传入独立 source root；archive、
   解压 tree、实际 import 和 receipt 尚不是同一证据链。

### 目标

在不开始 M7 fit 的前提下，交付可测试的三条 fail-closed 边界：

- 仅从 sealed raw snapshot 构建并验证 `market_state_population` artifact；未来 M7 adapter 只能
  接受该 artifact，不能接受 M3 DataFrame、Qlib `market` colset 或调用者投影的表。
- run authority 在服务器唯一账本中先注册；所有新增 started event 都从精确 current ledger head
  追加，同 run ID/authority/journal 不可替换。
- M6 replay 只从已验 SHA 的 archive 临时安全解压并 import；新的 server receipt 同时绑定 archive、
  source-manifest/tree、verifier、历史 verifier receipt、ledger 不变和 14 个 checkpoint 的精确重放。

### 非目标

- 不冻结 M7 derived research contract、候选预算或执行 spec；不执行 CCC、Gate、组合或任何真实
  `fit`。
- 不运行真实 raw snapshot state build，不主张其已 PIT-qualified；真实 build 前必须新开
  `point-in-time-data-audit` VERIFY。
- 不更改 `contracts/immutable/m6_*`、`evidence/gates/M6_peerlite_gate.json`、M5/M6 历史 ledger
  行、M6 checkpoint 或最终 OOS 封印。
- 不实现 M7 wrapper、CCC 或 state gate 本身；本变更只提供它们以后必须使用的安全输入和账本
  接口。

## 2. 仓库证据与方案比较

| 问题 | 方案 | 结论 | 原因 |
| --- | --- | --- | --- |
| state 来源 | 仅在 `select_state_population(frame)` 禁 label 列 | 拒绝 | 投影后的 M3 行集合已携带未来条件，列检查看不见来源。 |
| state 来源 | 给任意 DataFrame 加一个 provenance dataclass | 拒绝 | 调用者可伪造对象，且没有文件/partition hash 的可审计来源。 |
| state 来源 | snapshot-only server builder + immutable artifact loader | 采用 | builder 只打开 sealed raw manifest 列出的允许分区，artifact loader 校验 manifest、文件、状态 digest 和来源绑定。 |
| ledger 启动 | 对每次追加只查历史 prefix | 拒绝 | 任意后缀仍可被接受，过期 run 可写入。 |
| ledger 启动 | exact head 但不注册 run authority | 拒绝 | 首个 journal 在崩溃前未进入 ledger 时同 run ID 仍可被另一 journal 接管。 |
| ledger 启动 | run authority 先注册 + exact-head receipts | 采用 | `run_id -> journal/output/spec/allowed IDs/initial head` 一次性持久化，后续新增事件必须带上次 receipt 的 exact head。 |
| M6 replay | archive SHA + 外部 `--frozen-source-root` | 拒绝 | 正确 archive 仍可配错 root/import。 |
| M6 replay | archive-only temporary safe extraction | 采用 | 实际 import tree 必然来自被验 archive；receipt 可记录 manifest/tree/verifier digest。 |

## 3. 设计

### 3.1 `market_state_population` 的来源边界

#### 原始输入和 builder

新增 `scripts/server/build_m7_market_state_population.py`；它的唯一公开输入是：

```text
--snapshot-dir <sealed source snapshot>
--output-dir <new empty artifact directory>
```

它调用现有 `scripts/server/build_pit_data_product.py` 中新抽出的
`build_t_known_state_input(snapshot_dir)`。该函数只做以下 T 时已知步骤：

1. 验证 `snapshot_bundle_manifest.json`、所有允许 raw partition hash 和 pre-2025 开放范围；
2. 读取当日 OHLCV/成交额/换手、历史成分、security master、special status、corporate action
   和交易日历；
3. 用现有因果 `build_causal_daily_features()` 重建特征及 `feature_eligible` corporate-action mask；
4. 重建 `universe_member`、`listing_age_eligible`、`special_status_*`、`price_domain_valid` 和
   `is_active`（有当日合格原始行情即为 active）；
5. 输出只含 `(datetime, instrument)`、七个 eligibility flags 和四个 state-source 列的表。

它不得调用、导入或读取 `add_label_schedule`、`attach_labels`、`attach_open_limit_state`、
`attach_execution_halt`、`action_crosses_labels`，也不得读取 data product 的 matrix/population
文件。抽取后的函数由 unit test 以调用替身和 source-schema contract 验证这一点。

`market_state.py` 的 DataFrame selection 改为私有 `_select_state_population` primitive；它仅由
server builder 使用，不能成为 M7 模型或 Dataset 的输入 API。

#### artifact 格式和 loader

输出目录采用 `qlib_peerlite_market_state_population_v1`：

```text
market_state_population/
  population.parquet          # 仅四个 state-source 列 + (datetime, instrument)
  daily_state.parquet         # DAILY_PRODUCT_COLUMNS，逐日唯一
  market_state_manifest.json  # immutable provenance + inventory
```

manifest 必须包含并以 `content_sha256` 自绑定：

- `source_kind: "SEALED_RAW_SNAPSHOT"`、snapshot bundle SHA、允许 source manifest SHA、
  显式 `pre_final_oos_end_exclusive`；
- builder/causal-feature code SHA、eligibility predicate SHA、state input schema SHA；
- 两个文件的相对路径、SHA、rows、date bounds，以及 daily state/keyset digest summary；
- `status: "BUILT_NOT_PIT_QUALIFIED"`，不允许把数据 integrity 证明误报为 PIT PASS。

新增 `qlib_peerlite.data.market_state.load_verified_market_state_artifact(path)`；它只接受 artifact
目录，拒绝 data-product/M3 manifest、绝对/越界路径、hash 不匹配、错误 schema/source kind、非
有限值、重复/缺失日期或 state digest 不一致。它返回已验证的 daily state DataFrame。

未来 M7 Dataset adapter 的契约是：只可调用该 loader 并以 `DAILY_STATE_COLUMNS` exact-date join；
不得接收任意 DataFrame。当前 `PanelDataset` 同时收紧为：`market_state_columns` 要么为空，要么
与 `DAILY_STATE_COLUMNS` 精确同序；它们必须存在且与 feature/label 列不相交。

### 3.2 唯一账本、run authority 与恢复

保留 `LedgerPrefixBinding` 仅给 M6 archive 的历史 prefix 验证。为新 run 新增：

```python
@dataclass(frozen=True)
class LedgerHeadBinding:
    sha256: str
    byte_length: int
    candidate_evaluations: int
    model_fits: int

@dataclass(frozen=True)
class RunIntent:
    run_id: str
    family_id: str
    execution_spec_content_sha256: str
    journal_relpath: str
    output_relpath: str
    allowed_source_event_ids: tuple[str, ...]
    initial_ledger_head: LedgerHeadBinding
```

`RunIntent` 的 canonical JSON 写入运行前的 immutable file，包含 `content_sha256`。相对路径必须
非空、非绝对、无 `..`；允许 source event IDs 必须唯一且属于该 run ID。

新增 `register_run_authority(ledger_path, run_intent, expected_head)`：

1. 在 authoritative ledger lock 内要求当前 raw bytes 的 SHA、length、candidate/fit counts 与
   `expected_head` 全部精确相等；
2. 写入一个不计预算、带 hash 的 `RUN_AUTHORITY_REGISTERED` retained record；
3. 同 run ID 重试仅当完整 canonical authority 相等时 no-op；不同 journal/output/spec/allowed IDs
   或已有孤立 run source record 时 fail-closed；
4. 返回新的 `LedgerHeadBinding`，作为下一次 reconcile 的唯一合法 head。

`reconcile_started_events(...)` 改为接收 `expected_ledger_head`。它先验证已注册且匹配的
authority，再解析同一注册 journal 的 counted events。若有任何新的 normalized event，则在同一
lock 内要求 raw ledger 精确等于这个 current head；无新增且所有 event 已完全 retained 的同一
journal 可以 no-op。每次成功写入后的 receipt 返回新的 exact head。任何 crash 后恢复必须把上次
receipt 的 head 输入下一次 reconciliation；未知后缀、过期 head、不同 journal 或改过的 intent
均不写入字节。

`exclusive_run_lease()` 继续使用独立 `flock`，并新增 public `run_authority_lease(...)` context：
先持有 lease、注册/核验 authority，再允许 caller 执行 journal fsync → reconcile →
`assert_journal_starts_reconciled`。未来 M7 runner 必须以该 context 围住整个 run；本变更只提供
和测试此 public boundary，不调用 `model.fit`。

`scripts/reconcile_trial_ledger.py` 不再接受分散的 run ID/spec/prefix flags；它只接受
`--run-intent <immutable json>`、`--expected-head-...`、journal/ledger roots 和 limits。receipt 写入
input intent SHA、authority registration/no-op、old/new exact heads、追加数量和累积预算；全局 ledger
只保留相对 journal/output 路径，不记录绝对服务器路径。

### 3.3 M6 archive replay 的闭合证据链

`verify_m6_peerlite_archival_replay.py` 改为只接收 frozen archive，不接受外部 source root：

1. 验证 archive SHA，拒绝符号链接、hard link、绝对/`..` member、重复 member 或非单一根目录的
   tar；
2. 解压到 `TemporaryDirectory`，从这个唯一 tree 读取 `frozen_source_manifest.json`；
3. 验证 schema `qlib_peerlite_frozen_source_v1`、M6 revision、冻结 M6 execution spec hash 和所有
   code binding；计算完整 tree inventory digest；
4. 移除已预导入的 `qlib_peerlite*` module，只临时将 extracted `src` 放在 `sys.path[0]`，再执行
   14 个 checkpoint inference/replay；
5. receipt schema 升至 v2，并绑定 archive SHA/bytes、internal manifest SHA、tree inventory SHA、
   verifier SHA、Python/runtime summary、historical verification receipt SHA、M6 run/product/ledger
   input hashes、14/14 exact fold digests、`model_fit_calls == 0` 和 ledger hash before/after equality。

`m6_archive.py` 增加 receipt validator，供 M6.5 gate/test 验证这类 v2 receipt 的 content hash、
required bindings、14 folds、no-fit/no-OOS/no-ledger-mutation claims；它不改变 M6 immutable gate
的历史含义。

### 3.4 失败、兼容性、性能和回退

- 所有 schema/hash/path/head/authority/state/receipt 校验均在任何 output publish、ledger write 或
  checkpoint prediction 前失败。atomic ledger write 维持 temp+fsync+replace+directory fsync。
- 旧 M6 historical `LedgerPrefixBinding`、M6 v1 gate 和 M6 verification 继续可验证；新 v3 ledger
  records 只出现在其闭合 prefix 后。
- archive 解压只针对约 652KB 的冻结源码，临时目录在 job 结束后自动删除；state builder 仍是日频
  O(N) row pipeline，不构造 N×N 股票矩阵。
- 回退是停止使用这套未冻结 M7 namespace；不删除或覆盖 M6 artifacts。若真实 state build 的
  PIT VERIFY 未通过，artifact 保持 `BUILT_NOT_PIT_QUALIFIED`，M7 不得启动。

## 4. 验证义务

详细 test matrix 由下一阶段生成；至少必须包含：

1. M3 future-label/execution/purge 过滤后投影为允许列的 regression，不能作为 sealed source 进入
   builder/loader；同日 instrument 真正逆序时 daily state 和 digest 恒等。
2. source/data-product manifest、raw partition hash、builder code hash、state artifact files/digest、
   日期、NaN/Inf、重复 key、错误 bool、错误 `market_state_columns` 各自 fail-closed。
3. authority 首次注册、同 authority no-op、同 run ID 换 journal/output/spec/allowed ID 拒绝；
   stale/unknown current head、budget overflow、replace/fsync failure、lease contention、crash 后
   identical retry 都不产生 partial/duplicate ledger state。
4. fake archive success、tar traversal/link/duplicate/root failure、archive/schema/tree/code binding mutation、
   pre-import module isolation和 receipt mutation均 fail-closed；M6 server v3 replay 必须实际 14/14 PASS。
5. 新/实质变更的 `market_state.py`、`trial_ledger.py`、`m6_archive.py`、reconcile CLI、state builder
   和 archive replay script 逐文件 100% line + branch coverage；不得用 exclude/降低阈值实现。
6. CLI/data-pipeline E2E：从 synthetic sealed snapshot → artifact → verified loader；从 immutable
   run-intent → reconcile receipt → exact preflight；从 fake frozen archive → archival replay receipt。

## 5. 实施顺序

1. 抽取纯 T-known raw/state-input 函数，新增 snapshot-only state artifact builder/loader，并收紧
   Dataset state colset；先写 red regression。 
2. 引入 `LedgerHeadBinding`、run-authority registration/lease 和 CLI receipt，保留 M6 prefix API；
   先写 stale-head/run-ID/crash/concurrency red tests。
3. 改造 archive replay 为 archive-only safe extraction，扩展 receipt validator；写 fake archive
   source/tree/import isolation red tests。
4. 实现最小生产代码，补齐 unit/integration/fault tests和所有改变核心模块 100% line/branch coverage。
5. 上传完全相同 hash 的 verifier 到服务器并重新执行只读 14-fold M6 archival replay；复制新 receipt，
   将其绑定进 M6.5 gate/test evidence。
6. 完成独立 code review、CLI/data-pipeline E2E、M6.5 gate re-evaluation。只有全部 PASS 后才可进入
   第七步的 M7 derived contract/PIT VERIFY；若一项失败，保持 `NEEDS_CHANGES`。

## 6. 开放决策

无。实际 raw snapshot 的 PIT qualification 有明确所有者：进入第七步前由
`point-in-time-data-audit` 执行 VERIFY；在那之前本设计不会把任何生成的 artifact 描述为可训练
或有效 Alpha 输入。
