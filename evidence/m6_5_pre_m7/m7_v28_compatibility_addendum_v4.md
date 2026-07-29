# M7 v28/v26 兼容性附录 v4

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 架构：`architecture_confirmation_v28.md`
- canonical design：`m6_5_repair_change_design_v26.md`
- M7 subject：`m7_change_design_v4.md`
- behavior matrix：`m7_behavior_to_test_matrix_v4.md`

future Gate的唯一lineage是PreOOSAuxSnapshotV2及fixed+behavior双PASS qualification envelope；
generic `market_gate=True`永久关闭，专用factory固定`2*sigmoid`结构和checkpoint identity。

current cost/benchmark specs仍PLANNED，因此first M7 event/fit/claim均不允许。即使未来前置齐备，
当前预算也只允许两个隔离分支2 candidate/16 fit，到`8/60`；组合与额外fit要求新用户CR。

本附录不创建任何live object，不授权implementation、fit、screening、组合或final-OOS。

