# M7 前测试设计与 M6.5 验收矩阵 v2

状态：`REVISED_DRAFT — 待独立审查`。  
原则：先证明错误实现会失败，再写 M7 生产代码；所有 M7 单元/集成/E2E 只用小型版本化
合成产品，直到 state-product PIT gate 通过。

## 行为到测试矩阵

| ID | 不变量 | 层 | Oracle |
| --- | --- | --- | --- |
| M65-A1 | M6 close-time ledger prefix 和 Git 历史 code binding 可独立验证，后缀 append 不破坏它 | unit/mutation | 前缀 hash/event count 相等；后缀变化不影响 M6 archival verdict |
| M65-A2 | 受控 receipt/spec/score/checkpoint mutation 会使 archival verifier fail | mutation | 精确错误，不能产生 PASS |
| M65-A3 | 每折 checkpoint 从冻结 Git revision/data product 实际重放，keys/score digest 均等 | integration/server acceptance | 所有 14 fold 确切匹配 |
| LEDGER-U1 | `FIT_STARTED` 在 crash 后仍被 reconciliation 计入，完成/失败/中断都唯一 | unit/integration | global event 唯一、预算计数正确 |
| LEDGER-U2 | 两次 import 同 journal 是 no-op；冲突 source ID、断裂 prefix、并发锁竞争 fail-closed | unit/fault injection | 无重复/无部分 append |
| LEDGER-U3 | 下一 run preflight 拒绝未 reconciled 的已启动 fit 或重复 run ID | integration | 非零/明确错误 |
| POP-U1 | state population 只用 T-known allowlist/predicates，物理不含 label/execution fields | unit/contract | column/predicate allowlist 严格相等 |
| POP-U2 | future date、同日 future label、T+1 limit/halt、future action 或 label validity 变化不改变 T 的 population/state | PIT behavior/mutation | date key/count/state digest byte-identical |
| POP-U3 | T-known membership/status/feature invalid、重复 key、NaN/Inf、空 date 均 fail-closed | unit/negative | 明确错误，无输出 |
| STATE-U1 | 四个公式、排序不变性、key/count/state digest、精确日期广播正确 | unit/property | 逐数值 oracle / exact join |
| STATE-U2 | state date 不在 M3 supervised rows、重复/不等广播、nonfinite state 被拒绝 | integration/negative | 无 model fit |
| STATE-U3 | standardizer 只以 unique training dates fit，股票数变化不改变 mean/scale | unit/metamorphic | date-level payload 精确一致 |
| CCC-U1 | CCC formula/eps/reduction/singleton fallback 与 MSE 基线可区分 | unit | 解析计算一致 |
| CCC-U2 | validation/early stop 用 CCC；tie 保留最早 epoch；NaN fail | unit/integration | 指定 checkpoint epoch / exception |
| GATE-U1 | Gate 只接受 `market_state` 4D col_set，不接受旧 `market` 或 label | unit/contract | 明确错误 |
| GATE-U2 | 排列等变、单股、可变截面、padding、跨日期隔离、checkpoint replay | property/integration | score 等价 / exact replay |
| SPEC-U1 | 错误 input/state hash、budget prefix、loss rule、OOS seal、promotion artifact 全部 fail | contract | validator rejects |
| SPEC-U2 | 组合在两个 isolated engineering+science PASS 前不可创建；未触发预算不可挪用 | contract | validator rejects |
| EVAL-U1 | 开发期 weekly mapper/cost spec 对 benchmark/candidate 使用同一输入，指标公式可重算 | integration | receipt 与 oracle 一致 |
| RUN-E1 | 公开 M7 CLI 从 synthetic source/state/model spec 到 score/manifest/verifier 的成功路径 | E2E data pipeline | schema、row conservation、hash、repeatability |
| RUN-E2 | poison input、duplicate run, interrupted journal, verifier mismatch 都安全失败 | E2E fault injection | 无 success gate、无遗漏 ledger event |

## TDD 与 coverage

- 每个新生产行为先在隔离 worktree 或受控 mutation 中演示 expected-red；失败必须因正确的
  行为缺失/错误，而不是 fixture 或语法。
- 新增/实质变更的 M6.5/M7 核心生产模块必须 100% line 与 branch coverage；不对历史未改
  模块虚报覆盖率。coverage 命令、环境及原始输出必须写入 receipt。
- CPU 固定 seed 单元/集成；GPU 只在 server smoke/acceptance，固定 CUBLAS 和 torch
  deterministic 设置。无网络、sleep 或共享环境依赖。

## E2E 划分

- M6 archival replay：受冻结 Git revision、版本化 development product 与 server checkpoint
  约束；只读，不拟合，不消耗 model-fit 预算。
- M7 synthetic E2E：只准 synthetic product；证明接口，不证明 Alpha。
- M7 real development execution：只有派生契约、state PIT gate、M6.5 engineering gates 全部
  PASS 后才能启动；每一个真实 `FIT_STARTED` 即计数。

## 结论

`NEEDS_CHANGES`：这是修订测试设计，尚未获独立审查或执行。M7 仍 `NOT_RUN`。

