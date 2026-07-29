# M7 CCC / 市场状态 Gate 设计 v17

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v16.md`
- Base SHA：`637b167fdb651f10112971a0b4d41c86e9f5f868d427429bc6dda01e3857a978`
- 取代：M7 v16。

## 1. Mechanical sandbox receipt

RuntimeSandboxPolicyV2 exact deny set：

```text
clone,clone3,fork,vfork,execve,execveat,posix_spawn,posix_spawnp,
system,popen,subprocess,network_socket,connect,bind,listen,accept,
dynamic_eval,dynamic_exec,dynamic_library_load_unbound
```

platform缺任一可观测/enforce hook即FAIL closed。只允许preopened bound FDs；所有其他open/openat、
environment、clock、random和stdin拒绝。

receipt固定：

```text
<invocation_root>/runtime-closure-receipt.json
```

`RuntimeClosureReceiptV2` exact：

```json
{
  "schema_version": "qlib_peerlite_runtime_closure_receipt_v2",
  "trusted_supervisor_closure": "<ArtifactRefV1>",
  "runtime_sandbox_policy": "<ArtifactRefV1>",
  "invocation": "<ArtifactRefV1>",
  "executable_closure": "<ArtifactRefV1>",
  "interpreter": "<ArtifactRefV1>",
  "environment_lock": "<ArtifactRefV1>",
  "observed_imports": [{"name":"<ASCII>","path":"<fixed>","file_sha256":"sha256:<64hex>"}],
  "observed_native_loads": [{"name":"<ASCII>","path":"<fixed>","file_sha256":"sha256:<64hex>"}],
  "observed_resources": [{"name":"<ASCII>","path":"<fixed>","file_sha256":"sha256:<64hex>"}],
  "observed_fds": [{"fd":"<decimal>","role":"INPUT|OUTPUT","artifact":"<ArtifactRefV1>"}],
  "import_digest": "sha256:<64hex>",
  "native_digest": "sha256:<64hex>",
  "resource_digest": "sha256:<64hex>",
  "fd_digest": "sha256:<64hex>",
  "violation_counts": {
    "process": "0",
    "network": "0",
    "filesystem": "0",
    "environment": "0",
    "clock": "0",
    "random": "0",
    "stdin": "0",
    "dynamic_code": "0"
  },
  "verdict": "PASS",
  "canonical_sha256": "sha256:<64hex>"
}
```

arrays按name/path或fd数值排序唯一；digest使用对应row canonical JSON bytes的LP concat；
空array SHA256(empty)。trusted supervisor closure/hash来自request-external CLI，与issuer
trusted-input同等级，不从invocation读取。receipt由supervisor用durable temp/no-replace/fsync
发布；parser/resolver无该slot写权限。

## 2. Trusted-input equality and publication paths

CLI trusted inputs唯一映射：

| external input | must equal |
| --- | --- |
| policy file/canonical SHA | observed IssuerRegistryPolicy ArtifactRef |
| registry root path/device/inode | policy root、parent authorization root、freeze receipt observed root |
| validator closure file/canonical SHA | policy validator、parent authorization validator、freeze receipt validator |
| parent authorization ArtifactRef | policy authorization ref、registration ref、freeze receipt ref |

任一不等在读取request fields前FAIL。fixed finals/temps：

```text
parent-governance/issuer-policy-authorization.json[.tmp.<canonical>]
registrations/<seq20>.json[.tmp.<canonical>]
commits/<seq20>.json[.tmp.<canonical>]
receipts/<seq20>.json[.tmp.<canonical>]
```

publication/crash严格使用Capacity V8 durable temp table。parent authorization必须先于policy被
request使用且来自父治理fixed slot；request不能提供替代bytes。

## 3. Historical locator and manifest V2

locator grammar改为：

```text
security_id=<pct-utf8>&field=<LIST_DATE|DELIST_DATE>&revision=<pct-ascii>
```

`(security_id,field,source_revision_id)`三元组byte唯一；locator byte唯一；两者不得分别映射多个
rows。

HistoricalSecuritySourceManifestV2沿用V15 V1 wrapper但schema ID升级、locator grammar升级、
rows使用V16 field-grain schema。row digest继续用V16 preimages。

## 4. Evidence V4 and ObservationManifestV2

`LifecycleEvidenceRecordV4`以V16 V3为base，exact新增：

```text
event_vendor_available_time: UTC Z or null
```

并升级schema ID。它必须与resolved field row exact equality并纳入record canonical hash；
LIST/non-null DELIST nonnull，null DELIST null。

`LifecycleObservationManifestV2` exact：

```json
{
  "schema_version": "qlib_peerlite_lifecycle_observation_manifest_v2",
  "security_source_projection": "<ArtifactRefV1>",
  "prediction_date_axis": "<ArtifactRefV1>",
  "field_schema_registry": "<ArtifactRefV1>",
  "issuer_trust_anchor": "<ArtifactRefV1>",
  "historical_source_manifests": ["<ArtifactRefV1>"],
  "evidence_artifacts": [
    {"kind":"LIST","path":"<fixed>","file_sha256":"sha256:<64hex>"},
    {"kind":"DELIST","path":"<fixed>","file_sha256":"sha256:<64hex>"}
  ],
  "rows": {
    "path": "<fixed JSONL>",
    "file_sha256": "sha256:<64hex>",
    "row_count": "<positive decimal>",
    "key_digest": "sha256:<64hex>",
    "value_digest": "sha256:<64hex>",
    "logical_digest": "sha256:<64hex>"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

row exact：

```json
{
  "security_id": "<NFC>",
  "field": "LIST_DATE|DELIST_DATE",
  "observation_id": "<ASCII>",
  "value_json": "<canonical date or null>",
  "observed_from": "<UTC Z>",
  "observed_until": "<UTC Z or null>",
  "field_observation_available_time": "<UTC Z>",
  "event_vendor_available_time": "<UTC Z or null>",
  "historical_source_manifest": "<ArtifactRefV1>",
  "source_revision_id": "<ASCII>",
  "source_row_locator": "<exact V2 locator>",
  "source_record_canonical_sha256": "sha256:<64hex>",
  "source_available_time": "<UTC Z>",
  "snapshot_available_time": "<UTC Z>",
  "resolver_closure": "<ArtifactRefV1>",
  "runtime_closure_receipt": "<ArtifactRefV1>",
  "evidence_record": "<ArtifactRefV1>"
}
```

row key=`[security_id,field,observation_id]`且唯一。value digest逐row canonical JSON excluding key
fields；logical digest逐row LP(key)||LP(value canonical bytes)；rows按key UTF-8排序，empty不合法。
每个重复field与Evidence V4逐项exact equality；任一lineage字段丢失/替换HOLD。
