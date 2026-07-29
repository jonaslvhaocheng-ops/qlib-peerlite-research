# M6.5 有界修复变更设计 v27

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v26；v26及失败审查永久保留。

v27是自包含canonical design，不继承任何旧change-design段落。它只建设第七步前的M6.5：
T-known market state、synthetic trial-ledger mechanics、M6只读archival replay和当前M7
design-only工件。它不实现或运行M7，不改变预算，不访问final-OOS。

## 1. 当前事实与完成边界

| 项目 | 状态 |
| --- | --- |
| M6 | `PASS`，唯一close prefix `6 candidate / 44 fit` |
| M6.5 | `NEEDS_CHANGES` |
| M7 | `NOT_RUN` |
| final-OOS | sealed，未访问 |
| review前禁止 | test-design、implementation、replay、fit、budget、final-OOS |

M6.5最终PASS依次需要：design review、test design、expected-red、implementation、green/
coverage、independent code review、synthetic E2E、受绑定的M6 14-fold只读replay、M7当前
design review和M6.5 gate receipt。

Threat model：受信任research-server operator下的误配、crash、retry与cooperative
concurrency；不防御恶意root/kernel/native library或恶意同uid进程。

## 2. 模块与公共Gate

边界：

- `data.market_state`：纯函数，只依赖schema/NumPy/Pandas；
- `data.pre_oos_aux`：typed source projection与canonical logical digest；
- `governance.atomic_publish`：stdlib no-replace file/directory transaction；
- `governance.trial_ledger`：prefix/head/run/event mechanics；
- `governance.m6_archive`：M6 static/binding/runtime/staging验证；
- `scripts/server/*`：composition root，不被library import。

package root lazy-load模型；治理/数据import不得加载Torch。

统一异常`M7MarketStateNotAuthorized`。以下五个generic入口在
`market_gate=True`时必须于dataset read、journal/output create、checkpoint load或fit前拒绝：

1. `ExperimentConfig`
2. CLI
3. `PeerLiteModel`
4. `PeerLiteNetwork`
5. `PeerLiteModel.load_checkpoint`

false-gate M6 config/checkpoint兼容。`PanelDataset.market_state_columns`为空兼容；非空必须严格
等于固定四列且不与feature/label/legacy market相交，但schema guard不授予模型能力。

## 3. MarketStatePolicyV3

### 3.1 固定身份与日期

绑定：

- research contract file SHA
  `2f99bfb56929c732b24efe5da25c6c9d2786773ce95af347099228a521a9502c`；
- feature spec file SHA
  `b35da580ff710f7ca61f174d9f810f327942d190869ed422526e722eaeead12e`；
- `features.py` SHA
  `0de3b798e8f49032bb04c58507ab471591e167013d58ea9f3f86e62308b47ef0`；
- source manifests：
  - mkt_equd `d3f285c62c405ceed0b05fddc3abaf82f704815216ed42e454eab0e240ad3730`
  - idx_cons_core `d6c5e5b2acfe2b8b1d354a07a7fed0a3e5b594eaa7dafc2c871fed48a5565667`
  - md_security `4eff64dd068d805754cea9d1d9e720c7d7be7a180f6a23686f5434fbe3e03426`
  - md_trade_cal `1aefd73dfd64dc5bdbb4e688e0812f962b191353b8bb5b90a56428472cb7fd0b`
  - equ_inst_sstate `991212489d58c1ce3dc6aab7b1980774a4f0a80d28775a81bf11f954b811059e`
  - mkt_adjf `e40fb724d9fd2a900921f41206252b758b9bfe311bf143295f7566ebf06831b6`；
- adapter/slicer/builder/verifier/pure-state file SHA。

```text
timezone            = Asia/Shanghai
support_start       = 2011-09-01 inclusive
output_start        = 2012-01-01 inclusive bound
cutoff C            = 2025-01-01 exclusive
expected dates      = equal XSHG/XSHE open sessions
windows             = [5,10,20,60]
action mask         = trailing 60 instrument observations
aggregation dtype   = float64
empty expected day  = FAIL
```

builder只读verified `PreOOSAuxSnapshotV2`和`mkt_equd` pre-C partitions，不读M3 supervised
matrix、legacy market或`mkt_equd_2025/2026`。

### 3.2 Exact auxiliary schemas

Arrow types：ID/string UTF-8，dates `date32`，bool boolean。

| table | columns（? nullable） | primary key |
| --- | --- | --- |
| membership | `index_security_id,constituent_security_id,into_pub_date,into_eff_date,out_pub_date?,out_eff_date?` | first 4 |
| security | `security_id,exchange_cd,asset_class,list_date,delist_date?` | security_id |
| calendar | `calendar_date,exchange_cd,is_open` | exchange_cd,date |
| status | `security_id,sec_short_name?,party_state?,publish_date?,eff_date?` | all canonical values |
| action | `security_id,ex_div_date` | both |

nonnull列出现null FAIL。exact duplicate dedup；同primary key不同payload FAIL。所有date normalize为
timezone-naive date。

### 3.3 Availability-projected membership

entry只有`into_pub<C`且`into_eff<C`才进入protected table。逐日
`known_entry=max(into_pub,into_eff)`，T>=known_entry才active。

exit projection：

| source state | protected fields | pre-C daily rule |
| --- | --- | --- |
| pub=null, eff=null | null/null | no exit |
| pub<C, eff any present | retain pub+eff | exit at max(pub,eff)；max>=C则pre-C无影响 |
| pub<C, eff=null | pub/null | from pub UNKNOWN/excluded |
| pub>=C | null/null | transition pre-C unavailable；no effect |
| pub=null, eff<C | null/eff | from eff UNKNOWN/excluded |
| pub=null, eff>=C | null/null | no pre-C effect |

因此只有pre-C公告已经携带的future effective date可进入protected payload；
`pub>=C,eff<C`被投影为null/null，可被future poison任意修改而不影响protected digest。

index固定`1782/2103`。T需entry active且未exit/unknown；多个合法interval取union。

### 3.4 Security、calendar、status、action projection

**Security**

- asset `E`、XSHG/XSHE、`list_date<C`；
- `delist_date<C`保留，`delist_date>=C`投影为null，因为没有独立pre-C availability clock；
- 逐日仅T>=protected delist时排除；
- first open session>=list date为1，第60个完成session起eligible；
- T缺quote计audit并inactive。

**Calendar**

- 只保留date<C；XSHG/XSHE open集合exact equal；
- duplicate同值dedup，冲突FAIL。

**Status**

| source state | protected row | pre-C rule |
| --- | --- | --- |
| publish<C, eff present | retain both | transition at max；max>=C则pre-C无影响 |
| publish<C, eff=null | retain pub/null | from pub UNKNOWN |
| publish>=C | exclude row | pre-C unavailable |
| publish=null, eff<C | retain null/eff | from eff UNKNOWN |
| publish=null, eff>=C | exclude row | no pre-C effect |
| both null | FAIL | invalid |

complete event的`sec_short_name`先NFC、strip；null或strip后空一律转UNKNOWN。party_state可null，
只进入audit。nonempty complete event forbidden由
`upper(name)` regex `(?:^|\\*)ST|PT|退`决定。

同security/known_time：exact dup dedup；任一UNKNOWN则组为UNKNOWN；否则normalized name和
forbidden必须完全一致，不同FAIL。组按security/known_time排序；transition持续到下一event；
无event默认not forbidden/not unknown。

**Action**

- nonnull `(security_id,ex_div_date)`，只保留`[support_start,C)`；
- exact duplicate dedup，按UTF-8 ID bytes/date升序；
- adjustment factor不读。

### 3.5 Canonical logical oracle

每table先应用上述availability projection，再按primary key稳定升序。JSONL规则：

- schema列顺序；
- string NFC，status name另按strip规则；
- date `YYYY-MM-DD`、bool JSON、null JSON；
- 无空格UTF-8，每行一个`\n`。

manifest绑定schema、row count、key digest、logical SHA和单次Parquet file SHA。Parquet writer：
PyArrow22、dictionary false、zstd level3、statistics true、data page1.0、row group65536。

future-poison只改变目标T当时不可得的exit/status/delist/calendar/action记录；pre-C公告已携带
future effective date禁止作为“未来不可得值”修改。original/poison分别绑定source、mutation
ledger、code/env；protected schema/key/value/logical digests必须相同。independent verifier
重算，builder不能自签。

## 4. Feature、population与state

quote raw mapping严格为冻结OHLCV/amount/turnover；price>0，volume/amount>=0，turnover finite，
security/date duplicate FAIL。action只触发RAW窗口mask。

完整support quote panel上、任何universe/status筛选前调用固定
`build_causal_daily_features(windows=(5,10,20,60), mask=60)`。state population随后应用
membership、listing、active、status、price、mask、feature finiteness。

canonical `(datetime,instrument)`后：

```text
mkt_trend_20    = mean(ret_mean_20)
mkt_vol_20      = median(ret_std_20)
mkt_breadth_1d  = count(ret_1d > 0) / population_count
mkt_turnover_20 = median(turnover_mean_20)
```

float64，偶数median为两中值mean，禁止隐式drop，population非空。产品包含
population/daily_state/daily_population_audit/manifest，初始
`INTEGRITY_BUILT_NOT_PIT_QUALIFIED`；audit loader可读，model loader拒绝。

## 5. Atomic publication

### 5.1 File

same-parent private temp写满/fsync，`os.link(temp,final)` no-replace，fsync parent，unlink temp。
返回`CREATED`或`ALREADY_EXISTS_IDENTICAL`；不同bytes conflict；无overwrite fallback。

### 5.2 PreparedDirectoryTransactionV1

固定paths：

```text
.<target>.publish.lock
.<target>.PREPARED.json
<target>/
<target>/PUBLISH_COMPLETE.json
```

prepared在final payload前发布，绑定target/schema/content UUID、完整expected inventory、
logical digests、private staging path/inventory、policy/code SHA。

在parent publish lock内：

1. complete存在则复核prepared/full inventory，same返回existing；
2. prepared不存在no-replace发布；不同bytes conflict；
3. same prepared retry可重建staging，但必须exact inventory；
4. mkdir final；逐文件hardlink，existing必须hash/size相同；
5. fsync final，最后发布completion并fsync parent；
6. loader仅在prepared/completion/full inventory一致时读取。

crash释放lock；只有same claim可恢复。冲突或不可重建HOLD；不覆盖/删除/quarantine final。
commit后先将private staging directories恢复owner-writable，只unlink staging directory entries，
不修改hardlinked payload inode；失败只告警并计容量。staging byte cap/总阈值由runtime policy
固定。

## 6. Synthetic trial-ledger mechanics

M6.5只接受`M6_5_SYNTHETIC_TEST_ONLY`。LIVE/M7固定slot不存在时抛
`LiveRunAuthorityNotFrozen`。

### 6.1 Immutable identities

- M6 historical `LedgerPrefixBinding`；
- current whole `LedgerHeadBindingV1`；
- one-run `SyntheticRunAuthorityV2`：run_id、event plan、caps、M6 prefix；
- `RunRegistrationV2`；
- `JournalSnapshotV2`；
- `ReconciliationReceiptV2`；
- per-event canonical `claim`和`outcome`；
- run terminal `CLOSED/ABANDONED`。

每个authority root只允许exact one run。后续run必须使用新的immutable authority root。global
registry在固定`authority-generations/<monotonic_generation>.json` append-only登记root，
`run-index/sha256(run_id).json`保证全局唯一。global control lock内验证generation连续、前代
run terminal、current ledger head和新registration，再no-replace发布；没有mutable
`active-run.json`。

run terminal schema包含registration、status、last receipt/head、全部plan event partition：
`COMPLETED/FAILED/CLAIMED_INTERRUPTED/UNUSED`及reason；集合必须exact partition event plan。

### 6.2 Event与worker fencing

event状态：

```text
reconciled receipt -> claim -> outcome
outcome = COMPLETED | FAILED | CLAIMED_INTERRUPTED
```

claim fresh CREATED永久消费。retry使用plan内新attempt ID。

server-wide execution lease由**实际副作用worker进程直接取得和持有**。worker顺序：

1. 取得execution lease；
2. 取得global control→ledger locks；
3. 验registration、current head、event plan、caps；
4. 要求所有前序event已有durable outcome；
5. append/recover exact ledger batch和receipt；
6. fresh publish claim；
7. 释放global/ledger但worker保留execution lease；
8. worker自身执行fake observer并no-replace写durable outcome；
9. fsync outcome后释放lease。

parent launcher无claim/outcome写权限。parent死亡不影响worker持lease；worker死亡则OS释放lease。
recovery worker取得lease后，若claim存在无outcome，写`CLAIMED_INTERRUPTED`且不重放；下一个
预注册retry event只有看到该durable outcome后才可claim。两个worker不能并发副作用。

同run合法下一event推进head；历史event retry只需证明receipt/outcome仍是current ledger exact
prefix，返回existing，不因whole head推进ABANDON。foreign tail FAIL。authority root只有一个
run，ABANDONED仅显式irreconcilable failure；新run用新generation。

## 7. M6 archival replay

### 7.1 Trusted runtime与input binding

actual replay要求固定
`contracts/immutable/m6_replay_runtime_policy_v1.json`，不存在则拒绝。policy由独立builder/
reviewer创建，绑定M6 environment SHA、x86_64/Python3.11.14/torch2.7.1+cu126/CUDA12.6/
numpy2.4.6/pandas2.3.3/pyarrow22/qlib0.9.7、determinism、executable path/hash、distribution
RECORD closure、module/shared-object path/hash、CUDA device/driver/cuDNN/CUBLAS。issuer只读。

`M6ReplayInputBindingV3`绑定M6 gate/spec/run/verification/environment/prefix、transfer archive、
product/run/checkpoints/predictions、worker/launcher/validator/runtime policy和expected
`14 replay/0 fit/ledger unchanged/max date<C/CUDA only`。

### 7.2 Input、work、output

input transaction唯一顺序：

1. private staging copy/safe extract；source用O_NOFOLLOW，copy前后fstat一致；
2. payload inventory；
3. 写seal；
4. files0440；private dirs保持owner-only `0700`以便cleanup，final published dirs0550；
5. fsync/recheck；
6. prepared claim绑定包含seal的完整final inventory；
7. hardlink publication/completion；
8. child只读final input tree。

safe extraction拒绝absolute/`..`/duplicate/link/device/FIFO/socket/setuid/setgid，仅一top dir。

child写独立private work dir，不写input。结束后outer validator验runtime、input post-inventory、
raw schema、14 folds、0 fit、ledger unchanged，再以独立directory transaction发布output和
outer receipt。

replay是只读、确定性、不消耗trial budget，因此**不承诺exactly-once**。任何crash work dir
都不是成功产物；retry必须使用新verification attempt ID和新output root，可安全重新执行，
所有PASS receipt仍需exact input binding和14-fold equality。无需replay claim/outcome状态机。

### 7.3 Child与score

trusted executable以`-I -B`启动staged worker；验证runtime/distribution/module/CUDA。
每fold normalize date/instrument、unique key、stable sort、finite native float64；key digest
使用timestamp+0x1f+instrument+newline，score再加0x1f+`float.hex()`；`np.array_equal` exact。
legacy receipt不能关闭M6.5。

## 8. 当前M7 design-only bundle

- `m7_change_design_v5.md`
  SHA `59f24bbe0c6ae9568889518fd6c329420b4823306a715c6da5a565edf34fb2ad`
- `m7_behavior_to_test_matrix_v5.md`
  SHA `d149922b2d0536d284442142a90b25052e300a900a0a14ce15d690a5ef462992`

v5完整冻结V2 qualification的17+4项production predicates、外部trust anchors、专用Gate
create/reload、完整Lin CCC公式/dtype、first-event screening prerequisites、预算和owner stage。
M6.5只实现matrix中`M6.5_CONTRACT_ONLY`行，不写M7 production code。

## 9. Verification obligations 与顺序

review PASS后test design必须覆盖：

1. 五Gate入口、lazy import、false checkpoint；
2. 每table availability projection、null/name/status/delist、canonical poison；
3. file/directory每个crash点、same/different claim、concurrent retry、cleanup；
4. authority generations、run uniqueness、前序outcome、worker-held lease、claim crash/retry；
5. runtime policy、staging seal/mode/copy TOCTOU/safe extraction；
6. retryable read-only replay、14/0/unchanged、score bytes；
7. M7 contract-only predicates；
8. 新增/实质修改core code line/branch coverage 100%。

顺序：independent design review → test design → expected-red → implementation → green/coverage →
independent code review → synthetic E2E → bound M6 replay → M6.5 gate。任何失败回负责阶段。

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。这不是M6.5 PASS或M7授权。

