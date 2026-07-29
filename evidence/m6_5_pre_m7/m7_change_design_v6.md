# M7 CCC / 市场状态 Gate 设计 v6

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- 起点：M6 `6 candidate / 44 fit`
- 当前cap：`27 candidate / 60 fit`
- 取代：M7 v5；历史版本保留。

本文件不创建或运行任何M7对象。

## 1. 候选、预算与失败

仅两个隔离候选，各1 candidate、7 folds+1 deterministic refit，共2 candidate/16 fits，最大
到`8/60`。当前预算**没有replacement fit**：

- 任一fit `FAILED`或`CLAIMED_INTERRUPTED`，对应分支立即HOLD；
- run terminal将剩余该分支event标UNUSED；
- 不启动retry attempt；
- replacement、组合、额外seed、确认、M8 refit都要求新用户预算CR。

因此当前plan是无条件线性events，不含conditional retry或skip后继续。

## 2. QualificationEnvelopeV3

lineage固定为PreOOSAuxSnapshotV2→MarketStateProductV2→fixed audit→behavior audit→envelope。

### 2.1 Fixed audit exact contract

manifest schema=`pit_audit_manifest_v1`，且：

- status=PASS、pit_qualification=QUALIFIED、evidence_ceiling=PASS；
- claim=`MARKET_RECONSTRUCTIBLE`；
- contract_binding.execution_boundary=`PRODUCTION_CLI`；
- contract_binding.test_only_adapter=false；
- request scope=`FULL_TRAINING_INPUT`；
- exact check IDs，无重复无额外，全部PASS：

```text
I001 I002 S001 T001 T002 T003 U001 U002 C001 M001 A001 H001
Q001 Q002 Q003 L001 L002
```

- manifest content/report/file SHA和product/aux/contract/feature/policy/code parent bindings一致。

### 2.2 Official behavior exact contract

manifest_version=`pit_behavior_manifest_v1`、spec_version=`pit_behavior_spec_v1`、
status=PASS、certification_status=`NOVEL_CANDIDATE`，exact IDs无重复无额外、全部PASS：

```text
B001 B002 B003 B004
```

behavior manifest绑定original/probe lineage、perturbation ledger、protected_through、key/value
digests、content/report/file SHA及exact parent fixed audit。

`test_only_adapter=false`和`PRODUCTION_CLI`只在parent fixed PIT manifest的contract_binding验证，
不要求behavior manifest臆造这些字段。

另有外部`BehaviorIndependentReviewReceiptV1`，由derived contract固定review authority产生，
绑定behavior content/report/file SHA、parent audit content SHA、reviewer identity与verdict PASS。
它不改官方manifest；reviewer必须不同于state product builder，fixed-audit/behavior执行者若
官方artifact没有issuer字段则不作无法验证的identity声明。

外部trust anchors来自derived contract fixed slots，不从envelope自报。

## 3. Gate与CCC

generic Gate五入口永久拒绝；专用factory create/reload验证derived contract、QualificationV3、
screening prerequisites和live authority。固定Gate：

```text
state4 -> Linear(4,64)->GELU->Linear(64,64)->Sigmoid
gate=2*output
encoder_hidden*=gate
```

在assignment前注入；K16/hidden64/heads4不变。

CCC：

```text
p64=prediction.float64; y64=target.float64
mu_p=mean(p64); mu_y=mean(y64)
var_p=mean((p64-mu_p)^2); var_y=mean((y64-mu_y)^2)
cov=mean((p64-mu_p)*(y64-mu_y))
ccc=2*cov/(var_p+var_y+(mu_p-mu_y)^2+float64(1e-8))
loss_date=1-ccc
loss_batch=mean(loss_date)
```

singleton float64 MSE；nonfinite fail；strict `<` early stop；tie earliest。

## 4. First-event admission与测试owner

任何event前必须有frozen cost+fee receipt、benchmark+source certificate、mapper/metric hashes、
M6 artifacts、final-OOS seal和independent prerequisite PASS。当前均不齐，所以M7未授权。

M6.5只实现contract-only拒绝/validator测试；factory、CCC、Gate、真实screening属于未来
M7_IMPLEMENTATION/REAL_ACCEPTANCE。

结论：`READY FOR INDEPENDENT DESIGN REVIEW / M7 NOT AUTHORIZED`。

