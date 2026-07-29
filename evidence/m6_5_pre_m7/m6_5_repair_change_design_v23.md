# M6.5 有界修复变更设计 v23

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v28.md`
- 风险：`R3`
- 修订原因：关闭 v22 独立审查登记的 state 输入/OOS、run authority 与崩溃恢复、
  M6 archive handoff、public Gate 入口及 M7 状态指针缺口。

本设计只覆盖第七步之前的 M6.5 工程质量修复。它不使 M6.5 通过，不创建 M7
派生研究契约，不实现 CCC/Gate，不运行任何真实 fit，不消耗试验预算，也不读取
2025+ 最终顺序样本外行情。

## 1. True Status Card

| 字段 | 当前事实 |
| --- | --- |
| 阶段与轨道 | `M6.5-PRE-M7-ENGINEERING-QUALITY / STRICT` |
| 最近动作 | v22 两份独立 R3 设计审查完成并登记为 `NEEDS_CHANGES` |
| Executed / completed / passed | M6：`yes / yes / PASS`；M6.5：`yes / no / NEEDS_CHANGES`；M7：`no / no / NOT_RUN` |
| 最强证据 | M6 gate、M6 immutable spec、M6 close ledger prefix `6/44`、v28 architecture |
| 历史证据 | 既有 M6 server replay receipt 仅为历史证据，不能关闭本次 M6.5 |
| 当前 blocker | 本 v23 必须独立通过 R3 design review |
| 唯一下一动作 | 登记 v23 后进行新的独立设计审查 |
| 禁止动作 | test implementation、真实 replay、M7 contract/fit、final-OOS、组合或性能结论 |

## 2. 问题、目标与非目标

### 2.1 当前问题

1. `data.market_state` 是纯函数，但调用者仍可能先用未来 label/execution 条件筛行，再投影成
   合法列；现有设计也未固定完整 raw 输入日期、60 日公司行动掩码和物理 OOS 读取规则。
2. `LedgerPrefixBinding` 既表示历史前缀又被当作当前写入头；registration、journal snapshot
   和 receipt crash recovery 没有一套完整、不可重绑定的状态机。
3. M6 raw replay worker 独立接收 archive 与 source root，且历史 transfer manifest 与 worker
   期待的内部 manifest schema 不同，不能证明实际 import tree 来自受验 archive。
4. legacy `market_gate=True` 仍可由 config、CLI、public model/network constructor 或
   checkpoint load 进入；旧 `market` colset 含 label 字段。
5. 旧 M7 v2 review 早于 v28/v23，不能作为当前 M6.5 的设计通过证据。

### 2.2 目标行为

- 独立生成一个只含 T 时点可用信息的 `market_state_population` 产品；产品输出日期固定在
  `[2012-01-01, 2025-01-01)`，support 读取固定在 `[2011-09-01, 2025-01-01)`。
- M6.5 期间所有 live public Gate 入口在任何数据、journal、output 或 fit 副作用前稳定拒绝；
  M6 `market_gate=false` checkpoint 与 frozen-source replay 保持兼容。
- 新写入必须由 future frozen execution authority、不可覆盖 registration、不可覆盖 journal
  snapshot、历史 M6 prefix 和 exact whole-ledger head 共同授权；M6.5 只使用 synthetic authority。
- M6 replay 必须从预执行 binding 指定的 archive 安全解压、复算 canonical inventory，并由 fresh
  child 执行 14-fold/0-fit/ledger-unchanged 重放；只有 outer v2 receipt 可作为新验收证据。
- M7 保持 `NOT_RUN`；只交付一个明确引用 v28/v23 的 compatibility addendum。

### 2.3 非目标

- 不修改 M3/M5/M6 immutable contract、历史 gate/receipt、已有 JSONL bytes 或 frozen source。
- 不调用或重构 `build_pit_data_product.build_matrix()`。
- 不实现 M7 模型、CCC、Gate adapter、组合晋级、真实数据训练、回测或最终 OOS。
- 不引入 v27 的 setuid、namespace、cgroup、跨 uid、GPU ACL、服务进程或 hostile-host 承诺。
- 不把 raw data、checkpoint、server 绝对路径或 archive 提交 Git。

## 3. Repository evidence 与冻结身份

### 3.1 研究与特征身份

| 对象 | 路径 | 当前文件 SHA256 / 内容身份 |
| --- | --- | --- |
| PIT research contract | `contracts/immutable/research_contract_pit_v2.json` | file `2f99bfb56929c732b24efe5da25c6c9d2786773ce95af347099228a521a9502c`; canonical `5b7353756e0fded36622a6946011f77a99706ec82a9685cb2dd3c03bba37002d` |
| feature spec | `contracts/feature_spec.json` | `b35da580ff710f7ca61f174d9f810f327942d190869ed422526e722eaeead12e` |
| feature implementation | `src/qlib_peerlite/data/features.py` | `0de3b798e8f49032bb04c58507ab471591e167013d58ea9f3f86e62308b47ef0` |
| M6 spec | `contracts/immutable/m6_peerlite_execution_spec_v1.json` | `469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8` |
| M6 gate | `evidence/gates/M6_peerlite_gate.json` | `83cdc68597e6b3bddc79fe366d71d9c4cc08398d88f06c94087d4b56bbf8ae86` |
| M6 frozen revision | Git | `0af45727d7f51af1c5a597d4a06fa5f95e34f758` |

### 3.2 State source manifest allowlist

`MarketStateInputBindingV1` 必须绑定下列六份 manifest 的 exact file SHA256：

| source | manifest SHA256 |
| --- | --- |
| `mkt_equd` | `d3f285c62c405ceed0b05fddc3abaf82f704815216ed42e454eab0e240ad3730` |
| `idx_cons_core` | `d6c5e5b2acfe2b8b1d354a07a7fed0a3e5b594eaa7dafc2c871fed48a5565667` |
| `md_security` | `4eff64dd068d805754cea9d1d9e720c7d7be7a180f6a23686f5434fbe3e03426` |
| `md_trade_cal` | `1aefd73dfd64dc5bdbb4e688e0812f962b191353b8bb5b90a56428472cb7fd0b` |
| `equ_inst_sstate` | `991212489d58c1ce3dc6aab7b1980774a4f0a80d28775a81bf11f954b811059e` |
| `mkt_adjf` | `e40fb724d9fd2a900921f41206252b758b9bfe311bf143295f7566ebf06831b6` |

`mkt_limit`、`md_sec_halt`、M3 matrix、Qlib Dataset、label、execution、split、purge/embargo
产物不在 allowlist，builder 打开任何一个即失败。

## 4. 方案比较

| 方案 | 正确性 | 复杂度 | 可验证性 | 结论 |
| --- | --- | --- | --- | --- |
| 继续 DataFrame/自由 CLI，仅补禁列/hash | 不能排除“未来筛行后再投影”、stale head 或 archive/root splice | 低但保留 P0/P1 | 负对照无法证明来源 | 拒绝 |
| 恢复 v27 privileged control plane | 超出受信任 research-server threat model | 极高 | 与 M6.5 主要证据无直接关系 | 拒绝 |
| 单仓库 typed artifacts + no-replace files + existing locks + server composition roots | 每个发现都有前置 binding、失败规则和 receipt | 有界 | pure/unit、synthetic integration、后续单次 server E2E 可分层 | 采用 |

## 5. Proposed design

### 5.1 Package import 与 public Gate fail-closed

修改：

- `src/qlib_peerlite/__init__.py`
- `src/qlib_peerlite/config.py`
- `src/qlib_peerlite/cli.py`
- `src/qlib_peerlite/models/peerlite.py`
- `src/qlib_peerlite/data/dataset.py`

统一错误为 `M7MarketStateNotAuthorized`。以下入口必须在读取 dataset、创建 journal/output、
加载 gated state 或调用 fit 前拒绝 `market_gate=True`：

| 入口 | `market_gate=false` | `market_gate=true` |
| --- | --- | --- |
| `ExperimentConfig` | 保持现有行为 | 构造/校验时拒绝 |
| CLI | 保持现有行为 | parse 后、运行前拒绝 |
| `PeerLiteModel` | M5/M6 兼容 | constructor 拒绝 |
| `PeerLiteNetwork` | M6 checkpoint 兼容 | constructor 拒绝 |
| `PeerLiteModel.load_checkpoint()` | false-gate checkpoint 可加载 | checkpoint config 含 true 时拒绝 |

根包改为 metadata-only + `__getattr__` lazy export；`from qlib_peerlite import PeerLiteModel,
PeerLiteNetwork` 继续有效，`import qlib_peerlite.governance.trial_ledger` 不得加载 Torch。

`PanelDataset.market_state_columns`：

- 空列表继续兼容 M5/M6；
- 非空时必须严格等于 `DAILY_STATE_COLUMNS` 的固定顺序；
- 每列必须存在，且不得与 feature、label、legacy market 重叠；
- 该校验不授权 model 使用 state，只封闭 schema。

`data/qlib_dataset.py` 的 legacy `feature/label/market` 三组不变，避免改变 M6 历史行为。

### 5.2 MarketStatePolicyV1

新增：

- `src/qlib_peerlite/data/market_state_product.py`
- `scripts/server/build_market_state_product.py`
- `scripts/server/verify_market_state_product.py`

保留 `data.market_state` 为无 I/O pure primitives，并将每日聚合前顺序固定为
`(datetime, instrument)` ascending、所有 state source 强制 `float64`。

#### 5.2.1 固定日期与读取范围

`MarketStatePolicyV1` 固定：

```text
timezone                  = Asia/Shanghai
prediction_clock          = after T close
support_start_inclusive   = 2011-09-01
output_start_inclusive    = 2012-01-01
output_end_exclusive      = 2025-01-01
rolling_windows           = [5, 10, 20, 60]
corporate_action_mask     = trailing 60 eligible instrument observations
empty_output_day_policy   = FAIL
missing_quote_policy      = count then exclude
aggregation_dtype         = float64
```

行情只允许物理打开 `mkt_equd_2011.parquet` 至 `mkt_equd_2024.parquet`；2025/2026
文件名即使存在也不得 stat/hash/read。opened inventory 必须记录实际打开的相对路径、bytes、
SHA256、row count、min/max date，并断言 `max_date < 2025-01-01`。

`mkt_adjf.parquet` 是非分区文件，不能直接全表读取。builder 首先只读取 Parquet footer
metadata，生成 `PreOOSRowGroupPlanV1`。仅允许解码 `EX_DIV_DATE` 统计存在且
`row_group.max(EX_DIV_DATE) < 2025-01-01` 的完整 row group；缺统计、统计无效或横跨 cutoff
的 row group 一律 `HOLD/FAIL`，不得为取得少量 pre-OOS 行而解码混有 2025+ 的 row group。
实际打开 row-group inventory、min/max、rows 和 digest 写入 input binding/manifest。

其余四个非行情源仅允许固定列读取，并按每个 T 的公告/生效规则做 as-of 计算；任何
`publish/effective` 在 T 之后的记录必须在 future-poison 后对 T 输出零影响。manifest 记录
列 allowlist、过滤谓词、输入行数、用于 T 的行数和 future-poison receipt。

#### 5.2.2 固定 raw-field mapping 与计算顺序

```text
OPEN_PRICE      -> open
HIGHEST_PRICE   -> high
LOWEST_PRICE    -> low
CLOSE_PRICE     -> close
TURNOVER_VOL    -> volume
TURNOVER_VALUE  -> amount
TURNOVER_RATE   -> turnover
TRADE_DATE      -> datetime
SECURITY_ID     -> instrument as canonical decimal string
```

顺序不可交换：

1. 验证 snapshot bundle、六个 manifest 和 exact file/row-group inventory。
2. 用完整 support quote history 构造唯一 raw panel；先按 `security_id, trade_date` 检查唯一，
   再转成 `(datetime, instrument)`。
3. 仅用 `mkt_adjf.SECURITY_ID/EX_DIV_DATE` 构造同日 `corporate_action` bool；adjustment factor
   数值不得进入特征或状态。
4. 在**尚未按 universe/listing/status/state-finite 筛行**的完整 raw panel 上调用：

   `build_causal_daily_features(raw, windows=(5,10,20,60),
   corporate_action_column="corporate_action", mask_lookback_sessions=60)`。

5. 从该结果逐键取 `ret_mean_20、ret_std_20、ret_1d、turnover_mean_20` 与
   `feature_eligible`；不得重算、替换公式或将 mask 缩短为 20 日。
6. 再计算并应用 `U_state(T)`，最后只裁剪输出到 `[2012-01-01, 2025-01-01)`。

raw price domain 固定为 `open/high/low/close > 0` 且 `volume/amount >= 0`；
turnover 与四个 state source 必须有限。缺 quote 的 universe member 写入
`missing_quote_count` 后排除，不能静默内连接丢失。

#### 5.2.3 U_state(T) 与四个聚合公式

当且仅当以下条件全部为真才纳入：

1. CSI300/CSI500 ID 分别为 `1782/2103`；`announcement_time <= T` 且
   `T in [effective_from, effective_to)`；
2. 从交易日历计算的第 60 个有效交易日已经完成；`delist_date` 未在 T 前生效；
3. T 有 raw quote；
4. T-known special status 不 forbidden 且不 unknown；
5. raw price domain 有效；
6. 60-session corporate-action `feature_eligible=true`；
7. 四个 state source 全部有限。

每日 state 固定为：

```text
mkt_trend_20    = arithmetic mean(ret_mean_20)
mkt_vol_20      = median(ret_std_20)
mkt_breadth_1d  = count(ret_1d > 0) / population_count
mkt_turnover_20 = median(turnover_mean_20)
```

中位数使用 NumPy/Pandas float64 的常规偶数样本两中值均值规则；NaN/Inf 不参与的隐式
drop 禁止，发现即在 selection 前排除并计数。每日 population 必须非空。

#### 5.2.4 MarketStateInputBindingV1 与产品

builder 只接收一个 no-replace、canonical JSON `MarketStateInputBindingV1`，它绑定：

- research contract、feature spec、features.py 与 market_state.py 的 path/hash；
- 六个 source manifest 的 path/hash；
- exact allowed file/row-group inventory 与禁止清单；
- policy 全字段与 policy content hash；
- support/output/calendar bounds；
- snapshot root 的 authority-relative location；
- output root relative location，且目标必须不存在。

产品通过 sibling temporary directory + fsync + atomic rename 发布，只含：

- `population.parquet`
- `daily_state.parquet`
- `daily_population_audit.parquet`
- `market_state_manifest.json`

manifest 初始状态只能是 `INTEGRITY_BUILT_NOT_PIT_QUALIFIED`，包含 input-binding hash、
opened inventory、所有 output hash/rows/date bounds、schema/order、daily digest、
`final_oos_market_partitions_opened=false`。`purpose="audit"` loader 只验证完整性；
`purpose="model"` 必须额外绑定独立 PIT audit receipt `PASS`，M6.5 不颁发该 model capability。

### 5.3 Trial ledger：authority、registration、snapshot 与 exact head

修改：

- `src/qlib_peerlite/governance/trial_ledger.py`
- `scripts/reconcile_trial_ledger.py`

#### 5.3.1 Canonical artifact rules

所有治理 JSON 使用 UTF-8、sorted keys、无多余空白的 canonical bytes；`content_sha256`
从移除自身字段后的 canonical bytes 计算。registration、snapshot、reconciliation receipt
均以 `O_CREAT|O_EXCL`、file fsync、parent fsync 写入，禁止覆盖或原地编辑。

路径均相对 `authority_root`；解析必须逐 path component 拒绝空、`.`、`..`、symlink 和
root escape。CLI 只接受：

```text
reconcile_trial_ledger.py
  --authority-root <absolute existing root>
  --registration <root-relative json>
  --snapshot <root-relative json>
```

没有 free `run-id/family/prefix/limits/ledger/output/expected-head` flags。

#### 5.3.2 数据契约

`LedgerPrefixBinding` 只表示历史 M6 prefix。M6 close hash 与 `6/44` 来自 immutable
M6 evidence；`prefix_bytes=14328` 是验证 hash/count 后在 JSONL line boundary 导出的值，
不是 immutable gate 的原生字段。

`LedgerHeadBindingV1` 表示整个 current ledger raw bytes：

```text
schema_version, ledger_relpath, byte_length, sha256,
candidate_evaluations, model_fits, total_jsonl_records
```

`RunAuthorityV1` 由未来、M6.5 PASS 后冻结的 M7 execution authority 提供，包含：

```text
authority_id, purpose, status=FROZEN, ledger_relpath,
research_family_id,
research_contract path/hash/canonical_hash,
execution_spec path/hash/content_hash,
candidate_registry path/hash/content_hash,
M6 historical prefix binding,
total caps,
ordered allowed semantic event plan,
content_sha256
```

allowed plan 对每个事件固定 `event_seq、event type、evaluation_id、model_id、seed`，
fit 事件再固定 `fit_id/fold_id`。semantic hash 排除 timestamp，但 source event 的完整
raw hash仍进入 snapshot。M6.5 只使用 `purpose=M6_5_SYNTHETIC_TEST_ONLY` 的临时 fixture；
live path 必须拒绝 test-only authority。此设计不创建真实 M7 authority。

`RunRegistrationV1` 由已验证 authority 发行，no-replace，包含：

```text
authority_relpath/hash, run_id, initial_head H0,
journal_relpath, output_root_relpath, receipt_root_relpath,
allowed_plan_hash, registration_seq=1, content_sha256
```

同一个 `run_id` 只能有一个 registration。发行 receipt 绑定 authority hash、
registration hash 与 H0；registration 发行不修改 ledger。

`JournalSnapshotV1` 在 cooperative run lease 内、journal append+fsync 后 no-replace 生成：

```text
registration_relpath/hash, snapshot_seq, previous_snapshot_hash|null,
journal_relpath, journal_byte_length, journal_sha256,
ordered source_event_id/full_event_sha256 list,
expected_head_before, content_sha256
```

snapshot 绑定 journal 的完整字节前缀。journal 后续追加产生新 snapshot，不能改变旧 snapshot。
每个 snapshot 的 source events 必须是 registration plan 的有序前缀；跳号、未登记事件、payload
变异或 timestamp 之外的 semantic hash 变化全部拒绝。

#### 5.3.3 状态机与崩溃恢复

```text
AUTHORITY_VERIFIED
  -> REGISTRATION_ISSUED(R, H0)       # no ledger mutation
  -> JOURNAL_SNAPSHOT(S1, H0)         # journal fsynced; no ledger mutation
  -> RECONCILED(S1, H0 -> H1)         # first batch includes RUN_REGISTERED
  -> RECEIPT_AVAILABLE(S1, H0 -> H1)
  -> FIT_ALLOWED(exact source IDs covered by S1)
  -> JOURNAL_SNAPSHOT(S2, H1)
  -> RECONCILED(S2, H1 -> H2)
  -> ...
```

first reconciliation 在同一 ledger lock 内按以下顺序执行：

1. re-read authority、registration、snapshot raw bytes/hash；
2. 验证 M6 historical prefix；
3. 验证 entire ledger 等于 snapshot 中 H0；
4. 验证 plan、journal bytes、source IDs、semantic uniqueness 与 total caps；
5. 一次 atomic replacement 追加一个不计预算的 `RUN_REGISTERED` 和 S1 的 counted records；
6. re-read/fync 后计算 H1；
7. 以 no-replace receipt 记录 R/S1/H0/H1、appended IDs/counts。

S2+ 不再追加 `RUN_REGISTERED`，并要求 `previous_snapshot_hash` 与上一 receipt、
`expected_head_before=上一 H_after` 精确一致。

崩溃规则：

- replacement 前任何失败：ledger 原字节不变，不生成 success receipt；
- replacement 成功、receipt 前崩溃：retry 在锁内识别一段与 R/Sn 完全相同的已追加记录，
  重算该 batch 结束处的 H_after；只允许创建同一确定性 recovery receipt，不再追加事件；
- receipt 已存在：raw bytes/content hash 全同则返回 `ALREADY_RECONCILED`，不相同则拒绝；
- current ledger 有其他合法 tail 时，recovery 仍只通过 exact R/Sn records 推导历史 H_after；
  任何新追加请求若 expected head 不是 current whole-ledger head，一律 stale-head 失败；
- registration 在首次 append 前变 stale 不允许 rebase；必须使用新 run_id/registration；
- receipt 缺失或 source ID 未被 receipt 覆盖时，future runner 不得调用对应 fit。

`exclusive_run_lease` 从 registration validation 开始，覆盖 journal append、snapshot、
reconcile、receipt assertion 和该 run 的 fit；ledger lock 只覆盖短 reconciliation。
M6.5 不实现 future M7 runner，只用 fake runner 证明 `fit` 不能在 receipt 前被观察到。

### 5.4 M6 archival replay binding 与 launcher

新增：

- `src/qlib_peerlite/governance/m6_replay_binding.py`
- `scripts/server/issue_m6_replay_binding.py`
- `scripts/server/run_m6_archival_replay.py`

修改 raw worker：

- `scripts/server/verify_m6_peerlite_archival_replay.py`

`governance.m6_archive.verify_archived_m6_evidence()` 保持只读静态历史验证，不承担 checkpoint
load/replay。

#### 5.4.1 M6ReplayInputBindingV1

普通 server composition command 先运行 static verifier，再从 immutable M6 evidence 与
`m6_frozen_source_0af4572_manifest.json` 发行一个 pre-execution、no-replace binding。它绑定：

- M6 gate/spec/run/historical-verification/ledger-prefix 的 path/hash/content identity；
- transfer manifest file SHA `104740de8bb55b9ec07706f836e764cd40c45931516e43ab361de74861c6bd2c`；
- archive filename、bytes `664406`、SHA
  `d49a15fd5f90fb9bafac19052b826657f81be1c51295ef21b172a1fd80420a1d`；
- frozen Git revision；
- product manifest/product ID/rows/date max；
- run/checkpoint/prediction/fold identities；
- launcher/raw-worker path/hash；
- server-root-relative input paths、fresh attempt-root policy；
- expected `14 replay / 0 fit / ledger unchanged / max date < 2025-01-01 / cuda only`。

历史 transfer manifest 的 `source_tree_sha256_before_manifest` 只保留为 historical declaration，
不当作新 canonical inventory，因为其算法未被文档化。

#### 5.4.2 CanonicalTreeInventoryV1

binding issuer 安全解压 archive 到 fresh temporary root 后计算新 inventory：

1. tar member normalized POSIX path 必须相对、无空/`.`/`..`，且 archive 只能有一个 top-level dir；
2. 拒绝 duplicate path、symlink、hardlink、device、FIFO、socket、setuid/setgid bit；
3. inventory 只含实际解压后的 regular files，按相对 path bytewise ascending；
4. 每项为 `{relative_path, byte_length, sha256, mode_without_write_variance}`；
5. tree digest 为
   `sha256(canonical_json({"schema_version":"CanonicalTreeInventoryV1",
   "root_layout":"single_directory","files":[...]}))`。

internal `frozen_source_manifest.json` 不是 authority，也不是必需输入；若 archive 中存在，它只是
inventory 的普通文件。唯一 accepted historical transfer schema 是
`qlib_peerlite_m6_frozen_source_transfer_v1`，唯一新 source identity 是 binding 中的 canonical
inventory。

#### 5.4.3 Launcher / child interface

launcher 只接收 `--binding <absolute path>` 和一个尚不存在的
`--attempt-root <absolute path>`；所有 server input 路径来自 binding。它重新安全解压并复算
inventory，不接受独立 `source_root/product/run/ledger/device/hash` 参数。

launcher 在 attempt root 中 no-replace 写 `RawReplayInvocationV1`，绑定：

- M6ReplayInputBinding hash；
- fresh extracted root 与重算 inventory hash；
- product/run/historical verification/ledger 的已验证 absolute runtime paths；
- raw worker hash；
- device=`cuda`；
- exact child argv 与 allowlisted environment digest。

child argv 固定为：

```text
<bound-python> -I -B <bound-raw-worker> --invocation <absolute invocation.json>
```

environment 只继承 binding/launcher 明确列出的 `PATH、LD_LIBRARY_PATH、CUDA_VISIBLE_DEVICES`
（存在时），不设置 `PYTHONPATH`，并记录 key/value digest。fresh child 只把 extracted
`src` 加入 import path；父进程预先 import 的 live `qlib_peerlite` 不得影响它。

raw worker 最终 CLI 只接受 `--invocation`。它验证 invocation/binding/inventory/raw-worker hash
后加载 14 个 bound checkpoint，逐 fold exact 比较 keys 与 score bytes。源码静态和运行时
双重禁止 `fit`；CUDA 不可用或版本/结果不相等直接失败，无 CPU fallback。

outer receipt schema 为 `qlib_peerlite_m6_archival_replay_v2`，必须绑定 input binding、
inventory、invocation、raw receipt、runtime、14 fold 明细、ledger before/after、OOS=false。
独立 `validate_m6_archival_replay_receipt()` 重新验证所有引用。legacy raw v1 或历史 server
receipt 永远不能单独满足 M6.5 acceptance。

失败 attempt 可保留 failure log/receipt，但不得含 `status=PASS`；重试必须使用新 attempt root。

### 5.5 M7 compatibility addendum

新增 `evidence/m6_5_pre_m7/m7_v28_compatibility_addendum_v1.md`：

- 声明旧 `m7_design_review_v2.md` 是历史 design-only reference，不是当前 M6.5 gate PASS；
- M7 只能在 M6.5 gate `PASS` 后创建 derived contract；
- future M7 必须消费 PIT-qualified state product、frozen `RunAuthorityV1` 和已验 M6 outer replay；
- future adapter 名称固定为 `M7PeerLiteGateAdapter`，不得重新开启 legacy `market_gate`；
- CCC 的 loss/early-stop/tie/singleton 语义继续引用 v2，但尚未实现或冻结执行 spec；
- addendum 不授权训练、预算、组合、final-OOS 或模型选择。

`docs/STATUS.md` 只更新当前阶段/最近动作/blocker/下一步，保持它作为 sole progress tracker；
不改历史 M0–M6 结论。

## 6. Failure、并发、安全、资源与可观测性

| 场景 | 固定结果 |
| --- | --- |
| state binding/source/date/action mask 不符 | 不 publish usable product；M7 HOLD |
| 2025/2026 quote partition 或 straddling `mkt_adjf` row group | 在 value read 前失败 |
| empty daily population / non-finite state | 失败并保留 audit counts |
| Gate true 任一 public 入口 | 副作用前 `M7MarketStateNotAuthorized` |
| authority/registration/snapshot/path/head/plan/cap 不符 | ledger 零字节变化 |
| concurrent reconciler 同一 head | 一个成功；另一 exact no-op recovery 或 stale-head fail |
| crash after ledger replace | counted starts 保留；只生成确定性 recovery receipt |
| archive/tree/product/run/runtime/checkpoint 不符 | 无 outer PASS |
| CUDA 不可用 | replay FAIL，无 CPU fallback |
| replay 运行 | 0 fit、0 backtest、ledger unchanged、final-OOS sealed |

threat model 只覆盖受信任 research-server operator 下的意外错配、损坏、并发与 crash；不防御
恶意 root/kernel/native library。state product 按年度分区读取；replay 一次仅保留一个 fold 模型。
manifest/receipt 记录 hash、rows、date、head、IDs、runtime 和错误分类，不记录 raw values/secret。

## 7. Compatibility、rollout 与 rollback

- M6 frozen source、gate、receipt、checkpoint、ledger 历史 bytes 均只读。
- `LedgerPrefixBinding` 和 `verify_archived_m6_evidence()` 保持历史读取 API。
- 旧 loose reconciliation write API/CLI 是未通过的新 M6.5 surface，替换后不保留绕过入口。
- M5/M6 no-gate config、checkpoint 和 Qlib three-colset 保持回归兼容。
- rollout 顺序固定：design review → test design → expected red → implementation →
  green/coverage → independent code review → synthetic E2E；真实 server archival replay 只有 E2E
  route 明确授权后才可运行。
- rollback 只移除新增 M6.5 attempt/artifact namespace和 live code change；不回写历史 evidence。
  回滚后 M7 继续 `NOT_RUN`。

## 8. Verification obligations（交给 test-design 细化）

1. State：source allowlist、exact partition/row-group inventory、2011-09 support、2012–2024
   output、60-session mask、四公式、canonical order、missing quote/empty day、future poison、
   audit-only/model loader boundary。
2. Gate/import：五个 public 入口全部 fail-closed；false-gate checkpoint 可加载；
   governance import 不加载 Torch。
3. Ledger：M6 `6/44` 历史 prefix、exact whole head、authority/registration/snapshot、第二 journal/
   output、payload mutation、plan/cap、并发、replace fault、receipt crash recovery和 fit-before-receipt。
4. Replay：transfer manifest、canonical inventory、safe extraction、fresh child import、product/run/
   checkpoint/key/score mutation、14 folds、0 fit、ledger unchanged、CUDA/no fallback、legacy receipt
   rejection。
5. M7：current compatibility addendum 与 current status pointer 能机械证明 M7 仍未授权。
6. 新增或实质变更 core code 达到 100% line/branch coverage；任何例外为零。

关键 E2E 仅为 synthetic sealed snapshot→audit-only state、synthetic authority→ledger recovery、
fake archive→launcher/child/outer-validator。真实 M7 fit 和 final-OOS 不在 E2E。

## 9. Ordered implementation plan

1. 实现 lazy import、五入口 Gate 拒绝和 `PanelDataset` schema guard。
2. 实现 `MarketStatePolicyV1/InputBindingV1`、pure deterministic aggregation、synthetic builder/
   validator；不打开真实 snapshot。
3. 实现 ledger head/authority/registration/snapshot/state machine与受控 CLI；只用 temp synthetic
   ledger。
4. 实现 M6 replay input binding、canonical inventory、safe extraction、launcher/child
   invocation和 outer validator；unit/integration 使用 fake archive/checkpoint seams。
5. 写入 M7 compatibility addendum 与准确 `docs/STATUS.md` 指针。
6. 依质量 ledger 顺序完成 red、implementation、green、independent code review 和 synthetic E2E。
7. 只有 M6.5 全部门通过后，才另行决定是否执行一次真实只读 M6 server archival replay；
   本设计/本阶段不执行它。

每一步都没有隐藏研究选择；任何真实 source/PIT、Git object 或 CUDA 前提不满足时结果为
`HOLD/FAIL`，不会由实现者选择替代输入。

## 10. Open decisions

无。非分区 `mkt_adjf` row group 如果无法在物理上隔离 2025+，严格结果就是
`HOLD`；future M7 authority 不存在时严格结果就是不允许 live fit；CUDA 不满足时严格结果就是
replay FAIL。这些都是已定义的证据结果，不是待实现者决定的产品规则。

## 11. Verdict

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。

v23 关闭了 v22 的四类审查缺口，并保持 v28 的最小研究质量架构：没有生产权限控制面，
没有 M7 实证，没有 final-OOS，也没有新增研究语义。只有独立 review 对本文件给出
`PASS` 后，router 才能进入 test-design。
