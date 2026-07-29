# M6.5 有界修复变更设计 v42

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v41；旧canonical均为`SUPERSEDED_HISTORY`。

## 1. Direct immutable bundle

```text
capacity_reservation_protocol_v11.md 209368c0dfe0d13f5471ada6d381ac5aec7e37ff06fb68442d379e196b05e252
nested_directory_recovery_v4.md 57a46db7a4f4e2b142efbb5bbd0b3ea2dfa461a8817c8d675fa855d9f2760632
run_authority_generation_v12.md 69d52a04891ba3d00b2d1c8df944ebcf5ee0989690505e9a297696a4f0cfaa7b
m7_change_design_v20.md 5bc043ab057d718fa8a6583dce3809771347b2e50b51261226c621b67aef4752
m7_behavior_to_test_matrix_v20.md b2e79191c159c93fa9e4dbff23e76adce269ffa78b0abfb7016f01803b199970
score_replay_identity_v3.md 90c169d7ac4b7001fad2b3ffcc867ced240e2f8b77614adcf01fdee957f3c7bf
score_replay_plan_v3.md 8b70a5afc2201244bda854b0623fbfa8bed8c699a10194e14d0ec704589d87ef
```

每份versioned direct spec的Base path+完整SHA递归定义transitive closure；validator递归重算至
unversioned self-contained root。任一漂移STALE。pointer/addendum non-normative。

## 2. v41 review closure

- replay统一绑定current RuntimeStoragePolicyV5，target parent、same-device和root-disjoint exact；
- ImmutableFileManifestV2记录root/file device/inode/nlink，hash/validate/consume复用同一open FD；
- ReplayInputTransactionV1冻结并COMMITTED，和output transaction严格分离、不可alias；
- ScoreReplayReservationInvocationV1 exact bytes唯一决定attempt ID；
- raw parquet和固定output-manifest slot在同一Nested Recovery V4 payload中事务提交；
- sibling PREPARED/PUBLISH_COMPLETE/COMMITTED路径公式完全展开；
- trusted supervisor独占lease FD；worker从不获得lease或filesystem writable FD，只写framed pipe；
- supervisor先reap worker tree并确认pipe EOF，再从同一staging FD hash/seal/publish；
- RuntimeClosureReceiptV5使用default-deny syscall/opcode和same-FD staged-output evidence；
- ScoreReplayExecutionReceiptV1冻结launcher/code/runtime/argv/CUDA device、consumed input FDs、
  observed model calls、zero fit、ledger unchanged及OOS false；
- PairReceiptV3分别绑定input transaction、output transaction、execution receipt和fixed manifest；
- matrix v20覆盖policy downgrade、invocation substitution、transaction alias、CPU/self-report、
  stale writer、raw swap及unlisted write opcode。

## 3. Boundaries

M6 PASS且prefix 6/44；M7 NOT_RUN，future ceiling 8/60；replay NOT_AUTHORIZED且exact 2 merged+
14 per-fold；final-OOS sealed。设计PASS只允许test-design，不允许实现、训练、真实数据、fit、
replay、budget mutation、PIT或OOS。
