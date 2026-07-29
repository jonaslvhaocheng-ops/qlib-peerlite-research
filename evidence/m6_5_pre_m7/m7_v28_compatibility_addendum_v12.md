# M7 architecture-v28 / change-v34 兼容性附录 v12

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- canonical：`m6_5_repair_change_design_v34.md`
- M7：`m7_change_design_v12.md`
- matrix：`m7_behavior_to_test_matrix_v12.md`
- reservation：`capacity_reservation_protocol_v5.md`
- nested recovery：`nested_directory_recovery_v1.md`
- authority generation：`run_authority_generation_v4.md`

M7 v12 只补强 qualification 与执行前控制合同：固定 reservation/staging/lease roots，
attempt-derived 唯一路径，active/released 目录模式，持久 ArtifactRef 定位与双哈希域，
authority-registration-plan-purpose 等值约束，oversized orphan fail-closed，自包含
PREPARED 恢复，typed semantic poison，版本化 delist observation，以及闭合的
lifecycle wrappers、issuer evidence 和 SLA006 digest projection。

M7 v11 中已经冻结的 AP 语义、dual AP005、固定 audit/population/security/date axes、
CCC/Gate 双 generation、0 replacement、`6/44 → max 8/60` 和 first-event 禁入保持不变。

当前 cost、benchmark、lifecycle authority、screening prerequisite 和 live authority
仍不存在；本附录不授权 M7、fit、budget、replay、真实数据访问或 final-OOS。
