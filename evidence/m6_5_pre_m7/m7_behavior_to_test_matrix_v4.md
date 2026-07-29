# M7 behavior-to-test matrix v4

- 状态：`DESIGN_ONLY / NOT_EXECUTED`
- Subject：`m7_change_design_v4.md`
- Owner stage枚举：
  - `M6.5_CONTRACT_ONLY`：本轮可实现/验证的fail-closed和artifact validator；
  - `M7_IMPLEMENTATION`：M6.5 PASS及derived contract后才写的生产行为；
  - `M7_REAL_ACCEPTANCE`：live authority/PIT/prerequisite后才运行的真实开发期验收。

| ID | Owner stage | 行为 | Oracle |
| --- | --- | --- | --- |
| GATE-01 | M6.5_CONTRACT_ONLY | 五个generic Gate入口副作用前拒绝 | 固定异常；无dataset/output/journal/load/fit |
| QUAL-01 | M6.5_CONTRACT_ONLY | synthetic V2 qualification envelope validator拒绝自签、替换、缺receipt | table-driven contract negative |
| BUDGET-01 | M6.5_CONTRACT_ONLY | M6 `6/44`、只允许未来2 candidate/16 fit、组合禁入 | contract validator边界 |
| STAGE-01 | M6.5_CONTRACT_ONLY | M7 production factory/runner/live authority不存在或被拒绝 | import/CLI/fake-fs negative |
| QUAL-02 | M7_IMPLEMENTATION | exact V2 product + fixed/behavior PASS形成唯一envelope | hash/schema/receipt recompute |
| GATE-02 | M7_IMPLEMENTATION | 只有专用factory+capability可构造固定`2*sigmoid` Gate | bool/token/substitution拒绝 |
| STATE-01 | M7_IMPLEMENTATION | exact-date、同日state一致、unique-date train-only standardizer | property/metamorphic |
| CCC-01 | M7_IMPLEMENTATION | float32 input→float64 accumulation/return公式一致 | CPU hand calc, rtol/atol 1e-12 |
| CCC-02 | M7_IMPLEMENTATION | singleton MSE、nonfinite fail、tie earliest | table-driven/checkpoint epoch |
| PEER-01 | M7_IMPLEMENTATION | Gate保持排列等变、可变N、单股、mask、跨日隔离 | score permutation/exact oracle |
| CLAIM-01 | M7_IMPLEMENTATION | claim→outcome lease；crash为CLAIMED_INTERRUPTED且不可重放 | fault injection/event state |
| SCORE-01 | M7_IMPLEMENTATION | checkpoint绑定全部Gate/CCC/input identity并exact reload | key/score digest |
| PRE-01 | M7_REAL_ACCEPTANCE | cost/benchmark证书与screening bundle在first claim前PASS | 缺任一则0新ledger event |
| RUN-01 | M7_REAL_ACCEPTANCE | 两隔离候选各7 folds+1 refit且不超过8/60 | authoritative ledger |
| EVAL-01 | M7_REAL_ACCEPTANCE | 同mapper/benchmark/cost重算三项screening | independent metric receipt |
| OOS-01 | M7_REAL_ACCEPTANCE | 任何M7路径不打开final-OOS | filesystem access receipt |

## 当前M6.5完成边界

本轮只要求并实现`M6.5_CONTRACT_ONLY`行，以及M6.5自身market-state/ledger/replay测试。其余行
只接受design review，不写M7 production code、不expected-red、不转green。M6.5 synthetic
E2E证明拒绝和validator边界，不证明M7/PIT/Alpha。

