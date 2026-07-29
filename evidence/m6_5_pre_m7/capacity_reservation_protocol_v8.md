# CapacityReservationProtocolV8

- 状态：`DESIGN_ONLY`
- Base：`capacity_reservation_protocol_v7.md`
- Base SHA：`79696cfa6b071c29673a44fb85456b484fdbc5ee7eb28f65f8ba0abeb8717fbf`
- 取代：V7。

## 1. Exact composition

V7 logical/physical projection、bijection、fixed roots、marker/receipt、orphan、mode-seal和capacity
lock语义保留。V7 control set、byte reservation、lease acquisition、inventory phases和temp fsync
由本文件完整替换。

## 2. Exact control footprint

per-attempt最大同时存在exact 4 control directories：

```text
reservation_dir
reservation_dir/receipts
reservation_dir/inventories
staging_dir
```

exact 19 control file slots：

```text
RESERVED
MATERIALIZING
COMMITTED_OR_ABORTED
RELEASED
ABORT_ABSENCE
CLEANUP
POST_CLEANUP_LINK
SOURCE_REVALIDATION
STAGING_PHYSICAL
PAYLOAD_LOGICAL
PRE_SEAL_FINAL_PHYSICAL
SEALED_FINAL_PHYSICAL
LEASE_BINDING
PUBLISH_LOCK
DIRECTORY_PREPARED
DIRECTORY_PUBLISH_COMPLETE
DIRECTORY_COMMITTED
ONE_RESERVATION_TEMP
ONE_TRANSACTION_TEMP
```

`COMMITTED_OR_ABORTED`是互斥最大slot；temp是同类publish串行化后的最大同时数。故control
inode/entry constant exact为`4+19=23`。policy的`control_slot_max_bytes`必须恰含上述19 names、
排序唯一、每项positive decimal；`CONTROL_BYTE_CEILING=sum(max_bytes)`。

inventory slots替换为：

```text
<reservation_dir>/inventories/SOURCE_REVALIDATION.json
<reservation_dir>/inventories/STAGING_PHYSICAL.json
<reservation_dir>/inventories/PAYLOAD_LOGICAL.json
<reservation_dir>/inventories/PRE_SEAL_FINAL_PHYSICAL.json
<reservation_dir>/inventories/SEALED_FINAL_PHYSICAL.json
```

receipt新增：

```text
<reservation_dir>/receipts/POST_CLEANUP_LINK.json
```

## 3. Filesystem-block reservation

RuntimeStoragePolicyV4除V7字段外exact新增：

```text
filesystem_device
filesystem_fragment_bytes
regular_file_overhead_blocks
directory_block_ceiling
control_slot_max_bytes[exact 19]
lease_pool{root path/device/inode,slot_count,precreated slots}
```

`filesystem_fragment_bytes`必须等于目标filesystem `statvfs.f_frsize`且positive。每个precreated
lease slot是已存在regular 0440 lock file，slots从0连续，pool root no-symlink且不与数据roots
alias。pool自身已在policy freeze前计入baseline，不计作attempt新inode。

定义：

```text
alloc_file(size) =
  (ceil(size / f_frsize) + regular_file_overhead_blocks) * f_frsize
alloc_dir = directory_block_ceiling
```

零字节regular file仍承担overhead blocks。对payload `F,D,E,B`：

```text
payload_block_reservation =
  sum(alloc_file(size) for each logical regular file)
  + 2*(D+1)*alloc_dir

control_block_reservation =
  sum(alloc_file(slot_max_bytes) for exact 19 file slots)
  + 4*alloc_dir

filesystem_blocks_reserved =
  payload_block_reservation + control_block_reservation
filesystem_new_inodes_reserved = F + 2*(D+1) + 23
filesystem_new_entries_reserved = 2*(E+1) + 23
```

final files为staging hardlinks，所以不重复分配data blocks，但其directory entries已计入。
admission/free-space floor和streaming全部使用filesystem block reservation；实际值使用
no-follow `st_blocks*512`求和并加directory `st_blocks*512`。若实际allocation或任一目录超过
policy ceiling，PREPARED前ABORT、之后HOLD。logical bytes仅用于payload/cap审计，不再作为
`f_bavail` oracle。

## 4. Lease bootstrap without pre-admission inode

bootstrap是唯一允许的GC→lease顺序：

1. 先取得capacity/GC lock，不创建任何per-attempt path；
2. 扫描active LEASE_BINDING，选最小未绑定precreated pool slot并nonblocking flock；
3. 持GC+pool-slot lock重验全局blocks/inodes/entries/floors和attempt absence；
4. 在预留范围内创建reservation/staging dirs，发布exact `LeaseBindingV1`及RESERVED；
5. fsync相关parents后释放GC，但持续持有pool-slot lock作为attempt lease。

`LeaseBindingV1` exact：

```json
{
  "schema_version": "qlib_peerlite_lease_binding_v1",
  "attempt_id": "<64hex>",
  "lease_pool_policy": "<ArtifactRefV1>",
  "slot_index": "<decimal>",
  "slot_path": "<policy-derived absolute>",
  "slot_device": "<decimal>",
  "slot_inode": "<decimal>",
  "reserved": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

失败时在仍持GC+slot lock下完成无痕回滚，不能留下attempt dirs/markers。bootstrap完成后的固定
锁序恢复为attempt lease→GC→parent。没有空闲slot则拒绝且零副作用。

## 5. Durable temp publication

V7 temp状态表保留，但create顺序修正为：

```text
create temp -> write -> fsync(temp data) -> chmod0440
-> fsync(temp inode after chmod) -> fsync(parent)
-> hardlink no-replace -> fsync(parent)
-> unlink temp -> fsync(parent)
```

每个crash point都按V7状态表恢复；不存在chmod后未fsync mode的合法分支。

## 6. Phase-specific physical artifacts

`PhysicalInventoryV4`以V7 V3为base，新增`phase=STAGING|PRE_SEAL_FINAL|SEALED_FINAL`，
把`nlink`改名`observed_nlink`并声明它是发布时观测值，不是长期相等字段。

- STAGING：dirs0700、files0440；
- PRE_SEAL_FINAL：dirs0700、files0440，regular files与staging same inode且nlink>=2；
- SEALED_FINAL：dirs0550、files0440，regular files同inode且发布时nlink>=2。

POST_CLEANUP_LINK receipt exact逐logical regular path绑定staging/final device+inode、sealed observed
nlink、staging path result ENOENT、final post nlink=`1`，并绑定CLEANUP和SEALED_FINAL refs。
长期COMMITTED验证final dev/inode/size/hash/mode等于SEALED_FINAL，当前nlink>=1，并验证该receipt；
不要求已删除staging link继续存在。
