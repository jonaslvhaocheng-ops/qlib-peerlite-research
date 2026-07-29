# M7 CCC / 市场状态 Gate 变更设计

状态：`DRAFT — 不可实施，待独立 design review`  
所有者：Qlib PeerLite 主线  
需求：在不改变 M2/M3 冻结数据、标签、切分和最终 OOS 封印的前提下，分别评估
`PeerLite-K16-CCC` 与 `PeerLite-K16-MSE-Gate`。  
风险：`R3`。  
决策期限：M7 真实训练前；未通过 M6.5 不得建立 M7 契约或启动服务器训练。

## 问题与范围

### 当前可观察行为

M6 已证明 K16/K32 MSE PeerLite 能在 M3 预最终样本外产品上进行可复现的滚动训练、
checkpoint 重放和 score 输出。现有模型支持 CCC 与 market gate 的接口，但现有 Qlib
`market` 列包含逐股市场字段和 `label_open`/`label_close`，不满足 Gate 所需的“同日唯一、
因果市场状态”契约。

### 目标可观察行为

1. CCC 分支仅将训练损失从 MSE 改为逐日横截面 CCC；输入、模型大小、K=16、切分、
训练预算和 score schema 均保持锁定。
2. Gate 分支仅在 K16/MSE PeerLite 的 hidden state 上乘以一个由 4 维、逐日唯一、纯因果
市场状态产生的 `(0, 2)` 门；不读取 label 或未来日期。
3. 两个分支各自以同一 7 个开发滚动折运行；只有两个独立预设的门都通过后，才可按派生
契约预设的条件激活 CCC+Gate 组合分支。
4. 所有实际训练都保留 `(datetime, instrument, score, model_id, fold_id)`，并产生独立
manifest、checkpoint、Qlib Recorder readback、验证回执及追加式账本事件。

### 非目标

- 不改动 50 个主特征、标签、股票池、调仓规则、成本或 M3 PIT 产品。
- 不进行 K、网络宽度、attention heads、CCC 权重或 market-state 维度的搜索。
- 不访问 2025+、不跑组合/成本后选择、不给出 Alpha、投资或“前 1%”结论。
- 不把 M7 引入文本、LLM、分钟、高频、多任务或 SAM。

### 约束与假设

- 只消费 M3 `pit_data_product_2012_2024_v3` 的 50 个冻结特征和其当日 PIT 股票横截面。
- prediction time 是 T 收盘后；market state 只能使用 T 时已知的特征值。
- M7 前必须由新的派生研究契约（而非覆写 `research_contract_pit_v2.json`）锁定预算与
执行规格。派生契约仅扩展预先分配的 fit 容量；不得扩大数据、模型家族、OOS 或阈值语义。
- 现有 44 个真实 model fit 已计入账本；M7 设计阶段、合成测试和审查均不计入。

## 仓库证据与当前流

- `src/qlib_peerlite/data/qlib_dataset.py`：M3 product → Qlib `DatasetH`；旧 `market`
  col_set 不可用于 M7 Gate。
- `src/qlib_peerlite/models/peerlite.py`：已有 Peer Assignment、prototype aggregation、
  single-layer attention、CCC loss 和 Gate 接口；M6 K16 参数为 29,521。
- `scripts/server/run_m6_peerlite.py`、`verify_m6_peerlite.py`：可复用“冻结 spec → 运行 →
  独立验证”的模式，但不可直接改为 M7 runner。
- `contracts/immutable/research_contract_pit_v2.json`：CCC/Gate 已在同一研究家族，且要求
  先单独通过再允许组合；当前 limits 为 27 candidates / 60 fits。

## 方案比较

| 方案 | 优点 | 主要问题 | 决定 |
| --- | --- | --- | --- |
| A. 修改旧 `qlib_dataset.py` 的 market 列 | 代码少 | 改变 M6 绑定路径；易把 label/逐股值带入 Gate | 拒绝 |
| B. 建立 M7 独立 daily-state adapter、runner 和 verifier | 保留 M6 历史证据；PIT 边界清晰；可单独测试/回退 | 少量新增代码 | 采用 |
| C. 绕过 Qlib，用 ad-hoc DataFrame 训练 | 早期实现快 | 破坏统一 Dataset/Recorder 研究底座 | 拒绝 |

## 拟议设计

### 组件职责

| 组件 | 新/既有 | 职责 |
| --- | --- | --- |
| `m7_market_state.py` | 新 | 从只读 bound product 计算每日唯一、4 维因果 market state，验证键、日期、有限值和逐日 PIT 宇宙 |
| `m7_dataset.py` | 新 | 将 feature、label 与广播后的 `m7_market_state` 装入 Qlib `DatasetH`，不暴露旧 market 列 |
| `m7_peerlite.py` | 条件新 | 仅当需要按“唯一日期”拟合 market-state standardizer 时封装既有网络；不得改变 M6 模型路径 |
| `m7_spec.py` | 新 | 验证派生契约、预算前缀、输入/代码 hash、分支隔离和 OOS seal |
| `run_m7_increment.py` | 新 | 只执行一个冻结 CCC 或 Gate 分支；不含组合选择逻辑 |
| `verify_m7_increment.py` | 新 | 在独立进程重放 checkpoint、验证 score、账本与 Qlib Recorder 工件 |

### 固定 market-state 定义

对每个 prediction date `T`，以该日 M3 产品中全部合格的 CSI800 PIT 成分股横截面 `U(T)`
计算以下 4 个标量；每个输入是 T 时已知的冻结特征，均不含 label：

| 名称 | 公式 | 经济含义 |
| --- | --- | --- |
| `mkt_trend_20` | `mean_{i∈U(T)} ret_mean_20(i,T)` | 中期横截面市场趋势 |
| `mkt_vol_20` | `median_{i∈U(T)} ret_std_20(i,T)` | 典型个股波动环境 |
| `mkt_breadth_1d` | `mean_{i∈U(T)} 1[ret_1d(i,T)>0]` | 当日上涨广度 |
| `mkt_turnover_20` | `median_{i∈U(T)} turnover_mean_20(i,T)` | 市场流动性状态 |

规则：

- 每日 state 只能由完整 `U(T)` 的当日 50-feature 行计算；先按 `(datetime, instrument)`
  去重、排序并验证 PIT 键后再聚合。
- 一个 date 少于 1 个合格股、任一输入非有限、state 维度/顺序不符或 state 不能一对一
  广播回原面板时，运行 fail-closed。
- state 可以在同日广播给每一只股票供网络使用，但 standardizer 只在训练折的**唯一日期**
  state 上拟合；validation/test 只做 transform。这样不让当日股票数量改变缩放权重。
- 任何未来行、label 列、旧 `market` col_set 或最终 OOS 行进入聚合均为硬失败。

### 模型、数据与状态流

```text
bound product feature rows at T
      -> validate PIT universe/key/finite values
      -> daily 4D market state (unique T)
      -> training-fold-only state standardizer
      -> broadcast state to that date's stocks
      -> frozen PeerLite K16 network + [optional] Gate
      -> (datetime, instrument) score
```

CCC 仅替换 `_loss`；Gate 分支仍用 MSE。两者分别生成独立 `model_id` 和结果命名空间。
两个分支在任何时点都不能互相读取其验证/测试指标。组合分支不是 M7 runner 的隐式功能：
它必须由通过两个隔离 gate 后才可能创建的独立冻结 execution spec 触发。

### 成功、失败与恢复

- 成功：每折的输入 hash、每日 state hash、训练配置、checkpoint、score、Qlib recorder 和
  独立 replay 一致；真实标签 fit 和 candidate 事件原子追加到账本。
- 数据失败：state validation 或 PIT negative test 失败则不启动 fit、不写 candidate success；
  保留失败回执和临时输入 manifest。
- 运行失败：任何已启动真实标签 fit 都按契约计数；输出写入新的 run root，禁止覆盖。
- verifier 失败：M7 gate `FAIL/HOLD`，不得用指标、重试或新参数掩盖问题。
- 回退：不执行或停用 M7 runner；M6、M3 产品、原契约和最终 OOS 封印仍保持原样。

### 并发、幂等与资源

- 单一 run ID 与 output root；同 ID 已存在时 fail-closed。
- 每折串行执行，GPU 使用冻结的确定性设置；不允许并行写同一 trial ledger。
- 每日 state 聚合复杂度 O(rows)，Gate 维度固定 4；保持 PeerLite O(NK)，不建立 N×N 股票对。

### 安全、隐私与可观测性

- 无网络、无凭据、无外部文本输入；原始数据库和大工件不进 Git。
- manifest 记录输入、state、契约、代码、依赖与输出 hash；日志不得包含连接字符串或秘密。
- 运行报告记录每日期股数、state 缺失/失败计数、资源用量、OOS 访问状态和 ledger pre/post
  counts。

## 演进、兼容与预算

M7 使用派生而非覆盖的研究契约。作为用户已选择的完整闭环预算方案，设计候选上限仍为 27，
model-fit 上限建议由 60 派生为 108，并预先隔离：当前 44、CCC 8、Gate 8、条件组合 8、
确认期 28、最终 OOS 6、独立最终 OOS 重跑 6。未激活的条件分支配额作废，不可挪作新搜索。

此预算变更须在 M6.5 review 通过后、任何 M7 真实标签训练前，由
`quant-research-contract` 形成可验证的派生契约及 PIT 不变性回执。它不打开最终 OOS。

## 验证义务

- M6 追溯审查：代码、冻结 spec、账本生命周期和现有回归测试独立复验；发现的 P0–P2
  必须修复并重新审查。
- CCC：损失数学性质、单股 fallback、mask、每日期平均、checkpoint/replay 与固定种子。
- Gate：拒绝旧 market/label，验证四维 state 因果性、每日唯一性、PIT universe、训练折
  唯一日期标准化、广播、排列等变、全缺失/单股/多日期 batch 和 OOS seal。
- Pipeline E2E：从小型版本化合成 product 经公开 M7 CLI 到 score、manifest 和 verifier；
  覆盖成功、重复 run-id 拒绝和 poisoned-input 拒绝。

## 实施计划（仅在 M6.5 PASS 后）

1. 创建派生研究契约、M7 预算 spec 和不改变 PIT 输入语义的审计回执。
2. 完成 `m7_market_state.py` 与 M7 Dataset adapter 的 test-first/变异证明；先不使用真实数据。
3. 完成 CCC/Gate 模型 adapter、合成 smoke 和固定 deterministic replay。
4. 冻结 CCC 与 Gate 两份独立 execution spec，分别绑定 code/input/ledger prefix。
5. 在服务器执行 CCC、再执行 Gate；各自独立 verification、gate 与账本事件。
6. 仅按预设规则决定条件组合或 HOLD；M8 不得提前打开。

## 开放决策

| 决策 | 所有者 | 何时关闭 | 阻断效果 |
| --- | --- | --- | --- |
| M6 code/test review 的完整 P0–P2 结论 | 独立审查者 | M6.5 | 未关闭则禁止 M7 |
| 4D state 与 unique-day standardization 的独立设计审查 | 独立审查者 | M6.5 | 未通过则禁止 M7 实施 |
| 派生预算契约 60→108 的严格 validator | research-contract gate | M7 前 | 未通过则禁止真实训练 |
| M7 运行器的 test-first 和 E2E 证据 | 工程质量 gate | M7 代码后 | 未通过则禁止服务器真实训练 |

## 设计结论

`NEEDS_CHANGES`：设计为独立审查提供了可执行边界，但当前已有 M7 前置 P1，且尚未完成
独立设计审查、M6 code review、测试审查和派生契约验证。没有任何本文件的内容授权 M7
代码、真实标签训练或最终 OOS 访问。

