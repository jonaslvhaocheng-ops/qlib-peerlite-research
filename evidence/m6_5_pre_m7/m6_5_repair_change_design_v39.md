# M6.5 有界修复变更设计 v39

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v38；旧canonical均为`SUPERSEDED_HISTORY`。

## 1. Direct normative bundle

```text
capacity_reservation_protocol_v10.md 4cd04aaa213ecf4f5f97850df8a87d17936bff398ee65a2b5752b9769250b72d
nested_directory_recovery_v4.md 57a46db7a4f4e2b142efbb5bbd0b3ea2dfa461a8817c8d675fa855d9f2760632
run_authority_generation_v9.md 265962b0972dd3c38221b80e540f9ca28c3b454c68262fb3068d7a5d504cab2d
m7_change_design_v17.md b776b3e05abccb9a8aaf2a72190c9defcb48f4815a326823f2283897f9a1337c
m7_behavior_to_test_matrix_v17.md a82bab91d7b555161fb2b96f14ba337bdd9497a7d57a90b90f4c83254948f112
score_replay_identity_v1.md ed803a7df33eb3286d28a70ecd051c11d00911f1a1535d895eac9b580843d79f
```

Transitive closure由每份direct spec的Base path+SHA递归组成；递归终点及SHA：

```text
capacity v10→v9 32f6110d…→v8 de39c396…→v7 79696cfa…→v6 a2e2d563…
nested v4 57a46db7…→v3 0e527f20…→v2 a712b009…
authority v9→v8 c5772d9f…→v7 e41f6eab…→v6 fd3f6b5b…→v5 71c79627…
M7 v17→v16 637b167f…→v15 8ec3b876…→v14 7fa0a379…→v13 e907d921…
→v12 80240e3c…→v11 642e6e54…→v10 bfa95544…→v9 ad5ae903…
matrix v17→v16 40767b27…→v15 4db21494…→v14 641a8560…→v13 b23c66b4…
→v12 9df558dc…→v11 75bb5106…→v10 3dc53799…→v9 0088cf25…
```

省略号只用于人读短写；validator必须从每个base文件的完整64hex声明递归重算，不能比较短写。
任一direct/transitive漂移STALE。pointer/addendum non-normative。

## 2. v38 closure

- all roots identity-disjoint/non-nested；RESERVED valid temp也临时占用slot+capacity；
- lease grant删除claim ref并固定path，形成lock→grant→claim→STARTED单向DAG；
- closed lease inventory与AuthorityGenerationCommitV7，future precommit例外唯一；
- event result四类content均fixed path/schema/identity/checkpoint；
- reconciler必须持同一exclusive flock完成rescan→INTERRUPTED→ledger fsync；
- supervisor sandbox receipt closed schema，禁止全部spawn variants和dynamic code；
- trusted CLI inputs到policy/parent auth/freeze receipt逐字段exact equality；
- historical locator包含security+field+revision，revision tuple/locator分别唯一；
- Evidence V4含field-specific vendor clock；ObservationManifestV2完整保留全部lineage；
- replay全部移入独立exact-SHA ScoreReplayIdentityV1，避免canonical升级回退。

## 3. Fixed boundaries

- M6 PASS，prefix exact 6 candidate / 44 fit；
- M7 CCC/Gate commit-time永久上限8/60，失败/中断无replacement；
- replay exact 2 merged expected + 14 singleton-fold outputs，但`NOT_AUTHORIZED`；
- final-OOS sealed；
- v39 design PASS也只允许进入test-design，不允许实现/训练/真实数据/fit/replay/budget/OOS。
