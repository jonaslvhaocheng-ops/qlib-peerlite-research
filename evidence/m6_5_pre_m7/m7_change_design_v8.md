# M7 CCC / 市场状态 Gate 设计 v8

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- 架构：`architecture_confirmation_v28.md`
- 冻结研究契约：`contracts/immutable/research_contract_pit_v2.json`
- 起点：M6 `6 candidate / 44 fit`
- 当前上限：`27 candidate / 60 fit`
- 取代：M7 v7；历史版本与失败审查保留。

本文件不创建 derived contract、qualification、prerequisite、authority、runner或checkpoint，
不运行fit，不改变预算，不访问final-OOS。M6.5只可实现本文件标记为
`M6.5_CONTRACT_ONLY`的纯验证器和合成测试。

## 1. 两个隔离 generation 与预算

未来M7固定使用两个连续、独立authority generations：

| generation role | candidate | linear plan | failure |
| --- | --- | --- | --- |
| `M7_CCC_ISOLATED` | `PEERLITE_K16_CCC` | 1 candidate event + 7 folds + 1 deterministic refit | 本分支HOLD，余项UNUSED |
| `M7_GATE_ISOLATED` | `PEERLITE_K16_MSE_GATE` | 1 candidate event + 7 folds + 1 deterministic refit | 本分支HOLD，余项UNUSED |

第二generation的commit必须绑定第一generation的`CLOSED`或`ABANDONED` terminal；第一分支失败
不取消第二分支。两者共2 candidate/16 fits，最大到`8/60`。当前无replacement fit；任何
FAILED/CLAIMED_INTERRUPTED永久计数并使对应分支HOLD。组合、额外seed、确认、replacement和
M8 refit均要求新的用户预算CR。

## 2. MarketStateQualificationEnvelopeV5

唯一lineage：

```text
PreOOSAuxSnapshotV2
 -> MarketStateProductV2
 -> fixed PIT audit PASS
 -> official behavior manifest(s)
 -> availability supplement(s) + aux-prefix verification(s)
 -> independent behavior review receipt(s)
 -> immutable qualification envelope
```

### 2.1 Fixed PIT exact predicates

schema=`pit_audit_manifest_v1`，status=PASS，pit_qualification=QUALIFIED，
evidence_ceiling=PASS，claim=`MARKET_RECONSTRUCTIBLE`，
contract_binding.execution_boundary=`PRODUCTION_CLI`，
contract_binding.test_only_adapter=false，request scope=`FULL_TRAINING_INPUT`。

exact check set，无重复无额外，全部PASS：

```text
I001 I002 S001 T001 T002 T003 U001 U002 C001 M001 A001 H001
Q001 Q002 Q003 L001 L002
```

manifest content/report/file SHA及product/aux/contract/feature/policy/code parent bindings必须一致。

### 2.2 Official behavior 与独立 aux-prefix proof

future derived contract冻结exact unique horizon list。每个T对应一个独立official
request/manifest；manifest按T升序且一对一覆盖，不多不少。每个manifest：

- manifest_version=`pit_behavior_manifest_v1`；
- spec_version=`pit_behavior_spec_v1`；
- probe_type=`FUTURE_POISON`；
- status=PASS、certification_status=`NOVEL_CANDIDATE`；
- exact IDs `B001,B002,B003,B004`，无重复无额外、全部PASS；
- 一个scalar `protection.protected_through=T`；
- original/probe lineage、perturbation ledger、protected key/value digest、content/report/file SHA；
- exact parent fixed-audit content SHA。

official B004只证明official projected rows。envelope还必须绑定同T的
`AuxPrefixBehaviorVerificationV1`，独立复核aux、population和state三个产品的prefix；不得把
official B004解释为其未输出的证明。

official state flattening adapter固定为：

```text
sample_id      = "market_state|" + YYYY-MM-DD
prediction_time= 冻结契约中该date的T日收盘后预测时间，UTC RFC3339
feature_name   = 四个固定state列之一
feature_value_json = {"float_hex":"<Python float.hex canonical ASCII>"}
```

行按`prediction_time UTF-8 bytes, sample_id UTF-8 bytes, feature_name UTF-8 bytes`稳定升序；
同一T只选择`datetime<=T`。adapter code SHA、输入manifest SHA和输出logical digest写入official
request；这让B004可覆盖state values，但population count与aux lineage仍由独立verifier证明。

### 2.3 BehaviorAvailabilitySupplementV1 closed schema

严格对象只允许以下键：

```json
{
  "schema_version": "qlib_peerlite_behavior_availability_supplement_v1",
  "supplement_id": "<non-empty ASCII>",
  "official_behavior_manifest_sha256": "sha256:<64 lowercase hex>",
  "official_perturbation_ledger_sha256": "sha256:<64 lowercase hex>",
  "protected_through": "<UTC RFC3339>",
  "entries": [
    {
      "mutation_id": "<non-empty ASCII>",
      "source_id": "<non-empty ASCII>",
      "field": "<non-empty ASCII>",
      "baseline_value_sha256": "sha256:<64 lowercase hex>",
      "probe_value_sha256": "sha256:<64 lowercase hex>",
      "vendor_available_time": "<UTC RFC3339>",
      "comparison": "GT",
      "rationale_code": "<derived-contract allow-list member>"
    }
  ],
  "canonical_sha256": "sha256:<64 lowercase hex>"
}
```

unknown key、null、float、duplicate entry、空entries均拒绝。时间统一为`Z`结尾的UTC RFC3339且
每项`vendor_available_time > protected_through`。entries按
`mutation_id,source_id,field`的UTF-8 bytes升序。canonical hash排除`canonical_sha256`后使用：
UTF-8 JSON、keys字节序排序、strings NFC、arrays保持规范顺序、separators为`,`/`:`、无空格/
尾换行。official manifest/ledger/T必须exact匹配。

### 2.4 AuxPrefixBehaviorVerificationV1 closed schema

严格对象只允许：

```json
{
  "schema_version": "qlib_peerlite_aux_prefix_behavior_verification_v1",
  "verifier_code_sha256": "sha256:<64 lowercase hex>",
  "official_behavior_manifest_sha256": "sha256:<64 lowercase hex>",
  "supplement_sha256": "sha256:<64 lowercase hex>",
  "protected_through": "<UTC RFC3339>",
  "original_aux_manifest_sha256": "sha256:<64 lowercase hex>",
  "probe_aux_manifest_sha256": "sha256:<64 lowercase hex>",
  "original_population_manifest_sha256": "sha256:<64 lowercase hex>",
  "probe_population_manifest_sha256": "sha256:<64 lowercase hex>",
  "original_state_manifest_sha256": "sha256:<64 lowercase hex>",
  "probe_state_manifest_sha256": "sha256:<64 lowercase hex>",
  "checks": [
    {"check_id": "AP001", "status": "PASS"},
    {"check_id": "AP002", "status": "PASS"},
    {"check_id": "AP003", "status": "PASS"},
    {"check_id": "AP004", "status": "PASS"}
  ],
  "protected_key_count": "<decimal ASCII integer>",
  "protected_key_digest": "sha256:<64 lowercase hex>",
  "protected_value_digest": "sha256:<64 lowercase hex>",
  "canonical_sha256": "sha256:<64 lowercase hex>"
}
```

checks exact set且固定顺序：AP001 projected schemas；AP002 protected keys/counts；
AP003 protected values；AP004 protected logical digests。无额外/重复项，全部PASS。
`protected_key_count`用十进制字符串避免JSON数值歧义。manifest parent/T必须和official manifest及
supplement一致；original/probe必须同policy/code/env，仅poison集合不同。canonical规则同§2.3。

### 2.5 BehaviorIndependentReviewReceiptV1 closed schema

严格对象只允许：

```json
{
  "schema_version": "qlib_peerlite_behavior_review_receipt_v1",
  "receipt_id": "<non-empty ASCII>",
  "review_authority_path": "<fixed relative path>",
  "review_authority_sha256": "sha256:<64 lowercase hex>",
  "review_authority_version": "<non-empty ASCII>",
  "authority_valid_from": "<UTC RFC3339>",
  "authority_valid_until": "<UTC RFC3339>",
  "reviewed_at": "<UTC RFC3339>",
  "review_scope": "M7_STATE_BEHAVIOR_QUALIFICATION",
  "official_behavior_manifest_sha256": "sha256:<64 lowercase hex>",
  "official_behavior_report_sha256": "sha256:<64 lowercase hex>",
  "parent_fixed_audit_content_sha256": "sha256:<64 lowercase hex>",
  "supplement_sha256": "sha256:<64 lowercase hex>",
  "aux_prefix_verification_sha256": "sha256:<64 lowercase hex>",
  "reviewer_context_id": "<non-empty ASCII>",
  "builder_context_id": "<non-empty ASCII>",
  "verdict": "PASS",
  "canonical_sha256": "sha256:<64 lowercase hex>"
}
```

unknown/null/float拒绝；`valid_from <= reviewed_at < valid_until`；reviewed_at晚于全部被引artifact
的durable publication time且早于envelope creation；reviewer与builder不同。authority
path/hash/version由future derived contract fixed slot给出，过期、parent substitution或self-
asserted authority均拒绝。canonical规则同§2.3。

### 2.6 SecurityLifecycleAvailabilityAuthorityV1

`md_security.LIST_DATE/DELIST_DATE`的冻结source certificate写明availability“不定时”，因此
**禁止**把事件日期当作vendor availability。future derived contract必须绑定唯一fixed slot：

```text
contracts/immutable/security_lifecycle_availability_authority_v1.json
```

其closed schema必须绑定DataYes source/version、LIST_DATE和DELIST_DATE各自的
`vendor_available_time`语义与证据SHA、有效期、issuer authority及independent validation receipt。
authority缺失、过期、版本不匹配或不能逐row确定`available_time<=prediction_time`时，
qualification创建前FAIL/HOLD；不得降级、推断或用event date替代。当前该slot不存在，所以当前
只能测试fail-closed validator，不能生成qualification。

### 2.7 Envelope exact binding

envelope必须exact绑定fixed audit、每T的official manifest、supplement、aux verifier和review
receipt、security lifecycle authority以及所有trust-anchor hashes；数量和T一对一。外部trust
anchors来自derived contract fixed slots，不从envelope自报。

## 3. Market-state join、standardizer 与 Gate capability

### 3.1 State product and exact join

state schema的列必须**恰好**按以下顺序：

```text
mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20
```

qualified daily product以timezone-naive normalized date为键，每日恰好一行，无重复、缺失或
nonfinite。若上游为按股票broadcast representation，则归约前同日每行四列必须逐列
`float64.tobytes()`相同；否则FAIL，不允许取first/mean。

每个model sample date必须exact匹配一条state date；禁止as-of、前填、后填或跨日回退。上述schema、
日期、同日bytes、覆盖率和finite检查必须在创建Dataset、写journal/output或消耗candidate/fit前完成。

### 3.2 DailyStandardizerV1

每fold只取排序去重后的training dates，每date一条四列state，转换为native float64。逐列：

```text
mean = arithmetic_mean(train_unique_dates, float64)
scale = sqrt(arithmetic_mean((x - mean)^2, float64))  # population std, ddof=0
if scale < 1e-12: scale = 1.0
z = (x - mean) / scale
```

valid/test只transform，不参与统计。mean、scale均以float64 canonical hex保存；standardized output
在进入Gate前显式cast float32。checkpoint绑定四列exact order、mean/scale、sorted unique training
date digest、date count、standardizer schema/code SHA。reload重算并exact比较所有binding。

### 3.3 唯一 Gate capability

五个generic `market_gate=True`入口永久fail-closed。唯一create：

```text
M7PeerLiteGateFactory.create_verified(
    derived_contract,
    qualification_envelope,
    screening_prerequisites,
    live_authority
)
```

唯一reload：

```text
M7PeerLiteGateFactory.load_verified_checkpoint(
    path,
    derived_contract,
    qualification_envelope,
    screening_prerequisites,
    live_authority
)
```

factory产生内部`_VerifiedM7GateCapability`；普通bool/state/token不能走支持路径。固定结构：

```text
state[4]
 -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
 -> gate=2.0*output
encoder_hidden *= gate[date,1,64]
 -> assignment -> prototypes -> attention -> relative head
```

注入点在encoder后、assignment前；K16、hidden64、heads4及M6其余超参不变，O(NK)。
checkpoint必须绑定derived contract、qualification/prerequisite/live-authority、Gate code/结构、
state product/schema/join规则、standardizer全部字段、model config、feature names、fold/data/
runtime/code hashes。special reload逐项复核后才load。

## 4. CCC完整执行合同

原生prediction/target均float32；CCC内部：

```text
p64=prediction.float64; y64=target.float64
mu_p=mean(p64); mu_y=mean(y64)
var_p=mean((p64-mu_p)^2); var_y=mean((y64-mu_y)^2)
cov=mean((p64-mu_p)*(y64-mu_y))
ccc=2*cov/(var_p+var_y+(mu_p-mu_y)^2+float64(1e-8))
loss_date=1-ccc
loss_batch=arithmetic_mean(loss_date)
```

population denominator、variance correction=0；singleton为float64 MSE；loss return float64并
backprop到float32参数。training/validation/early-stop同定义，strict `<`更新，tie保留最早，
nonfinite立即失败。execution spec/checkpoint绑定全部dtype/reduction/epsilon字段；CPU oracle
rtol=atol=1e-12，CUDA以checkpoint/score exact replay为最终判据。

## 5. First-event admission 与 screening

任何candidate/fit/claim前，必须绑定PASS的immutable screening prerequisite：

- downstream frozen cost spec + 当前有效官方/券商fee receipt；
- downstream frozen benchmark spec + 独立source certificate/PIT path；
- weekly mapper、calendar、unfilled/capacity/cost、metric implementation SHA；
- M6 K16 benchmark predictions/portfolio hashes；
- 2018–2024 folds与final-OOS seal；
- independent validator receipt；
- 本文件§2完整qualification与§3 state/join/standardizer validation。

当前cost/benchmark/security-lifecycle authority仍PLANNED或缺失，因此first event禁止。

每分支相对同一M6 K16 benchmark要求：base-cost combined weekly net-excess IR delta>0、
至少5/7 folds delta正、stress-cost combined net-excess return>=0。两分支都通过也不自动
授权组合。

## 6. 测试owner与结论

M6.5只实现generic拒绝、qualification closed-schema validator、state join/standardizer纯函数及
预算/generation contract tests。factory神经网络、CCC训练、Gate训练属于`M7_IMPLEMENTATION`；
真实fit/screening属于`M7_REAL_ACCEPTANCE`。

结论：`READY FOR INDEPENDENT DESIGN REVIEW / M7 NOT AUTHORIZED`。
