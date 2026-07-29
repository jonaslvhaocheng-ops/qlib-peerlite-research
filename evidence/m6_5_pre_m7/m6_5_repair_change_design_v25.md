# M6.5 有界修复变更设计 v25

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v24 作为唯一 canonical change design；v24 及其失败审查永久保留。

本设计只建设第七步前的工程质量地基：T-known market state、crash-safe trial-ledger
mechanics、M6 checkpoint archival replay，以及当前 M7 design-only 工件。它不创建 live M7
authority/derived contract，不运行真实 fit，不改变预算，不访问 final-OOS。

## 1. 当前事实和完成定义

| 项目 | 当前事实 |
| --- | --- |
| M6 | `PASS`；唯一 close prefix `6 candidate / 44 fit` |
| M6.5 | `NEEDS_CHANGES` |
| M7 | `NOT_RUN` |
| 当前阻断 | v24 独立审查：5 个合并 P1、3 个独立 P2 concern |
| v25 下一动作 | 对 v25 + M7 v3 + test matrix v3 做新的独立 R3 review |
| review PASS 前 | 禁止 test-design、实现、replay、训练、预算、final-OOS |

M6.5 最终完成必须同时具备：

1. 当前 bundle 的独立 design review PASS；
2. reviewed test design、expected-red、implementation、green/coverage；
3. independent code review 关闭 P0/P1/P2；
4. synthetic E2E；
5. 新 M6 read-only 14-fold archival replay PASS；
6. 当前 M7 v3 的独立 design-review artifact；
7. M6.5 gate receipt。

## 2. Scope 与依赖边界

新增/修改边界保持 v28：

```text
sealed sources
  -> pre-OOS auxiliary slicer + independent verifier
  -> pure market-state primitives + audit-only product

synthetic authority
  -> global control lock -> register/snapshot/reconcile
  -> canonical one-shot claim -> fake observer only

M6 immutable evidence + transfer archive + trusted runtime policy
  -> prepared attempt staging -> seal
  -> fresh child 14-fold replay
  -> outer receipt validator

frozen contract + M6 close
  -> M7 v3 design-only + behavior-to-test matrix
```

Library data/governance modules不 import scripts；治理/数据 import不加载 Torch。hostile root、
kernel、恶意同 uid进程和 native injection 不在范围内；目标是受信任 operator下的误配、
crash、retry 与 cooperative concurrency。

## 3. 公共 Gate 和兼容

统一错误 `M7MarketStateNotAuthorized`。`ExperimentConfig`、CLI、`PeerLiteModel`、
`PeerLiteNetwork`、`PeerLiteModel.load_checkpoint()` 五个入口在
`market_gate=True` 时必须在 dataset read、journal/output create、checkpoint state load 或
fit 前拒绝。M6 false-gate config/checkpoint保持兼容。

package root以 lazy `__getattr__` 暴露模型类；治理/数据路径不能隐式加载 Torch。
`PanelDataset.market_state_columns` 为空兼容；非空必须严格等于固定
`DAILY_STATE_COLUMNS`，列存在且与 feature/label/legacy market不相交。这个 schema guard不
授予模型消费 state 的能力。

## 4. PreOOSAuxSnapshotV2

### 4.1 身份、日期和输入

`MarketStatePolicyV3` 绑定冻结 research contract、feature spec、`features.py`、六个 source
manifest、adapter/slicer/builder/pure-state code hash。

```text
timezone              = Asia/Shanghai
support_start         = 2011-09-01 inclusive
output_start          = 2012-01-01 inclusive bound
cutoff C              = 2025-01-01 exclusive
expected dates        = equal XSHG/XSHE open sessions
windows               = [5,10,20,60]
action mask           = trailing 60 instrument observations
aggregation dtype     = float64
empty expected day    = FAIL
```

state builder 只能读取 verified `PreOOSAuxSnapshotV2`，不能直接读取五个原始非行情单文件；
不能打开 `mkt_equd_2025/2026`。

所有 date clock先规范为 timezone-naive date。`pre(C,x)` 表示 `x != null and x < C`。

### 4.2 Membership exit 真值表

entry 的 pub/eff必须都 `pre(C, x)`，否则该 interval 不输出。exit 对原始
`out_pub/out_eff` 分别应用：

| pub pre-C | eff pre-C | sanitized pub/eff | incomplete | T-known 语义 |
| --- | --- | --- | --- | --- |
| 0 | 0 | null/null | false | pre-OOS 无已知退出 |
| 1 | 0 | pub/null | true | 从 pub 起 unknown并排除 |
| 0 | 1 | null/eff | true | 从 eff 起 unknown并排除 |
| 1 | 1 | pub/eff | false | 从 max(pub,eff) 起退出 |

这里“0”统一涵盖 source null 或 `>= C`；因此一个 pre-C、一个 post-C 精确落入 incomplete，
不存在 v24 的冲突。两个都 post-C或 null时 logical output都为 null/null。exact duplicate
dedup；相同 index/security/entry key 的非相同 interval FAIL。index固定 `1782/2103`，
interval union后同一 security/day只产生一个 universe bool。

### 4.3 其余 source 的完整规则

**Security master**

- 输出 `security_id,exchange_cd,asset_class,list_date,delist_date`；
- `security_id/list_date` 非 null，asset `E`，exchange XSHG/XSHE，`list_date < C`；
- `delist_date >= C` 置 null，pre-C 保留；exact duplicate dedup，key conflict FAIL；
- first open session `>= list_date` 是 session 1；第 60 个完成 session起 eligible；
- T 缺 quote时 `missing_quote_count += 1` 且 inactive。

**Calendar**

- 只输出 `calendar_date,exchange_cd,is_open` 且 date `< C`；
- XSHG/XSHE open-session集合完全相等，否则 FAIL；
- exact duplicate dedup，同 exchange/date冲突 FAIL。

**Special status clock 真值表**

| publish pre-C | effective pre-C | output | event |
| --- | --- | --- | --- |
| 0 | 0 | 不输出 | pre-OOS 不可得 |
| 1 | 0 | publish/null | UNKNOWN transition |
| 0 | 1 | null/effective | UNKNOWN transition |
| 1 | 1 | publish/effective | COMPLETE at max(clock) |

同 `security_id,known_time` 先分组，再按以下唯一 precedence合并：

1. exact canonical duplicate dedup；
2. 组内任一 UNKNOWN，则整组输出一个 UNKNOWN transition，complete不覆盖 unknown；
3. 全部 complete且规范化 `sec_short_name/forbidden` 相同，合为一个；
4. 全部 complete但名称或 forbidden冲突则 FAIL。

因此 null不参与全局排序歧义；组间只按
`(security_id,known_time,event_kind)`，其中同组已唯一。UNKNOWN 从 known_time起排除，直到
下一 complete/unknown transition。forbidden仅由
`upper(NFC(sec_short_name))` regex `(?:^|\\*)ST|PT|退` 决定；`party_state` 只进入 audit
payload。

**Corporate action**

- 唯一列/键为 `security_id:string, ex_div_date:date32`；
- 任一 null FAIL；只保留 `[support_start,C)`；
- exact duplicate dedup，按 UTF-8 security ID bytes、date升序；
- 不读取 adjustment factor。

### 4.4 Canonical logical payload 与 physical writer

每个 auxiliary table有固定 Arrow schema、列顺序和 primary key。protected oracle不是整个
provenance directory或任意 Parquet bytes，而是 canonical logical JSONL：

- 行先按表的 primary key稳定升序；
- string为 Unicode NFC、不得隐式 trim/case fold（规则明确要求的字段除外）；
- date为 `YYYY-MM-DD`；boolean为 JSON `true/false`；null为 JSON `null`；
- object keys按固定 schema列顺序写出，无空格 UTF-8，单个 `\n` 结尾；
- `logical_sha256` 对完整 bytes计算。

Parquet只是 transport；单次 build manifest仍绑定 file SHA。writer固定为 PyArrow 22、
`use_dictionary=false, compression=zstd, compression_level=3, write_statistics=true,
data_page_version=1.0, row_group_size=65536`。future-poison PASS比较每个 protected table的
schema、row count、key digest和 `logical_sha256`，不要求 provenance manifest或Parquet
metadata相同。

original 与 poison run各自绑定 source identity、mutation ledger、code/env。mutation集合固定
为 cutoff后 entry/exit/status/calendar/action新增/修改，以及已被 sanitization 置 null的
post-cutoff clock修改；受保护 pre-C logical payload必须完全相同。independent verifier重新
计算，不接受 builder自签。

### 4.5 Market state

quote/action/feature仍在完整 support quote panel上、universe/status筛选前计算固定50因果
features；state population随后应用 membership、listing、active、status、price、action mask
和 finiteness。

canonical `(datetime,instrument)`排序后：

```text
mkt_trend_20    = mean(ret_mean_20)
mkt_vol_20      = median(ret_std_20)
mkt_breadth_1d  = count(ret_1d > 0) / population_count
mkt_turnover_20 = median(turnover_mean_20)
```

偶数 median是两中值 float64 mean；禁止隐式 drop NaN/Inf；每日 population非空。产品初始
`INTEGRITY_BUILT_NOT_PIT_QUALIFIED`，audit loader可读、model loader拒绝。

## 5. Crash-atomic publication

### 5.1 单文件

```text
write same-parent private temp
fsync(temp)
link(temp, final)       # atomic no-replace
fsync(parent)
unlink(temp)
```

API 返回 `CREATED` 或 `ALREADY_EXISTS_IDENTICAL`；bytes不同返回 conflict。hardlink不支持或
跨文件系统时 fail-closed，无 overwrite fallback。

### 5.2 PreparedDirectoryTransactionV1

每个 target有固定 sibling：

```text
.<target>.publish.lock
.<target>.PREPARED.json
<target>/
<target>/PUBLISH_COMPLETE.json
```

prepared claim在任何 final payload前发布，包含：

- target relative path、schema version、content/publisher UUID；
- 完整 expected inventory `{relative_path,byte_length,sha256}`；
- canonical logical digests；
- private staging relative path及其 inventory；
- policy/code identity。

事务在固定 parent publish lock下执行：

1. 若 complete存在，重新验证 prepared + full final inventory；相同返回 existing-complete；
2. prepared不存在则 no-replace发布；存在且bytes不同则 conflict；
3. 相同 prepared的 retry可重建 private staging，但重建后必须与 expected inventory完全一致；
4. `mkdir(final)`；逐文件 hardlink，已存在文件必须 hash/size相同；
5. fsync files/final dir，最后 no-replace发布 completion marker并 fsync；
6. loader只有在 prepared、completion、full inventory三者一致时可读。

crash释放 OS lock；任何进程只能在取得同一 lock后恢复相同 claim。不同 claim、冲突 payload
或遗失且不可重建的 staging一律 HOLD；不自动删除、覆盖或 quarantine final。这样没有 lease、
PID 猜测或 marker-before-inventory悖论。

## 6. Trial-ledger 与一次性 fit

M6.5公开 authority只有 `M6_5_SYNTHETIC_TEST_ONLY`。固定 live slot
`contracts/immutable/m7_execution_authority_v1.json` 不存在，所以 LIVE/M7必须抛
`LiveRunAuthorityNotFrozen`。

### 6.1 唯一对象与锁

- historical `LedgerPrefixBinding`只读；
- `LedgerHeadBindingV1`绑定 current whole ledger；
- synthetic authority绑定 family/spec/caps/ordered fake event plan/M6 prefix；
- global run index：`run-index/sha256(run_id).json`；
- canonical claim slot：
  `fit-claims/sha256(registration_sha256 + 0x1f + source_event_id).json`；
- terminal slot：`terminals/sha256(registration_sha256).json`。

source event已包含固定 `fit_attempt_id`；retry必须是 event plan中的另一 event/attempt。
所有 register/reconcile/claim/terminal决策使用 authority root固定 global control lock；若
另有 ledger file lock，锁顺序永远是 `global control -> ledger`，任何 writer不得逆序。

### 6.2 原子决策流程

在同一锁域：

1. 验 authority、registration/index、snapshot、M6 prefix、plan、caps；
2. 验 current whole head H、exact journal batch和 semantic uniqueness；
3. 若 batch尚未追加，单次 append+fsync生成 H_after；若已存在则精确恢复 H_after；
4. 发布/核对 receipt；
5. 对 source event重新读取 current head、terminal和 canonical claim slot：
   - `current == H_after`、无 terminal、无 claim：publish claim；
   - claim publish返回 `CREATED`：锁释放后仅放行一次 fake observer；
   - `ALREADY_EXISTS_IDENTICAL`：返回 already-consumed，绝不放行 observer；
   - `current > H_after`：no-replace发布 `ABANDONED`，不创建 claim；
   - 非前缀、冲突 bytes、未知 batch：FAIL。

若在 receipt后 claim前 crash，后来没有 tail时retry可 fresh-create claim；若 later tail先进入，
retry必看到 head推进并 ABANDONED。若在 claim后 crash，existing claim只返回 consumed。
因此没有 receipt-only stale-tail放行窗口，也没有 pathname任选造成的双 claim。

`CLOSED` 仅在计划事件全部有 receipt/claim/observer terminal evidence且 current head精确匹配
时发布。ABANDONED remaining events不执行，future continuation必须新 run ID和预注册新
attempt IDs。

## 7. M6 archival replay

### 7.1 TrustedM6RuntimePolicyV1

actual replay在固定路径
`contracts/immutable/m6_replay_runtime_policy_v1.json` 不存在时一律拒绝。它必须在 replay
issuer之前由独立 runtime-policy builder + reviewer创建，并绑定：

- M6 `environment.json` exact SHA及其
  x86_64/Python 3.11.14/torch 2.7.1+cu126/CUDA 12.6/numpy 2.4.6/pandas 2.3.3/
  pyarrow 22.0.0/qlib 0.9.7/determinism；
- resolved Python executable path、regular-file SHA；
- `importlib.metadata` 对上述 distributions的 name/version与所有 RECORD file path/hash；
- named module origins与file SHA；
- import preflight后加载的 Python/shared-object path/hash closure；
- CUDA device、driver、cuDNN和 CUBLAS policy；
- builder/reviewer identity与 immutable policy SHA。

历史 M6 未记录的 driver/cuDNN不声称“历史相同”，但 policy→issuer→child必须一致，14-fold
exact score是最终功能兼容判据。replay issuer只能读取固定 policy，不能生成或改写它。

### 7.2 Input binding 与 prepared staging

`M6ReplayInputBindingV3` 在执行前绑定 M6 gate/spec/run/verification/environment/ledger prefix、
transfer archive、product/run/checkpoints/predictions、raw worker、launcher/validator、
TrustedRuntimePolicy及 expected `14 replay / 0 fit / ledger unchanged / max date<C / CUDA only`。

attempt root按 §5.2 prepared transaction创建。复制 source时 `O_NOFOLLOW` 打开，前后
`fstat(dev,ino,size,mtime_ns)`一致，stream hash与binding一致；safe extraction拒绝
absolute、`..`、duplicate、links、devices、FIFO/socket/setuid/setgid且只允许单 top directory。

### 7.3 Staging seal 和消费边界

1. 在 attempt lock下完成全部 payload；
2. 从 staging root directory FD以 no-follow重新遍历，计算
   `{relative_path,byte_length,sha256}`；
3. 写 `STAGING_SEALED.json`（其 inventory不自含 seal file）并 fsync；
4. files chmod `0440`，directories bottom-up chmod `0550`，再 fsync directories；
5. 重新打开 root dir FD，复算 payload inventory并与 seal/binding比较；
6. child启动前再核对 seal；child只从 sealed tree解析 input/import；
7. child退出后outer validator再复算 inventory，任何变化均 FAIL。

同 uid 的恶意进程可 chmod 回写不在 threat model内；在 cooperative process边界，attempt
lock、只读 modes、pre/post recheck与child不写输入共同限定 measured/consumed bytes。文档不
把它宣称为 hostile same-uid immutability。

### 7.4 Child 与 score

child使用 trusted policy中的 exact executable：

```text
<trusted-python> -I -B <staged-worker> --invocation <staged-invocation>
```

启动后验证 runtime policy、distribution closure、module origins/hashes和CUDA设置。每 fold
expected/replay Series normalize date、instrument、unique key、stable sort、finite native
float64；key digest与score digest沿用 frozen raw verifier的分隔符和 `float.hex()` 语义；
`np.array_equal`要求 exact score。outer receipt绑定所有 input/runtime/staging/raw/fold/
ledger before-after证据；legacy receipt不能关闭 M6.5。

## 8. 当前 M7 design-only 工件

本 bundle明确绑定：

- `m7_change_design_v3.md`
  SHA256 `b6f32870efe5251d2e846c176d5e7af4ea21e845cfee07b6e2bc528ec4d2a102`；
- `m7_behavior_to_test_matrix_v3.md`
  SHA256 `457af49e177600c9e180867b65e47dee037998c8f3813d3784a9acdc392c1d93`。

v3只允许未来两个隔离候选，共2 candidate/16 fit，使 current cap到 `8/60`；组合、额外 seeds、
确认和M8 refit全部要求未来单独预算 CR。M6.5 的独立 design review必须把这两个文件作为
subject，并另产出专门的 `m7_design_review_v3` artifact。该 review也不授权M7。

## 9. Verification obligations

后续 test-design必须至少覆盖：

1. 五 Gate入口、lazy import、false checkpoint与dataset schema guard；
2. 每个 auxiliary clock真值表、same-time precedence、canonical logical oracle、poison；
3. prepared directory在每个 crash point、same/different claim、concurrent retry下的状态；
4. M6 prefix/current head、run index、canonical claim、CREATED/EXISTS、receipt/claim/tail crash；
5. runtime policy substitution/closure、staging copy TOCTOU、seal/mode/pre-post mutation；
6. safe extraction、score canonical bytes、14/0/unchanged、legacy receipt rejection；
7. M7 v3矩阵的 contract/synthetic behavior；无 production M7实现；
8. 新增/实质修改核心 code line/branch coverage 100%，无静默例外。

E2E只用 synthetic source/authority/archive/fake child，直到独立 code review PASS；actual M6
replay是之后单独绑定的只读 acceptance，不含 fit或 final-OOS。

## 10. 顺序、失败与 verdict

顺序：

1. 独立审查 v25 + M7 v3 bundle；
2. review PASS后 test-design与expected-red；
3. Gate/import、atomic publication、aux/state、synthetic ledger、replay实现；
4. green/coverage、独立 code review、synthetic E2E；
5. trusted runtime policy review与actual M6 read-only replay；
6. M6.5 gate；仍不自动进入M7。

任一不匹配都 fail-closed并保留 evidence；不修改历史M6 bytes，不用增加复杂度补救。

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。v25关闭 v24 的目录 marker悖论、claim slot和 stale
tail窗口、source clock/tie歧义、future-poison oracle、staging seal、issuer自采 runtime及
当前M7 design/test/review成功路径，同时保持v28有界架构和M7/final-OOS禁入线。

