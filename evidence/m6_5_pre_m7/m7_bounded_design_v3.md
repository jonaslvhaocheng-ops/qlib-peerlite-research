# M7 Bounded CCC and Market-State Gate Design V3

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 取代：`m7_bounded_design_v2.md`
- 起点/上限：M6 `6/44`；未来初筛最大`8/60`。

## 1. Pre-fit authority and isolated identities

唯一BudgetLimitBinding是
`contracts/changes/m7_initial_screen_budget_binding_v1.json`，content SHA
`8937e019122b0009a92ac17ba1ad52ffd63be856e4a3faf44b44784ee917b275`；其file SHA由closure固定。
该文件本身不授权执行。未来derived contract通过独立quality gate后，必须在任何journal byte或fit
前绑定：

```text
budget binding
market-state product/source manifest/PIT parent/calendar/builder script+library
weekly portfolio mapper/trading calendar/benchmark PIT product
base+stress costs/unfilled-order+participation+cap rules
M6 K16 benchmark predictions/metric implementation/fold definition/final-OOS seal
```

每项为exact path/file/content hash；state六项必须等于
`MarketStateAuthorityBindingV1`。缺失、替换或derived-contract hash drift时0 event、0 fit。

seed固定7。候选仅：

```text
PEERLITE_K16_CCC
PEERLITE_K16_MSE_GATE
```

每候选1 evaluation、7 rolling fits和1 deterministic refit；exact fit IDs已冻结在budget binding。
refit只重复wf_2018相同数据/config/seed/checkpoint selection，必须scores、checkpoint bytes、
selected epoch及date-order digest bitwise exact；只作工程复现，不进入screen。失败/中断计预算且
HOLD，0 replacement。

## 2. One complete date per optimizer step CCC

model input float32，objective全部binary64。每个optimizer step必须exact一个完整date截面；禁止一
step多date、拆date、跨date gradient accumulation。每epoch dates按normalized date严格升序，
无PRNG、无shuffle；每date每epoch恰一次。checkpoint必须绑定：

```text
train_date_order_sha256,valid_date_order_sha256,one_date_per_step=true,
sampler_rule=ASCENDING_COMPLETE_DATE_NO_SHUFFLE,epsilon=1e-8,
input_dtype=float32,objective_dtype=float64,reducer_version
```

date-order digest preimage为每个`YYYY-MM-DD` ASCII前置8-byte big-endian length后连接。每date：

```text
mu_p=left_fold_mean(p); mu_y=left_fold_mean(y)
var_p=left_fold_mean((p-mu_p)^2)
var_y=left_fold_mean((y-mu_y)^2)
cov=left_fold_mean((p-mu_p)*(y-mu_y))
ccc=2*cov/(var_p+var_y+(mu_p-mu_y)^2+1e-8)
loss=1-ccc
```

行按NFC instrument UTF-8稳定排序；所有算术每操作舍入binary64，使用component V3 reducer。
singleton使用binary64 MSE。epoch train/valid objective为date loss按升序相同left-fold mean。
validation无shuffle；strict `<`更新best，tie保留最早；nonfinite立即FAIL。

## 3. Gate state alignment and statistics

Gate columns exact：

```text
mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20
```

model rows先验证`(date,instrument)`唯一。state product date唯一；exact-date many-to-one join后，
同date每只股票四值byte-identical且无cross-date shift/missing/extra。股票顺序置换后反置换输出
必须bitwise一致。

只使用fold unique train dates升序，每date等权，对每列使用V3 binary64 left-fold计算population
mean和`std(ddof=0)`；`std < 1e-12 -> binary64(1.0)`。mean/scale以column order的float.hex
canonical JSON绑定train-date SHA、state product及source manifest SHA。valid/test只transform，
不refit、不fill。

结构固定：

```text
state[4] -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
gate=2*output
encoder_hidden*=gate[date]
```

注入encoder后、assignment前；K16/hidden64/heads4及M6其余配置不变，O(NK)。checkpoint绑定
state authority、stats/date digest、model/data/runtime/code和budget binding。

## 4. Exact weekly screen

对每周w：

```text
strategy_net_return_w = realized portfolio return - all frozen costs
benchmark_return_w = frozen benchmark total return
excess_w = strategy_net_return_w - benchmark_return_w
```

每fold weeks由calendar exact覆盖、升序唯一、无missing；跨fold按date concat不得重叠，每周等权。
若n<2或sample std(ddof=1)=0则FAIL：

```text
IR = mean(excess_w) / std(excess_w,ddof=1) * sqrt(52)
combined net-excess =
  prod_w(1+strategy_net_return_w) / prod_w(1+benchmark_return_w) - 1
```

return `<=-1`非法。candidate `SCREEN_PASS` iff：

```text
base-cost combined IR(candidate)-IR(M6_K16) > 0
至少5/7 folds的IR delta > 0
stress-cost combined net-excess >= 0
PIT/工程/refit/budget全部PASS
```

0不满足前两个`>`；exact 5/7满足；stress exact 0满足`>=`。

## 5. No promotion at 8/60

输出只能`SCREEN_PASS|HOLD`。不得`PROMOTE|COMBINATION_ELIGIBLE`。五seed确认、4/5 seeds、60%
folds、bootstrap及组合都需新CR、derived contract和非重叠预算。本文不授权fit、budget mutation、
test execution或final OOS。
