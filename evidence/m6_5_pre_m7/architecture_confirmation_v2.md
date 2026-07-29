# M6.5 架构确认 v2 — M7 前工程闸门

状态：`REVISED_DRAFT / PENDING_INDEPENDENT_REVIEW`  
替代关系：本文件替代初始 `architecture_confirmation.md` 作为后续 M7 设计依据；初始文件与
其审查 hash 保留为历史证据。  
风险：`R3`；最终 OOS 继续封印。

## 纠正后的边界

| 层 | 允许职责 | 明确禁止 |
| --- | --- | --- |
| sealed raw snapshot | 生成仅 T 已知的 state population | 用 label/execution/未来事件过滤其成员 |
| `market_state_population` | 记录每日期 PIT key set、count、四个状态来源字段与 manifest hash | 直接复用 M3 supervised matrix 的行集合 |
| M3 supervised product | 仅提供已批准的 50-feature/label 行给 CCC/Gate 模型训练 | 充当完整市场横截面或 state population |
| M7 Dataset adapter | 按 `datetime` 将独立 daily state 精确 join 到 supervised rows | 读取旧 Qlib `market` 或任何 `label_*` 字段 |
| M7 model wrapper | 仅以唯一训练日期的 state 拟合 standardizer，再按日期广播 | 使用每股票重复行拟合 state standardizer |
| M7 runner / verifier | 独立 run root、journal、reconcile、replay 和证据 | 改写 M6 runner、M6 receipt 或 M6 immutable spec |

## 目标依赖图

```text
sealed raw snapshot + PIT membership/status at T
        │
        └──> m7_state_population.py
                    │  (daily keys/count/digest; no label/execution fields)
                    └──> m7_market_state.py (4D daily state)
                                  │
M3 supervised product ───────────┴──> m7_dataset.py
                                               │
                                  m7_peerlite.py (mandatory daily-state wrapper)
                                               │
                        run_m7_increment.py -> journal -> reconcile_trial_ledger.py
                                               │
                                  verify_m7_increment.py -> evidence / gate
```

允许依赖仅为 `raw/PIT -> state population -> state -> dataset -> model -> runner -> evidence`。
模型、state 和 dataset 层禁止导入结果指标、trial ledger、组合选择或 OOS 分区；治理层可读取
hash，但不能将结果反写入输入。

## 必须先关闭的基础修复

1. M6 archival verifier：让 M6 证据按 close-time ledger 前缀而非完整可追加文件验证，并在
   历史代码版本上独立重放 checkpoint。
2. Trial-ledger reconciler：以 source event ID、文件锁、fsync/原子 append 和幂等导入保证
   `FIT_STARTED` 即占用预算，异常/中断不漏记。
3. M7 state population：只由 T 已知的 membership、listing/status 和 causal feature eligibility
   构成；它有独立 PIT manifest、固定审计和 behavior/poison evidence。
4. M7 wrapper：必须使用 unique-date state standardization，并在 checkpoint 中保存 state schema、
   daily-statistics payload 和 input digest。

## 回退与审计原则

所有新增内容位于 M6.5/M7 命名空间；不运行新 runner 即可回退，不影响 M6 历史结论。若未来
变更共享 PeerLite 核心，M6 历史验证必须使用其冻结 Git revision/manifest，而不能错误地以
当前工作树替代历史代码。任何 P0/P1/P2 未关闭时，M7 真实 fit、组合状态激活和 M8 OOS
访问一律禁止。

## 结论

`NEEDS_CHANGES`：现有模块足以承载 M7，但只在上述新边界与独立审查通过后才可实施。

