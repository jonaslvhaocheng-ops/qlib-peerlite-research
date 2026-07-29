# M7 behavior-to-test matrix v8

| ID | Owner | Oracle |
| --- | --- | --- |
| GATE-01 | M6.5_CONTRACT_ONLY | 五generic入口在Dataset/journal/output/fit前拒绝 |
| QUAL-01 | M6.5_CONTRACT_ONLY | exact fixed17、QUALIFIED/PASS/PRODUCTION_CLI/FULL_TRAINING_INPUT |
| QUAL-02 | M6.5_CONTRACT_ONLY | 每T一个FUTURE_POISON manifest、exact B001-B004及一对一horizon |
| QUAL-03 | M6.5_CONTRACT_ONLY | supplement strict keys/types/order/hash/T/availability；unknown/null/float/duplicate拒绝 |
| QUAL-04 | M6.5_CONTRACT_ONLY | aux verifier exact AP001-AP004与aux/population/state prefix bindings |
| QUAL-05 | M6.5_CONTRACT_ONLY | review receipt authority有效期、时序、parent、reviewer≠builder与canonical hash |
| QUAL-06 | M6.5_CONTRACT_ONLY | security-lifecycle authority缺失/过期/版本错时qualification前HOLD；不得event-date推断 |
| STATE-01 | M6.5_CONTRACT_ONLY | exact四列顺序、每日一行、exact-date join、无缺失/重复/nonfinite |
| STATE-02 | M6.5_CONTRACT_ONLY | broadcast同日逐列float64 bytes一致；不一致拒绝而非归约 |
| STD-01 | M6.5_CONTRACT_ONLY | sorted unique train dates、float64 mean/population std、`<1e-12→1`、valid/test transform-only |
| STD-02 | M6.5_CONTRACT_ONLY | checkpoint contract绑定列序、mean/scale、train-date digest/count与code SHA |
| GEN-01 | M6.5_CONTRACT_ONLY | CCC/Gate各一generation；registration→commit→activation receipt无hash环 |
| BUDGET-01 | M6.5_CONTRACT_ONLY | `6/44 -> max8/60`，0 replacement |
| GATE-02 | M7_IMPLEMENTATION | capability-only fixed `2*sigmoid` create |
| LOAD-01 | M7_IMPLEMENTATION | generic load拒绝；special reload复核全部checkpoint bindings |
| CCC-01 | M7_IMPLEMENTATION | 完整float64公式/dtype，rtol/atol1e-12 |
| CLAIM-01 | M7_IMPLEMENTATION | worker lease、前序outcome、terminal recovery、失败分支HOLD |
| PRE-01 | M7_REAL_ACCEPTANCE | prerequisite缺任一则0 event |
| RUN-01 | M7_REAL_ACCEPTANCE | 两generation各7+1，总计不超过8/60 |
| EVAL-01 | M7_REAL_ACCEPTANCE | 同mapper/benchmark/cost独立重算 |
| OOS-01 | M7_REAL_ACCEPTANCE | final-OOS access=0 |

当前只实现`M6.5_CONTRACT_ONLY`；其余测试只保留设计占位，不得调用fit或真实数据执行。
