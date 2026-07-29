# M7 前测试设计与 M6.5 验收矩阵

状态：`DRAFT — 待独立 design review`  
风险：`R3`。测试目标是证伪不安全的 M7 实现，不是用覆盖率替代研究证据。

## 范围与固定测试边界

- 输入只限小型、版本化合成 product，直至派生契约和 PIT 不变性回执通过。
- M6 历史 MSE run 不倒称 test-first；对其做新鲜回归、独立读回和受控 mutation 证明。
- M7 新代码采用“expected-red → implementation → green”顺序；红测必须在隔离 worktree
  或受控 mutation 中为预期行为失败，而非语法/fixture 失败。
- 所有测试固定 seed、无网络、无 wall-clock sleep、无共享外部状态。

## 行为到测试矩阵

| ID | 行为/不变量 | 类型/层 | 最小输入 | Oracle | 覆盖义务 |
| --- | --- | --- | --- | --- | --- |
| M65-U1 | M6 冻结 gate 可读，历史 code/spec/receipt 哈希一致 | 回归 | 已提交 M6 evidence | 哈希与声明相符；历史 scope 不被扩大 | M6 evidence lifecycle |
| M65-U2 | M6 账本在 M7 追加后仍能验证其冻结前缀 | mutation/regression | 追加的合成非模型事件/隔离 copy | 前缀相等、后缀不被误判为 M6 证据 | append-only lifecycle |
| M65-U3 | 现有 M6 tests 可被受控的 score/hash/contract mutation 检出 | mutation | 隔离 worktree | 指定测试以预期 assertion 失败 | 测试有效性 |
| MS-U1 | 每日 state 仅使用四个冻结 feature 和该日 PIT 行 | unit/property | 2 日期/多股面板 | 精确 4D 聚合；无 label 访问 | formula / column allowlist |
| MS-U2 | 同日 state 唯一且广播后每股完全一致 | unit/property | 可变股数日 | 每日期只有一个 state，广播逐行相等 | date isolation |
| MS-U3 | 调换同日股票顺序不改变 state | metamorphic | 乱序同日面板 | state byte/float equality | order invariance |
| MS-U4 | future row/未来日期扰动不改变过去 state | PIT negative | 基线与 poisoned product | 过去日期 digest 完全一致 | no future dependence |
| MS-U5 | label、旧 market 列、缺少四个字段、NaN/Inf、重复 key、空日被拒绝 | negative | 最小坏面板 | 明确异常；不产生 output | fail-closed paths |
| MS-U6 | 训练 state standardizer 只在 unique train dates fit | unit/integration | train/valid/test 不同数量横截面 | train-date stats 精确；valid/test 无影响 | no fold / stock-count leakage |
| CCC-U1 | 预测等于目标时 CCC loss 最小；常量/单股稳定 fallback | unit | 小 tensor | 有限且按数学预期排序 | formula, n=1 |
| CCC-U2 | padding/mask 不改变有效股票损失 | property | 不同 padding sizes | 有效 score/loss 等价 | mask branch |
| GATE-U1 | Gate 拒绝缺失、错误维度、非恒定市场 state | unit | 1/多日期 batch | 明确 ValueError | input validation |
| GATE-U2 | Gate 对股票排列等变；单股、可变股数、全缺失 padded 行安全 | property | 多种横截面 | score 按排列一致；无 NaN | architecture invariants |
| GATE-U3 | Gate state 仅影响其日期，不发生跨日期 mixing | metamorphic | 两日期 batch，扰动一天 state | 另一日期 scores 不变 | date isolation |
| GATE-U4 | checkpoint 保存/加载后 Gate score 精确重放 | integration | 小 Qlib synthetic fold | bitwise/规定精度 equality | persistence |
| SPEC-U1 | CCC 和 Gate spec 各自拒绝错误 model/loss/state/ledger prefix/OOS seal | contract | JSON mutations | validator fail-closed | contract branches |
| SPEC-U2 | 条件组合不能在两个隔离 gate PASS 前被创建或执行 | contract | forged gate/evidence | validator rejects | promotion boundary |
| RUN-U1 | M7 CLI 从版本化小 product 产生统一 score、manifest 与 checkpoint | E2E CLI/data pipeline | synthetic bound product | schema、hash、row conservation | happy path |
| RUN-U2 | 重复 run ID、poisoned input、已打开 OOS 或 verifier mismatch 都 fail-closed | E2E CLI/data pipeline | controlled invalid inputs | 非零退出，无 success receipt | recovery / idempotency |
| RUN-U3 | CCC 与 Gate runner 不能读取彼此结果或启动组合 | integration | instrumented run roots | no forbidden file access / state | branch isolation |

## Fixture、seam 与确定性计划

- 在 `tests/fixtures` 或现有临时 `tmp_path` builder 内生成含 50 feature、明确 market-state
  source列、label 和 calendar 的小型合成 product；不得用服务器真实数据。
- state aggregator 是纯函数，直接以 DataFrame 测试；Qlib adapter 以 `DatasetH.prepare` 做
  边界验证；runner 只经其公开 CLI/`--spec` 接口做 E2E。
- 使用固定 seed `{7}`、CPU 做单元/集成；GPU 确定性只作为服务器 smoke，记录
  `CUBLAS_WORKSPACE_CONFIG=:4096:8`。
- 对 `M65-U3` 用隔离 git worktree 或临时副本篡改测试对象；绝不改动不可变 M6 证据。

## 覆盖与验收

M7 新增核心生产代码要求 100% line/branch coverage（由适配后的项目工具实际测量）；若当前
仓库没有可用 branch coverage 配置，M6.5 必须先把此缺口明确为 `NEEDS_CHANGES`，不能用
估计百分比写 PASS。现有全量 `pytest`、Ruff 与 M6 focused tests 必须新鲜运行，且其命令、
退出码、版本与输出摘要保留在 evidence receipt。

M6.5 通过条件：独立 M6 code review、M6 test revalidation、M7 design review 和本测试设计均
无未解决 P0/P1/P2；否则不产生 M6.5 `PASS`，M7 保持 `NOT_RUN`。

## 结论

`NEEDS_CHANGES`：测试范围已定义，但尚未获得独立设计审查、M6 审查最终结论、红测证明或
任何 M7 实现/执行证据。

