# M7 CCC / 市场状态 Gate 设计 v4

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- 风险：`R3`
- 架构：`architecture_confirmation_v28.md`
- 冻结研究契约：`contracts/immutable/research_contract_pit_v2.json`
- 历史起点：M6 `PASS`，唯一 close prefix `6 candidate / 44 fit`
- 取代：M7 v3；v3与其 `NEEDS_CHANGES` 审查永久保留。

本文件不创建 derived contract、qualification envelope、screening prerequisite、live authority、
runner或checkpoint，不运行fit，不改变预算，不访问final-OOS。

## 1. 固定候选与预算

只允许相对冻结 `PEERLITE_K16_MSE` 的两个隔离候选：

| candidate | 唯一变化 | candidate events | fit events |
| --- | --- | ---: | ---: |
| `PEERLITE_K16_CCC` | loss/validation/early-stop | 1 | 7 folds + 1 deterministic refit |
| `PEERLITE_K16_MSE_GATE` | verified 4D market state | 1 | 7 folds + 1 deterministic refit |

当前 cap `27 candidate / 60 fit`；第一阶段结束最大 `8/60`。组合、额外seed、确认、M8 refit
全部HOLD，必须有新的用户预算CR。失败/中断/异常的started event永久计数。

## 2. MarketStateQualificationEnvelopeV1

Gate的唯一数据 lineage：

```text
PreOOSAuxSnapshotV2
 -> MarketStateProductV2(INTEGRITY_BUILT_NOT_PIT_QUALIFIED)
 -> independent fixed PIT audit PASS
 -> independent future-poison behavior audit PASS
 -> MarketStateQualificationEnvelopeV1
```

qualification envelope是immutable downstream object，绑定：

- exact aux/product manifest及全部file SHA、canonical logical digests、date range与schema；
- `MarketStatePolicyV3`、research contract、feature spec与builder/verifier code SHA；
- fixed PIT audit schema/status=`PASS`、receipt/content SHA；
- behavior audit schema/status=`PASS`、original/poison identities、mutation ledger、protected
  key/value digests和receipt SHA；
- independent issuer identity、envelope canonical SHA与固定slot。

字符串状态或builder自签receipt没有能力。任一引用、schema、hash、日期或PASS predicate不符，
factory在dataset read/journal/output/fit前拒绝。

## 3. 唯一 Gate capability

五个generic `market_gate=True` 入口永久fail-closed。future唯一支持路径是
`M7PeerLiteGateFactory.from_verified_envelope(derived_contract, envelope)`：

1. 验 M6.5 PASS、derived contract、qualification envelope、screening prerequisites、
   live authority与exact code identity；
2. 产生内部 `_VerifiedM7GateCapability`，绑定上述canonical hashes；
3. 使用非public constructor创建固定 K16 MSE Gate model；
4. 普通bool、任意state frame或手工token不能走支持路径。

该capability是cooperative Python API边界，不宣称抵御恶意同进程代码。public constructor和
checkpoint loader仍拒绝generic Gate。

固定网络注入：

```text
state[4]
 -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
 -> gate = 2.0 * sigmoid_output
encoder_hidden = encoder_hidden * gate[date,1,64]
 -> peer assignment/prototypes/attention/head
```

注入点在encoder后、assignment前。K=16、hidden=64、heads=4及M6其余超参不变，复杂度O(NK)。
checkpoint schema必须绑定 capability/envelope/derived-contract hash、state列顺序、unique
training-date standardizer mean/scale、training-date digest、Gate code hash/structure和所有
M6基线配置。`scale < 1e-12 -> 1.0`。

## 4. CCC numeric contract

model prediction与target原生float32；仅计算CCC时二者显式cast到`torch.float64`。每日期
mean/variance/covariance、batch date mean与epsilon `float64(1e-8)`均float64；population
denominator；singleton用float64 MSE；loss返回float64并直接backprop至float32参数。validation
和early-stop完全相同；strict `<`更新checkpoint，tie保留最早epoch；nonfinite立即失败。

execution spec/checkpoint绑定：

```text
input_dtype=float32
target_dtype=float32
accumulation_dtype=float64
epsilon_dtype=float64
loss_return_dtype=float64
variance_correction=0
date_reduction=arithmetic_mean
```

CPU手算测试绝对/相对容差均`1e-12`；CUDA acceptance以checkpoint exact replay和score exact
digest为最终oracle。

## 5. ScreeningPrerequisiteBundleV1

任何M7 candidate event、fit event或claim前，fixed live authority必须绑定一个immutable
bundle，且validator PASS：

- `contracts/cost_spec.json` 的下游冻结版本，status=`FROZEN`，绑定当前生效官方/券商费率
  receipt、base/stress slippage和全部费用公式；
- `contracts/benchmark_spec.json` 的下游冻结版本，status=`FROZEN`，绑定独立source
  certificate、PIT constituent/weight/return path和fallback禁止规则；
- weekly mapper、execution calendar、unfilled-order、capacity/cost和metric implementation
  code SHA；
- frozen M6 K16 benchmark prediction/portfolio artifact hashes；
- development folds 2018–2024与final-OOS seal；
- independent validator PASS receipt。

当前cost/benchmark spec仍是PLANNED，所以没有这个bundle；结论只能是M7未授权，且不得消费
第一个fit。

## 6. Screening与生命周期

在相同七个development folds、weekly mapper、universe、execution和cost下，相对M6 K16：

1. base-cost combined weekly net-excess IR delta `>0`；
2. 至少`5/7` fold delta正；
3. stress-cost combined net-excess return `>=0`；
4. 产物标记 `PRE_FINAL_OOS_SCREENING_ONLY`。

future live run必须使用M6.5定义的registration/event/claim/outcome状态机和execution lease。
claim后crash产生`CLAIMED_INTERRUPTED`，永久消费但不重放；下一步只能走plan中预注册的retry
attempt。两个隔离分支都通过也不自动授权组合。

## 7. 结论

`READY FOR CURRENT INDEPENDENT DESIGN REVIEW / M7 NOT AUTHORIZED`。这是未来可证伪设计，不是
实现或执行许可。

