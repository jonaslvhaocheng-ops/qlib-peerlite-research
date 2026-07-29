# CapacityReservationProtocolV5

- 状态：`DESIGN_ONLY`
- 范围：M6.5 synthetic/replay staging；不授权replay。

## 1. Canonical objects and storage policy

`ArtifactRefV1` exact：

```json
{"path":"<fixed relative path>","file_sha256":"sha256:<64hex>","canonical_sha256":"sha256:<64hex>"}
```

file SHA=包含embedded canonical字段的完整file bytes；canonical SHA=排除自身后的canonical JSON。
所有JSON strict、NFC、无float/duplicate/unknown；decimal用ASCII string。

`RuntimeStoragePolicyV1` exact：

```json
{
  "schema_version": "qlib_peerlite_runtime_storage_policy_v1",
  "reservation_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "staging_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "lease_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "target_parents": [
    {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"}
  ],
  "per_attempt_staging_byte_cap": "<positive decimal>",
  "aggregate_staging_byte_threshold": "<positive decimal>",
  "minimum_free_filesystem_bytes": "<positive decimal>",
  "canonical_sha256": "sha256:<64hex>"
}
```

roots realpath/no-symlink；三roots和target parents两两path/ancestor/inode分离。staging root与每个
target parent必须同device以支持hardlink。attempt ID=
`sha256(invocation exact bytes).hexdigest()`。

唯一派生：

```text
reservation_dir=reservation_root/attempt_id
staging_dir=staging_root/attempt_id
lease_path=lease_root/(attempt_id+".lock")
```

marker中的path必须exact等于派生结果；不能自报其他relative path。

## 2. Fixed slots, modes and publication

```text
<reservation_dir>/RESERVED.json
<reservation_dir>/MATERIALIZING.json
<reservation_dir>/COMMITTED.json
<reservation_dir>/ABORTED.json
<reservation_dir>/receipts/ABORT_ABSENCE.json
<reservation_dir>/receipts/CLEANUP.json
<reservation_dir>/RELEASED.json
```

reservation/receipts dirs在active lifecycle为0700；marker/receipt files为0440。每次publish：
在active same-parent temp写满/fsync/chmod0440，hardlink no-replace，fsync dir，unlink temp。
existing identical返回existing；different HOLD。

RELEASED及其全链验证、staging zero后，依次receipts dir→reservation dir chmod/fsync0550，再fsync
reservation root。scanner只有在两个dirs（若receipts存在）均0550时才释放charge。crash在
RELEASED后/mode seal前仍计费；recovery持locks完成chmod，不改marker bytes。

## 3. Exact marker schemas

所有parent使用`ArtifactRefV1`，不存在“裸SHA”。

RESERVED：

```json
{
  "schema_version":"qlib_peerlite_staging_reserved_v5",
  "attempt_id":"<64hex>",
  "origin":"NORMAL|ORPHAN_RECOVERY",
  "invocation":"<ArtifactRefV1>",
  "runtime_policy":"<ArtifactRefV1>",
  "source_inventory":"<ArtifactRefV1>",
  "target_parent_index":"<decimal>",
  "target_name":"<[A-Za-z0-9._-]+>",
  "expected_logical_bytes":"<decimal>",
  "canonical_sha256":"sha256:<64hex>"
}
```

target names `.`/`..`或以`.COMMITTED/.PREPARED`冲突者拒绝。NORMAL expected<=cap；
ORPHAN_RECOVERY仅允许observed actual<=cap且expected=cap。

MATERIALIZING：

```json
{
  "schema_version":"qlib_peerlite_staging_materializing_v5",
  "attempt_id":"<64hex>",
  "reserved":"<ArtifactRefV1>",
  "source_inventory":"<ArtifactRefV1>",
  "canonical_sha256":"sha256:<64hex>"
}
```

COMMITTED：

```json
{
  "schema_version":"qlib_peerlite_staging_committed_v5",
  "attempt_id":"<64hex>",
  "reserved":"<ArtifactRefV1>",
  "materializing":"<ArtifactRefV1>",
  "prepared":"<ArtifactRefV1>",
  "sibling_committed":"<ArtifactRefV1>",
  "payload_inventory":"<ArtifactRefV1>",
  "canonical_sha256":"sha256:<64hex>"
}
```

ABORTED：

```json
{
  "schema_version":"qlib_peerlite_staging_aborted_v5",
  "attempt_id":"<64hex>",
  "reserved":"<ArtifactRefV1>",
  "materializing":"<ArtifactRefV1 or null>",
  "absence_receipt":"<ArtifactRefV1>",
  "reason":"SOURCE_TOCTOU|EXPECTED_BYTES_EXCEEDED|CAP_EXCEEDED|SAFE_EXTRACTION_FAILED|ORPHAN_RECOVERY",
  "canonical_sha256":"sha256:<64hex>"
}
```

RELEASED：

```json
{
  "schema_version":"qlib_peerlite_staging_released_v5",
  "attempt_id":"<64hex>",
  "terminal_type":"COMMITTED|ABORTED",
  "terminal":"<ArtifactRefV1>",
  "cleanup_receipt":"<ArtifactRefV1>",
  "canonical_sha256":"sha256:<64hex>"
}
```

Refs的path必须等于§2固定slot；file/canonical SHA均重算。

## 4. Receipts

ABORT_ABSENCE exact绑定attempt/reserved/materializing、policy、parent target device/inode、三个locks
的派生paths，以及exact四checks PREPARED/ROOT/INTERNAL/SIBLING（fixed derived names、ENOENT、
errno2）。checks在attempt→GC→parent publish三锁同一临界区由parent FD no-follow执行。

CLEANUP exact绑定attempt、mode OWNER_ABORT|POST_COMMIT、terminal ArtifactRef、staging root
device/inode、pre-inventory ArtifactRef、removed count、post count=0、post bytes=0及root
ABSENT|EMPTY。两receipt使用§1 canonical规则和§2固定slots。

## 5. Admission, charge and orphan

锁序永远attempt lease→GC→可选parent publish。attempt lease从admission前持有至cleanup/mode seal。
policy/roots/derived paths先由FD+fstat重验。

actual=staging_dir下no-follow regular-file st_size和。valid sealed RELEASED chain charge=0；valid
active charge=max(expected,actual)；malformed/missing RESERVED或unowned orphan charge=
max(cap,actual)并HOLD。

```text
aggregate=sum(charge)
outstanding=sum(max(0,(valid expected else cap)-actual) for active)
new_expected<=cap
aggregate+new_expected<=threshold
statvfs_available-outstanding-new_expected>=minimum_free
```

全部成立才在同一GC临界区发布NORMAL RESERVED。

actual>cap的orphan永久HOLD，绝不创建synthetic chain或自动删除。actual<=cap且三锁absence proof
通过的orphan可生成ORPHAN_RECOVERY RESERVED(expected=cap)→ABORTED→cleanup→RELEASED。

## 6. Cleanup and validation

PREPARED前owner abort；任一publish path存在则禁止。PREPARED后只走绑定的nested transaction
recovery spec，永不ABORT。cleanup只chmod private dirs0700、unlink entries/rmdir；不chmod/
truncate/write regular files。任一ref/hash/mode/slot/path/root/chain/zero check失败继续按cap或
expected计费并HOLD。
