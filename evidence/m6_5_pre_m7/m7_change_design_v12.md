# M7 CCC / 市场状态 Gate 设计 v12

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v11.md`
- Base SHA：`642e6e54a30c6436ae76a6da2b2e638a4fa3ac844c9f2b0f7d6dd6755e9b3add`
- 取代：M7 v11；历史版本与失败审查保留。

## 1. Exact composition

保留v11 §1、§3及其明确保留的v9 budget/fixed-PIT/supplement/review/envelope、Gate/state/CCC/
admission/test-ownership段。仅：

| v11 | v12 |
| --- | --- |
| §2全部 | 本文件§2完整替换 |
| §4全部 | 本文件§3完整替换 |

不创建authority/qualification，不运行fit，不改预算，不访问final-OOS。

## 2. Typed ObservationFieldAdapterV3

### 2.1 FieldSchemaRegistryV1

parameters必须绑定strict registry：

```json
{
  "schema_version": "qlib_peerlite_field_schema_registry_v1",
  "fields": [
    {
      "source_id": "<ASCII>",
      "table_id": "<ASCII>",
      "field": "<ASCII>",
      "json_type": "STRING|DATE|BOOLEAN|INTEGER|FINITE_NUMBER|NULLABLE_DATE",
      "nullable": true,
      "domain_code": "<fixed parser/domain ID>",
      "production_parser_sha256": "sha256:<64hex>"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

按source/table/field UTF-8排序、唯一，无unknown/null（nullable bool除外）/float。DATE必须
`YYYY-MM-DD`；INTEGER canonical decimal；FINITE_NUMBER finite canonical decimal；enum/string
按domain parser。两side必须先解析为typed value，再canonicalize。

### 2.2 Versioned field observations

raw grain是one-record-per-field-observation，不是final row。identity：

```text
tuple=LP(source_id)||LP(table_id)||LP(pk_json)||LP(field)||LP(observation_id)
raw_key=sha256(tuple).hexdigest()
sample_id=source_id+"|"+table_id+"|"+sha256(pk_json).hexdigest()
```

payload exact：

```json
{
  "source_id": "<ASCII>",
  "table_id": "<ASCII>",
  "primary_key_json": "<canonical JSON array as string>",
  "field": "<ASCII>",
  "observation_id": "<ASCII>",
  "observed_from": "<UTC RFC3339 Z>",
  "observed_until": "<UTC RFC3339 Z or null>",
  "value_json": "<canonical typed scalar as string>"
}
```

official三个clocks nonnull；available_time=field observation available time；没有独立revision/
universe clock时exact等于available_time并在parameters声明。

DELIST observation history必须版本化：

- null observation也有nonnull observation available time；
- 后续date observation是新observation_id；
- intervals按observed_from连续、不重叠，最后until=null；
- 每个qualified security从listing observation可得起至cutoff的每个prediction time恰有一个
  latest observation with `available_time<=P`；否则lifecycle qualification HOLD。

因此2023退市证券在2020选择当时的null observation，`delist_effective=false`，不会因最终值提前
剔除；2023 date observation可得后才按event boundary生效。

### 2.3 Typed semantic poison

baseline/probe changed set必须：

- identity、interval、三个clocks byte-identical；
- 两side value都通过同一production parser/domain；
- canonical typed values语义不等；
- probe是production parser可接受的合法值；
- only `value_json` bytes不同；
- available_time>T；
- supplement raw_key/time/two canonical value hashes exact一对一。

不同数字文本但同typed value、非法date/enum/range、clock-only/key/metadata-only mutation均FAIL。
changed set非空。official十slots和state scalar CSV在此重述为：
code_or_query=adapter；parameters=registry/adapter/T/source/lifecycle/policy；environment=runtime；
baseline/probe raw snapshot和output按side；其余parent audit/ledger/receipt按official名称，无private
key。state value是float.hex JSON string。

## 3. SecurityLifecycleAvailabilityAuthorityV4

### 3.1 ArtifactRef and canonical rules

所有ref exact `{"path":"<fixed relative regular no-symlink>","file_sha256":"sha256:<64hex>",
"canonical_sha256":"sha256:<64hex>"}`；file SHA含canonical字段的完整bytes，canonical SHA排除自身。
unknown/duplicate/float拒绝，strings NFC，arrays固定顺序。

### 3.2 SecuritySourceProjectionV3

wrapper exact：

```json
{
  "schema_version": "qlib_peerlite_security_source_projection_v3",
  "parent_fixed_audit": {
    "manifest_file_sha256": "sha256:<64hex>",
    "content_sha256": "sha256:<64hex>"
  },
  "population_authority": {
    "path": "<fixed>",
    "file_sha256": "sha256:<64hex>",
    "security_key_count": "<positive decimal>",
    "security_key_digest": "sha256:<64hex>"
  },
  "source_snapshot": "<ArtifactRef>",
  "source_id": "DataYes.md_security",
  "source_version": "<ASCII>",
  "columns": ["security_id","source_row_locator","list_date","delist_date","source_record_sha256"],
  "rows": {
    "path": "<fixed JSONL>",
    "file_sha256": "sha256:<64hex>",
    "row_count": "<positive decimal>",
    "key_digest": "sha256:<64hex>"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

row exact：

```json
{
  "security_id": "<NFC>",
  "source_row_locator": "security_id=<percent-encoded UTF-8>",
  "list_date": "YYYY-MM-DD",
  "delist_date": "YYYY-MM-DD or null",
  "source_record_sha256": "sha256:<64hex>"
}
```

source hash preimage canonical exact source triple；row axis exact等于population authority count/digest。

### 3.3 PredictionDateAxisV2

wrapper exact：

```json
{
  "schema_version": "qlib_peerlite_prediction_date_axis_v2",
  "contract_sha256": "sha256:<64hex>",
  "calendar_manifest": "<ArtifactRef>",
  "timezone": "Asia/Shanghai",
  "start_inclusive": "2012-01-01",
  "end_exclusive": "2025-01-01",
  "rows": {
    "path": "<fixed JSONL>",
    "file_sha256": "sha256:<64hex>",
    "row_count": "<positive decimal>",
    "key_digest": "sha256:<64hex>"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

row exact `{"prediction_date":"YYYY-MM-DD","prediction_time":"<UTC RFC3339 Z>"}`；open sessions
全覆盖，按date排序；key digest=sha256(concat(LP(date ASCII)))。

### 3.4 Issuer authority and evidence digest

`LifecycleEvidenceIssuerAuthorityV2` exact：

```json
{
  "schema_version": "qlib_peerlite_lifecycle_evidence_issuer_authority_v2",
  "issuer_id": "<ASCII>",
  "issuer_version": "<ASCII>",
  "valid_from": "<UTC Z>",
  "valid_until": "<UTC Z>",
  "authorized_statements": [
    {
      "statement_id": "<ASCII>",
      "kind": "DATAYES_MD_SECURITY_LIST_AVAILABILITY_V1|DATAYES_MD_SECURITY_DELIST_AVAILABILITY_V1",
      "path": "<fixed evidence JSONL>",
      "file_sha256": "sha256:<64hex>",
      "record_count": "<positive decimal>",
      "key_digest": "sha256:<64hex>",
      "value_digest": "sha256:<64hex>",
      "logical_digest": "sha256:<64hex>"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

exact两statements按kind排序。evidence record exact：

```json
{
  "evidence_record_id": "<ASCII>",
  "issuer_statement_id": "<ASCII>",
  "security_id": "<NFC>",
  "field": "LIST_DATE|DELIST_DATE",
  "observation_id": "<ASCII>",
  "value_json": "<canonical DATE or null as string>",
  "observed_from": "<UTC Z>",
  "observed_until": "<UTC Z or null>",
  "field_observation_available_time": "<UTC Z>",
  "event_vendor_available_time": "<UTC Z or null>",
  "source_version": "<ASCII>"
}
```

evidence key=`[issuer_statement_id,evidence_record_id]`；value=whole record minus those two key fields；
schema/key/value/logical digest使用AP LP算法。statement exact授权file及四metrics；record statement
ID、kind、source version必须匹配。

### 3.5 LifecycleObservationManifestV1

wrapper exact：

```json
{
  "schema_version": "qlib_peerlite_lifecycle_observation_manifest_v1",
  "security_source_projection": "<ArtifactRef>",
  "prediction_date_axis": "<ArtifactRef>",
  "field_schema_registry": "<ArtifactRef>",
  "issuer_authority": "<ArtifactRef>",
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

observation row exact：

```json
{
  "security_id": "<NFC>",
  "field": "LIST_DATE|DELIST_DATE",
  "observation_id": "<ASCII>",
  "value_json": "<canonical DATE or null string>",
  "observed_from": "<UTC Z>",
  "observed_until": "<UTC Z or null>",
  "field_observation_available_time": "<UTC Z>",
  "event_vendor_available_time": "<UTC Z or null>",
  "source_version": "<ASCII>",
  "evidence_kind": "LIST|DELIST",
  "evidence_record_id": "<ASCII>",
  "evidence_record_file_sha256": "sha256:<64hex>",
  "source_record_sha256": "sha256:<64hex>"
}
```

key=`[security_id,field,observation_id]`。LIST每security至少一条；DELIST intervals必须从list
observation可得时起连续覆盖cutoff，null→date history合法且不重叠。

### 3.6 SLA006 records

对security axis×date axis exact笛卡尔积，key=`[security_id,prediction_date]`，value exact：

```json
{
  "list_observation_known": true,
  "listed_sessions": "<decimal>",
  "listing_eligible": true,
  "delist_observation_known": true,
  "delist_event_present": false,
  "delist_effective": false,
  "active": true
}
```

若观察覆盖缺失，validation直接FAIL/HOLD，不生成可PASS UNKNOWN row。对合格axis，按prediction
time选择latest available observation；null delist=known/no event。listed sessions、09:30 boundary
和active公式在此完整定义：eligible=list known且从first open>=list date到D inclusive
>=60；delist effective=known+date present且first open>=event date 09:30<=prediction；active=
eligible and not effective。

records按security UTF-8/date排序；count=security_count*date_count。schema/key/value/logical digest
按AP LP算法。

### 3.7 Final authority V4 and receipt V4

final authority exact：

```text
schema_version,authority_id,parent_fixed_audit{file/content SHA},
contract_sha256,population_authority{ArtifactRef,count,key_digest},
security_source_projection{ArtifactRef},prediction_date_axis{ArtifactRef},
field_schema_registry{ArtifactRef},issuer_authority{ArtifactRef},
observation_manifest{ArtifactRef},calendar_manifest{ArtifactRef},
timezone="Asia/Shanghai",session_open="09:30:00",
valid_from,valid_until,statement_sha256,
independent_validation_receipt{path,file_sha256,canonical_sha256},
canonical_sha256
```

receipt exact：

```text
schema_version,authority_statement_sha256,parent audit file/content SHA,contract SHA,
population/security/date axis counts+digests,
source/registry/issuer/observation/calendar file+canonical SHAs,
validator code/env SHAs,
sla006{row_count,schema_sha256,key_digest,value_digest,logical_digest},
checks exact SLA001..SLA006 all PASS,
verdict PASS,reviewer_context_id,issuer_context_id,canonical_sha256
```

statement→receipt→final单向；roles paths/SHAs两两分离，禁止self/ancestor/container/downstream。
receipt逐wrapper strict解析并全量重算，不接受extra nesting。slot/coverage/history/issuer/digest任一
不符即qualification前HOLD。
