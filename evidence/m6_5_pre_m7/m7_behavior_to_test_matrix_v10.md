# M7 behavior-to-test matrix v10

Base：v9 matrix exact SHA
`0088cf25f5328b4c128d42d4b51772c21648609c41bfaf419fefb19c58841d58`。
保留v9全部行；以下精确替换/新增：

| ID | Owner | Oracle |
| --- | --- | --- |
| QUAL-02 | M6.5_CONTRACT_ONLY | official scalar/十slots；one-record-per-field snapshot、raw key与supplement一对一 |
| QUAL-04 | M6.5_CONTRACT_ONLY | closed AP invocation + 六个product manifests绑定official snapshots/T/policy/source |
| QUAL-05 | M6.5_CONTRACT_ONLY | 三产品非空expected axis、15 equality、exact AP001-AP005 |
| QUAL-06A | M6.5_CONTRACT_ONLY | official baseline/probe CSV逐侧等于state product，receipt expected keys独立重算 |
| QUAL-07 | M6.5_CONTRACT_ONLY | lifecycle exact role DAG/source/evidence/rows/authority/receipt schemas |
| QUAL-07A | M6.5_CONTRACT_ONLY | evidence locator/hash、calendar 09:30边界、60 sessions、全security×date SLA006 |
| QUAL-08 | M6.5_CONTRACT_ONLY | lifecycle slot缺失/回边/过期/coverage错时qualification前HOLD |
| SCORE-01 | M6.5_CONTRACT_ONLY | M6五列身份、2×7 exact fold集合/窗口/SHA，再显式三列canonical projection |
| RES-01 | M6.5_CONTRACT_ONLY | 初始/resume/recovery先attempt lease；malformed RELEASED仍计费 |
| ABORT-01 | M6.5_CONTRACT_ONLY | abort锁序及四个publish path同临界区absence receipt |
| GEN-02 | M6.5_CONTRACT_ONLY | registration/generation commit/activation receipt exact closed schemas |

仍只实现`M6.5_CONTRACT_ONLY`；M7 implementation/fit/final-OOS未授权。
