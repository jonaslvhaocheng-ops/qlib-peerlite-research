# M7 behavior-to-test matrix v9

| ID | Owner | Oracle |
| --- | --- | --- |
| GATE-01 | M6.5_CONTRACT_ONLY | 五generic入口在Dataset/journal/output/fit前拒绝 |
| QUAL-01 | M6.5_CONTRACT_ONLY | exact fixed17与parent资格字段 |
| QUAL-02 | M6.5_CONTRACT_ONLY | 每T一份FUTURE_POISON、exact B001-B004、official scalar CSV和十slot映射 |
| QUAL-03 | M6.5_CONTRACT_ONLY | supplement strict keys/types/order/hash/T/availability |
| QUAL-04 | M6.5_CONTRACT_ONLY | aux/population/state逐产品projection及schema/key/value/logical digests重算 |
| QUAL-05 | M6.5_CONTRACT_ONLY | exact AP001-AP004且15个equality全部true；status-only fixture拒绝 |
| QUAL-06 | M6.5_CONTRACT_ONLY | review receipt authority有效期、hash DAG、parent与reviewer≠builder |
| QUAL-07 | M6.5_CONTRACT_ONLY | lifecycle authority/rows/receipt exact schema、SLA001-006、coverage与visibility replay |
| QUAL-08 | M6.5_CONTRACT_ONLY | lifecycle slot缺失/过期/版本错时qualification前HOLD，不得event-date推断 |
| STATE-01 | M6.5_CONTRACT_ONLY | exact四列/每日一行/exact-date/no missing-duplicate-nonfinite |
| STATE-02 | M6.5_CONTRACT_ONLY | broadcast同日逐列float64 bytes一致 |
| STD-01 | M6.5_CONTRACT_ONLY | unique train dates、float64 population std、`<1e-12→1`、transform-only |
| STD-02 | M6.5_CONTRACT_ONLY | checkpoint contract绑定列序/stat/date digest/count/code |
| GEN-01 | M6.5_CONTRACT_ONLY | CCC/Gate各一generation；registration→commit→receipt无环 |
| BUDGET-01 | M6.5_CONTRACT_ONLY | `6/44 -> max8/60`，0 replacement |
| GATE-02 | M7_IMPLEMENTATION | capability-only `2*sigmoid` create |
| LOAD-01 | M7_IMPLEMENTATION | generic load拒绝；special reload完整复核 |
| CCC-01 | M7_IMPLEMENTATION | 完整float64公式/dtype，rtol/atol1e-12 |
| CLAIM-01 | M7_IMPLEMENTATION | worker lease、前序outcome、terminal、失败HOLD |
| PRE-01 | M7_REAL_ACCEPTANCE | prerequisite缺任一则0 event |
| RUN-01 | M7_REAL_ACCEPTANCE | 两generation各7+1，不超过8/60 |
| EVAL-01 | M7_REAL_ACCEPTANCE | 同mapper/benchmark/cost独立重算 |
| OOS-01 | M7_REAL_ACCEPTANCE | final-OOS access=0 |

当前只实现`M6.5_CONTRACT_ONLY`；其余不得调用fit或真实数据执行。
