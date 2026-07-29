# M7 behavior-to-test matrix v6

| ID | Owner | Oracle |
| --- | --- | --- |
| GATE-01 | M6.5_CONTRACT_ONLY | 五generic入口副作用前拒绝 |
| QUAL-01 | M6.5_CONTRACT_ONLY | exact fixed IDs集合、17 PASS及全部qualification字段 |
| QUAL-02 | M6.5_CONTRACT_ONLY | exact B001-B004、official schema、parent contract_binding与independent review receipt |
| BUDGET-01 | M6.5_CONTRACT_ONLY | `6/44 -> max 8/60`，failed/interrupted分支HOLD且0 replacement |
| STAGE-01 | M6.5_CONTRACT_ONLY | production factory/live authority不存在或拒绝 |
| GATE-02 | M7_IMPLEMENTATION | capability-only固定`2*sigmoid`create |
| LOAD-01 | M7_IMPLEMENTATION | generic load拒绝；special reload重验全部bindings |
| STATE-01 | M7_IMPLEMENTATION | exact-date、同日一致、train-only daily standardizer |
| CCC-01 | M7_IMPLEMENTATION | 完整float64公式，rtol/atol 1e-12 |
| CLAIM-01 | M7_IMPLEMENTATION | worker lease、前序outcome、失败后HOLD无replacement |
| PRE-01 | M7_REAL_ACCEPTANCE | prerequisite缺任一则0 event |
| RUN-01 | M7_REAL_ACCEPTANCE | 两分支各7+1且总计不超过8/60 |
| EVAL-01 | M7_REAL_ACCEPTANCE | 同mapper/benchmark/cost独立重算 |
| OOS-01 | M7_REAL_ACCEPTANCE | final-OOS access=0 |

当前只实现`M6.5_CONTRACT_ONLY`行。

