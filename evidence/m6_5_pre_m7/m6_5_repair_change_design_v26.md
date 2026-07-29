# M6.5 有界修复变更设计 v26

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v25 作为 canonical subject；v25及失败审查永久保留。

## 1. Canonical composition 与边界

v26是一个无歧义composite design：

1. normative base是v25 exact SHA
   `f59698a1e76b8bcf9e23895b39222f1abc151c7b36e4cf189d1632d1b9f3f3c2`；
2. 本文件§2–§6对v25对应段落作完整替换，冲突时本文件优先；
3. v25其余§1–§3、§4.4–§4.5、§5.1、§7.1、§7.4、§9–§10逐字继续有效；
4. M7 subject改为v4与matrix v4，v3不再current。

该引用是固定hash的规范合并，不是把实现决定留给旧版本。v26仍只允许M6.5 design/test/code/
synthetic evidence和之后绑定的只读M6 replay；不授权M7 implementation/fit、预算变化或
final-OOS。

## 2. PreOOSAuxSnapshotV2 exact tables 与 daily lifecycle

所有date为Arrow `date32`，ID为UTF-8 string，boolean为bool。source字段状态分三类：
`SOURCE_NULL`、`PRESENT_PRE_C`、`PRESENT_POST_C`，不得把后两类合并。cutoff
`C=2025-01-01 exclusive`。

### 2.1 Exact schemas

| table | exact output columns（顺序） | primary key |
| --- | --- | --- |
| membership | `index_security_id!, constituent_security_id!, into_pub_date!, into_eff_date!, out_pub_date?, out_eff_date?` | first 4 columns |
| security | `security_id!, exchange_cd!, asset_class!, list_date!, delist_date?` | `security_id` |
| calendar | `calendar_date!, exchange_cd!, is_open!` | `exchange_cd,calendar_date` |
| status | `security_id!, sec_short_name?, party_state?, publish_date?, eff_date?` | all 5 canonical values |
| action | `security_id!, ex_div_date!` | both columns |

`!/?`只表示nullable，不写入列名。exact duplicate dedup；相同primary key但非相同payload
FAIL。status允许同security多个event，按§2.4分组后必须唯一。calendar同key冲突FAIL。
初始状态：非成员、未上市、未处于special-status forbidden/unknown、无action。

### 2.2 Membership

entry row只有 `into_pub/into_eff` 都非null才合法；每日：

```text
known_entry = max(into_pub, into_eff)
entry_active(T) = T >= known_entry
```

若 `known_entry>=C`，该interval对protected pre-C output无贡献，可以从aux logical table排除。

exit逐日状态：

| out_pub | out_eff | pre-C T语义 |
| --- | --- | --- |
| null | null | 无已知exit |
| present | present | `known_exit=max(pub,eff)`；仅当`T>=known_exit`失效；若known_exit>=C则pre-C无影响 |
| present | null | 若pub<C，从pub起UNKNOWN并排除；若pub>=C，pre-C无影响 |
| null | present | 若eff<C，从eff起UNKNOWN并排除；若eff>=C，pre-C无影响 |

因此 `pub<C,eff>=C` 是已公告的future-effective exit：T<C仍按成员处理；它不是unknown。
`pub>=C,eff<C` 在pre-C尚未公告，`known_exit>=C`，同样不提前退出。双clock存在时logical
table保留两个原值，即使一个post-C；这是pre-C公告已携带的计划字段，future-poison不得修改。

CSI300/500 IDs固定`1782/2103`；T须满足entry、未触发exit/unknown，多个合法interval取union。

### 2.3 Security、calendar与listing

security只保留asset `E`、XSHG/XSHE、`list_date<C`。`delist_date`保留原值；逐日只有
`T>=delist_date`才排除，绝不因future delist提前删除历史。first open session
`>=list_date`为1，第60个已完成session起eligible。缺T quote计audit并inactive。

calendar只保留date<C；XSHG/XSHE `is_open==1`集合必须exact equal。expected output dates从该
集合生成，空日FAIL。

### 2.4 Special status

transition time规则：

| publish | effective | pre-C T语义 |
| --- | --- | --- |
| null | null | row FAIL |
| present | present | `known=max(pub,eff)`；仅当`T>=known`应用；known>=C时pre-C无影响 |
| present | null | pub<C时从pub起UNKNOWN；pub>=C时pre-C无影响 |
| null | present | eff<C时从eff起UNKNOWN；eff>=C时pre-C无影响 |

同 `security_id,known_time`：

1. exact canonical duplicate dedup；
2. 任一真实missing-clock UNKNOWN使整组UNKNOWN；
3. 否则 normalized name/forbidden相同则合并，不同则FAIL。

group排序 `(security_id,known_time,event_kind)`；UNKNOWN/complete都从known_time起持续至下一
transition。无历史event默认not forbidden/not unknown。forbidden regex、party_state audit和
NFC规则沿用v25。`PRESENT_POST_C`从不单独制造UNKNOWN。

### 2.5 Action 与 canonical oracle

action任一null FAIL；只保留`[support_start,C)`，exact duplicate dedup，UTF-8 ID bytes/date
升序。所有table继续使用v25 canonical logical JSONL；poison只可修改T后且当时不可得的值，
不得修改pre-C公告中已经携带的post-C effective date。每个mutation明确记录字段在目标T的
availability classification。

## 3. Event、run 与 execution 状态机

### 3.1 两层状态

每个source event有canonical slots：

```text
receipt -> claim -> outcome
outcome ∈ COMPLETED | FAILED | CLAIMED_INTERRUPTED
```

claim fresh `CREATED`永久消费attempt。outcome slot由
`sha256(registration_sha + source_event_id)`唯一派生。FAILED表示observer实际启动并给出
durable failure；CLAIMED_INTERRUPTED表示claim已存在但没有durable started/outcome证据，
不得重放。

run状态：

```text
ACTIVE -> CLOSED
ACTIVE -> ABANDONED   # 仅显式supersession或irreconcilable foreign tail
```

同一run的合法下一event推进ledger head，不会使旧event或整个run ABANDONED。历史event retry
验证其receipt/claim/outcome仍是current ledger的exact prefix后直接返回existing outcome，不
用旧H_after与whole current head相等。

### 3.2 Active run 与锁

authority root有canonical `active-run.json` no-replace index。一个ACTIVE registration完成或
显式ABANDONED前，其他run不能register/claim。crash不自动把ACTIVE转给新run；只有同一
registration recovery或authority中预定义supersession event可改变。

锁顺序：

```text
execution lease -> global control lock -> ledger lock
```

纯register/reconcile可跳过execution lease，但持有global/ledger时绝不反向等待lease。

### 3.3 Claim-to-outcome

observer path先取得server-wide execution lease，再在global+ledger临界区reconcile并决策：

- 无claim：publish claim；只有fresh CREATED进入observer；
- claim+outcome：返回existing outcome；
- claim无outcome：
  - 若当前进程刚fresh CREATED且仍持lease，进入observer；
  - crash后retry取得新lease时，no-replace发布`CLAIMED_INTERRUPTED`，不重放；
- planned next event要求current head等于本run最后receipt H_after；
- foreign/unregistered tail FAIL；只有authority显式supersession才run ABANDONED。

fresh claim后释放global/ledger但持有execution lease直到durable outcome fsync；随后才释放
lease。observer未启动前crash与启动后未写outcome的crash都保守归
`CLAIMED_INTERRUPTED`。plan可使用另一个预注册retry attempt继续；原attempt永久消费。

`CLOSED`要求所有实际执行的event有outcome，所有remaining event按plan标unused，current
head等于last receipt；不要求每个预算上限event都执行。

M6.5只运行fake observer。future live仍因authority slot不存在而拒绝。

## 4. Replay staging唯一事务顺序

input与output是两个独立transaction。

### 4.1 Immutable input transaction

唯一顺序：

1. 在private sibling staging复制/解压全部inputs；
2. 计算payload inventory；
3. 写 `STAGING_SEALED.json`，其内容绑定payload inventory；
4. files `0440`、dirs bottom-up `0550`，fsync并从root dir FD重新核对；
5. 形成prepared claim，expected final inventory包含payload和seal file；
6. 在publish lock下no-replace发布prepared、final hardlinks与completion；
7. loader复核prepared/completion/full inventory后，child只读消费final input tree。

completion后input tree不可再增加任何文件。private staging仅在final full validation后unlink
其目录项；hardlinked final inode不修改。清理失败只告警/计容量，不改变PASS；每attempt
staging byte cap与总容量阈值写入runtime policy。

### 4.2 Mutable work 与 immutable output transaction

child获得一个与input sibling、执行前为空的private work dir，只能写raw result/log，不得写
input tree。invocation绑定work path但不预判output bytes。child结束后：

1. outer validator检查exit/runtime/input post-inventory；
2. 验raw result schema/14 folds/0 fit/ledger unchanged；
3. 对work output计算完整inventory；
4. 以另一个`PreparedDirectoryTransactionV1`发布immutable output和completion；
5. outer receipt只能引用completed input/output transactions。

crash work dir永不被loader当成功产物；相同attempt retry不重放已claim execution，而创建新的
verification attempt ID。

## 5. M7 v4 binding

当前M7 subjects：

- `m7_change_design_v4.md`
  SHA `c4c6144ad23cbf8f7f534ff1b2c3116be3f74fd872a70cec688a09a35a7a469d`；
- `m7_behavior_to_test_matrix_v4.md`
  SHA `c02684727b45596cb3fa5cd7ca3c04d15d3f2b948d80e9beda00fb3aac58e89a`。

v4关闭：

1. exact V2 lineage与immutable fixed+behavior qualification envelope；
2. generic Gate永久关闭、专用factory/capability和固定`2*sigmoid`注入/checkpoint；
3. cost/benchmark证书、mapper/metric hash在first event前的screening bundle；
4. CCC float32 input、float64 accumulation/epsilon/return；
5. 每个测试行的M6.5/M7 implementation/real acceptance owner。

当前M6.5只实现matrix的`M6.5_CONTRACT_ONLY`行；不得把未来M7生产行加入本轮red/green。

## 6. Review closure map 与 verdict

| v25 finding | v26 closure |
| --- | --- |
| daily lifecycle/schema遗漏 | §2 exact schemas与entry/exit/delist/status daily state |
| post-C clock被当null | §2三态classification与max(pub,eff) |
| valid multi-event被abandon | §3 event/run分层与exact-prefix retry |
| claim crash/并发 | §3 execution lease + CLAIMED_INTERRUPTED |
| staging顺序 | §4 input seal-before-prepare与独立output transaction |
| M7 V1/V2与Gate capability | §5 / M7 v4 qualification+factory |
| screening不可执行 | M7 v4 first-event prerequisite bundle |
| CCC dtype | M7 v4 float64 numeric contract |
| matrix范围漂移 | matrix v4 owner stage |
| staging cleanup P3 | §4.1 unlink-only与capacity policy |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。v26仍不等于M6.5 PASS；review PASS前不得进入
test-design、implementation、replay、M7或final-OOS。

