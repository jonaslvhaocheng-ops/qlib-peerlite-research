# M7 behavior-to-test matrix v5

- 状态：`DESIGN_ONLY / NOT_EXECUTED`
- Subject：`m7_change_design_v5.md`
- Owner stages：`M6.5_CONTRACT_ONLY`、`M7_IMPLEMENTATION`、`M7_REAL_ACCEPTANCE`

| ID | Owner | 行为 / oracle |
| --- | --- | --- |
| GATE-01 | M6.5_CONTRACT_ONLY | 五个generic Gate入口副作用前固定拒绝 |
| QUAL-01 | M6.5_CONTRACT_ONLY | validator逐项拒绝17/4 checks、QUALIFIED/PASS/PRODUCTION_CLI/FULL_TRAINING_INPUT/test-only/hash/parent/issuer变异 |
| BUDGET-01 | M6.5_CONTRACT_ONLY | `6/44`起点、仅+2/+16、组合和第17 fit拒绝 |
| STAGE-01 | M6.5_CONTRACT_ONLY | production factory/live authority不存在或拒绝 |
| QUAL-02 | M7_IMPLEMENTATION | exact V2 fixed+behavior双PASS形成envelope |
| GATE-02 | M7_IMPLEMENTATION | 只有factory capability构造固定`2*sigmoid` Gate |
| LOAD-01 | M7_IMPLEMENTATION | generic loader拒绝；专用loader重验全部capability/checkpoint bindings |
| STATE-01 | M7_IMPLEMENTATION | exact-date/同日一致/unique-date train-only standardizer |
| CCC-01 | M7_IMPLEMENTATION | 完整Lin CCC与float64 contract手算一致，rtol/atol 1e-12 |
| CCC-02 | M7_IMPLEMENTATION | singleton MSE、nonfinite fail、tie earliest |
| PEER-01 | M7_IMPLEMENTATION | 排列等变、可变N、单股、mask、跨日隔离 |
| CLAIM-01 | M7_IMPLEMENTATION | worker直接持lease；前序outcome门；crash不可重放 |
| PRE-01 | M7_REAL_ACCEPTANCE | cost/benchmark/prerequisite缺任一则0新event |
| RUN-01 | M7_REAL_ACCEPTANCE | 两候选各7+1，不超过`8/60` |
| EVAL-01 | M7_REAL_ACCEPTANCE | 同mapper/benchmark/cost独立重算screening |
| OOS-01 | M7_REAL_ACCEPTANCE | 所有M7路径final-OOS access=0 |

当前M6.5只实现`M6.5_CONTRACT_ONLY`；其余只做设计审查，不写production code或red/green测试。

