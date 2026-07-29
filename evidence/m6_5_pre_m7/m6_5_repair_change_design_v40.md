# M6.5 有界修复变更设计 v40

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v39；旧canonical均为`SUPERSEDED_HISTORY`。

## 1. Direct immutable bundle

```text
capacity_reservation_protocol_v11.md 209368c0dfe0d13f5471ada6d381ac5aec7e37ff06fb68442d379e196b05e252
nested_directory_recovery_v4.md 57a46db7a4f4e2b142efbb5bbd0b3ea2dfa461a8817c8d675fa855d9f2760632
run_authority_generation_v10.md 8a86443ea68582d84a69f5194b64a6d07ce7081f1f392e66b9905954b06371a8
m7_change_design_v18.md 3b82fb2c5518f2765505169697fe139ffa4165751a0675e0607293fe0319d37a
m7_behavior_to_test_matrix_v18.md 5ff12c3a924bdd4308eb8b69f76ea72a35db2be5dd935635a4f1b015da8b59f7
score_replay_identity_v1.md ed803a7df33eb3286d28a70ecd051c11d00911f1a1535d895eac9b580843d79f
score_replay_plan_v1.md 96949101947b63b6d57d3ba963d7b7e95acc5513313eea5384f5b4418e43e145
```

每份versioned direct spec的Base path+完整SHA递归定义transitive closure；validator递归重算至
unversioned self-contained root。任一漂移STALE。pointer/addendum non-normative。

## 2. v39 closure

- duplicate RESERVED finals/temps在任何promotion前完成全量检查；
- EventExecutionLeaseV2 exact schema和lease inventory全字段LP digest；
- wrapper使用单一wrapper ID，四种content使用四个独立content IDs；
- inner observations/predictions/training/refit/checkpoint/metrics固定schema/path/identity；
- external trust保持Authorization→Policy单向，不引用不存在的policy auth field；
- sandbox deny全部path mutation syscall，每closure execution使用唯一receipt slot；
- evidence采用JSONL artifact+record ID+record canonical SHA；
- ObservationManifest historical set coverage及schema/key/value/logical digest全部冻结；
- ScoreReplayPlanV1将2×7 inputs/output slots与运行后receipts分离并closed schema。

## 3. Boundaries

M6 PASS且prefix 6/44；M7 NOT_RUN，future ceiling 8/60；replay NOT_AUTHORIZED且exact 2 merged+
14 per-fold；final-OOS sealed。设计PASS只允许test-design，不允许实现、训练、真实数据、fit、
replay、budget mutation或OOS。
