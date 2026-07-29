# M6.5 有界修复变更设计 v33

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v32；历史版本与失败审查保留。

## 1. Exact composition

base为v32 exact SHA
`fbc5d53c40589787c832b54585dd2a07355ba07c4539d4f2de9cc785d7335cba`。

| v32 | v33 |
| --- | --- |
| §1 | 本文件§1完整替换 |
| §2 | 本文件§2完整替换 |
| §3全部 | 本文件§3完整替换 |
| §4.1–§4.3 | 逐字保留 |
| §4 title前新增约束 | 本文件§4 |
| §5全部 | 本文件§5完整替换 |
| §6 | 本文件§6完整替换 |
| §7 | 本文件§7完整替换 |

v32 §4.1–§4.3的RegistrationV3、GenerationCommitV3、ActivationReceiptV2完整保留并受本文件§4
RunAuthorityV3约束。v32其他未替换ancestry继续有效。本文不引用任何被本表完整替换的段落。
不授权实现、server replay、M7、fit、budget变更或final-OOS。

## 2. M7 qualification v11

本文件§6绑定的M7 v11自包含冻结：

- official十slots、state scalar output；
- value-only FUTURE_POISON与null-DELIST nonnull observation clock；
- AP product record views/LP digests、closed invocation/manifests、dual-sided AP005；
- fixed audit/population/security/date axes；
- issuer-authorized vendor evidence；
- exact security×prediction-date SLA006 records/digests。

current lifecycle authority slot仍不存在，故只能执行negative fail-closed validator，不得生成真实
qualification。

## 3. CapacityReservationV4 closed protocol

### 3.1 Common scalar/object rules

所有对象strict JSON：unknown key、duplicate key、float、NaN/Inf拒绝；strings NFC；SHA格式
`sha256:<64 lowercase hex>`；byte counts/IDs用nonnegative decimal ASCII；relative paths不得
absolute/`..`/empty segment/symlink。canonical SHA排除自身后用UTF-8、keys字节序、`,`/`:`
separators、无空格/尾换行。

每个文件先在same-parent private temp写满、fsync、chmod0440，再hardlink no-replace到final，
fsync parent并unlink temp。existing identical返回existing，不同bytes HOLD。reservation
directories 0550；lock files不属于evidence。

`TargetPathsV1` exact：

```json
{
  "parent": "<relative path>",
  "target_name": "<single path component>",
  "prepared_name": ".<target>.PREPARED.json",
  "root_name": "<target>",
  "internal_complete_name": "<target>/PUBLISH_COMPLETE.json",
  "sibling_committed_name": ".<target>.COMMITTED.json"
}
```

### 3.2 Five marker schemas

`RESERVED.json` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_reserved_v4",
  "attempt_id": "<[a-z0-9-]+>",
  "origin": "NORMAL|ORPHAN_RECOVERY",
  "invocation_sha256": "sha256:<64hex>",
  "target": "<TargetPathsV1>",
  "private_staging_path": "<relative path>",
  "expected_logical_bytes": "<decimal ASCII>",
  "source_inventory_sha256": "sha256:<64hex>",
  "runtime_policy_sha256": "sha256:<64hex>",
  "attempt_lease_path": "<relative path>",
  "canonical_sha256": "sha256:<64hex>"
}
```

NORMAL expected来自sealed source inventory且`<=per_attempt_cap`；ORPHAN_RECOVERY expected恰等于
runtime policy per-attempt cap，source inventory为orphan no-follow scan digest。

`MATERIALIZING.json` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_materializing_v4",
  "attempt_id": "<id>",
  "reserved_sha256": "sha256:<64hex>",
  "private_staging_path": "<same path>",
  "source_inventory_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`COMMITTED.json` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_committed_v4",
  "attempt_id": "<id>",
  "reserved_sha256": "sha256:<64hex>",
  "materializing_sha256": "sha256:<64hex>",
  "prepared_sha256": "sha256:<64hex>",
  "sibling_committed_sha256": "sha256:<64hex>",
  "payload_inventory_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`ABORTED.json` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_aborted_v4",
  "attempt_id": "<id>",
  "reserved_sha256": "sha256:<64hex>",
  "materializing_sha256": "sha256:<64hex> or null",
  "absence_receipt_sha256": "sha256:<64hex>",
  "reason": "SOURCE_TOCTOU|EXPECTED_BYTES_EXCEEDED|CAP_EXCEEDED|SAFE_EXTRACTION_FAILED|ORPHAN_RECOVERY",
  "canonical_sha256": "sha256:<64hex>"
}
```

null只允许在尚未MATERIALIZING的abort。

`RELEASED.json` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_released_v4",
  "attempt_id": "<id>",
  "terminal_type": "COMMITTED|ABORTED",
  "terminal_sha256": "sha256:<64hex>",
  "cleanup_receipt_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

COMMITTED/ABORTED互斥；legal chains恰为
`R→M→C→Released`、`R→A→Released`、`R→M→A→Released`。

### 3.3 Receipt schemas

`AbortAbsenceReceiptV2` exact：

```json
{
  "schema_version": "qlib_peerlite_abort_absence_receipt_v2",
  "attempt_id": "<id>",
  "reserved_sha256": "sha256:<64hex>",
  "materializing_sha256": "sha256:<64hex> or null",
  "target": "<TargetPathsV1>",
  "parent_device": "<decimal ASCII>",
  "parent_inode": "<decimal ASCII>",
  "locks": {
    "attempt_lease_path": "<relative>",
    "gc_lock_path": "<relative>",
    "parent_publish_lock_path": "<relative>"
  },
  "checks": [
    {"name": "PREPARED", "relative_path": "<exact>", "result": "ENOENT", "errno": "2"},
    {"name": "ROOT", "relative_path": "<exact>", "result": "ENOENT", "errno": "2"},
    {"name": "INTERNAL_COMPLETE", "relative_path": "<exact>", "result": "ENOENT", "errno": "2"},
    {"name": "SIBLING_COMMITTED", "relative_path": "<exact>", "result": "ENOENT", "errno": "2"}
  ],
  "invocation_sha256": "sha256:<64hex>",
  "runtime_policy_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

checks exact顺序，全部用parent directory FD的`fstatat(...,AT_SYMLINK_NOFOLLOW)`在同一三锁临界区。

`StagingCleanupReceiptV2` exact：

```json
{
  "schema_version": "qlib_peerlite_staging_cleanup_receipt_v2",
  "attempt_id": "<id>",
  "cleanup_mode": "OWNER_ABORT|POST_COMMIT",
  "terminal_sha256": "sha256:<64hex>",
  "private_staging_path": "<relative>",
  "pre_cleanup_inventory_sha256": "sha256:<64hex>",
  "removed_entry_count": "<decimal ASCII>",
  "post_cleanup_entry_count": "0",
  "post_cleanup_logical_bytes": "0",
  "root_result": "ABSENT|EMPTY",
  "canonical_sha256": "sha256:<64hex>"
}
```

receipt只在成功时发布；warning不是receipt，不能产生RELEASED。

### 3.4 Lock order, admission and conservative charge

initial/resume/abort/recovery先独占attempt lease，再GC lock；需要target判定时再parent publish lock。
attempt lease持有至terminal+cleanup。normal publish持attempt→parent，释放parent后才可取GC。

runtime policy必须先strict验证三个positive decimal：

```text
per_attempt_staging_byte_cap
aggregate_staging_byte_threshold
minimum_free_filesystem_bytes
```

policy malformed则阻止所有admission。no-follow扫描每attempt实际regular-file logical bytes。

- 完整验证R→terminal→RELEASED、cleanup receipt和zero staging的attempt：charge=0；
- valid active RESERVED：`charge=max(expected,actual)`；
- malformed/missing RESERVED或unowned orphan：
  `charge=max(per_attempt_staging_byte_cap,actual)`并HOLD。

```text
current_aggregate=sum(charge_i)
outstanding_reserved=sum(max(0,reserved_or_cap_i-actual_i) for charge_i>0)
```

新attempt在同一GC临界区必须：

```text
new_expected <= per_attempt_cap
current_aggregate + new_expected <= aggregate_threshold
statvfs_available - outstanding_reserved - new_expected >= minimum_free_bytes
```

然后发布RESERVED。actual每次write前/后重算且不得超过expected/cap。malformed marker永不退化为
actual-only或免计费。

### 3.5 Abort, commit cleanup and recovery

owner abort持attempt→GC→parent lock，生成§3.3 exact四路径absence receipt；任一存在/HOLD时不删。
锁内发布ABORTED，释放parent后仅chmod private dirs0700并no-follow bottom-up unlink/rmdir，禁止
chmod/truncate/write shared regular files；cleanup receipt→RELEASED。

PREPARED后禁止ABORT，只能same-claim nested transaction recovery。sibling COMMITTED完整验证后
发布reservation COMMITTED，再unlink-only cleanup；失败不RELEASE且继续charge。orphan必须先按
cap计费，再在三锁absence proof后生成ORPHAN_RECOVERY RESERVED→ABORTED→RELEASED。无age/PID
推断，不处理final/其他root。

## 4. RunAuthorityV3 closed upstream object

`linear_event_plan_sha256`只能绑定先发布的`LinearEventPlanV3`：

```json
{
  "schema_version": "qlib_peerlite_linear_event_plan_v3",
  "plan_id": "<ASCII>",
  "events": [
    {
      "event_seq": "<zero-padded decimal ASCII>",
      "source_event_id": "<ASCII>",
      "event_type": "CANDIDATE|FIT|DETERMINISTIC_REFIT|SYNTHETIC_OBSERVER",
      "evaluation_id": "<ASCII>",
      "model_id": "<ASCII>",
      "fold_id": "<ASCII or NONE>",
      "seed": "<decimal ASCII>"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

events非空、seq连续、source_event_id唯一；无extension/null/float。plan schema没有authority、
registration/commit/receipt/root hash字段，且先于authority发布。

v32 §4.1 registration绑定的`authority.json`只能是：

```json
{
  "schema_version": "qlib_peerlite_run_authority_v3",
  "authority_id": "<ASCII>",
  "purpose": "M6_5_SYNTHETIC_TEST_ONLY|M7_CCC_ISOLATED|M7_GATE_ISOLATED",
  "run_id": "<ASCII>",
  "generation_number": "<positive decimal ASCII>",
  "linear_event_plan_sha256": "sha256:<64hex>",
  "roots": {
    "journal": "<relative>",
    "snapshot": "<relative>",
    "output": "<relative>"
  },
  "caps": {
    "candidate_evaluations": "<decimal ASCII>",
    "model_fits": "<decimal ASCII>"
  },
  "m6_prefix": {
    "candidate_evaluations": "6",
    "model_fits": "44",
    "binding_sha256": "sha256:<64hex>"
  },
  "derived_contract_sha256": "sha256:<64hex> or null",
  "screening_prerequisite_sha256": "sha256:<64hex> or null",
  "real_fit_authorized": false,
  "final_oos_access_authorized": false,
  "issued_at": "<UTC RFC3339 Z>",
  "issuer_policy_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

当前M6.5 purpose必须synthetic，两个nullable字段为null、real fit=false。future M7 purpose要求两个
hash nonnull且由新授权流程产生；本轮没有该对象。final-OOS始终false。

strict schema没有registration/current commit/activation receipt/root inventory/container hash字段；
unknown key或任何string value等于当前registration/commit/receipt path或SHA也拒绝。authority先于
registration发布，canonical SHA排除自身，故不能形成下游回边。v32 §4.1–§4.3其余DAG保持。

## 5. ScoreReplayCanonicalV3：two merged expected + fourteen per-fold replay

### 5.1 Frozen identities

M6 spec file SHA
`469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8`，
content SHA
`60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69`。

expected恰两份model-level merged files：

| model | file SHA | rows |
| --- | --- | --- |
| PEERLITE_K16_MSE | `559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3` | 949014 |
| PEERLITE_K32_MSE | `008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55` | 949014 |

两份expected exact五列、各含exact七个nonempty folds。replay恰十四份**per-fold** immutable outputs：
每个`(model,fold)`唯一relative path、唯一output file SHA、exact五列、所有row model/fold等于外层
identity且只含该一个fold。不得共享model-level replay output、不得重复path/SHA凑14。

outer plan恰2×7 pairs，绑定expected merged SHA、expected fold receipt file/content SHA、checkpoint
SHA、per-fold replay path/SHA；无额外/缺失/replacement。

### 5.2 Canonicalize before window test

每side先验证五列顺序，然后：

1. aware datetime转Asia/Shanghai local date；naive normalize到midnight；
2. 得到canonical `YYYY-MM-DD`后才检查fold inclusive window；
3. instrument=NFC、strip不变、nonempty string，禁止数值转string；
4. score=native finite float64；
5. model/fold逐行exact；
6. unique `(date,instrument)`并按date、instrument UTF-8 bytes稳定排序。

windows exact为v32 §5.1列出的2018-01-09至2024-12-17七段；该表在v32 §5.1未被本文件单独继承，
所以这里完整列出：

```text
wf_2018 2018-01-09..2018-12-28
wf_2019 2019-01-09..2019-12-31
wf_2020 2020-01-09..2020-12-31
wf_2021 2021-01-11..2021-12-31
wf_2022 2022-01-11..2022-12-30
wf_2023 2023-01-10..2023-12-22
wf_2024 2024-01-09..2024-12-17
```

expected slice从merged file按已验证fold过滤；replay就是singleton-fold file。投影三列后：

```text
key_row=date+"T00:00:00"||0x1f||instrument||0x0a
score_row=date+"T00:00:00"||0x1f||instrument||0x1f||float.hex||0x0a
identity_row=model||0x1f||fold||0x0a
```

比较row count、identity/key/score SHA、MultiIndex及`np.array_equal(float64)`。PASS还要求14 unique
pairs、0 fit、ledger bytes/head unchanged、CUDA-only、transactions COMMITTED、final-OOS false。

## 6. Current M7 v11

- `m7_change_design_v11.md`
  SHA `642e6e54a30c6436ae76a6da2b2e638a4fa3ac844c9f2b0f7d6dd6755e9b3add`
- `m7_behavior_to_test_matrix_v11.md`
  SHA `75bb5106313ff5d2508d03dfaf4e8a55c67a75625efadc552a6cf1431f40bf57`

## 7. v32 closure

| blocker | closure |
| --- | --- |
| replaced-section references | §3/§5 fully restate；M7 v11 replaced sections self-contained |
| reservation schemas | §3.1–§3.3 five markers+receipts+publication |
| malformed RESERVED | §3.4 charge=cap/HOLD |
| RunAuthority backedge | §4 strict upstream-only schema |
| clock-only/null DELIST | M7 v11 §2 value-only + observation clock |
| AP005 single value | M7 v11 §3 dual official/state/equal |
| lifecycle axes/issuer/SLA006 | M7 v11 §4 exact axes, issuer map and records/digests |
| replay grain/window order | §5 two merged expected + 14 per-fold, canonical date first |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。仍不等于M6.5 PASS，不授权实现/replay/M7。
