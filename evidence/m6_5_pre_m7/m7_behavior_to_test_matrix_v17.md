# M7 behavior-to-test matrix v17

Base v16 SHA：
`40767b2765d5e7e1a9b37acc8d232108275af5170b82d7d870443e23f65c7a4e`。
V16 rows保留，新增：

| ID | Fixture | Oracle | Zero side effect |
| --- | --- | --- | --- |
| RES-TEMP-01 | valid RESERVED temp/final absent + second attempt | temp binds slot/reservation and is recovered first | second no marker |
| RES-TEMP-02 | malformed temp or duplicate slot claims | global HOLD | no admission |
| ROOT-01 | alias/nested/bind-mounted roots | policy FAIL | no scan/write |
| LEASE-05 | construct grant then claim | one-way hashes constructible | one claim |
| LEASE-06 | reconciler races worker flock | only lock holder proceeds | <=1 outcome |
| COMMIT-01 | lease inventory missing/wrong digest/future extra | activation FAIL | no commit |
| CONTENT-01 | valid wrapper + foreign/generic content | FAIL strict content | no outcome |
| LOC-01 | same security LIST/DELIST/revisions | V2 locators unique | no collision |
| LOC-02 | duplicate revision tuple/different locator | HOLD | no manifest |
| OBS-01 | observation row drops any V4 lineage field | strict FAIL | no SLA006 |
| SANDBOX-02 | vfork/clone3/posix_spawn/execveat/system | supervisor denies | no receipt PASS |
| SANDBOX-03 | forged supervisor receipt | trusted closure/evidence mismatch FAIL | no qualification |
| TRUST-05 | any CLI→policy/auth/receipt equality mismatch | FAIL before request | no anchor |
| REPLAY-04 | aware timezone/naive midnight/fold boundary mutation | ReplayIdentityV1 FAIL | no replay PASS |

只允许synthetic contract tests；M7/fit/replay/真实数据/budget/final-OOS未授权。
