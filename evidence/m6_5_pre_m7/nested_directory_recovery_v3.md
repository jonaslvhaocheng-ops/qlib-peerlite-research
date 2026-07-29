# NestedDirectoryRecoveryV3

- 状态：`DESIGN_ONLY`
- Base：`nested_directory_recovery_v2.md`
- Base SHA：`a712b0094ae1571027e0c92bd9b92a68ce3aa5708d47b5cdbc2343ba834b1bd7`
- 取代：V2。

## 1. Exact composition

V2 fixed target paths、lock order、no-follow、mode seal、same-claim recovery及capacity terminal保留。
V2 §2–§3对象与inode语义由本文件完整替换；JSON publication/recovery采用Capacity V7 §4。

## 2. Closed transaction objects

`DirectoryPreparedV3` exact：

```json
{
  "schema_version": "qlib_peerlite_directory_prepared_v3",
  "attempt_id": "<64hex>",
  "runtime_policy": "<ArtifactRefV1>",
  "target_parent_index": "<decimal>",
  "target_name": "<ASCII>",
  "target_parent_device": "<decimal>",
  "target_parent_inode": "<decimal>",
  "source_revalidation": "<ArtifactRefV1>",
  "staging_physical_inventory": "<ArtifactRefV1>",
  "payload_logical_manifest": "<ArtifactRefV1>",
  "schema_uuid": "<UUID lowercase>",
  "content_uuid": "<UUID lowercase>",
  "code_artifact": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

PREPARED不含final root/directory inode，也不引用尚不存在的FINAL_PHYSICAL。

`DirectoryPublishCompleteV3` exact：

```json
{
  "schema_version": "qlib_peerlite_directory_publish_complete_v3",
  "attempt_id": "<64hex>",
  "prepared": "<ArtifactRefV1>",
  "payload_logical_manifest": "<ArtifactRefV1>",
  "final_physical_inventory": "<ArtifactRefV1>",
  "target_parent_device": "<decimal>",
  "target_parent_inode": "<decimal>",
  "target_root_device": "<decimal>",
  "target_root_inode": "<decimal>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`DirectoryCommittedV3` exact：

```json
{
  "schema_version": "qlib_peerlite_directory_committed_v3",
  "attempt_id": "<64hex>",
  "prepared": "<ArtifactRefV1>",
  "publish_complete": "<ArtifactRefV1>",
  "payload_logical_manifest": "<ArtifactRefV1>",
  "final_physical_inventory": "<ArtifactRefV1>",
  "target_parent_device": "<decimal>",
  "target_parent_inode": "<decimal>",
  "target_root_device": "<decimal>",
  "target_root_inode": "<decimal>",
  "file_mode": "0440",
  "directory_mode": "0550",
  "canonical_sha256": "sha256:<64hex>"
}
```

三个对象固定slots与V2相同；logical/physical inventory固定slots由Capacity V7 §3定义。

## 3. Bijection and inode predicates

PREPARED前：

```text
source revalidation projection
== staging physical projection
== payload logical manifest
```

final tree建成后独立发布FINAL_PHYSICAL，要求其projection exact等于payload logical manifest。
因此每个relative path/type/size/content一一对应，无missing/extra/rename/subset。

regular file逐path要求：

```text
S_ISREG(staging) and S_ISREG(final)
and staging.st_dev == final.st_dev
and staging.st_ino == final.st_ino
and staging.st_nlink >= 2 and final.st_nlink >= 2
and size/content_sha/mode match manifests
```

directory只要求path集合、mode、device及FINAL_PHYSICAL观测inode内部一致；不与staging directory
inode相等。completion和committed的root device/inode必须等于FINAL_PHYSICAL root及fstat。

## 4. Recovery refinements

V2 state machine继续适用，但：

- existing regular file只按§3 hardlink predicate接受；
- existing directory只按final inventory/expected path接受；
- final tree完成后先发布FINAL_PHYSICAL，再发布PUBLISH_COMPLETE；
- 所有JSON temp/final crash states严格使用Capacity V7 §4，无额外恢复选择；
- PREPARED后发现logical bijection失败、inventory缺失或control/payload reservation越界均HOLD，
  不abort或删除final。
