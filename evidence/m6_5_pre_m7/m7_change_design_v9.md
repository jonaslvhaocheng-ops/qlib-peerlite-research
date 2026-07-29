# M7 CCC / 市场状态 Gate 设计 v9

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- 架构：`architecture_confirmation_v28.md`
- 冻结研究契约：`contracts/immutable/research_contract_pit_v2.json`
- 起点：M6 `6 candidate / 44 fit`
- 当前上限：`27 candidate / 60 fit`
- 取代：M7 v8；历史版本与失败审查保留。

本文件不创建derived contract、qualification、prerequisite、authority、runner或checkpoint，
不运行fit，不改变预算，不访问final-OOS。M6.5只可实现本文件标记为
`M6.5_CONTRACT_ONLY`的纯验证器和合成测试。

## 1. 两个隔离 generation 与预算

| generation role | candidate | linear plan | failure |
| --- | --- | --- | --- |
| `M7_CCC_ISOLATED` | `PEERLITE_K16_CCC` | 1 candidate + 7 folds + 1 deterministic refit | 本分支HOLD，余项UNUSED |
| `M7_GATE_ISOLATED` | `PEERLITE_K16_MSE_GATE` | 1 candidate + 7 folds + 1 deterministic refit | 本分支HOLD，余项UNUSED |

第二generation commit必须绑定第一generation的`CLOSED`或`ABANDONED` terminal；第一分支失败不
取消第二分支。总增量2 candidate/16 fits，最大到`8/60`。FAILED或CLAIMED_INTERRUPTED永久
计数并使本分支HOLD；无replacement。组合、额外seed、确认、replacement或M8 refit要求新用户CR。

## 2. MarketStateQualificationEnvelopeV6

唯一lineage：

```text
PreOOSAuxSnapshotV2
 -> MarketStateProductV2
 -> fixed PIT audit PASS
 -> one-official-FUTURE_POISON-manifest per T
 -> availability supplement + aux-prefix verification per T
 -> independent review receipt per T
 -> security-lifecycle availability authority
 -> immutable qualification envelope
```

### 2.1 Fixed PIT predicates

parent必须：

- schema=`pit_audit_manifest_v1`；
- status=PASS、pit_qualification=QUALIFIED、evidence_ceiling=PASS；
- claim=`MARKET_RECONSTRUCTIBLE`；
- execution_boundary=`PRODUCTION_CLI`、test_only_adapter=false；
- scope=`FULL_TRAINING_INPUT`；
- exact、无重复/额外且全部PASS：
  `I001 I002 S001 T001 T002 T003 U001 U002 C001 M001 A001 H001
  Q001 Q002 Q003 L001 L002`。

manifest content/report/file SHA和product/aux/contract/feature/policy/code parent bindings必须一致。

### 2.2 Official behavior mapping

future derived contract冻结exact unique horizons；一T一official request/manifest，按T升序一对一
覆盖。每个manifest必须：

- `pit_behavior_manifest_v1` / `pit_behavior_spec_v1`；
- `probe_type=FUTURE_POISON`；
- PASS / `NOVEL_CANDIDATE`；
- exact `B001,B002,B003,B004`，无重复/额外且全部PASS；
- scalar `protection.protected_through=T`；
- exact parent fixed-audit content SHA。

state output CSV恰为：

```text
sample_id,prediction_time,feature_name,feature_value_json
```

每行：

```text
sample_id       = "market_state|" + YYYY-MM-DD
prediction_time = 契约中该date的T日收盘后时间，UTC六位小数Z
feature_name    = 固定四列之一
feature_value_json = JSON string scalar，内容为Python float.hex，例如"0x1.0000000000000p+0"
```

禁止object编码。行按official canonical key排序，只输出date<=T。

official request不增加私有key。既有十个artifact slots映射固定：

- `baseline_raw_snapshot` / `probe_raw_snapshot`：original/probe snapshots；
- `code_or_query`：state flatten adapter exact source；
- `parameters`：T、四列顺序、original/probe input manifest SHA、projection spec ID；
- `environment`：runtime/locale/timezone/package closure；
- `baseline_output` / `probe_output`：上述CSV exact bytes；
- `pit_audit_manifest`、`perturbation_ledger`、`pipeline_receipt`：按official spec。

pipeline receipt按official字段绑定这些SHA、run IDs、protection与probe。这样B004只证明state
official rows；aux和population由§2.4独立证明。

### 2.3 BehaviorAvailabilitySupplementV1

strict object只允许：

```json
{
  "schema_version": "qlib_peerlite_behavior_availability_supplement_v1",
  "supplement_id": "<ASCII>",
  "official_behavior_manifest_sha256": "sha256:<64hex>",
  "official_perturbation_ledger_sha256": "sha256:<64hex>",
  "protected_through": "<UTC RFC3339 Z>",
  "entries": [
    {
      "mutation_id": "<ASCII>",
      "source_id": "<ASCII>",
      "raw_key": "<ASCII>",
      "field": "<ASCII>",
      "baseline_value_sha256": "sha256:<64hex>",
      "probe_value_sha256": "sha256:<64hex>",
      "vendor_available_time": "<UTC RFC3339 Z>",
      "comparison": "GT",
      "rationale_code": "<derived-contract allow-list member>"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/null/float、空entries或duplicate拒绝；每项available_time>T。entries按
`mutation_id,source_id,raw_key,field` UTF-8 bytes排序。canonical hash排除自身，使用UTF-8 JSON、
keys字节序排序、NFC strings、固定array顺序、`,`/`:` separators、无空格/尾换行。官方
manifest/ledger/T exact匹配。

### 2.4 AuxPrefixBehaviorVerificationV2：可重算三产品证明

#### 输入视图与canonical records

verifier只读取official request已绑定的original/probe snapshots、supplement、原/探针
PreOOSAuxSnapshotV2 manifest、population manifest和state manifest。每个产品在T上形成records：

- `aux`：五个exact tables
  `membership,security,calendar,status,action`。按PreOOSAuxSnapshotV2规则和supplement逐field
  投影，仅保留`vendor_available_time<=T`可得值；unavailable field按该table规则置null或排除row。
  record key=`[table, primary-key canonical JSON array, field]`，value为canonical JSON scalar。
- `population`：对每个date<=T：
  - member record key=`["member",date,instrument]`、value=`true`；
  - count record key=`["count",date]`、value为十进制JSON string。
- `state`：对每个date<=T和固定四列：
  key=`["state",date,column]`，value为JSON string scalar `float64.hex()`。

dates是`YYYY-MM-DD`；strings NFC；bool/null为JSON scalar；禁止NaN/Inf。primary-key列序来自
PreOOSAuxSnapshotV2 exact schema。records按canonical key UTF-8 bytes稳定升序，无duplicate。

定义：

```text
LP(x) = uint64 big-endian len(x) || x
key_bytes   = canonical UTF-8 JSON(record key), separators ","/":", no whitespace
value_bytes = canonical UTF-8 JSON scalar(record value)
schema_bytes= canonical UTF-8 JSON of exact product/table/column/type/order declaration
key_digest     = sha256(concat(LP(key_bytes)))
value_digest   = sha256(concat(LP(key_bytes)||LP(value_bytes)))
logical_digest = sha256(LP(schema_bytes)||concat(LP(key_bytes)||LP(value_bytes)))
```

#### Closed receipt

strict object只允许：

```json
{
  "schema_version": "qlib_peerlite_aux_prefix_behavior_verification_v2",
  "verification_id": "<ASCII>",
  "verifier_code_sha256": "sha256:<64hex>",
  "environment_sha256": "sha256:<64hex>",
  "invocation_sha256": "sha256:<64hex>",
  "report_sha256": "sha256:<64hex>",
  "official_behavior_manifest_sha256": "sha256:<64hex>",
  "supplement_sha256": "sha256:<64hex>",
  "protected_through": "<UTC RFC3339 Z>",
  "products": {
    "aux": "<ProductPrefixComparisonV1>",
    "population": "<ProductPrefixComparisonV1>",
    "state": "<ProductPrefixComparisonV1>"
  },
  "checks": [
    {"check_id": "AP001", "status": "PASS"},
    {"check_id": "AP002", "status": "PASS"},
    {"check_id": "AP003", "status": "PASS"},
    {"check_id": "AP004", "status": "PASS"}
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

`products` exact keys/order为aux,population,state；每个
`ProductPrefixComparisonV1` exact shape：

```json
{
  "baseline_manifest_sha256": "sha256:<64hex>",
  "probe_manifest_sha256": "sha256:<64hex>",
  "schema_sha256": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  },
  "key_count": {
    "baseline": "<decimal ASCII>",
    "probe": "<decimal ASCII>",
    "equal": true
  },
  "key_digest": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  },
  "value_digest": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  },
  "logical_digest": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  }
}
```

AP001=三产品schema equal；AP002=三产品key count/digest equal；AP003=三产品value digest equal；
AP004=三产品logical digest equal。exact set/order、全部PASS，且全部15个`equal=true`；validator
必须从bound manifests重算，不接受status自报。unknown/null/float/extra product/check拒绝。
canonical规则同§2.3。

### 2.5 BehaviorIndependentReviewReceiptV2

strict object只允许：

```json
{
  "schema_version": "qlib_peerlite_behavior_review_receipt_v2",
  "receipt_id": "<ASCII>",
  "review_authority_path": "<fixed relative path>",
  "review_authority_sha256": "sha256:<64hex>",
  "review_authority_version": "<ASCII>",
  "authority_valid_from": "<UTC RFC3339 Z>",
  "authority_valid_until": "<UTC RFC3339 Z>",
  "reviewed_at": "<UTC RFC3339 Z>",
  "review_scope": "M7_STATE_BEHAVIOR_QUALIFICATION",
  "official_behavior_manifest_sha256": "sha256:<64hex>",
  "official_behavior_report_sha256": "sha256:<64hex>",
  "parent_fixed_audit_content_sha256": "sha256:<64hex>",
  "supplement_sha256": "sha256:<64hex>",
  "aux_prefix_verification_sha256": "sha256:<64hex>",
  "reviewer_context_id": "<ASCII>",
  "builder_context_id": "<ASCII>",
  "verdict": "PASS",
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/null/float拒绝；`valid_from<=reviewed_at<valid_until`；reviewer!=builder。authority
path/hash/version来自derived-contract fixed slot。receipt通过内容SHA形成下游依赖：创建者必须先
读取并验证全部被引exact bytes，再no-replace发布receipt；envelope再绑定receipt SHA。validator只
证明该hash DAG与当前bytes，不从filesystem mtime或自报时间声称历史publication order。
canonical规则同§2.3。

### 2.6 SecurityLifecycleAvailabilityAuthorityV1 closed schema

future fixed slot：

```text
contracts/immutable/security_lifecycle_availability_authority_v1.json
```

strict authority只允许：

```json
{
  "schema_version": "qlib_peerlite_security_lifecycle_availability_authority_v1",
  "authority_id": "<ASCII>",
  "source_id": "DataYes.md_security",
  "source_version": "<ASCII>",
  "source_snapshot_manifest_sha256": "sha256:<64hex>",
  "availability_rows": {
    "path": "<fixed relative JSONL path>",
    "sha256": "sha256:<64hex>",
    "row_count": "<decimal ASCII>",
    "key_digest": "sha256:<64hex>"
  },
  "semantics": [
    {
      "field": "LIST_DATE",
      "event_value_column": "list_date",
      "available_time_column": "list_vendor_available_time",
      "row_key": ["security_id"],
      "visibility_comparison": "LE"
    },
    {
      "field": "DELIST_DATE",
      "event_value_column": "delist_date",
      "available_time_column": "delist_vendor_available_time",
      "row_key": ["security_id"],
      "visibility_comparison": "LE"
    }
  ],
  "evidence_artifacts": [
    {
      "kind": "<derived-contract allow-list member>",
      "path": "<fixed relative path>",
      "sha256": "sha256:<64hex>"
    }
  ],
  "issuer_authority_path": "<fixed relative path>",
  "issuer_authority_sha256": "sha256:<64hex>",
  "issuer_authority_version": "<ASCII>",
  "valid_from": "<UTC RFC3339 Z>",
  "valid_until": "<UTC RFC3339 Z>",
  "statement_sha256": "sha256:<64hex>",
  "independent_validation_receipt": {
    "path": "<fixed relative path>",
    "sha256": "sha256:<64hex>"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

`statement_sha256`对排除`statement_sha256`、`independent_validation_receipt`和
`canonical_sha256`后的authority statement按§2.3规则计算；receipt先绑定statement，final
authority再绑定receipt，禁止hash环。semantics exact两项/顺序；evidence非空、kind唯一并排序。
availability JSONL每行exact keys：

```json
{
  "security_id": "<NFC non-empty string>",
  "list_date": "YYYY-MM-DD",
  "list_vendor_available_time": "<UTC RFC3339 Z>",
  "delist_date": "YYYY-MM-DD or null",
  "delist_vendor_available_time": "<UTC RFC3339 Z or null>",
  "source_record_sha256": "sha256:<64hex>",
  "evidence_sha256": "sha256:<64hex>"
}
```

按security_id UTF-8 bytes排序、唯一；delist两字段必须同为null或同为nonnull。row_count/key
digest重算。authority canonical规则同§2.3。

independent validation receipt exact shape：

```json
{
  "schema_version": "qlib_peerlite_security_lifecycle_validation_receipt_v1",
  "authority_statement_sha256": "sha256:<64hex>",
  "rows_sha256": "sha256:<64hex>",
  "validator_code_sha256": "sha256:<64hex>",
  "environment_sha256": "sha256:<64hex>",
  "checks": [
    {"check_id": "SLA001", "status": "PASS"},
    {"check_id": "SLA002", "status": "PASS"},
    {"check_id": "SLA003", "status": "PASS"},
    {"check_id": "SLA004", "status": "PASS"},
    {"check_id": "SLA005", "status": "PASS"},
    {"check_id": "SLA006", "status": "PASS"}
  ],
  "verdict": "PASS",
  "reviewer_context_id": "<ASCII>",
  "issuer_context_id": "<ASCII>",
  "canonical_sha256": "sha256:<64hex>"
}
```

exact checks：SLA001 schema/hash；SLA002 row unique/order/coverage；SLA003 source row equality；
SLA004 per-row evidence hash；SLA005 timestamp/validity；SLA006 visibility replay；reviewer!=issuer。

rows必须exact覆盖qualified md_security projection内所有security_id；list/delist值与source exact
相等。对prediction time P：

```text
list visible   iff list_vendor_available_time <= P
list eligible time = max(list_date session boundary, list_vendor_available_time)
delist visible iff both delist fields nonnull and delist_vendor_available_time <= P
delist exclusion time = max(delist_date session boundary, delist_vendor_available_time)
```

不可见字段投影为null/row inactive，禁止event-date推断。authority在derived-contract
`qualification_created_at`必须满足`valid_from<=time<valid_until`。slot缺失、过期、版本/coverage/
evidence不符即qualification前FAIL/HOLD。当前slot不存在，所以只有negative validator路径可执行。

### 2.7 Envelope exact binding

envelope exact绑定fixed audit；每T的一份official manifest、supplement、AP verification和review
receipt；以及security authority/rows/validation receipt。数量/T必须一对一。trust anchors均来自
derived-contract fixed slots，不从envelope自报。

## 3. State join、standardizer 与 Gate

state列必须恰好按序：

```text
mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20
```

qualified daily product以timezone-naive normalized date为键，每日恰好一行，无重复/缺失/
nonfinite。broadcast representation归约前，同日每行四列逐列`float64.tobytes()`必须一致，否则
FAIL，禁止取first/mean。每个model date exact匹配一条state date；禁止as-of/ffill/bfill。所有检查
在Dataset、journal/output、candidate/fit前完成。

每fold standardizer只取排序去重training dates，每date一条四列并转native float64：

```text
mean = arithmetic_mean(x)
scale = sqrt(arithmetic_mean((x-mean)^2))  # population, ddof=0
if scale < 1e-12: scale=1.0
z=(x-mean)/scale
```

valid/test只transform；Gate输入前cast float32。checkpoint绑定列序、float64 hex mean/scale、
sorted unique training-date digest/count、standardizer schema/code SHA并在reload重算。

五个generic `market_gate=True`入口永久fail-closed。唯一create/reload：

```text
M7PeerLiteGateFactory.create_verified(
  derived_contract, qualification_envelope, screening_prerequisites, live_authority)
M7PeerLiteGateFactory.load_verified_checkpoint(
  path, derived_contract, qualification_envelope, screening_prerequisites, live_authority)
```

内部capability不能由bool/state/token伪造。结构固定：

```text
state[4] -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
gate=2*output
encoder_hidden *= gate[date,1,64]
-> assignment -> prototypes -> attention -> relative head
```

注入在encoder后/assignment前；K16、hidden64、heads4及M6其余超参不变，O(NK)。checkpoint还
绑定derived contract、qualification/prerequisite/live authority、Gate code/结构、state product、
join、model/feature/fold/data/runtime/code hashes；special reload逐项复核后才load。

## 4. CCC完整执行合同

prediction/target原生float32；内部：

```text
p64=prediction.float64; y64=target.float64
mu_p=mean(p64); mu_y=mean(y64)
var_p=mean((p64-mu_p)^2); var_y=mean((y64-mu_y)^2)
cov=mean((p64-mu_p)*(y64-mu_y))
ccc=2*cov/(var_p+var_y+(mu_p-mu_y)^2+float64(1e-8))
loss_date=1-ccc
loss_batch=arithmetic_mean(loss_date)
```

population denominator、variance correction=0；singleton=float64 MSE；loss返回float64并反传到
float32参数。train/validation/early-stop同定义，strict `<`更新，tie保留最早，nonfinite立即
失败。execution spec/checkpoint绑定dtype/reduction/epsilon；CPU oracle rtol=atol=1e-12，
CUDA以checkpoint/score exact replay为最终判据。

## 5. First-event admission

任何candidate/fit/claim前必须绑定PASS immutable prerequisites：

- frozen cost spec + 当前有效官方/券商fee receipt；
- frozen benchmark spec + 独立source certificate/PIT path；
- weekly mapper、calendar、unfilled/capacity/cost、metric implementation SHA；
- M6 K16 benchmark predictions/portfolio hashes；
- 2018–2024 folds与final-OOS seal；
- independent validator receipt；
- §2完整qualification和§3 state/join/standardizer validation。

当前cost、benchmark、security authority和live authority缺失，first event禁止。每分支相对同一
M6 K16 benchmark要求base-cost combined weekly net-excess IR delta>0、至少5/7 folds为正、
stress-cost combined net-excess return>=0。两分支通过也不自动授权组合。

## 6. Test ownership

M6.5只实现generic拒绝、§2 closed-schema/negative qualification validators、§3 state join/
standardizer纯函数和预算/generation contract tests。神经网络factory、CCC/Gate训练属于
`M7_IMPLEMENTATION`；真实fit/screening属于`M7_REAL_ACCEPTANCE`。

结论：`READY FOR INDEPENDENT DESIGN REVIEW / M7 NOT AUTHORIZED`。
