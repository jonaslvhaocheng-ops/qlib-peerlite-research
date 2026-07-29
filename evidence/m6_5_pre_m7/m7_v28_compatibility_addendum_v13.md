# M7 architecture-v28 / change-v35 兼容性附录 v13

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- canonical：`m6_5_repair_change_design_v35.md`
- capacity：`capacity_reservation_protocol_v6.md`
- transaction：`nested_directory_recovery_v2.md`
- authority：`run_authority_generation_v5.md`
- M7：`m7_change_design_v13.md`
- matrix：`m7_behavior_to_test_matrix_v13.md`

v35 只关闭 v34 独立审查提出的执行前控制缺口：四维容量和inode门、source expected equality、
streaming enforcement、跨协议identity、closed transaction schemas、fixed temp recovery、
durable activation、跨generation `6/44→8/60`预算、CCC/Gate qualification顺序、typed numeric
canonicalization、PRE_LIST语义及evidence-record/source reconciliation。

PeerLite结构、M6已验证结果、两merged expected+十四per-fold replay粒度、AP语义、dual AP005、
CCC/Gate隔离和final-OOS边界均未改变。

当前 cost、benchmark、真实 lifecycle authority、screening prerequisite、qualification 和 live
authority仍不存在；本附录不授权M7、fit、budget、replay、真实数据或final-OOS。
