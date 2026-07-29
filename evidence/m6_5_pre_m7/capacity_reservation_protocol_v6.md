# CapacityReservationProtocolV6

- 状态：`DESIGN_ONLY`
- 取代：`capacity_reservation_protocol_v5.md`
- 范围：M6.5 synthetic/replay staging control；不授权 replay。

## 1. Canonical objects, inventories and storage policy

所有 JSON 必须 strict parse：UTF-8/NFC、无 duplicate/unknown key、无 float、decimal 为无前导零
ASCII 非负整数。canonical SHA 为排除对象自身 `canonical_sha256` 字段后的 canonical JSON SHA；
file SHA 为包含该字段的最终完整文件 bytes SHA。

`ArtifactRefV1` exact：

```json
{
  "path": "<fixed relative regular-file path>",
  "file_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`InventoryManifestV2` exact：

```json
{
  "schema_version": "qlib_peerlite_inventory_manifest_v2",
  "root_path": "<fixed absolute or fixed relative path>",
  "root_device": "<decimal>",
  "root_inode": "<decimal>",
  "regular_file_count": "<decimal>",
  "directory_count": "<decimal>",
  "entry_count": "<decimal>",
  "logical_bytes": "<decimal>",
  "entries": [
    {
      "relative_path": "<normalized nonempty relative path>",
      "type": "REGULAR|DIRECTORY",
      "device": "<decimal>",
      "inode": "<decimal>",
      "mode": "0440|0550|0700",
      "size": "<decimal>",
      "sha256": "sha256:<64hex>|null"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

entries 按 relative path UTF-8 byte 排序且唯一；DIRECTORY 的 size=`0`、sha=`null`；
REGULAR 必须有内容 SHA。所有计数与 no-follow FD walk 独立重算相等。symlink、device、FIFO、
socket、hardlink escape 或 root/device 漂移均 HOLD。

`RuntimeStoragePolicyV2` exact：

```json
{
  "schema_version": "qlib_peerlite_runtime_storage_policy_v2",
  "reservation_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "staging_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "lease_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "target_parents": [
    {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"}
  ],
  "per_attempt_staging_byte_cap": "<positive decimal>",
  "per_attempt_regular_file_cap": "<positive decimal>",
  "per_attempt_directory_cap": "<positive decimal>",
  "per_attempt_entry_cap": "<positive decimal>",
  "aggregate_staging_byte_threshold": "<positive decimal>",
  "aggregate_regular_file_threshold": "<positive decimal>",
  "aggregate_directory_threshold": "<positive decimal>",
  "aggregate_entry_threshold": "<positive decimal>",
  "minimum_free_filesystem_bytes": "<positive decimal>",
  "minimum_free_filesystem_inodes": "<positive decimal>",
  "canonical_sha256": "sha256:<64hex>"
}
```

roots 必须 realpath/no-symlink；三 roots 与 target parents 两两 path/ancestor/inode 分离；
staging root 与每个 target parent 同 device。`statvfs.f_bavail*f_frsize` 和 `f_favail` 均参与
admission。policy malformed 或 platform 不提供可信 `f_favail` 时拒绝 admission。

## 2. Derived identities, path classes and fixed slots

attempt ID=`sha256(invocation exact file bytes).hexdigest()`。唯一派生：

```text
reservation_dir = reservation_root/attempt_id
staging_dir     = staging_root/attempt_id
lease_path      = lease_root/(attempt_id+".lock")
target_parent   = runtime_policy.target_parents[target_parent_index]
target_root     = target_parent/target_name
prepared_path   = target_parent/("."+target_name+".PREPARED.json")
completion_path = target_root/"PUBLISH_COMPLETE.json"
committed_path  = target_parent/("."+target_name+".COMMITTED.json")
publish_lock    = target_parent/("."+target_name+".publish.lock")
```

refs 分三类且不得混用：

1. reservation-local：RESERVED/MATERIALIZING/COMMITTED/ABORTED/RELEASED 及 receipts，path
   必须等于下列固定 slot；
2. policy-fixed upstream：invocation、runtime policy、source inventory，path 必须等于调用入口
   冻结的 policy slot 且位于 reservation/staging/target roots 之外；
3. target-derived transaction：PREPARED、PUBLISH_COMPLETE、sibling COMMITTED、payload/staging
   inventories，path 必须等于上述派生 target path 或对应规范明确的派生 inventory slot。

reservation slots：

```text
<reservation_dir>/RESERVED.json
<reservation_dir>/MATERIALIZING.json
<reservation_dir>/COMMITTED.json
<reservation_dir>/ABORTED.json
<reservation_dir>/receipts/ABORT_ABSENCE.json
<reservation_dir>/receipts/CLEANUP.json
<reservation_dir>/RELEASED.json
```

每个 JSON slot 的唯一 private temp 为 `<slot>.tmp.<attempt_id>`。active reservation/receipts dirs
为0700，marker/receipt files为0440。publish 使用 same-parent temp write/fsync/chmod0440，
hardlink no-replace，fsync dir，unlink temp，再 fsync dir。existing final identical 时 resume；
different bytes HOLD。仅允许当前 exact temp；其 inode/bytes 与 intended final 一致时可删除，
不一致或出现任何其他未知 entry 均 HOLD。

完整验证 RELEASED 链且 staging zero 后，receipts dir（若存在）再 reservation dir 依次
chmod/fsync 0550，最后 fsync reservation root。两目录未全部 seal 前继续计费。

## 3. Marker schemas and source-size equality

`RESERVED` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_reserved_v6",
  "attempt_id": "<64hex>",
  "origin": "NORMAL|ORPHAN_RECOVERY",
  "invocation": "<ArtifactRefV1>",
  "runtime_policy": "<ArtifactRefV1>",
  "source_inventory": "<ArtifactRefV1>",
  "target_parent_index": "<decimal>",
  "target_name": "<[A-Za-z0-9._-]+>",
  "expected_logical_bytes": "<decimal>",
  "expected_regular_file_count": "<decimal>",
  "expected_directory_count": "<decimal>",
  "expected_entry_count": "<decimal>",
  "canonical_sha256": "sha256:<64hex>"
}
```

NORMAL 的四个 expected 必须分别等于 verifier 对 sealed source `InventoryManifestV2` 的独立
重算结果，且不超过四个 per-attempt caps；不是调用方自报值。ORPHAN_RECOVERY 四个 expected
恰等于 policy 的四个 per-attempt caps，且 observed actual 四项都不超过各 cap。

`MATERIALIZING` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_materializing_v6",
  "attempt_id": "<64hex>",
  "reserved": "<ArtifactRefV1>",
  "source_inventory": "<ArtifactRefV1>",
  "source_revalidation": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

source_revalidation 是新发布的 `InventoryManifestV2`，四 metrics、entries 与 RESERVED
source inventory 全部相等；不相等时 MATERIALIZING 不得发布并走 owner abort。

`COMMITTED` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_committed_v6",
  "attempt_id": "<64hex>",
  "reserved": "<ArtifactRefV1>",
  "materializing": "<ArtifactRefV1>",
  "prepared": "<ArtifactRefV1>",
  "publish_complete": "<ArtifactRefV1>",
  "sibling_committed": "<ArtifactRefV1>",
  "payload_inventory": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`ABORTED` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_aborted_v6",
  "attempt_id": "<64hex>",
  "reserved": "<ArtifactRefV1>",
  "materializing": "<ArtifactRefV1 or null>",
  "absence_receipt": "<ArtifactRefV1>",
  "reason": "SOURCE_TOCTOU|EXPECTED_BYTES_EXCEEDED|CAP_EXCEEDED|ENTRY_CAP_EXCEEDED|INODE_FLOOR_EXCEEDED|SAFE_EXTRACTION_FAILED|ORPHAN_RECOVERY",
  "canonical_sha256": "sha256:<64hex>"
}
```

`RELEASED` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_released_v6",
  "attempt_id": "<64hex>",
  "terminal_type": "COMMITTED|ABORTED",
  "terminal": "<ArtifactRefV1>",
  "cleanup_receipt": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

legal chains 仅 `R-M-C-Released`、`R-A-Released`、`R-M-A-Released`；C/A 互斥。

## 4. Closed receipt schemas

`AbortAbsenceReceiptV3` exact：

```json
{
  "schema_version": "qlib_peerlite_abort_absence_receipt_v3",
  "attempt_id": "<64hex>",
  "reserved": "<ArtifactRefV1>",
  "materializing": "<ArtifactRefV1 or null>",
  "runtime_policy": "<ArtifactRefV1>",
  "target_parent_index": "<decimal>",
  "target_name": "<ASCII>",
  "target_parent_device": "<decimal>",
  "target_parent_inode": "<decimal>",
  "attempt_lease_path": "<derived absolute path>",
  "gc_lock_path": "<policy-fixed absolute path>",
  "parent_publish_lock_path": "<derived absolute path>",
  "checks": [
    {"name":"PREPARED","path":"<derived>","result":"ENOENT","errno":"2"},
    {"name":"ROOT","path":"<derived>","result":"ENOENT","errno":"2"},
    {"name":"PUBLISH_COMPLETE","path":"<derived>","result":"ENOENT","errno":"2"},
    {"name":"SIBLING_COMMITTED","path":"<derived>","result":"ENOENT","errno":"2"}
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

checks exact order，均由 parent/root FD no-follow，在 attempt→GC→parent 三锁同一临界区获得。

`StagingCleanupReceiptV3` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_cleanup_receipt_v3",
  "attempt_id": "<64hex>",
  "cleanup_mode": "OWNER_ABORT|POST_COMMIT",
  "terminal": "<ArtifactRefV1>",
  "runtime_policy": "<ArtifactRefV1>",
  "staging_path": "<derived absolute path>",
  "staging_root_device": "<decimal>",
  "staging_root_inode": "<decimal>",
  "pre_cleanup_inventory": "<ArtifactRefV1>",
  "removed_regular_file_count": "<decimal>",
  "removed_directory_count": "<decimal>",
  "removed_entry_count": "<decimal>",
  "post_cleanup_regular_file_count": "0",
  "post_cleanup_directory_count": "0",
  "post_cleanup_entry_count": "0",
  "post_cleanup_logical_bytes": "0",
  "root_result": "ABSENT|EMPTY",
  "canonical_sha256": "sha256:<64hex>"
}
```

receipt 只在成功时发布；warning 不是 receipt，不能发布 RELEASED。

## 5. Admission, streaming enforcement and conservative charge

锁序固定为 attempt lease→GC→可选 parent publish。attempt lease 从 admission 前持有至 cleanup
与 mode seal 完成。所有 root/path/device/inode 和 policy SHA 在每次临界操作前重验。

对每个 active attempt，重算
`actual=(bytes,regular_files,directories,entries)`。valid active 的 charge 每维分别为
`max(expected,actual)`；malformed/missing RESERVED 或 unowned orphan 每维分别为
`max(per_attempt_cap,actual)` 并 HOLD；完整 sealed RELEASED 且 staging 四项为零才全维 charge=0。

新 NORMAL admission 必须同时满足：

```text
new_expected_each_dimension <= corresponding_per_attempt_cap
aggregate_bytes + new_expected_bytes <= aggregate_byte_threshold
aggregate_files + new_expected_files <= aggregate_file_threshold
aggregate_dirs + new_expected_dirs <= aggregate_directory_threshold
aggregate_entries + new_expected_entries <= aggregate_entry_threshold
free_bytes - outstanding_bytes - new_expected_bytes >= minimum_free_bytes
f_favail - outstanding_entries - new_expected_entries >= minimum_free_inodes
```

`outstanding=max(0,expected-actual)` 按各维计算。所有条件在同一 GC 临界区成立才发布 RESERVED。

安全物化在创建每个 directory、临时 file、最终 hardlink 的前后都重算 next actual；必须满足
`next_actual<=expected<=cap` 的四维不变量，并再次检查 byte/inode floor。任何一步将越界时，
不得创建该 entry；在 PREPARED 前发布对应 ABORTED、cleanup、RELEASED。不能等待下一次 scanner。

actual 任一维超过 cap 的 orphan 永久 HOLD，绝不创建 synthetic chain、删除或自动释放。
四维均不超过 cap 且三锁 absence receipt 完整时，才允许 ORPHAN_RECOVERY
`RESERVED(expected=all caps)→ABORTED→cleanup→RELEASED`。

## 6. Cross-protocol equality and terminal validation

Capacity 与 `NestedDirectoryRecoveryV2` 必须逐项相等：

| Capacity chain | Nested transaction |
| --- | --- |
| RESERVED.attempt_id | PREPARED.attempt_id |
| RESERVED.runtime_policy | PREPARED.runtime_policy |
| derived target parent/name | PREPARED target_parent_index/target_name及全部derived paths |
| MATERIALIZING.source_revalidation | PREPARED.source_inventory |
| staging inventory after materialization | PREPARED.staging_inventory |
| PREPARED.payload_inventory | PUBLISH_COMPLETE.payload_inventory |
| PUBLISH_COMPLETE.payload_inventory | sibling COMMITTED.payload_inventory |
| COMMITTED payload/prepared/completion/sibling refs | 对应 target-derived exact refs |

任一 ref 的 path/file/canonical SHA 或任一重复字段不等即 HOLD。PREPARED 前才可 owner abort；
任一 transaction artifact 已存在后只走 V2 recovery，永不 ABORT。cleanup 只操作本 attempt 私有
staging entries，不 chmod/truncate/write shared regular files。
