# CapacityReservationProtocolV10

- 状态：`DESIGN_ONLY`
- Base：`capacity_reservation_protocol_v9.md`
- Base SHA：`32f6110dd10c7b6e80da922a8c934ba4032548e97528f88ea4bb6a61599d025f`
- 取代：V9。

## 1. Root disjointness

reservation/staging/lease-pool/all target-parent roots除same device外，还必须pairwise：

```text
different normalized realpaths
neither path is ancestor/descendant of another
different (st_dev,st_ino)
no bind mount or alias after FD/fstat verification
```

目录entries按`(parent_dev,parent_ino,name_bytes)`全scope union计数；每entry恰归属一个root和一个
attempt。任一overlap/alias/ambiguous ownership使policy FAIL。

## 2. RESERVED temp is a provisional binding

capacity lock内，每次admission前先全量分类：

```text
reservation_root/<attempt_id>.RESERVED.json
reservation_root/<attempt_id>.RESERVED.json.tmp.<attempt_id>
```

valid final绑定其slot与reservation；valid temp即使final缺失也**同样临时绑定**其声明slot和全部
reserved blocks/inodes/entries。scanner先按V8 temp table把valid temp恢复为final，再考虑新
admission。temp+final same inode清理temp；different inode/bytes HOLD。

malformed/partial temp无法可信解析slot或capacity时，使**整个admission全局HOLD**，不得猜空slot；
保守charge使用per-attempt maxima。两个temp/final声明同slot、同attempt两个不同temp或一个slot
多claim均HOLD。只有完成全部temp recovery和duplicate scan后，才选择最小未绑定precreated slot。

因此“temp fsync、final缺失、flock已释放”时，第二attempt不能取得该slot。
