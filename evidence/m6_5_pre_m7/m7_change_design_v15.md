# M7 CCC / 市场状态 Gate 设计 v15

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v14.md`
- Base SHA：`7fa0a3798047b1427d978bdcc238f04a8afa84ff64318b1d4b9b2abcccb8100b`
- 取代：M7 v14。

## 1. Exact composition

V14 decimal、PRE_LIST、interval、historical revision目标和V13/V12 ancestry保留。V14 parser
registry/closure、issuer anchor和historical source resolver由本文件完整替换。

## 2. FieldSchemaRegistryV4 and executable closure

`FieldSchemaRegistryV4` exact：

```json
{
  "schema_version": "qlib_peerlite_field_schema_registry_v4",
  "canonical_numeric_algorithm": "QLIB_PEERLITE_CANONICAL_DECIMAL_V1",
  "fields": [
    {
      "source_id": "<ASCII>",
      "table_id": "<ASCII>",
      "field": "<ASCII>",
      "json_type": "STRING|DATE|BOOLEAN|INTEGER|FINITE_NUMBER|NULLABLE_DATE",
      "nullable": true,
      "domain_code": "<ASCII>",
      "parser_closure": "<ArtifactRefV1>"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

fields按source/table/field UTF-8排序唯一；nullable只允许JSON bool。每个domain_code在其closure
domain_table恰一行，entrypoint和domain implementation module都必须在source_files恰一行。

`ExecutableClosureManifestV2` exact：

```json
{
  "schema_version": "qlib_peerlite_executable_closure_manifest_v2",
  "closure_id": "<ASCII>",
  "entrypoint": {"module":"<ASCII dotted>","callable":"<ASCII>"},
  "source_files": [
    {"module":"<ASCII dotted>","path":"<fixed>","file_sha256":"sha256:<64hex>"}
  ],
  "native_dependencies": [
    {"name":"<ASCII>","path":"<fixed>","file_sha256":"sha256:<64hex>"}
  ],
  "resource_files": [
    {"name":"<ASCII>","path":"<fixed>","file_sha256":"sha256:<64hex>"}
  ],
  "interpreter": "<ArtifactRefV1>",
  "environment_lock": "<ArtifactRefV1>",
  "domain_table": [
    {"domain_code":"<ASCII>","implementation_module":"<ASCII dotted>","callable":"<ASCII>"}
  ],
  "import_roots": ["<fixed absolute path>"],
  "allowed_environment": {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TZ": "UTC",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1"
  },
  "io_policy": {
    "network": "DENY",
    "stdin": "DENY",
    "wall_clock": "DENY",
    "randomness": "DENY",
    "filesystem": "READ_ONLY_BOUND_ARTIFACTS"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

arrays排序唯一，无未列环境变量/I/O/import/resource。validator以clean env和只读FD映射加载；
unbound config/lookup/locale resource、network/env/time/random、shadow import、runtime drift均FAIL。

## 3. Request-external issuer registry

`IssuerRegistryPolicyV1` exact：

```json
{
  "schema_version": "qlib_peerlite_issuer_registry_policy_v1",
  "parent_research_contract": "<ArtifactRefV1>",
  "registry_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "global_lock_path": "<absolute fixed>",
  "genesis_head": "sha256:<64hex>",
  "independent_validator_closure": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

policy属于M7 request之外已冻结的研究治理层，parent contract是当前
`research_contract_pit_v2` ArtifactRef，不是未来M7 derived contract。

固定：

```text
registrations/<seq20>.json
commits/<seq20>.json
receipts/<seq20>.json
```

`IssuerAnchorRegistrationV1` exact绑定sequence、previous commit、policy、issuer authority
ArtifactRef、issuer ID/version/status ACTIVE。`IssuerAnchorCommitV1` exact绑定registration、
previous commit/head及new head：

```text
new_head = sha256(
  bytes.fromhex(previous_head)
  || LP(bytes.fromhex(registration.canonical_sha256))
)
```

`IssuerAnchorFreezeReceiptV1` exact绑定policy、registration、commit、observed root identity、
observed head、validator closure及verdict PASS。三者在external global lock内连续scan、
no-replace/fsync；sequence1从policy genesis开始，gap/fork/unknown拒绝。

`IssuerTrustAnchorV2`仅是已提交注册的closed view：

```json
{
  "schema_version": "qlib_peerlite_lifecycle_issuer_trust_anchor_v2",
  "registry_policy": "<ArtifactRefV1>",
  "registration": "<ArtifactRefV1>",
  "commit": "<ArtifactRefV1>",
  "freeze_receipt": "<ArtifactRefV1>",
  "issuer_authority": "<ArtifactRefV1>",
  "issuer_id": "<ASCII>",
  "issuer_version": "<ASCII>",
  "status": "ACTIVE",
  "canonical_sha256": "sha256:<64hex>"
}
```

它不含derived contract hash。未来derived contract只单向绑定这个既存anchor；若需post-freeze
receipt，可同时引用contract+anchor但不得作为pre-freeze existence证据。当前external registry
objects不存在，所以M7继续NOT_AUTHORIZED。

## 4. Closed historical source and resolver

`HistoricalSecuritySourceManifestV1` exact：

```json
{
  "schema_version": "qlib_peerlite_historical_security_source_manifest_v1",
  "source_snapshot": "<ArtifactRefV1>",
  "source_id": "DataYes.md_security",
  "source_version": "<ASCII>",
  "snapshot_available_time": "<UTC Z>",
  "snapshot_schema": "<ArtifactRefV1>",
  "locator_grammar": "SECURITY_ID_PERCENT_ENCODED_V1",
  "resolver_closure": "<ArtifactRefV1>",
  "rows": {
    "path": "<fixed JSONL>",
    "file_sha256": "sha256:<64hex>",
    "row_count": "<positive decimal>",
    "locator_digest": "sha256:<64hex>",
    "logical_digest": "sha256:<64hex>"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

resolver_closure必须是§2同schema的ExecutableClosureManifestV2，I/O只允许manifest/snapshot/
rows FDs。locator exact `security_id=<RFC3986 percent-encoded UTF-8>`，在manifest内唯一。

historical row exact：

```json
{
  "security_id": "<NFC>",
  "source_row_locator": "<exact locator>",
  "list_date": "YYYY-MM-DD",
  "delist_date": "YYYY-MM-DD or null",
  "event_vendor_available_time": "<UTC Z or null>",
  "source_available_time": "<UTC Z>",
  "source_record_canonical_sha256": "sha256:<64hex>"
}
```

record SHA排除自身后重算。LIST evidence选择list_date；DELIST选择delist_date。clock角色：

- event vendor time：vendor声明事件值首次发布；
- source available time：该sealed snapshot/row通过source系统可解析；
- field observation time：研究系统允许该field observation参与预测。

nonnull event必须：

```text
event_vendor_available_time <= source_available_time
source_available_time <= field_observation_available_time == observed_from
```

null DELIST的event vendor time必须null，但仍要求source available<=observation。evidence V3直接
绑定HistoricalSecuritySourceManifest ArtifactRef、locator、row SHA及resolver closure；所有
common fields与resolved row相等。snapshot schema/locator/resolver/resource任何漂移HOLD。

revision、PRE_LIST、interval selection与cutoff latest→final projection equality继续按V14执行。
