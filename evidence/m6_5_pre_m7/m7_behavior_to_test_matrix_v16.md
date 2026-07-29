# M7 behavior-to-test matrix v16

Base v15 matrix SHA：
`4db214941d62962766058ee0735a23e1e7fed89e183bba21178ce6ea1bde58ac`。
V15 rows保留，新增：

| ID | Fixture | Oracle | Zero side effect |
| --- | --- | --- | --- |
| DEV-01 | any root/target on second device | policy FAIL | no activation marker |
| DEV-02 | all target parents + hardlink pair scan | blocks dedup inode once | no false HOLD |
| LEASE-03 | crash before/after single RESERVED activation | zero effect or deterministic resume | no dangling ref |
| LEASE-04 | two markers bind one pool slot | HOLD under capacity lock | no new dirs |
| INODE-01 | two logical paths share staging inode | FAIL before PREPARED | no final root |
| EXEC-01 | two workers consume one STARTED | one flock/lease only | execution count<=1 |
| EXEC-02 | claim durable, STARTED absent, invalid lease | permanent HOLD | no cancel/retry |
| RESULT-01 | wrong kind/schema/path/model/fold/seed/checkpoint | FAIL before OUTCOME | no ledger append |
| TRUST-03 | trusted CLI policy SHA substituted by request | FAIL | no registration |
| TRUST-04 | parent authorization absent/wrong amendment | FAIL | no anchor |
| PROC-01 | fork/exec/subprocess/dynamic code attempt | sandbox FAIL | no qualification |
| PROC-02 | observed import/resource/FD set differs | receipt FAIL | no qualification |
| CLOCK-02 | LIST and DELIST field revisions have distinct clocks | each exact chain PASS | no clock reuse |
| CLOCK-03 | vendor>source>snapshot>observation inversion | HOLD | no SLA006 |
| SCHEMA-01 | extra/missing issuer/receipt/evidence key | strict FAIL | no downstream object |
| SHA-01 | prefixed SHA passed directly to hex decoder | validator strips only after strict parse | no crash/fallback |

所有test为M6.5 synthetic contract-only；M7/fit/replay/真实数据/budget mutation/final-OOS未授权。
