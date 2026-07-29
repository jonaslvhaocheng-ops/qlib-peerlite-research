# M7 CCC / 市场状态 Gate 设计 v7

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- 架构：`architecture_confirmation_v28.md`
- 冻结研究契约：`contracts/immutable/research_contract_pit_v2.json`
- 起点：M6 `6 candidate / 44 fit`
- 当前上限：`27 candidate / 60 fit`
- 取代：M7 v6；历史版本与失败审查保留。

本文件不创建 derived contract、qualification、prerequisite、authority、runner或checkpoint，
不运行fit，不改变预算，不访问final-OOS。

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

## 2. MarketStateQualificationEnvelopeV4

唯一lineage：

```text
PreOOSAuxSnapshotV2
 -> MarketStateProductV2
 -> fixed PIT audit PASS
 -> one or more official behavior manifests
 -> independent behavior review receipts
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

### 2.2 Official behavior list

每个T对应一个独立official request/manifest；不向closed schema添加字段。每个manifest：

- manifest_version=`pit_behavior_manifest_v1`；
- spec_version=`pit_behavior_spec_v1`；
- probe_type=`FUTURE_POISON`；
- status=PASS、certification_status=`NOVEL_CANDIDATE`；
- exact IDs `B001,B002,B003,B004`，无重复无额外、全部PASS；
- 一个scalar `protection.protected_through=T`；
- original/probe lineage、perturbation ledger、protected key/value digest、content/report/file SHA；
- exact parent fixed-audit content SHA。

envelope绑定由future derived contract冻结的unique horizon list；manifest按
`protected_through`升序且一对一覆盖，不多不少。逐字段availability解释放在独立
`BehaviorAvailabilitySupplementV1`，它绑定official manifest/ledger SHA但不修改official bytes。

每个manifest另有`BehaviorIndependentReviewReceiptV1`，由derived contract固定review
authority发布，绑定manifest content/report/file SHA、parent audit、supplement SHA、reviewer
identity与PASS。reviewer不同于state product builder；官方artifact未提供执行者identity时不作
无法验证的“与audit issuer不同”声明。

外部trust anchors来自derived contract fixed slots，不从envelope自报。

## 3. 唯一 Gate capability

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
state product/schema/列顺序、daily standardizer mean/scale、unique training-date digest、
model config、feature names、fold/data/runtime/code hashes。state standardizer只以unique training
dates拟合，valid/test只transform；`scale<1e-12 -> 1.0`。special reload逐项复核后才load。

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
- independent validator receipt。

当前cost/benchmark仍PLANNED，因此first event禁止。

每分支相对同一M6 K16 benchmark要求：base-cost combined weekly net-excess IR delta>0、
至少5/7 folds delta正、stress-cost combined net-excess return>=0。两分支都通过也不自动
授权组合。

## 6. 测试owner与结论

M6.5只实现generic拒绝、qualification validator和预算/generation contract tests。
factory/CCC/Gate属于`M7_IMPLEMENTATION`；真实fit/screening属于`M7_REAL_ACCEPTANCE`。

结论：`READY FOR INDEPENDENT DESIGN REVIEW / M7 NOT AUTHORIZED`。

