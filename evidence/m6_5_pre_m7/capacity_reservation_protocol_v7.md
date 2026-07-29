# CapacityReservationProtocolV7

- 状态：`DESIGN_ONLY`
- Base：`capacity_reservation_protocol_v6.md`
- Base SHA：`a2e2d563445a033d41b28d21328563fe12bce9b4caabd14672ce54fb110459fb`
- 取代：V6。

## 1. Exact composition

V6 的 canonical/ref/policy root、marker、receipt、lock、orphan和mode-seal规则保留，但下列内容
被本文件完整替换：

| V6 | V7 |
| --- | --- |
| InventoryManifestV2作为payload equality | §2 logical/physical split |
| derived inventory slots | §3 fixed slots |
| temp recovery prose | §4 closed transition table |
| §5 capacity/admission/streaming | §5完整替换 |
| §6 cross-protocol equality | §6完整替换 |

本文件未授权 replay。

## 2. Payload logical projection and physical inventories

`PayloadLogicalManifestV1` 不包含任何 root/device/inode：

```json
{
  "schema_version": "qlib_peerlite_payload_logical_manifest_v1",
  "regular_file_count": "<decimal>",
  "directory_count": "<decimal excluding logical root>",
  "entry_count": "<decimal = files + directories>",
  "logical_bytes": "<decimal>",
  "entries": [
    {
      "relative_path": "<normalized nonempty relative path>",
      "type": "REGULAR|DIRECTORY",
      "size": "<decimal>",
      "sha256": "sha256:<64hex>|null"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

DIRECTORY size=0/SHA=null；REGULAR有size/content SHA。entries按path UTF-8排序且唯一；parent
directories必须存在；禁止symlink/device/FIFO/socket和case-normalization collision。

`PhysicalInventoryV3` exact：

```json
{
  "schema_version": "qlib_peerlite_physical_inventory_v3",
  "root_path": "<fixed path>",
  "root_device": "<decimal>",
  "root_inode": "<decimal>",
  "logical_projection": "<ArtifactRefV1>",
  "entries": [
    {
      "relative_path": "<normalized nonempty relative path>",
      "type": "REGULAR|DIRECTORY",
      "device": "<decimal>",
      "inode": "<decimal>",
      "nlink": "<positive decimal>",
      "mode": "0440|0550|0700",
      "size": "<decimal>",
      "sha256": "sha256:<64hex>|null"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

其entries投影掉device/inode/nlink/mode后必须exact等于logical projection。source revalidation、
staging和final三份physical inventories的logical projection ArtifactRef必须相同，所以每个
relative path/type/size/content恰好一一对应：无缺失、额外、rename、subset或duplicate。

## 3. Exact inventory/control slots and accounting class

每attempt固定：

```text
<reservation_dir>/inventories/SOURCE_REVALIDATION.json
<reservation_dir>/inventories/STAGING_PHYSICAL.json
<reservation_dir>/inventories/PAYLOAD_LOGICAL.json
<reservation_dir>/inventories/FINAL_PHYSICAL.json
```

对应 private temp 仍按V6 `<slot>.tmp.<attempt_id>`。inventories dir为0700 active/0550 sealed；
四个files 0440。这四项和reservation/receipts/markers/temps/lease/publish lock/transaction markers
全部属于`CONTROL`，绝不进入PayloadLogicalManifest，但必须进入filesystem capacity accounting。

payload roots：

```text
staging physical root = staging_dir/payload
final physical root   = derived target_root
```

staging/final inventory的root path必须分别等于上述值。PAYLOAD_LOGICAL在任何物化前由sealed
source inventory独立投影并发布；SOURCE_REVALIDATION在MATERIALIZING前重新扫描原source；
STAGING_PHYSICAL在PREPARED前发布；FINAL_PHYSICAL只能在final tree建成后发布。

## 4. Atomic publication temp transition table

适用于reservation marker、receipt、inventory及transaction JSON；每次只允许一个fixed temp，
均在持对应lock时按下表执行：

| temp | final | relation | action |
| --- | --- | --- | --- |
| absent | absent | - | create temp→write→fsync→chmod0440→fsync parent；进入下一行 |
| valid | absent | intended bytes/mode | hardlink no-replace temp→final；fsync parent；unlink temp；fsync parent；return final |
| absent | valid | intended bytes/mode | return existing final |
| valid | valid | same `(st_dev,st_ino)`且intended bytes/mode | unlink temp；fsync parent；return final |
| present | present | inode different，无论bytes | HOLD |
| present | any | temp bytes/mode/path不等intended | HOLD |
| any | present | final bytes/mode/path不等intended | HOLD |

crash 在 write/fsync/chmod/link/dir-fsync/unlink/second-dir-fsync 任一点，重试只按表继续；不得
delete/recreate valid final。任何非fixed temp或unknown entry HOLD。

## 5. Exact worst-case reservation and admission

设logical payload `F=regular_file_count`、`D=directory_count`、`E=F+D`、`B=logical_bytes`。
payload 与 filesystem 分开：

```text
payload_bytes_reserved       = B
payload_files_reserved       = F
payload_directories_reserved = D
payload_entries_reserved     = E

filesystem_new_inodes_reserved = F + 2*(D+1) + 21
filesystem_new_entries_reserved = 2*(E+1) + 21
filesystem_new_bytes_reserved = B + CONTROL_BYTE_CEILING
```

解释：

- staging创建F个regular inode和D+1个dirs；
- final创建D+1个dirs；F个final files是staging hardlinks，不新增inode但新增entries；
- `21`是per-attempt worst-case同时存在的控制inode/entries：reservation/receipts/inventories
  三dirs、staging_dir wrapper一dir、最多四个reservation chain finals、两个receipts、四inventories、lease、publish lock、
  三transaction finals、一个reservation-side temp、一个transaction-side temp；
- temp+final coexistence已包含两个temp；
- `CONTROL_BYTE_CEILING`是RuntimeStoragePolicyV3的positive decimal固定值，必须大于或等于对
  21个控制对象逐slot maximum serialized bytes求和；validator按每slot max表独立重算。

RuntimeStoragePolicyV3在V6 V2字段上新增：

```text
per_attempt_filesystem_inode_cap
per_attempt_filesystem_entry_cap
aggregate_filesystem_inode_threshold
aggregate_filesystem_entry_threshold
control_byte_ceiling
control_slot_max_bytes[exact 18 file slots]
```

slot表无extra，sum必须等于control ceiling；dirs不占bytes但占inodes/entries。

在唯一GC/capacity lock内，scanner通过三个root FDs全量no-follow统计所有active与sealed
reservation metadata、staging及未提交target transaction entries。sealed RELEASED只将staging
payload bytes/files/dirs降为零；其永久reservation metadata、inventory和markers仍按实际
inode/entry/bytes计费，绝不归零，直到另一个未来且未授权的archival policy安全迁移它们。

admission在同一lock内同时要求：

```text
payload expected <= payload per-attempt caps
filesystem worst-case expected <= filesystem per-attempt caps
aggregate observed+outstanding+new <= all byte/inode/entry thresholds
f_bavail*f_frsize - outstanding_bytes - new_filesystem_bytes >= minimum_free_bytes
f_favail - outstanding_inodes - new_filesystem_inodes >= minimum_free_inodes
```

随后在该lock内发布RESERVED才释放lock；两个并发admission不能观察同一未扣减floor。

streaming时分别维护：

- logical payload：staging/final投影永远是PAYLOAD_LOGICAL的prefix，结束时exact bijection；
- filesystem：每次mkdir/temp/final/hardlink/marker前后均不超过本attempt worst-case reservation
  且全局floor仍满足；
- temp+final同时存在使用预留control slot，不与payload F/E比较。

empty payload (`F=D=E=B=0`) 仍预留`2 roots + 21 control` inodes/entries。任一步越过任一
reservation时，PREPARED前ABORT；PREPARED后HOLD/recovery，不等待scanner。

## 6. Cross-protocol equality

Capacity V7与NestedRecoveryV3必须满足：

```text
RESERVED attempt/policy/target == PREPARED attempt/policy/target
RESERVED source inventory projection == PAYLOAD_LOGICAL
SOURCE_REVALIDATION logical projection == PAYLOAD_LOGICAL
STAGING_PHYSICAL logical projection == PAYLOAD_LOGICAL
PREPARED.payload_logical_manifest == PAYLOAD_LOGICAL ArtifactRef
completion.payload_logical_manifest == PREPARED.payload_logical_manifest
completion.final_physical_inventory == FINAL_PHYSICAL ArtifactRef
sibling COMMITTED repeats the same logical/final refs
Capacity COMMITTED repeats PREPARED/completion/sibling/logical/final refs
```

所有 path/file/canonical SHA及重复identity exact equality。regular final files逐path必须与staging
是同一hardlink inode；directory inode只在FINAL_PHYSICAL观察，绝不在PREPARED预报。
