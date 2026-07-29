# M6.5 有界修复变更设计 v24

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v23 作为 canonical change design；v23 与其 `NEEDS_CHANGES` 审查永久保留。

本设计只建设第七步之前的 M6.5 工程质量地基：T-known state mechanics、安全试验计数
mechanics、M6 checkpoint archival replay mechanics，以及 M7 design-only handoff。
它不创建 M7 derived contract，不实现 CCC/Gate，不运行真实 fit，不增加预算，不访问
2025+ 行情分区，也不形成 Alpha/组合/交易结论。

## 1. 当前事实与验收边界

| 字段 | 当前事实 |
| --- | --- |
| 阶段 | `M6.5-PRE-M7-ENGINEERING-QUALITY / STRICT` |
| M6 | `PASS`，close prefix 为 `6 candidate / 44 fit` |
| M6.5 | `NEEDS_CHANGES` |
| M7 | `NOT_RUN` |
| 最近证据 | v23 两份独立 R3 review 均为 `NEEDS_CHANGES` |
| 下一动作 | v24 独立 R3 design review |
| review 通过前禁止 | test-design、实现、replay、训练、final-OOS |

M6 close hash/count 由 immutable M6 evidence 固定；`14328` bytes 是 verifier 在 JSONL line
boundary 上导出的长度，不声称 gate 原生保存该字节数。

## 2. Scope

### 2.1 必须修复

1. legacy Gate 可从含未来 label/execution 条件的 `market` 路径取 state。
2. state 辅助源的 as-of/非分区读取与第 60 日、status transition、expected calendar 未完全冻结。
3. historical prefix 与 current ledger head 未分离；registration、snapshot、receipt 与 fit launch
   在 crash/retry 下可漏计或复用。
4. raw M6 replay 的 verified paths 可能在 child consumption 前变化，且 runtime/score bytes
   未形成唯一 canonical contract。
5. 旧 M7 v2 review 不是当前 v28/v24 的 gate PASS。

### 2.2 非目标

- 不修改 M3/M5/M6 immutable contract、历史 gate/receipt、JSONL bytes、checkpoint 或 frozen source。
- 不调用/重构 `build_pit_data_product.build_matrix()`。
- 不实现 live M7 run authority、M7 runner/model、CCC、Gate adapter、组合或回测。
- 不恢复 v27 setuid/namespace/cgroup/跨 uid/GPU ACL/服务进程。
- threat model 是受信任 research-server operator 下的误配、崩溃与 cooperative concurrency，
  不防御恶意 root/kernel/native library。

## 3. 方案与边界

| 方案 | 结论 |
| --- | --- |
| DataFrame + free CLI + path hash | 拒绝；不能证明来源、current head 或 consumed bytes |
| v27 privileged control plane | 拒绝；超出 M6.5 与当前 threat model |
| typed immutable artifacts + atomic no-replace publication + existing locks + attempt staging | 采用；每个 finding 有一个可测边界且不新增服务 |

模块方向：

```text
sealed source snapshot
  -> pre-OOS auxiliary slicer + independent verifier
  -> market-state builder/pure primitives
  -> audit-only product

synthetic frozen authority
  -> registration -> journal snapshot -> exact-head reconciliation
  -> one-shot FitLaunchClaim
  -> fake fit observer only

M6 immutable evidence + transfer archive
  -> pre-execution binding
  -> attempt-owned staged bytes
  -> fresh child 14-fold replay
  -> outer receipt validator
```

## 4. 公共 Gate 与 import 边界

修改 `__init__.py`、`config.py`、`cli.py`、`models/peerlite.py`、`data/dataset.py`。

统一错误：`M7MarketStateNotAuthorized`。以下入口对 `market_gate=True` 必须在 dataset read、
journal/output create、checkpoint state load 或 fit 前拒绝：

| 入口 | false | true |
| --- | --- | --- |
| `ExperimentConfig` | 兼容 | config validation 拒绝 |
| CLI | 兼容 | parse 后、side effect 前拒绝 |
| `PeerLiteModel` | 兼容 | constructor 拒绝 |
| `PeerLiteNetwork` | 兼容 | constructor 拒绝 |
| `PeerLiteModel.load_checkpoint()` | M6 false checkpoint 可加载 | config 含 true 时拒绝 |

package root 使用 lazy `__getattr__` 暴露 `PeerLiteModel/PeerLiteNetwork`；治理/数据 import 不加载
Torch。legacy Qlib `feature/label/market` 三组不改。

`PanelDataset.market_state_columns` 为空时兼容；非空时必须严格等于固定顺序
`DAILY_STATE_COLUMNS`，列存在且与 feature/label/market 完全不相交。该 schema guard 不授权
模型读取 state。

## 5. State data product

### 5.1 冻结身份

`MarketStatePolicyV2` 绑定：

- research contract file SHA
  `2f99bfb56929c732b24efe5da25c6c9d2786773ce95af347099228a521a9502c`
  与 canonical hash
  `5b7353756e0fded36622a6946011f77a99706ec82a9685cb2dd3c03bba37002d`；
- feature spec SHA
  `b35da580ff710f7ca61f174d9f810f327942d190869ed422526e722eaeead12e`；
- `features.py` SHA
  `0de3b798e8f49032bb04c58507ab471591e167013d58ea9f3f86e62308b47ef0`；
- 六个 source manifest exact SHA（与 v23 §3.2 相同）；
- adapter policy、slicer、builder、pure state implementation各自的 file/content hash。

日期：

```text
timezone                = Asia/Shanghai
support_start           = 2011-09-01 inclusive
output_start            = 2012-01-01 inclusive bound
output_end              = 2025-01-01 exclusive
expected_output_dates   = equal XSHG/XSHE open-session set within output bounds
windows                 = [5, 10, 20, 60]
corporate_action_mask   = trailing 60 instrument observations
aggregation dtype       = float64
empty expected day      = FAIL
```

`2012-01-01` 不是强行输出一行；实际第一行是 expected open-session set 中第一个日期。

### 5.2 PreOOSAuxSnapshotV1：唯一辅助源成功路径

新增：

- `src/qlib_peerlite/data/pre_oos_aux.py`
- `scripts/server/build_pre_oos_aux_snapshot.py`
- `scripts/server/verify_pre_oos_aux_snapshot.py`

state builder 不直接打开原始五个非行情单文件。独立 slicer 从已验证 sealed snapshot读取固定
列，通过 PyArrow dataset filter 将 delivered rows 限于 cutoff 规则，先写一个新的
`PreOOSAuxSnapshotV1`。这一步是 PIT sanitization，不计算 label、return、model、metric 或
组合；它不打开 `mkt_equd_2025/2026`。

原文件可能含 cutoff 后辅助事件，manifest 必须诚实记录
`source_file_may_contain_post_cutoff=true`；本项目的“final-OOS market partitions opened=false”
专指 outcome-bearing `mkt_equd_2025/2026` 物理分区。辅助源 PIT 安全由**净化后的输出、
独立 as-of verifier 与 future-poison**证明，不伪称源文件没有未来记录。

派生规则：

| source | slicer output |
| --- | --- |
| `idx_cons_core` | 保留 entry 两时钟均 `< cutoff` 的 CSI300/500 rows；exit 两时钟均 `< cutoff` 才保留，否则两者都置 null；一有一无则保留已知值并标 `exit_clock_incomplete=true` |
| `md_security` | `list_date < cutoff`；`delist_date >= cutoff` 置 null；只保留 XSHG/XSHE equity |
| `md_trade_cal` | 只保留 `calendar_date < cutoff` 的 XSHG/XSHE rows |
| `equ_inst_sstate` | 只保留 `max(publish_date, eff_date) < cutoff`；单时钟缺失且另一时钟 `< cutoff` 的 row 保留并标 unknown |
| `mkt_adjf` | 只保留 `ex_div_date in [support_start, cutoff)`；只输出 security_id/ex_div_date |

slicer output 不包含原始 `id/update_time/ticker` 等非必要列。每个 output file 有 unique key、
schema、rows、min/max clocks、SHA；`max effective delivered clock < cutoff`。输出 root 使用
§8 的 crash-atomic directory publication，状态先为 `BUILT_NOT_VERIFIED`。

独立 verifier：

1. 重新验证原 snapshot/manifest hash、slicer code/policy hash；
2. 验 output schema/key/date/null sanitization；
3. 对每个 source 执行 predetermined future poison：在 cutoff 后追加/改变 entry/exit/status/
   calendar/action rows，或改变被置 null 的 cutoff 后字段；重建后所有 protected
   `[2012-01-01, cutoff)` auxiliary output bytes必须完全相同；
4. 产生独立 `PreOOSAuxVerificationV1 PASS`，builder 只接受 exact-bound PASS。

builder 不能自签该 verification receipt。

### 5.3 MarketStateSourceAdapterPolicyV2

#### Calendar

- columns：`calendar_date, exchange_cd, is_open`；
- date normalize 到 timezone-naive midnight；
- 分别选择 XSHG/XSHE、`is_open == 1`；
- 两集合必须完全相同，否则 FAIL；
- support/output expected dates都从该集合产生；
- duplicate exact rows dedup；同 key 冲突 FAIL。

#### Membership

columns：
`index_security_id, constituent_security_id, into_pub_date, into_eff_date,
out_pub_date, out_eff_date, exit_clock_incomplete`。

- index IDs 固定 `1782/2103`，最终 universe 为两者并集；
- entry 两时钟均非 null；known entry time=`max(into_pub, into_eff)`；
- T eligible 需 `T >= known_entry_time`；
- exit 两时钟都有值时 known exit time=`max(out_pub, out_eff)`，`T >= known_exit_time`
  后该 interval 失效；
- 两个 exit clock 都 null 表示 pre-OOS 内无已知退出；
- `exit_clock_incomplete=true` 时，从唯一已知 exit clock 起该 interval 为 unknown并排除；
- exact duplicate interval dedup；同 index/security/entry key 的非相同 interval FAIL；
- 多个互不冲突 interval按 union；同一 security 同日只输出一个 universe bool。

#### Security master / listing

- columns：`security_id, exchange_cd, asset_class, list_date, delist_date`；
- asset_class=`E` 且 XSHG/XSHE；
- security_id/list_date 必须非 null；exact duplicate dedup，冲突 FAIL；
- first open session `>= list_date` 计 session 1；T 为第 60 个已完成 open session时
  `listing_age_eligible=true`；
- `delist_date` 非 null且 `T >= delist_date` 时排除；
- T 缺 quote 计 `missing_quote_count` 并 `is_active=false`。

#### Special status

- columns：
  `security_id, sec_short_name, party_state, publish_date, eff_date, clock_incomplete`；
- 两时钟完整时 known time=`max(publish_date, eff_date)`；
- 单时钟缺失时，从唯一已知时钟起 `special_status_unknown=true`，直到下一个完整事件；
- 两时钟都缺失的 row FAIL；
- forbidden 仅由
  `upper(sec_short_name)` regex `(?:^|\\*)ST|PT|退` 决定；
  `party_state` 只进入 audit digest，不另猜 vendor code；
- 每个 security按 `(known_time, publish_date, eff_date)` 排序；exact duplicate dedup；
  同 known_time 但状态/名称冲突 FAIL；
- 完整事件状态持续到下一完整/unknown事件；无历史事件默认 not forbidden/not unknown。

#### Quote / action / feature

- quote raw mapping与 v23 相同；`open/high/low/close > 0`、`volume/amount >= 0`，
  turnover finite；duplicate security/date FAIL；
- action是 `(security_id, ex_div_date)` exact membership，不使用 adjustment factor；
- 在完整 support quote panel上、任何 universe/status/state筛选前调用：

  `build_causal_daily_features(... windows=(5,10,20,60),
  corporate_action_column="corporate_action", mask_lookback_sessions=60)`；

- 只取 `ret_mean_20, ret_std_20, ret_1d, turnover_mean_20, feature_eligible`；
- state population再应用 membership/listing/active/status/price/mask/finiteness。

### 5.4 四个 daily state

canonical sort `(datetime,instrument)`；source 强制 float64：

```text
mkt_trend_20    = mean(ret_mean_20)
mkt_vol_20      = median(ret_std_20)
mkt_breadth_1d  = count(ret_1d > 0) / population_count
mkt_turnover_20 = median(turnover_mean_20)
```

偶数 median 为两中值 float64 mean；NaN/Inf 禁止隐式 drop。每日 population 非空。

产品仍为 `population.parquet、daily_state.parquet、daily_population_audit.parquet、
market_state_manifest.json`。状态初始
`INTEGRITY_BUILT_NOT_PIT_QUALIFIED`；audit loader可读，model loader需未来独立 PIT PASS，
M6.5 不提供 model capability。

## 6. Trial ledger mechanics

修改 `governance.trial_ledger` 和受控 CLI；M6.5 的公开行为只允许
`purpose=M6_5_SYNTHETIC_TEST_ONLY`。任何 `purpose=LIVE/M7` 都抛
`LiveRunAuthorityNotFrozen`，因为 fixed live slot
`contracts/immutable/m7_execution_authority_v1.json` 当前不存在。M6.5 不创建它。

### 6.1 Immutable objects

- `LedgerPrefixBinding`：只读 M6 historical prefix。
- `LedgerHeadBindingV1`：整个 ledger的 relative path、bytes、SHA、record/candidate/fit counts。
- `SyntheticRunAuthorityV1`：test-only family/spec/caps/ordered event plan/M6 prefix。
- `RunRegistrationV1`：authority hash、run_id、H0、唯一 journal/output/receipt paths、plan hash。
- `JournalSnapshotV1`：registration、seq、previous snapshot、完整 journal prefix bytes/hash、
  ordered source event/full hashes、expected head。
- `ReconciliationReceiptV1`：registration/snapshot/H_before/H_after/appended IDs/counts。
- `FitLaunchClaimV1`：registration/snapshot/receipt/source event/fit_attempt_id，表示该 attempt
  已永久消费。
- `RunTerminalV1`：`CLOSED` 或 `ABANDONED`、last receipt/head、remaining plan IDs和 reason。

event plan 对每个 attempt 固定 `event_seq,type,evaluation_id,model_id,seed`，fit 再固定
`fit_id,fold_id,fit_attempt_id`。retry 必须是 plan 中另一个 attempt ID并重新计数。

### 6.2 Global run index

在 authority root 的固定 `run-index/sha256(run_id).json` 下维护
`run_id -> registration_sha256`。registration issuer在同一 registry lock中使用 §8
atomic no-replace publish；相同 registration idempotent，第二 registration/hash/path拒绝。

### 6.3 状态机

```text
AUTHORITY_VERIFIED
 -> REGISTRATION_INDEXED(R,H0)
 -> SNAPSHOT(S1,H0)
 -> RECONCILED(S1,H0->H1) + RECEIPT
 -> FIT_LAUNCH_CLAIM(source event)       # one shot, durable before fit
 -> fake fit observer in M6.5 only
 -> next snapshot only if current head == prior H_after
 -> CLOSED
```

首次 reconciliation 在 ledger lock 内验证 authority/registration/snapshot raw hash、M6 prefix、
current whole head、plan、journal、semantic uniqueness和 caps，一次 replacement追加
`RUN_REGISTERED` + counted records。S2+ 不再注册 run。

claim 规则：

- receipt覆盖 source event后才可 publish claim；
- claim publish成功即视为 fit attempt 已启动，即使进程在真正进入 fit 前崩溃也不允许复用；
- 已有同 source event claim：永远不再次放行；
- retry使用新的 registered/counted attempt ID。

tail规则：

- active cooperative run lease 内不允许另一 run；
- crash释放 lease后若 current head已超过旧 run receipt H_after，旧 run必须 no-replace发布
  `ABANDONED`；不得 rebase或创建 S2；
- 已 claim attempt保持已消费；未 claim的 remaining plan不执行；
- future continuation必须用新 run_id及 authority预先允许的 remaining/retry attempt IDs。

replacement后 receipt前崩溃时，recovery只识别 exact R/S batch并复算历史 H_after；若后有合法
tail仍可补 receipt，但旧 run立即 `ABANDONED`。任何未知/不精确 batch失败。

## 7. M6 archival replay

### 7.1 Frozen inputs

`M6ReplayInputBindingV2` pre-execution、no-replace，绑定：

- immutable M6 gate/spec/run/verification/environment/ledger prefix；
- environment file SHA
  `e4e6168405cc34ae20c21f8f883a326b8d4508115495b7a1a13460ba1659d870`；
- transfer manifest SHA
  `104740de8bb55b9ec07706f836e764cd40c45931516e43ab361de74861c6bd2c`；
- archive bytes `664406` 与 SHA
  `d49a15fd5f90fb9bafac19052b826657f81be1c51295ef21b172a1fd80420a1d`；
- product/run/checkpoint/prediction/fold identities；
- issuer/launcher/raw-worker/outer-validator hashes；
- expected `14 replay, 0 fit, ledger unchanged, max date < cutoff, cuda only`。

historical transfer tree hash保留为声明，不作为新 inventory算法。

### 7.2 RuntimeBindingV1

从 M6 `environment.json` 冻结并在 checkpoint load前严格比较：

```text
machine=x86_64
python version=3.11.14
torch=2.7.1+cu126
torch CUDA=12.6
numpy=2.4.6
pandas=2.3.3
pyarrow=22.0.0
qlib=0.9.7
cuda_available=true
CUBLAS_WORKSPACE_CONFIG=:4096:8
deterministic_algorithms=true/warn_only=false
cudnn_benchmark=false/cudnn_deterministic=true
```

kernel string只记录不比较。issuer还记录 current `sys.executable` resolved path、regular-file
SHA、Python module origins、CUDA device name/capability、driver和 cuDNN version；child必须与
同一 pre-execution binding完全相同。历史缺少的 driver/cuDNN值不作“与 M6 相同”声明，但在
issuer→child之间必须稳定。最终历史兼容判据仍是 14 fold exact scores。

### 7.3 Attempt-owned staging

launcher只接收 pre-execution binding和不存在的 attempt root。它不让 child重新打开原路径：

1. 对 archive、raw worker、product manifest/data、run manifest/predictions/checkpoints、
   historical verification与只读 ledger snapshot逐文件执行 `copy_and_hash`；
2. source用 `O_NOFOLLOW` 打开，copy前后 `fstat(dev,ino,size,mtime_ns)` 必须相同；
3. copy bytes边读边 hash并与 binding expected hash比较，fsync后用 §8 no-replace发布到
   attempt `staging/`；
4. child所有输入只能解析在 staging root 内；原路径随后变化不影响消费；
5. frozen source archive在 staging内安全解压，拒绝 absolute/`..`/duplicate/link/device/FIFO/
   socket/setuid/setgid，只有单一 top directory；
6. `CanonicalTreeInventoryV2` items只有
   `{relative_path, byte_length, sha256}`，按 UTF-8 POSIX path bytes升序；不含 mode字段。

若 staging容量不足或任何 source在copy时变化，attempt FAIL，无 PASS。

### 7.4 Child 与 canonical score

`RawReplayInvocationV2` 绑定 staging inventory、RuntimeBinding、raw worker、device和 exact argv。
child argv：

```text
<bound sys.executable> -I -B <staged raw worker> --invocation <staged invocation>
```

child启动后再次验证 executable/runtime/module origin，并只从 staged extracted `src` import。

每 fold expected/replay Series 均：

1. datetime timezone-naive normalize；
2. instrument canonical string；
3. unique key后按 `(datetime,instrument)` stable ascending；
4. score转 NumPy float64 native values，要求 finite；
5. equality使用相同 key index和 `np.array_equal(float64 arrays)`；
6. key digest逐行写 `timestamp.isoformat UTF-8 + 0x1f + instrument UTF-8 + \\n`；
7. score digest逐行写同 key、再 `0x1f + float(value).hex() ASCII + \\n`。

这正是 frozen raw verifier现有 digest语义，v24将其提升为明确 contract。

outer v2 receipt绑定 input/runtime/staging/extracted tree/invocation/raw receipt/14 folds/
ledger before-after。独立 outer validator重新复算；legacy receipt不能关闭 M6.5。

## 8. Crash-atomic no-replace publication

新增一个低层 stdlib helper，供 registration/snapshot/receipt/claim/binding/invocation复用：

```text
atomic_publish_file_no_replace(final, bytes):
  write private same-directory temp -> fsync
  os.link(temp, final)                # atomic, fails EEXIST
  fsync(parent)
  unlink(temp)
```

final永远不会出现 partial bytes；现有 final bytes全同则 idempotent，否则 FAIL。hardlink不支持或
跨文件系统则 fail closed，无 overwrite fallback。

目录产品：

1. `mkdir(final)` 原子取得 no-replace namespace；
2. fully written temp files逐一以上述 hardlink方式发布；
3. 最后发布 `PUBLISH_COMPLETE.json`，loader在 marker前永不读取目录；
4. crash recovery以 marker中的 exact inventory恢复缺失 links；冲突文件 quarantine并 FAIL；
5. final已被另一 publisher claim则不覆盖。

这解决 O_EXCL直接写 partial receipt和 rename overwrite窗口，不需要服务或特权。

## 9. Failure / compatibility / rollback

| 失败 | 结果 |
| --- | --- |
| auxiliary slice/as-of/poison 不符 | state HOLD；不产生 model-capable input |
| mkt_equd 2025/2026 被请求 | value read前 FAIL |
| empty/nonfinite state | FAIL并保留 audit |
| Gate true | side-effect前稳定拒绝 |
| live authority | M6.5 一律 `LiveRunAuthorityNotFrozen` |
| stale head/plan/cap/index conflict | ledger零字节变化 |
| claim后 crash | attempt已计数，不能复用 |
| post-crash later tail | old run `ABANDONED`，不得继续 |
| replay source copy期间变化/runtime mismatch | no PASS |
| CUDA unavailable/score mismatch | FAIL，无 CPU fallback |

M5/M6 no-gate config/checkpoint/Qlib groups、M6 static verifier、historical prefix APIs保持兼容。
rollback只移除新增 live code和M6.5 attempt namespace，不修改历史证据；M7继续 `NOT_RUN`。

## 10. Verification obligations

交给后续 `eng-design-tests` 细化：

1. 五 Gate入口、lazy import、false checkpoint兼容。
2. aux slicer逐源 schema/null/cutoff/future poison、独立 verifier、builder只能读 verified slice。
3. exact calendar/第60日/entry-exit/status tie/unknown/quote/action/60-mask/四公式/canonical order。
4. file/directory no-replace在partial write、EEXIST、crash/recovery、concurrent publisher下的行为。
5. M6 prefix/current head、run index、registration/snapshot、receipt recovery、one-shot claim、
   claim前/后/fit中 crash、post-tail ABANDONED。
6. replay staging copy TOCTOU、safe extraction、runtime/module origin、score bytes、14/0/unchanged和
   legacy receipt rejection。
7. 新增/实质修改 core code 100% line/branch coverage，无例外。

E2E仅使用 synthetic snapshot/authority/archive与fake child；不运行 M7 fit或final-OOS。

## 11. Ordered implementation

1. import/Gate/PanelDataset guard。
2. atomic no-replace helper与故障测试。
3. aux slicer/verifier、source adapter、state product pure/build/verify。
4. synthetic-only authority、run index、snapshot/reconcile、one-shot claim和terminal state。
5. replay binding/runtime/staging/child/outer validator。
6. M7 compatibility pointer。
7. 依 router完成 test-design、expected-red、implementation、green/coverage、independent
   code-review、synthetic E2E。

## 12. Open decisions 与 verdict

无。辅助源可以被净化但 verifier失败时结果为 `HOLD`；live authority不存在时结果为拒绝；
runtime不匹配时 replay失败。这些是固定证据结果，不留给实现者选择替代方案。

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。v24关闭 v23 的一次性 fit、source adapter/
pre-OOS success path、authority anchor/run index、crash-atomic publication、post-tail终态以及
replay consumed-bytes/runtime/canonical-score缺口，同时保持 v28 的有界单仓库架构和 M7禁入线。
