# M7 CCC / 市场状态 Gate 设计 v5

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- 风险：`R3`
- 架构：`architecture_confirmation_v28.md`
- 研究契约：`contracts/immutable/research_contract_pit_v2.json`
- 起点：M6 `PASS`，唯一close prefix `6 candidate / 44 fit`
- 取代：M7 v4；历史版本与失败审查保留。

本文件不创建derived contract、qualification/prerequisite bundle、live authority、runner或
checkpoint，不运行fit，不改变预算，不访问final-OOS。

## 1. 候选与预算

只允许两个隔离候选：

| candidate | 唯一变化 | events |
| --- | --- | --- |
| `PEERLITE_K16_CCC` | CCC loss/validation/early-stop | 1 candidate + 7 folds + 1 deterministic refit |
| `PEERLITE_K16_MSE_GATE` | verified 4D market state | 1 candidate + 7 folds + 1 deterministic refit |

当前cap `27 candidate / 60 fit`；最大从`6/44`到`8/60`。组合、额外seed、确认和M8 refit要求
新用户预算CR，不能挪用失败/未触发配额。

## 2. MarketStateQualificationEnvelopeV2

唯一lineage：

```text
PreOOSAuxSnapshotV2
 -> MarketStateProductV2(INTEGRITY_BUILT_NOT_PIT_QUALIFIED)
 -> fixed PIT audit PASS
 -> behavior audit PASS
 -> immutable qualification envelope
```

validator必须同时验证，不得只看status：

### 2.1 Fixed PIT predicates

- target=`FULL_TRAINING_INPUT`；
- `pit_qualification=QUALIFIED`；
- `evidence_ceiling=PASS`；
- `execution_boundary=PRODUCTION_CLI`；
- `test_only_adapter=false`；
- 固定17项checks逐项`PASS`且count=17；
- audit manifest与report的exact content/file SHA一致；
- product/aux manifest、schema、logical digest、date range、contract/feature/policy/builder/
  verifier SHA与audit parent bindings一致；
- independent issuer不是builder identity。

### 2.2 Behavior predicates

- 四个固定behavior checks逐项`PASS`且count=4；
- original/poison source identity、mutation ledger、protected schema/key/value digests完整；
- behavior manifest、report/content/file SHA一致；
- exact parent绑定同一个fixed-audit-qualified product与policy/code；
- `test_only_adapter=false`，独立issuer不是builder/fixed-audit issuer。

外部trust anchors来自future derived contract固定slot，不能从envelope自报。任一predicate、
hash、parent或independence不符，dataset read/journal/output/checkpoint load/fit前拒绝。

## 3. 专用 Gate capability 与 checkpoint

五个generic `market_gate=True` 入口永久fail-closed。唯一支持路径：

```text
M7PeerLiteGateFactory.create_verified(
    derived_contract,
    qualification_envelope,
    screening_prerequisites,
    live_authority
)
```

factory验证全部固定slot/hash后产生内部 `_VerifiedM7GateCapability`。普通bool、state frame或
手工token不能调用支持constructor。cooperative Python边界不声称抵御恶意同进程代码。

固定结构和注入点：

```text
state[4]
 -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
 -> gate = 2.0 * sigmoid_output
encoder_hidden *= gate[date,1,64]
 -> assignment -> prototypes -> attention -> relative head
```

K16、hidden64、heads4及M6其余超参不变，复杂度O(NK)。state exact-date、同日一致；unique
training dates拟合standardizer，`scale<1e-12 -> 1.0`。

generic `PeerLiteModel.load_checkpoint()`继续拒绝Gate。唯一reload路径：

```text
M7PeerLiteGateFactory.load_verified_checkpoint(
    path,
    derived_contract,
    qualification_envelope,
    screening_prerequisites,
    live_authority
)
```

它重新产生capability，并验证checkpoint schema、state/envelope/prerequisite/contract/code
hash、Gate结构、standardizer、training-date digest与全部M6配置后才load state dict。

## 4. CCC完整数学与dtype

每个日期：

```text
p64 = prediction.float64
y64 = target.float64
mu_p = mean(p64)
mu_y = mean(y64)
var_p = mean((p64 - mu_p)^2)
var_y = mean((y64 - mu_y)^2)
cov   = mean((p64 - mu_p) * (y64 - mu_y))
ccc   = (2 * cov) /
        (var_p + var_y + (mu_p - mu_y)^2 + float64(1e-8))
loss_date = 1 - ccc
loss_batch = arithmetic_mean(loss_date)
```

输入/target原生float32；accumulation、epsilon和loss return为float64；variance correction=0。
singleton使用float64 MSE。training/validation/early-stop同定义；strict `<`更新，tie最早；
nonfinite失败。CPU oracle `rtol=atol=1e-12`，CUDA最终以checkpoint/score exact replay判断。

## 5. First-event screening prerequisites

任何candidate event、fit event或claim前，immutable
`M7ScreeningPrerequisiteBundleV1`必须PASS并被derived contract/live authority绑定：

- downstream frozen cost spec status=`FROZEN`及当前有效官方/券商费率receipt；
- downstream frozen benchmark spec status=`FROZEN`及独立source certificate/PIT path；
- weekly mapper、calendar、unfilled/capacity/cost和metric implementation SHA；
- M6 K16 benchmark predictions/portfolio artifacts；
- 2018–2024 folds和final-OOS seal；
- independent validator receipt。

当前cost/benchmark均PLANNED，所以M7未授权且不能消费第一个event。

## 6. Screening、生命周期与结论

相对同一M6 K16 benchmark，同时要求base-cost combined IR delta>0、至少5/7 fold delta正、
stress-cost combined net-excess return>=0。两个分支都通过也不自动授权组合。

future live worker必须直接持有M6.5规定的fenced execution lease，从claim到durable outcome；
下一个event要求全部前序event已有durable outcome。crash后attempt永久计数且不重放，只能使用
预注册retry attempt。

结论：`READY FOR INDEPENDENT DESIGN REVIEW / M7 NOT AUTHORIZED`。

