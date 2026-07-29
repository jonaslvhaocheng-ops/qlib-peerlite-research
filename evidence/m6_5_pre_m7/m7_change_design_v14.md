# M7 CCC / 市场状态 Gate 设计 v14

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v13.md`
- Base SHA：`e907d9216334fbb00c6a0c1827bcc493c4a8c424e9c56508d890bb09bf1f37fd`
- 取代：M7 v13。

## 1. Exact composition

V13 interval、PRE_LIST、source reconciliation目标、dual qualification及其V12 base均保留。
V13 parser/numeric、issuer-time和evidence lineage由本文件§2–§4完整替换。

## 2. ParserClosureManifestV1 and decimal fix

FieldSchemaRegistryV3的每个field不再直接指单file parser，而指
`parser_closure: ArtifactRefV1`。`ParserClosureManifestV1` exact：

```json
{
  "schema_version": "qlib_peerlite_parser_closure_manifest_v1",
  "closure_id": "<ASCII>",
  "entrypoint": {"module":"<ASCII dotted>","callable":"<ASCII>"},
  "source_files": [
    {"module":"<ASCII dotted>","path":"<fixed>","file_sha256":"sha256:<64hex>"}
  ],
  "native_dependencies": [
    {"name":"<ASCII>","path":"<fixed>","file_sha256":"sha256:<64hex>"}
  ],
  "interpreter": "<ArtifactRefV1>",
  "environment_lock": "<ArtifactRefV1>",
  "domain_table": [
    {"domain_code":"<ASCII>","implementation_module":"<ASCII dotted>","callable":"<ASCII>"}
  ],
  "import_roots": ["<fixed absolute path>"],
  "canonical_sha256": "sha256:<64hex>"
}
```

arrays按name/module/domain排序且唯一；closure必须递归枚举所有production imports/native libs，
禁用user site/current directory/shadow path；validator在clean environment仅从fixed roots加载，
逐文件重hash并验证observed interpreter/env。unbound import、domain alias、shadow module、
runtime drift全部FAIL。

FINITE_NUMBER唯一grammar修正为：

```text
0
| -?0\.[0-9]*[1-9]
| -?[1-9][0-9]*(?:\.[0-9]*[1-9])?
```

所以`0.5`、`-0.5`、`0.0001`、`-0.0001`合法；`-0`、`-0.0`、`0.50`、`.5`、`00.5`、
`1e-3`非法。其余V13 arbitrary-precision和domain规则不变。

## 3. IssuerTrustAnchorV1

取消不可证明的历史`verified_at in valid interval`声明。使用冻结时已存在的append-only信任锚：

```json
{
  "schema_version": "qlib_peerlite_lifecycle_issuer_trust_anchor_v1",
  "contract_sha256": "sha256:<64hex>",
  "issuer_authority": "<ArtifactRefV1>",
  "issuer_id": "<ASCII>",
  "issuer_version": "<ASCII>",
  "status": "ACTIVE",
  "registration_sequence": "<positive decimal>",
  "previous_registration": "<ArtifactRefV1 or null>",
  "registry_head_before": "sha256:<64hex>",
  "registry_head_after": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

它必须在M7 derived contract freeze前存在于contract-bound append-only registry，sequence连续、
previous/head链完整、no-replace/fsync且由独立validator重算。M7 contract直接绑定其ArtifactRef；
qualification只接受status ACTIVE的exact frozen anchor，不使用receipt self-reported time、mtime或
wall clock证明历史存在。若freeze时没有该锚，M7保持NOT_AUTHORIZED。

LifecycleEvidenceIssuerAuthorityV3删除V2 `valid_from/valid_until`，新增
`trust_anchor: ArtifactRefV1`，其余authorized statements/digests保留。receipt绑定anchor、
authority和contract exact refs。

## 4. HistoricalSourceRecordV1 and evidence V2

每条LIST/DELIST evidence必须直接绑定当时sealed source：

```json
{
  "schema_version": "qlib_peerlite_lifecycle_evidence_record_v2",
  "evidence_record_id": "<ASCII>",
  "issuer_statement_id": "<ASCII>",
  "security_id": "<NFC>",
  "field": "LIST_DATE|DELIST_DATE",
  "observation_id": "<ASCII>",
  "value_json": "<canonical DATE or null string>",
  "observed_from": "<UTC Z>",
  "observed_until": "<UTC Z or null>",
  "field_observation_available_time": "<UTC Z>",
  "event_vendor_available_time": "<UTC Z or null>",
  "source_snapshot": "<ArtifactRefV1>",
  "source_row_locator": "<fixed locator>",
  "source_record_canonical_sha256": "sha256:<64hex>",
  "source_available_time": "<UTC Z>",
  "source_version": "<ASCII>",
  "canonical_sha256": "sha256:<64hex>"
}
```

source snapshot必须是contract-authorized immutable snapshot；locator通过snapshot-specific
strict resolver得到同security historical row；row canonical SHA、source version及available
time全部重算。必须：

```text
source_available_time <= field_observation_available_time
historical source row security_id == evidence security_id
historical source row selected field canonical value == evidence value_json
```

nonnull event还要求event vendor time不晚于field observation time；null DELIST vendor time为null。

Lifecycle observation row V2不复制含糊final hash，exact为evidence record的common fields加：

```text
evidence_artifact_file_sha256
evidence_record_id
evidence_record_canonical_sha256
source_snapshot ArtifactRef
source_row_locator
source_record_canonical_sha256
source_available_time
```

validator先以artifact SHA+record ID解析record并比较所有common fields，再独立解析historical source
并重算derived source fields；不是要求两个不同schema逐字段全等。

LIST/DELIST历史修订允许，但每条revision都必须绑定对应historical source record。qualification
cutoff的latest observation必须与sealed final SecuritySourceProjectionV3字段相等；较早observation
可不同，PIT selection只使用当时available interval。孤立record、未授权snapshot、跨security
locator、clock inversion或final reconciliation mismatch均HOLD。
