# CapacityReservationProtocolV9

- 状态：`DESIGN_ONLY`
- Base：`capacity_reservation_protocol_v8.md`
- Base SHA：`de39c396b6b26f3e3be579db6ab94d5e3fc078da61adce72c46b6d97cb090b98`
- 取代：V8。

## 1. One filesystem and complete scan scope

RuntimeStoragePolicyV5要求reservation root、staging root、precreated lease pool及**每一个**
target parent的`st_dev`都exact等于唯一`filesystem_device`；任一不同即policy FAIL。root list按
absolute path UTF-8排序唯一，并保存每个path/device/inode。

capacity scanner的完整scope恰为：

```text
reservation_root
staging_root
lease_pool_root
all target_parents in policy order
```

通过root FDs no-follow递归扫描。regular-file allocated blocks按`(st_dev,st_ino)`全scope去重一次；
directory blocks按directory inode去重一次；同inode跨attempt出现直接HOLD，唯一允许的跨root共享
inode是同attempt staging→final manifest明确列出的hardlink pair。block/inode/entry/floor均在
该唯一device上重算。

## 2. Single durable reservation activation

删除V8 `LeaseBindingV1`和`reservation_dir/RESERVED.json`。唯一activation marker固定为：

```text
reservation_root/<attempt_id>.RESERVED.json
```

`ReservedActivationV9` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_reserved_v9",
  "attempt_id": "<64hex>",
  "origin": "NORMAL|ORPHAN_RECOVERY",
  "invocation": "<ArtifactRefV1>",
  "runtime_policy": "<ArtifactRefV1>",
  "source_inventory": "<ArtifactRefV1>",
  "target_parent_index": "<decimal>",
  "target_name": "<ASCII>",
  "lease_slot_index": "<decimal>",
  "lease_slot_path": "<policy-derived absolute>",
  "lease_slot_device": "<decimal>",
  "lease_slot_inode": "<decimal>",
  "expected_logical_bytes": "<decimal>",
  "expected_regular_file_count": "<decimal>",
  "expected_directory_count": "<decimal>",
  "expected_entry_count": "<decimal>",
  "filesystem_blocks_reserved": "<decimal>",
  "filesystem_inodes_reserved": "<decimal>",
  "filesystem_entries_reserved": "<decimal>",
  "canonical_sha256": "sha256:<64hex>"
}
```

bootstrap：

1. 取得capacity lock，零per-attempt path；
2. 选择未被任何valid activation marker绑定的最小precreated lease slot并flock；
3. 重算capacity，使用V8 durable temp protocol在reservation root发布唯一activation marker；
4. marker parent fsync成功即容量与slot同时激活；之后才创建reservation/staging dirs；
5. crash在marker前零durable side effect（只有temp按closed table恢复）；crash在marker后由marker
   唯一重建dirs/chain，不删除marker、不重复reservation；
6. recovery在capacity lock内重取marker指定slot；slot被其他marker绑定则HOLD。

不存在两个final的先后或dangling ref。

## 3. Exact footprint and unique staging inodes

control最大为4 dirs+18 files=`22`；V8 exact19 file set删除`LEASE_BINDING`，其余名称不变。
policy `control_slot_max_bytes`必须恰含18 names。activation RESERVED虽位于reservation root，仍是
该18中的RESERVED slot。

STAGING_PHYSICAL发布前要求所有logical regular paths的`(st_dev,st_ino)`两两唯一且
`observed_nlink=1`；禁止source/materializer保留内部hardlink或外部link。PRE_SEAL/SEALED时每个
pair nlink=2；POST_CLEANUP后final nlink=1。因此receipt规则不再依赖未声明前提。

V8 formulas把control constant `23`替换为`22`，control file count `19`替换为`18`；其余
fragment/block/directory overhead计算不变。所有variable-size control object在activation前以
schema maximum serializer计算，必须不超过对应slot max，否则不发布marker。
