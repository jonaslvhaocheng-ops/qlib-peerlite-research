# M7 CCC / 市场状态 Gate 设计 v16

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v15.md`
- Base SHA：`8ec3b876bdace09f62c323ba9c935dee3c33519f7a1dc8f14ac8276712da623a`
- 取代：M7 v15。

## 1. Executable closure runtime enforcement

ExecutableClosureManifestV3在V15 V2 `io_policy`新增：

```json
{
  "process_spawn": "DENY",
  "fork_exec": "DENY",
  "subprocess": "DENY",
  "dynamic_code": "DENY"
}
```

并新增`runtime_sandbox_policy: ArtifactRefV1`。每次parser/resolver运行必须产生
`RuntimeClosureReceiptV1`，exact绑定closure、sandbox policy、interpreter/env、observed imports/
native loads/resource opens/FD allowlist，及`network/process/time/random/env violations=0`。
supervisor以OS sandbox禁止clone/fork/exec/network，关闭stdin，只传bound read-only FDs和exact
allowed env；receipt由supervisor而非parser自报。缺receipt或observed set不等closure即FAIL。

## 2. Externally authorized issuer registry

trusted inputs由validator CLI/父治理启动参数提供：

```text
trusted_issuer_policy_file_sha256
trusted_issuer_policy_canonical_sha256
trusted_registry_root_path/device/inode
trusted_validator_closure_file/canonical_sha256
parent_governance_authorization ArtifactRef
```

这些值不得从request、anchor、issuer policy或derived contract解析。当前项目不存在该外部输入，
所以真实anchor必拒绝。

`ParentGovernanceIssuerPolicyAuthorizationV1` exact：

```json
{
  "schema_version": "qlib_peerlite_parent_governance_issuer_policy_authorization_v1",
  "parent_research_contract": "<ArtifactRefV1>",
  "authorized_issuer_registry_policy": "<ArtifactRefV1>",
  "authorized_registry_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "authorized_validator_closure": "<ArtifactRefV1>",
  "amendment_commit": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

它位于parent governance固定slot并在M7 request之前no-replace/fsync；CLI trusted hash必须指它。

三个registry object exact：

`IssuerAnchorRegistrationV2`

```json
{
  "schema_version": "qlib_peerlite_issuer_anchor_registration_v2",
  "sequence": "<positive decimal>",
  "previous_commit": "<ArtifactRefV1 or null>",
  "registry_policy": "<ArtifactRefV1>",
  "parent_governance_authorization": "<ArtifactRefV1>",
  "issuer_authority": "<ArtifactRefV1>",
  "issuer_id": "<ASCII>",
  "issuer_version": "<ASCII>",
  "status": "ACTIVE",
  "canonical_sha256": "sha256:<64hex>"
}
```

`IssuerAnchorCommitV2`

```json
{
  "schema_version": "qlib_peerlite_issuer_anchor_commit_v2",
  "sequence": "<positive decimal>",
  "registration": "<ArtifactRefV1>",
  "previous_commit": "<ArtifactRefV1 or null>",
  "previous_head": "sha256:<64hex>",
  "new_head": "sha256:<64hex>",
  "registry_policy": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`IssuerAnchorFreezeReceiptV2`

```json
{
  "schema_version": "qlib_peerlite_issuer_anchor_freeze_receipt_v2",
  "registration": "<ArtifactRefV1>",
  "commit": "<ArtifactRefV1>",
  "registry_policy": "<ArtifactRefV1>",
  "parent_governance_authorization": "<ArtifactRefV1>",
  "observed_registry_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "observed_head": "sha256:<64hex>",
  "validator_closure": "<ArtifactRefV1>",
  "verdict": "PASS",
  "canonical_sha256": "sha256:<64hex>"
}
```

head算法对`sha256:` token先严格校验并剥离prefix再hex decode：

```text
new_head=sha256(raw32(previous_head)||LP(raw32(registration.canonical_sha256)))
```

sequence路径、排序、unknown拒绝；publication采用Capacity V8 durable temp table，registration→
commit→receipt各fsync，crash仅identical resume、different HOLD。所有重复refs exact equality。

## 3. Field-grain historical lineage and closed Evidence V3

historical row grain改为one field revision：

```json
{
  "security_id": "<NFC>",
  "field": "LIST_DATE|DELIST_DATE",
  "source_revision_id": "<ASCII>",
  "source_row_locator": "<exact unique locator>",
  "value_json": "<canonical DATE or null string>",
  "event_vendor_available_time": "<UTC Z or null>",
  "source_available_time": "<UTC Z>",
  "source_record_canonical_sha256": "sha256:<64hex>"
}
```

LIST value nonnull且vendor time nonnull；DELIST nonnull时vendor time nonnull，null时vendor time
null。manifest snapshot time加入完整偏序：

```text
nonnull: event_vendor <= source_available <= snapshot_available <= observation
null: source_available <= snapshot_available <= observation
```

claim ceiling=`SYSTEM_REPLAYABLE_PIT`，不声称早于系统摄取即可使用。

rows按`security_id UTF-8, field ASCII, source_revision_id UTF-8`排序。digest preimages：

```text
locator_row=LP(security_id)||LP(field)||LP(source_revision_id)||LP(locator)
logical_row=LP(security_id)||LP(field)||LP(source_revision_id)||LP(value_json)
            ||LP(event_vendor_time or "NULL")||LP(source_available_time)
            ||LP(source_record_canonical_sha256)
```

concat rows后SHA256；空集不合法。

`LifecycleEvidenceRecordV3` exact：

```json
{
  "schema_version": "qlib_peerlite_lifecycle_evidence_record_v3",
  "evidence_record_id": "<ASCII>",
  "issuer_statement_id": "<ASCII>",
  "security_id": "<NFC>",
  "field": "LIST_DATE|DELIST_DATE",
  "observation_id": "<ASCII>",
  "value_json": "<canonical DATE or null string>",
  "observed_from": "<UTC Z>",
  "observed_until": "<UTC Z or null>",
  "field_observation_available_time": "<UTC Z>",
  "historical_source_manifest": "<ArtifactRefV1>",
  "source_revision_id": "<ASCII>",
  "source_row_locator": "<exact locator>",
  "source_record_canonical_sha256": "sha256:<64hex>",
  "source_available_time": "<UTC Z>",
  "snapshot_available_time": "<UTC Z>",
  "resolver_closure": "<ArtifactRefV1>",
  "runtime_closure_receipt": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/null仅按value/vendor rules允许；all refs/hash/locator/common fields与resolved field-row exact。
Lifecycle observation manifest row引用该record ArtifactRef并重复其identity/interval/value/source
bindings；重复不等HOLD。LIST/DELIST intervals分别独立验证。
