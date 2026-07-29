# M7 architecture-v28 / change-v37 兼容性说明 v15

- 分类：`INFORMATIONAL_NAVIGATION / NON_NORMATIVE`
- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- canonical：`m6_5_repair_change_design_v37.md`

v37只关闭v36审查发现的可实现性问题：physical block reservation、precreated lease bootstrap、
phase-specific sealed inventory、durable run-ledger transitions、request-external issuer registry、
parser/resource/resolver closure、完整clock偏序及replay digest preimages。

PeerLite模型结构、Qlib接口、M6 `6/44`、两merged+十四per-fold和final-OOS边界不变。本文不属于
normative bundle，不授权训练、fit、replay、真实数据、budget或final-OOS。
