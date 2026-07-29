# M7 behavior-to-test matrix v13

Base v12 matrix SHA：
`9df558dcb671facc1556ace0b53b9f855a67bc68fd80677dfbbf781c6f60d6d3`。
保留其余基础行，替换/新增：

| ID | Owner | Oracle |
| --- | --- | --- |
| CAP-01 | M6.5_CONTRACT_ONLY | expected四metrics等于sealed source独立重算；低报/TOCTOU拒绝 |
| CAP-02 | M6.5_CONTRACT_ONLY | byte/file/dir/entry四维caps与aggregate门；`f_favail` inode floor |
| CAP-03 | M6.5_CONTRACT_ONLY | 每个创建/写/hardlink前后四维不变量；越界在PREPARED前abort |
| CAP-04 | M6.5_CONTRACT_ONLY | fixed temp只清理identical本attempt temp；unknown entry HOLD |
| TXN-01 | M6.5_CONTRACT_ONLY | PREPARED/completion/sibling closed schemas与cross-protocol equality |
| TXN-02 | M6.5_CONTRACT_ONLY | existing final必须与staging exact `(st_dev,st_ino)` hardlink相同 |
| AUTH-01 | M6.5_CONTRACT_ONLY | fixed registry paths、global lock、no-replace/fsync、commit唯一激活点 |
| AUTH-02 | M6.5_CONTRACT_ONLY | exact 6/44 head；trial purpose仅[]→CCC→CCC,Gate；累计<=8/60 |
| AUTH-03 | M6.5_CONTRACT_ONLY | FAILED/INTERRUPTED/ABORT仍计费、无replacement；两purpose均qualification PASS |
| LIFE-01 | M6.5_CONTRACT_ONLY | canonical decimal grammar、parser ArtifactRef、semantic noop拒绝 |
| LIFE-02 | M6.5_CONTRACT_ONLY | intervals半开、same-time冲突拒绝、唯一selection |
| LIFE-03 | M6.5_CONTRACT_ONLY | PRE_LIST固定false/0；coverage从LIST observed_from开始 |
| LIFE-04 | M6.5_CONTRACT_ONLY | evidence artifact+record canonical hash；source/security/final equality |
| LIFE-05 | M6.5_CONTRACT_ONLY | issuer在receipt verified_at有效；event clock不晚于observation clock |
| REPLAY-01 | M6.5_CONTRACT_ONLY | 2 merged expected + 14 singleton-fold outputs；date canonicalize后检查window |

只实现 M6.5 contract-only tests；M7 authority、fit、replay、真实数据与 final-OOS 均未授权。
