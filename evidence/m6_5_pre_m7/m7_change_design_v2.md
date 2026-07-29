# M7 CCC / 市场状态 Gate 变更设计 v2

状态：`REVISED_DRAFT — 不可实施，待独立设计审查`  
依据：初始设计的独立审查 `m7_design_review.md`。  
风险：`R3`。  
不变项：A 股日频、统一 `(datetime, instrument) -> score`、M3 supervised 输入、标签、
滚动切分、最终 OOS 封印和研究家族均不改变。

## 1. 问题、目标与非目标

M6 已经验证 MSE PeerLite 的历史工程链路，但不能安全地把旧 Qlib `market` 组交给 Gate：
它包含未来 label 字段，且成员行会被未来执行/label 条件筛除。M7 要实现两个隔离的真实
研究增量：

1. `PEERLITE_K16_CCC`：仅将优化/验证准则改为预定义 CCC。
2. `PEERLITE_K16_MSE_GATE`：仅把预定义 4 维 T-known daily state 注入 K16/MSE PeerLite。

非目标：搜索状态维度/公式、K、网络宽度、heads、loss 权重或成本参数；访问 2025+；文本、
LLM、分钟、高频、SAM、多任务；以及任何实盘或“Alpha 已成立”结论。

M7 可以在已经封闭的 2018–2024 开发滚动测试折上，按冻结组合/成本规范计算**开发期**科学
晋级指标；这不是最终 OOS，也不能修改候选、参数或阈值。M8 才能一次性打开最终 OOS。

## 2. 已知证据与可选方案

| 方案 | 结果 |
| --- | --- |
| 从 M3 supervised matrix 聚合 state | 拒绝：成员受 T+1/T+5 label/execution/action 过滤，PIT 不成立 |
| 修改旧 `market` 组、删两列 | 拒绝：历史 M6 路径被混淆，且不能修复 future-conditioned membership |
| 建立独立 T-known state population，再按 date join M3 rows | 采用：PIT 语义、回退与审计边界明确 |

## 3. 新数据产品：market_state_population

### 3.1 输入与资格

从同一 sealed raw snapshot 重建每个日期 `T` 的 `U_state(T)`。一行可进入 state population 当且
仅当下列条件均在 T 收盘预测时已知：

- 是历史 PIT CSI800 成分、上市至少 60 个合格交易日、未退市；
- T 时已知的 special-status 不为禁止/未知；
- 原始价格域有效，四个 state-source causal features 均有限；
- feature corporate-action mask 在 T 已知的窗口规则内有效；
- date 位于预最终 OOS开发期且 key 唯一。

明确**不允许**把下列字段/筛选用作 state population 条件或产物列：`label`、`label_open`、
`label_close`、`label_start/end`、T+1 开盘涨跌停、execution halt、label-cross-action、
label availability、purge/embargo、任何 T 后 event。M3 supervised matrix 可以在后续 model
阶段有这些标签性筛选，但它绝不是 `U_state(T)` 的来源。

### 3.2 固定 daily state

`U_state(T)` 排序后逐日期聚合为：

| 列 | 公式 |
| --- | --- |
| `mkt_trend_20` | `mean(ret_mean_20)` |
| `mkt_vol_20` | `median(ret_std_20)` |
| `mkt_breadth_1d` | `mean(1[ret_1d > 0])` |
| `mkt_turnover_20` | `median(turnover_mean_20)` |

每份 state product 必须包含：日期、四个 state 值、`population_count`、排序 key-set SHA256、
state SHA256、source snapshot/feature-spec/code hash。没有任何 state source 行、非有限 state、
重复 key、缺失日期或不精确 date join 一律 fail-closed。

### 3.3 PIT 证据

在任何真实 M7 fit 前，派生契约绑定 state product，并新增：

- fixed audit：source fields、availability clocks、state-population predicates、key/count/state digest；
- behavior audit：扰动未来日期、同日某股的 future label、execution eligibility 或 future action，
  过去及当日 `state` 必须 byte-identical；
- join audit：每个 M3 supervised date 精确对应一个 state date，且所有 model rows 同日 state
  完全相同。

## 4. 模型与接口

### 4.1 强制 M7 wrapper

`m7_peerlite.py` 为必需组件，不可只复用现有 row-level standardizer：

1. 从 Dataset 的 `market_state` col_set 读出广播行，按 date 严格验证 exact equality；
2. 只抽取 unique training dates 拟合 `DailyMarketStateStandardizer`；
3. 对 valid/test 仅 transform；按 date 精确 join/broadcast回各股票；
4. checkpoint 保存 state schema/order、daily mean/scale、training-date digest、state product hash；
5. 缺 state、NaN/Inf、维度错、重复/非一致行、日期错配均抛出可审计错误。

Gate 输入固定为 4 维，`MarketStateGate` 输出 `(0,2)` gate；复杂度仍是 O(NK)，不建立 N×N
股票对。Gate 分支采用 MSE，其余网络结构、K=16、hidden=64、heads=4、dropout、batch size 与
M6 K16 基线固定一致。

### 4.2 CCC 的完整冻结语义

`PEERLITE_K16_CCC` 的每日期 valid-stock loss 为 Lin CCC 的 `1 - ccc`：`eps=1e-8`，population
mean/variance/covariance，batch objective 是日期 loss 的算术平均。只有一个有效股票时退化为
该日期 MSE。validation 和 early stopping **同样**使用这一定义；NaN/Inf 立即 fail，最优
checkpoint 仅在严格 `<` 改善时更新（平局保留最早 epoch）。这些规则、loss 名称、epsilon、
reduction、fallback 和 checkpoint selection 都进入 immutable M7 execution spec。

## 5. 工程与科学晋级的分离

### 5.1 工程 PASS

每个分支必须有 qualified input/state manifest、frozen spec、每折 checkpoint、精确 replay、
score schema、Qlib Recorder independent readback、journal reconciliation 和 verifier PASS。
工程 PASS 不等于模型有效。

### 5.2 科学 screening PASS（开发期，预注册）

在同一 7 个 2018–2024 rolling test folds、同一 weekly portfolio mapper、同一 PIT universe、
同一交易约束及 `contracts/cost_spec.json` 的 base/stress cost 下，候选相对冻结
`PEERLITE_K16_MSE` 必须同时满足：

1. base-cost combined development weekly net-excess IR delta `> 0`；
2. 七个固定 fold 中 base-cost net-excess IR delta 为正的比例 `>= 0.60`（即至少 5/7）；
3. 压力成本下 candidate 的 combined development net-excess return 不低于 0；
4. 所有输出均标记 `PRE_FINAL_OOS_SCREENING_ONLY`，不得回写模型/阈值。

M7 promotion spec 必须将 portfolio mapper、cost-spec hash、benchmark score artifact hash、
日历、周频 rebalancing、未成交/成本规则与各计算公式一并冻结。若不能在 M7 前冻结这套
开发期评估规范，两个 isolated branch 只可获工程 PASS，组合永远 `HOLD`。

### 5.3 条件组合与确认

- 组合 `PEERLITE_K16_CCC_GATE` 只有 CCC 与 Gate 都取得 **工程 PASS + 科学 screening PASS**
  后才会有单独 execution spec，绝不由 runner 隐式激活。
- 所有允许分支完成后，若至少一项增量满足科学 screening PASS，按“base-cost combined IR
  delta 更高；完全相同则 `CCC_GATE > CCC > MSE_GATE`”选择唯一 confirmatory target。该
  选择规则在契约中固定；若无增量通过，则 M7 `HOLD`，不进入确认或组合。
- 该目标以额外固定 seeds `{19,42,73,101}` 各跑七折（seed 7 已是筛选证据）；确认产物只
  报告稳定性，最终研究结论仍由 M8 final OOS 给出。

## 6. 账本、崩溃与恢复

- run ID、output root 和 journal path 在启动前冻结；重复 run ID fail-closed。
- 每一 `CANDIDATE_EVALUATION_STARTED` / `MODEL_FIT_STARTED` 都拥有 deterministic
  `source_event_id`，先写入并 fsync run-local journal；`FIT_STARTED` 即消耗预算。
- `reconcile_trial_ledger.py` 使用 OS file lock 和 atomic append，将 journal 事件导入全局
  ledger；同 source ID+payload 重跑为 no-op，ID 冲突或 hash 前缀不符为 hard fail。
- 下一个真实 fit 的 preflight 必须验证所有该 run 的 started events 都已 reconciliation；
  crash/restart 只能从未开始 fit 继续，不能重用或遗漏已开始 fit。

## 7. 固定预算与事件分配

派生契约将 model-fit cap 从 60 改为 108，candidate cap 保持 27；它不扩大数据、模型家族或
OOS。配额不可互相挪用：

| 阶段 | fits | candidate event 规则 |
| --- | ---: | --- |
| 已消耗 M0–M6 | 44 | 当前 append-only 历史 |
| CCC isolated seed 7 | 8 | 1 screen candidate，7 folds + 1 deterministic refit |
| Gate isolated seed 7 | 8 | 1 screen candidate，7 folds + 1 deterministic refit |
| CCC+Gate 条件分支 | 8 | 仅双隔离 science PASS 后，1 screen candidate |
| 单一获选 target 确认 | 28 | 4 seed-specific confirmation candidates，各 7 folds |
| M8 计划内季度 refit | 6 | confirmatory fit，不可用于搜索 |
| M8 独立重跑 | 6 | verification fit，不可用于搜索 |
| 上限 | 108 | 未触发分支配额作废 |

若数据可用性使 M8 季度次数不是 6，必须在访问 final OOS 前建立新的派生预算契约；不可默认
挪用该缓冲。

## 8. 失败、可观测性与回退

state/PIT/audit/ledger/contract/checkpoint/verifier 任一失败都停止相应分支，保留 source manifest、
journal 和失败 receipt；不得通过调参、换 universe、改 state 或新增试验掩盖。日志记录 daily
population count/digest、state errors、ledger pre/post counts、资源和 OOS access count；无 raw
数据或秘密进 Git。回退是停止 M7 namespace；M6 历史工件不变。

## 9. 实施顺序（仍需 M6.5 通过）

1. 修复 M6 archival verification 与 ledger reconciliation，完成 red/green/mutation tests。
2. 冻结派生研究契约和 M7 state-product contract；不触碰 final OOS。
3. 在合成 product 上先完成 state population、state aggregation、M7 wrapper 与 CCC tests。
4. 对真实开发期 raw snapshot 构建 state population，执行增量 PIT fixed/behavior audit。
5. 冻结隔离 CCC/Gate specs、运行器与 promotion evaluation spec。
6. 执行 CCC 与 Gate；按上述预注册规则决定组合/HOLD；M8 继续封印。

## 10. 结论

`NEEDS_CHANGES`：v2 关闭了初始设计的三个 P1 方案缺口，但尚未经独立审查，也尚未产生
派生契约、M7 代码、真实训练或最终 OOS 证据。

