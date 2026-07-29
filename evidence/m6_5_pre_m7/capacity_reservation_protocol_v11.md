# CapacityReservationProtocolV11

- 状态：`DESIGN_ONLY`
- Base：`capacity_reservation_protocol_v10.md`
- Base SHA：`4cd04aaa213ecf4f5f97850df8a87d17936bff398ee65a2b5752b9769250b72d`
- 取代：V10。

capacity lock内顺序唯一为：

1. read-only全量分类所有RESERVED finals和temps；
2. 解析全部valid bindings，malformed立即global HOLD；
3. 在**任何promotion前**检查attempt/slot/path/capacity duplicate；任一duplicate HOLD且零write；
4. duplicates=0后，按attempt ID UTF-8排序逐个使用closed temp table恢复valid temp；
5. fsync后重新全量scan并确认无temp/different object；
6. 才选择新slot和执行admission。

不得先promotion再发现duplicate。
