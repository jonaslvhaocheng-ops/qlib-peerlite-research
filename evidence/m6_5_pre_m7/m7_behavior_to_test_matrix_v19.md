# M7 behavior-to-test matrix v19

- Base：`m7_behavior_to_test_matrix_v18.md`
- Base SHA：`5ff12c3a924bdd4308eb8b69f76ea72a35db2be5dd935635a4f1b015da8b59f7`

V18 rows全部保留，新增：

| ID | Fixture | Oracle | Zero side effect |
| --- | --- | --- | --- |
| CONTENT-04 | valid fit content but receipt checkpoint/metrics refs differ | strict equality FAIL | no wrapper/outcome |
| CONTENT-05 | foreign-event rows, metrics or checkpoint bytes | event-root containment FAIL | no wrapper/outcome |
| CONTENT-06 | raw binary/Markdown/generic ArtifactRef substitutes typed ref | target schema/ref parser FAIL | no wrapper/outcome |
| LOCK-04 | worker closes or loses flock after STARTED | revoke OUTPUT FDs, terminate/HOLD | no result/outcome |
| LOCK-05 | reconciler races stale worker | only current flock owner may publish | one terminal transition |
| RECEIPT-02 | delimiter-collision inputs | LP execution IDs differ | no slot collision |
| RECEIPT-03 | closure ID contains `/`, `..`, separator or control | digest-derived segment only | no path escape |
| FD-01 | write/pwrite/writev/shared mmap to INPUT or unknown FD | syscall oracle DENY | no mutation |
| FD-02 | FD device/inode/flags changed between entry and exit | receipt FAIL | no PASS receipt |
| REPLAY-06 | plan output `../`, absolute, symlink, hardlink alias or cross-device | root-FD containment FAIL | no output |
| REPLAY-07 | pair merged ref differs from expected_models ref | strict equality FAIL | no execution |
| REPLAY-08 | raw file presented as canonical JSON ref or vice versa | ref type FAIL | no execution |
| REPLAY-09 | crash after output publish before pair receipt | recovery validates transaction; no aggregate PASS | no replacement |
| REPLAY-10 | missing/extra/duplicate receipt or unknown output | exact 14 coverage FAIL | no aggregate PASS |

所有测试只使用synthetic fixtures。M7、fit、replay、真实数据、PIT、预算和final-OOS仍未授权。
