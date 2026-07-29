# M7 behavior-to-test matrix v7

| ID | Owner | Oracle |
| --- | --- | --- |
| GATE-01 | M6.5_CONTRACT_ONLY | 五generic入口副作用前拒绝 |
| QUAL-01 | M6.5_CONTRACT_ONLY | exact fixed17、QUALIFIED/PASS/PRODUCTION_CLI/FULL_TRAINING_INPUT |
| QUAL-02 | M6.5_CONTRACT_ONLY | 每T一个FUTURE_POISON manifest、exact B001-B004、horizon list、supplement/review receipt |
| GEN-01 | M6.5_CONTRACT_ONLY | CCC/Gate各一generation；前者terminal后后者仍可commit |
| BUDGET-01 | M6.5_CONTRACT_ONLY | `6/44 -> max8/60`，0 replacement |
| GATE-02 | M7_IMPLEMENTATION | capability-only fixed `2*sigmoid` create |
| LOAD-01 | M7_IMPLEMENTATION | generic load拒绝；special reload复核全部checkpoint bindings |
| STATE-01 | M7_IMPLEMENTATION | exact-date、同日一致、unique-date train-only standardizer |
| CCC-01 | M7_IMPLEMENTATION | 完整float64公式/dtype，rtol/atol1e-12 |
| CLAIM-01 | M7_IMPLEMENTATION | worker lease、前序outcome、terminal recovery、失败分支HOLD |
| PRE-01 | M7_REAL_ACCEPTANCE | prerequisite缺任一则0 event |
| RUN-01 | M7_REAL_ACCEPTANCE | 两generation各7+1，总计不超过8/60 |
| EVAL-01 | M7_REAL_ACCEPTANCE | 同mapper/benchmark/cost独立重算 |
| OOS-01 | M7_REAL_ACCEPTANCE | final-OOS access=0 |

当前只实现`M6.5_CONTRACT_ONLY`。

