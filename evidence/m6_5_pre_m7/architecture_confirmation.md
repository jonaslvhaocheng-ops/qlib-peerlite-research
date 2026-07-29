# M6.5 架构确认 — M7 前工程闸门

状态：`DESIGN_ONLY / PENDING_INDEPENDENT_REVIEW`  
范围：M7 的 CCC 与市场状态 Gate 基础设施；不触碰 2025+ 最终样本外。  
风险：`R3`（量化模型决策、真实标签训练、审计与 OOS 边界）。

## 目的与边界

本文件把用户要求的 design review、code review 和测试前置为 M6.5 硬闸门。它不改变
冻结研究家族、数据源、标签、切分、最终 OOS 封印或已有 M6 结论；它只决定 M7 是否具备
安全的工程入口。

M6 的历史 MSE 执行已由冻结规范及独立验证绑定。M6.5 不重写该历史结论，也不把现有
测试追溯称为 test-first。任何后续修正均须有新的、明确版本化的 M7 产物；不能把新代码
伪装为 M6 的运行代码。

## 已核实的当前边界

| 层 | 当前所有者 | 已知接口/约束 | M7 允许的作用 |
| --- | --- | --- | --- |
| PIT 数据 | `data/manifests/pit_data_product_2012_2024_v3/` | 50 个冻结因果特征，2025+ 未打开 | 只读消费；不得覆写、回填或扩展最终 OOS |
| Qlib 适配 | `src/qlib_peerlite/data/qlib_dataset.py` | 产生 `(datetime, instrument)` 面板与 `DatasetH` | M7 不修改此 M6 绑定文件；用独立 M7 adapter 构造安全的 market-state 列 |
| 模型 | `src/qlib_peerlite/models/peerlite.py` | `fit(dataset)`、`predict(dataset)`，统一 score 接口 | 复用已审查的 PeerLite 网络；M7 Gate 不可消费旧 `market` 列 |
| 治理 | `contracts/immutable/*`、`contracts/trial_ledger.jsonl` | 契约不可覆写、账本追加、OOS 封印 | 由新派生契约锁定预算、代码与输入；不修改 M2/M3/M6 不可变文件 |
| 服务器执行 | `scripts/server/run_m6_peerlite.py` | M6 的冻结专用运行器 | 新增 M7 专用 runner/verifier；不把 M7 分支塞入 M6 runner |
| 证据 | `evidence/gates/*` | M6 gate 仅说明 MSE 历史运行 | 新增 `evidence/m6_5_pre_m7/` 与之后的 M7 证据命名空间 |

## 已发现的关键阻断

独立 M6 代码审查已确认：`qlib_dataset.py` 的旧 `market` col_set 含有逐股不同的
`label_open`、`label_close`。它们是 T+1 开盘及 T+5 收盘标签的组成，既不是 date-constant
的市场状态，也不能进入 Gate。M6 未启用 Gate，故该历史 M6 结论不受影响；但任何 M7
Gate 若读取旧 `market` col_set 都必须 fail-closed。

因此 M7 的 market state 必须是独立、纯特征输入、每日期唯一的 4 维产品，且要通过新的
PIT 与负对照测试。此项是 M7 实现的不可绕过前置条件。

## 拟定目标结构与依赖规则

```text
M3 bound product (read-only)
        │
        ├──> m7_market_state.py (pure causal daily aggregation)
        │           │
        └──> m7_dataset.py (Qlib DatasetH with feature/label/m7_market_state)
                    │
                    ├──> m7_peerlite.py (only if daily-state standardization needs a wrapper)
                    └──> run_m7_increment.py -> score / checkpoint / receipts
                                                   │
                                      verify_m7_increment.py (independent readback)
```

允许的依赖方向：`data -> model -> runner -> evidence`；治理模块可读取所有产物的 hash，
但模型和数据模块不得读取 trial ledger、结果指标或最终 OOS 分区。

禁止：

- M7 从旧 `market` col_set、任何 label、未来日期、当前股票池或未冻结外部指数读取状态；
- 修改 M6 专用 runner 或把 M7 输出写进 M6 目录；
- 由模型结果决定 market-state 公式、维度、K、候选或最终 OOS 范围；
- 把工程质量证据当作 PIT 审计、研究契约或试验账本的替代品。

## 变更隔离与可回退性

M7 新文件必须置于独立 M7 命名空间；回退就是不执行其 runner，不影响已验证的 M6
工件。若共享 `PeerLiteModel` 需要修复，必须先证明该修复影响的 M6/M7 语义，并创建
独立版本或重跑受影响的冻结范围；不得静默修改历史绑定代码。

## 架构确认结论

当前模块边界足以承载 M7，但仅在采用上述“独立 market-state adapter + 独立 runner”
的前提下。此确认不批准实施，也不批准 M7 训练；须待独立 design review、测试设计和
M6 代码/测试审查的 P0–P2 问题全部关闭。

