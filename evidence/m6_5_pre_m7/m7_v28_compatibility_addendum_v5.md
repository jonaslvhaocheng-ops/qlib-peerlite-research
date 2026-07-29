# M7 v28/v27 兼容性附录 v5

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- canonical：`m6_5_repair_change_design_v27.md`
- M7：`m7_change_design_v5.md`
- matrix：`m7_behavior_to_test_matrix_v5.md`

v27为自包含M6.5设计。M7 v5只允许未来两个隔离候选2 candidate/16 fit，到`8/60`；当前
cost/benchmark仍PLANNED，qualification/prerequisite/live authority均不存在，因此first event
禁止。generic Gate永久关闭；future仅有专用create/reload capability。

本附录不创建live对象，不授权implementation、fit、screening、组合或final-OOS。

