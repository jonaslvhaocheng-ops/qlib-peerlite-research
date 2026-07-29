# M7 behavior-to-test matrix v12

Base v11 matrix SHA：
`75bb5106313ff5d2508d03dfaf4e8a55c67a75625efadc552a6cf1431f40bf57`。
保留其余基础行，替换/新增：

| ID | Owner | Oracle |
| --- | --- | --- |
| POISON-01 | M6.5_CONTRACT_ONLY | typed canonical semantic inequality；illegal/non-domain/noop拒绝 |
| POISON-02 | M6.5_CONTRACT_ONLY | versioned null→date DELIST history；2023退市证券2020仍active |
| LIFE-01 | M6.5_CONTRACT_ONLY | source/date/issuer/observation/final/receipt wrappers unknown-key拒绝 |
| LIFE-02 | M6.5_CONTRACT_ONLY | issuer exact授权evidence file与key/value/logical digests |
| LIFE-03 | M6.5_CONTRACT_ONLY | full observation coverage；missing interval HOLD，不产生PASS UNKNOWN |
| LIFE-04 | M6.5_CONTRACT_ONLY | SLA006 exact Cartesian records与四digests |
| RES-01 | M6.5_CONTRACT_ONLY | active dir0700→RELEASED fsync→0550；fixed receipt slots |
| RES-02 | M6.5_CONTRACT_ONLY | root/device/inode+attempt-derived paths、ArtifactRefs、file/canonical domains |
| RES-03 | M6.5_CONTRACT_ONLY | oversized orphan permanent HOLD；PREPARED recovery完整state machine |
| AUTH-01 | M6.5_CONTRACT_ONLY | authority-registration equality、plan ArtifactRef、purpose/event/caps matrix |

只实现M6.5 contract-only；M7/fit/final-OOS未授权。
