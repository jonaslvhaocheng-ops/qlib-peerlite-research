# M7 behavior-to-test matrix v20

- Base：`m7_behavior_to_test_matrix_v19.md`
- Base SHA：`dab4f6fbb2627064de80ec26b3920f5f78de0c196efacf1429bce93b0003f82a`

V19 rows全部保留，新增：

| ID | Fixture | Oracle | Zero side effect |
| --- | --- | --- | --- |
| POLICY-01 | RuntimeStoragePolicyV2 substituted for required V5 | target schema FAIL | no reservation |
| INVOCATION-01 | same invocation slot, different bytes/attempt ID | deterministic exact invocation FAIL | no activation |
| TX-01 | input transaction missing, aliased to output or not COMMITTED | role/type/equality FAIL | no replay |
| OUTPUT-01 | manifest outside fixed payload slot or different bytes | transaction inventory FAIL/HOLD | no pair receipt |
| EXEC-01 | self-reported zero-fit without observed-call receipt | evidence missing FAIL | no pair receipt |
| EXEC-02 | CPU selected or CUDA runtime/device mismatch | execution receipt FAIL | no pair receipt |
| LOCK-06 | killed worker retains attempted filesystem FD | worker never receives such FD | no mutation |
| LOCK-07 | worker tree not reaped or pipe not EOF | supervisor retains flock/HOLD | no publication |
| RAW-01 | manifest verified then path inode/symlink swapped | same-open-FD consumption unaffected or FAIL | no substitute read |
| RAW-02 | nlink/device/inode differs from input transaction | identity FAIL | no replay |
| SYS-01 | pwritev2/copy_file_range/sendfile/splice/fallocate/io_uring write | default DENY | no mutation |
| COMPLETE-01 | payload-internal completion substituted for sibling formula | path equality FAIL | no COMMITTED |

所有测试只使用synthetic fixtures；M7、fit、replay、真实数据、PIT、budget和final-OOS未授权。
