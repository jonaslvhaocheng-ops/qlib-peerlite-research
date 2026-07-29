# M7 Bounded CCC and Market-State Gate Design V2

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 取代：`m7_bounded_design_v1.md`
- 起点/上限：M6 `6/44`，未来筛选阶段最大`8/60`。

## 1. Isolated screening candidates and fit identities

fixed screening seed=`7`。候选：

```text
PEERLITE_K16_CCC
PEERLITE_K16_MSE_GATE
```

每候选1 evaluation + 7 rolling fold fits + 1 deterministic refit。fold fit ID exact
`<model_id>:screen:seed7:<fold_id>`。refit只重复`wf_2018`的相同train/valid/test、seed、配置和
checkpoint selection，fit ID exact`<model_id>:deterministic_refit:seed7:wf_2018`；其唯一目的为
工程复现，要求score bitwise exact，不进入筛选指标。失败/中断计预算且HOLD，0 replacement。

## 2. Complete-date CCC objective

输入float32；计算float64。每个date截面在一个epoch恰出现一次，绝不跨batch拆分。固定
`DateBatchSampler`以date升序列表和`seed+epoch`生成确定性permutation，再把一个或多个**完整**
date截面组成优化batch。每date：

```text
mu_p=mean(p); mu_y=mean(y)
var_p=mean((p-mu_p)^2); var_y=mean((y-mu_y)^2)
cov=mean((p-mu_p)*(y-mu_y))
ccc=2*cov/(var_p+var_y+(mu_p-mu_y)^2+1e-8)
loss_date=1-ccc
```

singleton date使用float64 MSE。batch loss是其中完整dates的等权mean；epoch training/validation
objective也是所有unique dates的等权mean，与date截面大小和batch packing无关。validation dates
升序、无shuffle。strict `<`更新best，tie保留最早；nonfinite立即FAIL。checkpoint记录sampler、
date digests、epsilon、dtype、reduction和best epoch。

## 3. Gate statistics and structure

Gate input exact四列：

```text
mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20
```

只使用fold unique training dates，按date升序，对每列float64计算population
`mean`和`std(ddof=0)`；每date等权一次。`std<1e-12 -> 1.0`。mean/scale以column order的
`float.hex` strings canonical JSON序列化并绑定unique train-date SHA。valid/test只transform，
不重新拟合；exact-date join，无fill。

结构：

```text
state[4] -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
gate=2*output
encoder_hidden*=gate[date]
```

注入encoder后、assignment前；K16/hidden64/heads4及M6其他配置不变，O(NK)。checkpoint绑定
state product/source manifest、columns、stats/date SHA、model/data/runtime/code hashes。

## 4. Exact screening metrics

未来derived contract在任何fit前必须提供下列exact `{path,file_sha256,content_sha256}` refs：

```text
weekly portfolio mapper
trading calendar
benchmark PIT product
base and stress cost specs
unfilled-order/participation/cap rules
M6 K16 benchmark predictions
metric implementation
2018-2024 fold definition
final-OOS seal
```

缺任一即0 event。对每周w：

```text
strategy_net_return_w = realized portfolio return - all frozen costs
benchmark_return_w = frozen benchmark total return
excess_w = strategy_net_return_w - benchmark_return_w
```

fold内week必须由calendar exact覆盖、升序唯一、无missing；跨fold按日期concat且不得重叠，每周等权。
IR若n<2或sample std(ddof=1)=0则FAIL，否则：

```text
IR = mean(excess_w) / std(excess_w,ddof=1) * sqrt(52)
```

combined net-excess return：

```text
prod_w(1+strategy_net_return_w) / prod_w(1+benchmark_return_w) - 1
```

任一return `<=-1`非法。每候选`SCREEN_PASS` iff：

```text
base-cost combined IR(candidate) - combined IR(M6_K16) > 0
至少5/7 folds的 IR(candidate)-IR(M6_K16) > 0
stress-cost combined net-excess return >= 0
全部PIT/工程/复现/预算检查PASS
```

严格边界：0不满足前两个`>`；exact 5/7满足count；stress exact 0满足`>=`。

## 5. No promotion at 8/60

本阶段输出只能是每候选`SCREEN_PASS|HOLD`。不得输出`PROMOTE`或
`COMBINATION_ELIGIBLE`。五seed `{7,19,42,73,101}`确认、4/5 seeds、60% folds和bootstrap规则
需要新的CR、derived contract及非重叠预算。只有该确认阶段PASS后，才可产生
`PROMOTE`；两模块都PROMOTE后才可产生`COMBINATION_ELIGIBLE_BUT_UNBUDGETED`，组合仍需第三个
CR。本文不授权fit、budget mutation或final-OOS。
