# M7 architecture-v28 / change-v36 兼容性说明 v14

- 分类：`INFORMATIONAL_NAVIGATION / NON_NORMATIVE`
- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- canonical：`m6_5_repair_change_design_v36.md`

v36继续保持architecture v28的低复杂度研究主线：不改变PeerLite、数据、score或组合接口，只把
M6.5执行前控制改成可实现、可失败注入测试的合同。容量使用logical/physical分离和最坏瞬时
预留；authority按commit永久预留budget；lifecycle绑定parser closure、冻结issuer trust anchor及
逐observation历史source record。

两merged expected+十四per-fold replay、M6 `6/44`、M7 `NOT_RUN`、final-OOS sealed均未改变。
本文不属于normative bundle，也不授权任何执行。
