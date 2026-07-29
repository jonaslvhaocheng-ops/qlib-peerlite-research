# NestedDirectoryRecoveryV2

- 状态：`DESIGN_ONLY`
- 取代：`nested_directory_recovery_v1.md`
- 适用：`CapacityReservationProtocolV6` 的 PREPARED 后 immutable directory transaction。

## 1. Fixed paths and canonical rules

target paths 只能由 V6 runtime policy、`target_parent_index` 和 `target_name` 派生：

```text
publish_lock    = target_parent/("."+target_name+".publish.lock")
prepared_path   = target_parent/("."+target_name+".PREPARED.json")
target_root     = target_parent/target_name
completion_path = target_root/"PUBLISH_COMPLETE.json"
committed_path  = target_parent/("."+target_name+".COMMITTED.json")
```

三个 JSON 的 private temp 分别为 `<path>.tmp.<attempt_id>`；仅该 temp 可在 identical
inode/bytes 验证后清理，其他 sibling/internal unknown entry 一律 HOLD。ArtifactRef、canonical
JSON、file/canonical SHA 和 inventory semantics 完全采用 Capacity V6 §1。

## 2. Closed transaction schemas

`DirectoryPreparedV2` exact：

```json
{
  "schema_version": "qlib_peerlite_directory_prepared_v2",
  "attempt_id": "<64hex>",
  "runtime_policy": "<ArtifactRefV1>",
  "target_parent_index": "<decimal>",
  "target_name": "<ASCII>",
  "target_parent_device": "<decimal>",
  "target_parent_inode": "<decimal>",
  "source_inventory": "<ArtifactRefV1>",
  "staging_inventory": "<ArtifactRefV1>",
  "payload_inventory": "<ArtifactRefV1>",
  "schema_uuid": "<UUID lowercase>",
  "content_uuid": "<UUID lowercase>",
  "code_artifact": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`DirectoryPublishCompleteV2` exact：

```json
{
  "schema_version": "qlib_peerlite_directory_publish_complete_v2",
  "attempt_id": "<64hex>",
  "prepared": "<ArtifactRefV1>",
  "payload_inventory": "<ArtifactRefV1>",
  "target_parent_device": "<decimal>",
  "target_parent_inode": "<decimal>",
  "target_root_device": "<decimal>",
  "target_root_inode": "<decimal>",
  "regular_file_count": "<decimal>",
  "directory_count": "<decimal>",
  "entry_count": "<decimal>",
  "logical_bytes": "<decimal>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`DirectoryCommittedV2` exact：

```json
{
  "schema_version": "qlib_peerlite_directory_committed_v2",
  "attempt_id": "<64hex>",
  "prepared": "<ArtifactRefV1>",
  "publish_complete": "<ArtifactRefV1>",
  "payload_inventory": "<ArtifactRefV1>",
  "target_parent_device": "<decimal>",
  "target_parent_inode": "<decimal>",
  "target_root_device": "<decimal>",
  "target_root_inode": "<decimal>",
  "file_mode": "0440",
  "directory_mode": "0550",
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/extra/null 字段拒绝。PREPARED、completion、sibling committed 分别固定在 §1 的三个
paths；payload/staging inventory 固定在 derived inventory slots。payload inventory 不包含
PREPARED、completion、sibling markers或其temps。

## 3. Exact cross-object equalities and hardlink predicate

除了 Capacity V6 §6，transaction 内还必须满足：

```text
all attempt_id equal
all runtime-policy and target parent identities equal
PREPARED payload_inventory == completion payload_inventory == committed payload_inventory
completion four metrics == independently recomputed final payload inventory
all parent/root device+inode fields == fstat values
```

对每个已存在 final regular file，`inode-compatible` 的唯一含义为：

```text
S_ISREG(staging.mode) and S_ISREG(final.mode)
and staging.st_dev == final.st_dev
and staging.st_ino == final.st_ino
and staging.st_nlink >= 2 and final.st_nlink >= 2
and size/mode/content_sha256 == inventory values
```

即它必须就是同一个 staging inode 的 hardlink；仅内容相等但 inode 不同不接受。directory 必须
是本 transaction 创建并与 prepared inventory 的 exact path/device/inode/mode 相符。

## 4. Locking, publication and recovery

worker 持 attempt lease，再取 target parent publish lock；持 publish lock 时不得持 GC lock。
所有 lookup 通过已验证 parent/root FDs 加 `AT_SYMLINK_NOFOLLOW`。

1. sibling COMMITTED 存在：全量验证三对象、inventories、modes、inode predicate及父目录持久化
   evidence；valid 返回 COMMITTED，invalid HOLD，不改 payload。
2. PREPARED 不存在：返回 NOT_PREPARED；此规范不得创建 PREPARED。
3. PREPARED 存在且 completion 不存在：
   - staging exact 且 inventories匹配：创建/验证0700 root/dirs，逐file no-follow hardlink；
     existing 必须满足§3；每步执行 Capacity V6 四维 streaming enforcement；
     fsync files/dirs后，以fixed temp+hardlink no-replace发布completion并fsync target root；
   - staging缺失、变化或不匹配：HOLD，不 abort、不删除 final。
4. completion 存在且 sibling 不存在：验证 exact payload；descendant dirs bottom-up
   chmod/fsync0550，root chmod/fsync0550，fsync parent；以fixed temp+hardlink no-replace发布
   sibling COMMITTED，再 fsync parent。
5. sibling 发布后只验证，不再写 payload。

每个 publish 的 existing identical bytes resume，different bytes HOLD。crash 后必须用同一
PREPARED bytes 重入。不同 PREPARED、extra/missing payload、symlink/device/FIFO/socket、
mode/hash/inode冲突、未知 temp/entry 均 HOLD；无 overwrite/delete/quarantine。

## 5. Capacity terminal

释放 publish lock 后才可取得 GC lock。只有 transaction COMMITTED 全链验证通过，才发布
Capacity V6 COMMITTED；随后 POST_COMMIT unlink-only cleanup、RELEASED和0550 mode seal。
recovery 永不发布 ABORTED。input/output 各有独立 attempt、reservation和 transaction 链。
