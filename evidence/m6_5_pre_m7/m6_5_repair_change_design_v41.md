# M6.5 有界修复变更设计 v41

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v40；旧canonical均为`SUPERSEDED_HISTORY`。

## 1. Direct immutable bundle

```text
capacity_reservation_protocol_v11.md 209368c0dfe0d13f5471ada6d381ac5aec7e37ff06fb68442d379e196b05e252
nested_directory_recovery_v4.md 57a46db7a4f4e2b142efbb5bbd0b3ea2dfa461a8817c8d675fa855d9f2760632
run_authority_generation_v11.md 9bf0fd64c8397e2630773fe9e029043d69c4ab020e123092cf7438aa49685b2e
m7_change_design_v19.md 0a0bb3e6e17e98b52cc2e384743541fe30d7529e89a9f5eb1d295062d6cd7f09
m7_behavior_to_test_matrix_v19.md dab4f6fbb2627064de80ec26b3920f5f78de0c196efacf1429bce93b0003f82a
score_replay_identity_v2.md 135344637dd0694526f657996a2ebd957f9a93951ad528c088d1401faef3e3c6
score_replay_plan_v2.md f2d4fb763e744f2569f1cdd7689e0c959fdf1ae899381586317de5a9bbc6e589
```

每份versioned direct spec的Base path+完整SHA递归定义transitive closure；validator递归重算至
unversioned self-contained root。任一漂移STALE。pointer/addendum non-normative。

## 2. v40 review closure

- event-local raw table/bytes使用独立typed refs，固定slot、target schema及完整logical identity；
- observations、predictions、metrics、checkpoint、fit/refit receipts的exact schema和交叉相等冻结；
- worker使用同一open file description持续持event flock至OUTCOME receipt fsync，失锁即撤权终止；
- lease inventory digest统一为全字段LP并使用exact `event_seq`命名与明确编码；
- execution ID使用全字段LP，closure目录使用canonical SHA，root-FD no-follow阻止碰撞与路径逃逸；
- RuntimeClosureReceiptV4记录FD device/inode/flags/operations，完整write-like oracle仅允许OUTPUT FD；
- replay区分CanonicalJson、ImmutableFileManifest和OutputSlot三种身份，不得混用；
- ScoreReplayIdentityV2明确执行前只冻结input与安全slot，运行后SHA只进入receipt；
- ScoreReplayPlanV2固定output root/路径语法、2×7 pair、transaction slots、PairReceiptV2、
  AggregateResultV2、coverage digest及全crash recovery table；
- v19 test matrix加入所有本轮对抗反例并显式声明Base path+SHA。

## 3. Boundaries

M6 PASS且prefix 6/44；M7 NOT_RUN，future ceiling 8/60；replay NOT_AUTHORIZED且exact 2 merged+
14 per-fold；final-OOS sealed。设计PASS只允许test-design，不允许实现、训练、真实数据、fit、
replay、budget mutation、PIT或OOS。
