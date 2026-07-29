# M7 Bounded CCC and Market-State Gate Design V1

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 起点：M6 PASS，历史预算prefix `6 candidate / 44 fit`
- 最大未来预算：`8 candidate / 60 fit`

## 1. Two isolated candidates

未来M7只允许两个隔离候选：

| candidate | delta from M6 K16 |
| --- | --- |
| `PEERLITE_K16_CCC` | loss由MSE替换为CCC；结构与特征不变 |
| `PEERLITE_K16_MSE_GATE` | 加入小型market-state gate；loss仍MSE |

每候选固定1 candidate evaluation、7 rolling fold fits和1 deterministic refit，共2 candidate、
16 fits。任一失败/中断仍计数且该候选HOLD，无replacement。两候选不能共享checkpoint、早停结果
或训练统计。

## 2. CCC semantics

prediction/target输入float32；每个date截面内部以float64计算：

```text
mu_p = mean(p)
mu_y = mean(y)
var_p = mean((p-mu_p)^2)
var_y = mean((y-mu_y)^2)
cov = mean((p-mu_p)*(y-mu_y))
ccc = 2*cov / (var_p + var_y + (mu_p-mu_y)^2 + 1e-8)
loss_date = 1 - ccc
loss_batch = arithmetic mean(loss_date)
```

variance使用population denominator，不作Bessel correction。singleton date使用float64 MSE。
training、validation和early-stop使用同一loss；strict `<`才更新best，tie保留最早checkpoint；
nonfinite立即失败。checkpoint必须记录loss schema、epsilon、dtype、reduction、fold、seed、data/code
hash。

## 3. Market-state Gate semantics

Gate只接收通过M6.5验证的T-known日级四维state：

```text
mkt_trend_20,mkt_vol_20,mkt_turnover_20,mkt_amount_20
```

state按date唯一；只以当前fold的unique training dates拟合mean/scale，valid/test只transform；
`scale < 1e-12`时设为1.0。exact-date join，不允许前向填充、label-conditioned population或从模型
rows重新聚合。

结构固定：

```text
state[4] -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
gate = 2 * output
encoder_hidden = encoder_hidden * gate[date]
```

注入在encoder后、peer assignment前；K=16、hidden=64、heads=4，其他M6 K16配置不变，复杂度
保持O(NK)。checkpoint绑定state product/schema/columns、train-only standardizer、unique train-date
digest、model/data/runtime/code hashes。

## 4. Score, evaluation and promotion

两候选统一输出：

```text
(datetime,instrument) -> score
```

沿用冻结2018–2024七fold、相同seed、weekly top-10%、2%单股上限、5% ADV participation、
base/stress cost与M6 K16 benchmark。每候选晋级必须同时满足：

```text
base-cost combined weekly net-excess IR delta > 0
至少5/7 fold net-excess IR delta > 0
stress-cost combined net-excess return >= 0
无PIT、工程、复现或预算失败
```

筛选阶段固定seed；确认阶段种子集合仍为`{7,19,42,73,101}`，但确认fits需要后续单独预算和合同，
本M7初始预算不包含。

## 5. Combination trigger

只有CCC和Gate两者都独立通过全部门槛，才产生
`COMBINATION_ELIGIBLE_BUT_UNBUDGETED`决策。当前8/60上限没有第三候选的8个fits容量，因此不得
运行CCC+Gate组合；组合必须先由新change request冻结候选、预算、seed和判据。任一单模块失败则
删除该增强，不增加复杂度补救。

## 6. Preconditions and boundary

任何M7 contract freeze或fit前仍要求：

- M6.5全部quality stages PASS；
- market-state product及PIT/future-poison证据PASS；
- cost、benchmark、portfolio mapper和final-OOS seal refs冻结；
- trial ledger exact 6/44 prefix及8/60 cap可验证；
- M7 execution spec和derived research contract另行冻结。

本文不创建这些authority，不运行fit，不访问final-OOS，不改变预算。
