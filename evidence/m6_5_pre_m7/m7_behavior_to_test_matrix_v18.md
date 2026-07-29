# M7 behavior-to-test matrix v18

Base v17 SHA：
`a82bab91d7b555161fb2b96f14ba337bdd9497a7d57a90b90f4c83254948f112`。
V17 rows保留，新增：

| ID | Fixture | Oracle | Zero side effect |
| --- | --- | --- | --- |
| RES-TEMP-03 | two valid temps same slot | duplicate HOLD before promotion | no finals |
| LEASE-07 | lease V2 schema/downstream claim injection | strict FAIL | no claim |
| LEASE-08 | inventory raw-delimiter collision | LP digest differs/FAIL | no commit |
| CONTENT-02 | wrapper/content reuse schema ID | distinct parser IDs required | no outcome |
| CONTENT-03 | foreign inner prediction/receipt/checkpoint | identity/path FAIL | no wrapper |
| TRUST-06 | authorization→policy valid vs policy→authorization cycle | only one-way PASS | no cycle |
| FS-01 | openat2/rename/link/symlink/mkdir/chmod mutation | sandbox deny | no filesystem change |
| RECEIPT-01 | two closure executions same root | unique execution slots | no collision |
| OBS-02 | JSONL row wrong ID/hash/artifact | FAIL | no observation manifest |
| OBS-03 | manifest unused/undeclared/duplicate | FAIL coverage | no SLA006 |
| DIGEST-01 | schema/key/value/order mutation | exact digest mismatch | no authority |
| REPLAY-05 | plan missing/extra pair or duplicate output slot | strict FAIL | no replay |

仅synthetic contract tests；M7/fit/replay/真实数据/budget/final-OOS未授权。
