# M7 CCC / 市场状态 Gate 设计 v3

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- 风险：`R3`
- 架构：`evidence/m6_5_pre_m7/architecture_confirmation_v28.md`
- 冻结研究契约：`contracts/immutable/research_contract_pit_v2.json`
- 历史起点：M6 `PASS`，唯一 close prefix 为 `6 candidate / 44 fit`
- 取代：v2 作为当前 M7 design-only subject；v2 与其历史审查保留。

本文件只满足 M6.5 要求的当前 M7 设计工件，不创建 derived contract、execution authority、
runner、checkpoint 或模型结果，不运行真实 fit，不改变预算，不访问 final-OOS。

## 1. 固定研究问题

M7 只允许相对冻结 `PEERLITE_K16_MSE` 的两个隔离增量：

1. `PEERLITE_K16_CCC`：只改变 loss、validation 与 early-stop criterion；
2. `PEERLITE_K16_MSE_GATE`：只增加经独立 PIT 审计的四维 T-known daily market state。

两个分支不能互相共享结果来改参数。`CCC+Gate` 只有两个隔离分支均通过预注册工程门和科学
screening、且另一个用户批准的预算/执行契约生效后才可成为新候选；当前不得创建或运行。

## 2. 输入与 Gate 边界

- 监督输入、标签、滚动折、K=16、hidden=64、heads=4、dropout、optimizer、seed 7 与 M6
  K16 基线保持一致。
- Gate 只能消费未来 `PIT_QUALIFIED` 的 `MarketStateProduct`，其唯一来源是
  `PreOOSAuxSnapshotV1 -> T-known state builder`。
- legacy Qlib `market`、M3 supervised matrix、label/execution/purge/embargo 或 T 后事件不能
  构造 state。
- 每个 model date 必须 exact join 一个 state date；同日所有 instrument 的四维 state
  byte-identical。缺日、重复、nonfinite 或 schema/order 不符在 fit 前失败。
- state standardizer 只用 unique training dates 拟合；每维 `scale < 1e-12` 时固定为 `1.0`。
  valid/test 只 transform。
- Gate 输入顺序固定：
  `mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20`。

未来 `M7PeerLiteGateAdapter` 是唯一可开放 Gate 的入口；现有通用
`market_gate=True` 永久 fail-closed，不能因 M6.5 PASS 被重新启用。

## 3. CCC 精确语义

每个日期有效股票的 Lin CCC：

```text
ccc = 2 * cov(y, p) /
      (var(y) + var(p) + (mean(y) - mean(p))^2 + 1e-8)
loss_date = 1 - ccc
loss_batch = arithmetic mean(loss_date)
```

mean/variance/covariance 使用 population denominator。日期只有一个有效样本时退化为该日
MSE。training、validation、early stopping 使用相同定义；NaN/Inf 立即失败；checkpoint 只在
严格更小 validation loss 时替换，完全相等保留最早 epoch。

## 4. 预算与事件

当前冻结 cap 是 `27 candidate / 60 model fit`；M6 close 后只剩 16 fit。M7 第一阶段精确
分配如下，不得挪用：

| candidate | candidate events | fit events | 内容 |
| --- | ---: | ---: | --- |
| CCC isolated seed 7 | 1 | 8 | 7 rolling folds + 1 deterministic refit |
| Gate isolated seed 7 | 1 | 8 | 7 rolling folds + 1 deterministic refit |

因此第一阶段结束上限为 `8 candidate / 60 fit`。每个
`CANDIDATE_EVALUATION_STARTED/MODEL_FIT_STARTED` 在真实标签参与前由未来 live authority
登记并永久计数；失败、中断、异常也计数。M6.5 synthetic authority不能被升级为 live。

组合、额外 seeds、确认和 M8 refit 在当前预算内都是 `HOLD`。若未来要继续，必须在不看
final-OOS 的条件下另立用户批准的预算 CR 和 derived contract；不得把未触发配额、失败 fit
或 deterministic refit 解释为可复用预算。

## 5. 工程门与科学 screening

工程 PASS 要求：frozen execution spec、qualified input/state manifests、每折 checkpoint、
exact replay、统一 score schema、Recorder independent readback、账本/claim/terminal receipts
和 independent verifier 全部通过。工程 PASS 不代表有效 Alpha。

科学 screening 在固定七个 2018–2024 development rolling folds上，相对同一冻结 M6 K16
benchmark，使用相同 weekly mapper、CSI800 PIT universe、执行规则和
`contracts/cost_spec.json`：

1. base-cost combined development weekly net-excess IR delta `> 0`；
2. 至少 `5/7` folds 的 base-cost net-excess IR delta 为正；
3. stress-cost combined development net-excess return `>= 0`；
4. 所有产物标记 `PRE_FINAL_OOS_SCREENING_ONLY`。

指标或任一分支失败时只能 `HOLD/REJECT`，不能改 state、loss、模型、成本、阈值、universe
或再加试验补救。两个隔离分支都通过也不自动授权组合。

## 6. 生命周期与可复现性

- future live run 必须绑定 M6.5 PASS、derived contract、PIT-qualified state、M6 replay PASS、
  固定 authority slot、current ledger head 和 event plan；
- event receipt 后只有 canonical source-event claim slot 的 fresh `CREATED` 能放行一次 fit；
- crash 后已 claim attempt 永久消费；stale-tail run必须 `ABANDONED`；
- `predictions.parquet` 仍输出
  `datetime,instrument,score,model_id,fold_id`，唯一键、finite score、canonical order；
- checkpoint 绑定模型/CCC/Gate/state-standardizer/data/fold/runtime/code identity；
- final-OOS 在 M8 freeze 前保持物理与逻辑封印。

## 7. 失败与结论

任何 contract、PIT、state、budget、claim、runtime、checkpoint、replay、metric 或审查失败都
保留 evidence 并停止，不修改 M6 历史。

结论：`READY FOR CURRENT INDEPENDENT DESIGN REVIEW / M7 NOT AUTHORIZED`。本设计只定义未来
M7 的最小可证伪路径，不是执行许可。

