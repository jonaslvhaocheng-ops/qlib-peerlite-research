# M7 CCC / 市场状态 Gate 设计 v10

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v9.md`
- Base SHA：`ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94`
- 取代：M7 v9；历史版本与失败审查保留。

## 1. Exact composition

v9 §1、§2.1、§2.3、§2.5、§2.7及§3–§6逐字保留。仅作以下完整替换：

| v9 | v10 |
| --- | --- |
| §2.2全部 | 本文件§2 |
| §2.4全部 | 本文件§3 |
| §2.6全部 | 本文件§4 |

本文件不创建任何authority/qualification/prerequisite，不运行fit，不改变预算，不访问final-OOS。

## 2. Official behavior 与 WholeRecordFieldAdapterV1

### 2.1 Official output

一T一official FUTURE_POISON request/manifest；exact B001–B004。state output CSV保持official exact
四列。`feature_value_json`是`float64.hex()`的JSON string scalar。十个official artifact slots映射
沿用v9，但`parameters`必须额外绑定本节adapter spec ID/SHA。

### 2.2 One-record-per-field raw snapshot

baseline/probe `pit_behavior_snapshot_v1`由同一个hash-bound
`WholeRecordFieldAdapterV1`产生。每个source row的每个被审计field恰生成一条record：

```text
tuple_bytes = LP(source_id UTF-8)
            || LP(table_id UTF-8)
            || LP(canonical primary-key JSON UTF-8)
            || LP(field UTF-8)
raw_key  = sha256(tuple_bytes).hexdigest()
sample_id= source_id + "|" + table_id + "|" + sha256(primary-key JSON).hexdigest()
```

`LP=uint64 big-endian length || bytes`。record exact shape仍为official：

```json
{
  "raw_key": "<64 lowercase hex>",
  "sample_id": "<non-empty string>",
  "available_time": "<UTC RFC3339 Z>",
  "revision_known_time": "<UTC RFC3339 Z>",
  "universe_known_time": "<UTC RFC3339 Z>",
  "payload": {
    "source_id": "<ASCII>",
    "table_id": "<ASCII>",
    "primary_key_json": "<canonical JSON array encoded as a JSON string>",
    "field": "<ASCII>",
    "value_json": "<canonical JSON scalar encoded as a JSON string>"
  }
}
```

payload不含其他key。source primary key/field/value按PreOOSAuxSnapshotV2 exact schemas。available
time只能来自已绑定source clock；LIST_DATE/DELIST_DATE来自§4 authority。若没有独立revision/
universe clock，则对应字段exact等于available_time并在parameters声明
`fallback=AVAILABLE_TIME`；不得自造更早时间。

original/probe records使用同一tuple identity。每个perturbation ledger entry与supplement entry
通过raw_key一对一；changed record的available_time必须等于supplement
vendor_available_time且`>T`。baseline/probe value hashes从payload `value_json` exact UTF-8 bytes
重算。未变化field records byte-identical；probe至少一条变化。

parameters exact绑定：

- adapter spec ID=`qlib_peerlite_whole_record_field_adapter_v1`；
- adapter source SHA、LP/canonical JSON policy SHA；
- exact source/table/field allow-list；
- baseline/probe source manifest SHA；
- lifecycle authority final canonical SHA；
- T、state四列顺序与projection policy SHA。

因此official B002 whole-record future predicate与项目逐field availability使用同一record grain。

## 3. AuxPrefixBehaviorVerificationV3

### 3.1 Closed invocation

strict `AuxPrefixInvocationV3`只允许：

```json
{
  "schema_version": "qlib_peerlite_aux_prefix_invocation_v3",
  "invocation_id": "<ASCII>",
  "protected_through": "<UTC RFC3339 Z>",
  "official_request_sha256": "sha256:<64hex>",
  "official_manifest_sha256": "sha256:<64hex>",
  "official_report_sha256": "sha256:<64hex>",
  "official_baseline_snapshot_sha256": "sha256:<64hex>",
  "official_probe_snapshot_sha256": "sha256:<64hex>",
  "official_baseline_output_sha256": "sha256:<64hex>",
  "official_probe_output_sha256": "sha256:<64hex>",
  "official_expected_keys_sha256": "<64hex>",
  "supplement_sha256": "sha256:<64hex>",
  "projection_policy_sha256": "sha256:<64hex>",
  "products": {
    "aux": {"baseline": "<manifest ref>", "probe": "<manifest ref>"},
    "population": {"baseline": "<manifest ref>", "probe": "<manifest ref>"},
    "state": {"baseline": "<manifest ref>", "probe": "<manifest ref>"}
  },
  "verifier_code_sha256": "sha256:<64hex>",
  "environment_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

manifest ref exact keys为`path,sha256`。unknown/null/float拒绝。official request的十slot hashes、
manifest/report/T与此处必须exact一致。

### 3.2 PrefixProductManifestV1

六个manifest（3 products × 2 sides）各自strict：

```json
{
  "schema_version": "qlib_peerlite_prefix_product_manifest_v1",
  "product": "aux|population|state",
  "side": "baseline|probe",
  "protected_through": "<UTC RFC3339 Z>",
  "official_raw_snapshot_sha256": "sha256:<64hex>",
  "root_source_manifest": {
    "path": "<fixed relative path>",
    "sha256": "sha256:<64hex>"
  },
  "projection_policy_sha256": "sha256:<64hex>",
  "schema_sha256": "sha256:<64hex>",
  "records": {
    "path": "<relative JSONL>",
    "sha256": "sha256:<64hex>",
    "row_count": "<positive decimal ASCII>"
  },
  "key_count": "<positive decimal ASCII>",
  "key_digest": "sha256:<64hex>",
  "value_digest": "sha256:<64hex>",
  "logical_digest": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

product/side/path与invocation slot exact匹配。baseline/probe
`official_raw_snapshot_sha256`分别等于official两个snapshot slot；T/policy一致。root source：
aux=对应PreOOSAuxSnapshotV2，population/state=对应MarketStateProductV2 parent manifest。
records使用v9 §2.4的三产品record views和LP digest算法，非空。

verifier不信manifest digests：从official raw snapshot、source manifest、supplement、lifecycle
authority和projection code重新构造每侧expected records，再验证records exact bytes、coverage、
count及全部digests。source-derived expected key axis必须非空并exact等于records key axis；不存在
“两份相同空manifest”PASS路径。verifier还从root source按§2 adapter重建整份official raw
snapshot并要求exact byte/hash相等，证明official snapshot不是无关输入。

### 3.3 Official state cross-check

verifier独立解析official baseline/probe CSV，按sample_id/date/feature/value重建v9 state record，
用同一schema/LP算法生成每侧`official_state_projection`。它必须分别与对应state product
manifest的：

```text
row_count/key_count/key_digest/value_digest/logical_digest
```

exact相等。official receipt的`expected_key_count/expected_keys_sha256`必须由该独立state key axis
按official behavior spec canonical-key算法重算并相等，不能信adapter自报。

### 3.4 Verification receipt

每个`ProductPrefixComparisonV1` exact shape：

```json
{
  "baseline_manifest_sha256": "sha256:<64hex>",
  "probe_manifest_sha256": "sha256:<64hex>",
  "schema_sha256": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  },
  "key_count": {
    "baseline": "<positive decimal ASCII>",
    "probe": "<positive decimal ASCII>",
    "equal": true
  },
  "key_digest": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  },
  "value_digest": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  },
  "logical_digest": {
    "baseline": "sha256:<64hex>",
    "probe": "sha256:<64hex>",
    "equal": true
  }
}
```

V3 receipt是strict object，exact shape：

```json
{
  "schema_version": "qlib_peerlite_aux_prefix_behavior_verification_v3",
  "verification_id": "<ASCII>",
  "invocation_sha256": "sha256:<64hex>",
  "verifier_code_sha256": "sha256:<64hex>",
  "environment_sha256": "sha256:<64hex>",
  "report_sha256": "sha256:<64hex>",
  "official_behavior_manifest_sha256": "sha256:<64hex>",
  "supplement_sha256": "sha256:<64hex>",
  "protected_through": "<UTC RFC3339 Z>",
  "products": {
    "aux": "<ProductPrefixComparisonV1>",
    "population": "<ProductPrefixComparisonV1>",
    "state": "<ProductPrefixComparisonV1>"
  },
  "official_state_crosscheck": {
    "baseline": {
      "official_output_sha256": "sha256:<64hex>",
      "state_product_manifest_sha256": "sha256:<64hex>",
      "key_count": "<positive decimal ASCII>",
      "key_digest": "sha256:<64hex>",
      "value_digest": "sha256:<64hex>",
      "logical_digest": "sha256:<64hex>",
      "equal": true
    },
    "probe": "<same exact object>",
    "receipt_expected_key_count": "<positive decimal ASCII>",
    "derived_expected_key_count": "<positive decimal ASCII>",
    "receipt_expected_keys_sha256": "<64hex>",
    "derived_expected_keys_sha256": "<64hex>",
    "equal": true
  },
  "checks": [
    {"check_id": "AP001", "status": "PASS"},
    {"check_id": "AP002", "status": "PASS"},
    {"check_id": "AP003", "status": "PASS"},
    {"check_id": "AP004", "status": "PASS"},
    {"check_id": "AP005", "status": "PASS"}
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

AP001=input lineage/schema/coverage；AP002=三产品key count/digest；AP003=value digest；
AP004=logical digest；AP005=official↔state逐侧cross-check和receipt expected keys。exact五项、无
额外/重复、全部PASS；三products全部15 equality、crosscheck全部equal均为true。receipt还绑定
verifier code/environment/report SHA和canonical SHA，unknown/null/float拒绝。

## 4. SecurityLifecycleAvailabilityAuthorityV2

### 4.1 Acyclic fixed roles

唯一角色图：

```text
issuer authority
sealed md_security source projection
two vendor evidence JSONL artifacts
  -> authority statement
  -> independent validation receipt
  -> final lifecycle authority
  -> qualification
```

exact evidence kinds只有：

```text
DATAYES_MD_SECURITY_LIST_AVAILABILITY_V1
DATAYES_MD_SECURITY_DELIST_AVAILABILITY_V1
```

issuer path必须位于derived contract固定的`contracts/immutable/external_authorities/`，source/
evidence paths必须位于固定`evidence/pit/source_authorities/`且是regular no-symlink files。
authority、validation receipt及包含它们的bundle路径禁止作为issuer/source/evidence；五类角色
path与SHA两两不同；禁止ancestor/container hash和任何指向下游角色的字段。各schema不含任意
extension/map字段，因此不能藏回边。statement hash排除receipt/final canonical，DAG无环。

### 4.2 SealedSecuritySourceProjectionV1

source manifest strict绑定一个JSONL，列恰为：

```json
{
  "security_id": "<NFC string>",
  "list_date": "YYYY-MM-DD",
  "delist_date": "YYYY-MM-DD or null",
  "source_record_sha256": "sha256:<64hex>"
}
```

按security_id UTF-8 bytes唯一升序。`source_record_sha256` preimage是从sealed DataYes
md_security row提取exact：

```json
{"DELIST_DATE":"YYYY-MM-DD or null","LIST_DATE":"YYYY-MM-DD","SECURITY_ID":"<string>"}
```

UTF-8、keys字节序、NFC、`,`/`:`、无空格/尾换行。manifest exact字段：

```json
{
  "schema_version": "qlib_peerlite_sealed_security_source_projection_v1",
  "source_id": "DataYes.md_security",
  "source_version": "<ASCII>",
  "source_snapshot_manifest_sha256": "sha256:<64hex>",
  "columns": ["security_id", "list_date", "delist_date", "source_record_sha256"],
  "rows": {
    "path": "<fixed relative JSONL path>",
    "sha256": "sha256:<64hex>",
    "row_count": "<positive decimal ASCII>",
    "key_digest": "sha256:<64hex>"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/null/float拒绝；columns exact顺序。key digest=
`sha256(concat(LP(security_id UTF-8)))`。该projection exact覆盖fixed PIT audit使用的qualified
md_security security IDs。

### 4.3 Vendor evidence and availability rows

两份evidence JSONL每行exact：

```json
{
  "evidence_record_id": "<ASCII>",
  "security_id": "<NFC string>",
  "field": "LIST_DATE|DELIST_DATE",
  "event_value": "YYYY-MM-DD or null",
  "vendor_available_time": "<UTC RFC3339 Z or null iff DELIST null>",
  "source_version": "<ASCII>",
  "issuer_statement_id": "<ASCII>"
}
```

canonical record hash按§4.2 JSON规则。按`security_id,field` UTF-8 bytes唯一排序。availability
row不再有自由`evidence_sha256`，而是exact：

```json
{
  "security_id": "<string>",
  "source_record_sha256": "sha256:<64hex>",
  "list_date": "YYYY-MM-DD",
  "list_vendor_available_time": "<UTC RFC3339 Z>",
  "list_evidence_artifact_kind": "DATAYES_MD_SECURITY_LIST_AVAILABILITY_V1",
  "list_evidence_record_id": "<ASCII>",
  "list_evidence_record_sha256": "sha256:<64hex>",
  "delist_date": "YYYY-MM-DD or null",
  "delist_vendor_available_time": "<UTC RFC3339 Z or null>",
  "delist_evidence_artifact_kind": "DATAYES_MD_SECURITY_DELIST_AVAILABILITY_V1",
  "delist_evidence_record_id": "<ASCII or null>",
  "delist_evidence_record_sha256": "sha256:<64hex or null>"
}
```

每个ref以kind定位authority中唯一artifact，再以record_id定位唯一record；security/field/value/
time/version与availability row及source projection exact一致。list必有证据；delist三字段同null
或同nonnull。availability rows key digest同§4.2。

### 4.4 Calendar/session and visibility replay

calendar固定为parent PIT audit绑定的`md_trade_cal` snapshot/manifest exact SHA；timezone固定
`Asia/Shanghai`；只使用XSHG/XSHE exact相等open sessions。

```text
session_open(D) = D日09:30:00 Asia/Shanghai；
若event date非open session，则取首个>=event date的open session 09:30。
prediction_time(D) = 冻结研究契约的D日收盘后时间。
```

对每个qualified security和每个pre-OOS prediction date D：

```text
list_known = list_vendor_available_time <= prediction_time(D)
listed_sessions = count(open session S with S>=first_open_on_or_after(list_date) and S<=D)
listing_eligible = list_known and listed_sessions >= 60

delist_known = delist_date/time nonnull
               and delist_vendor_available_time <= prediction_time(D)
delist_effective = delist_known
                   and session_open(first_open_on_or_after(delist_date))
                       <= prediction_time(D)
active = listing_eligible and not delist_effective
```

SLA006 exact replay axis是source projection全部security × fixed calendar全部pre-OOS prediction dates；
输出key/count/logical digest写入validation receipt。禁止event-date availability推断。

### 4.5 Final authority and validation receipt

authority V2 strict shape：

```json
{
  "schema_version": "qlib_peerlite_security_lifecycle_availability_authority_v2",
  "authority_id": "<ASCII>",
  "source_id": "DataYes.md_security",
  "source_version": "<ASCII>",
  "source_projection": {
    "path": "<fixed relative path>",
    "sha256": "sha256:<64hex>",
    "canonical_sha256": "sha256:<64hex>"
  },
  "availability_rows": {
    "path": "<fixed relative path>",
    "sha256": "sha256:<64hex>",
    "row_count": "<positive decimal ASCII>",
    "key_digest": "sha256:<64hex>"
  },
  "evidence_artifacts": [
    {
      "kind": "DATAYES_MD_SECURITY_LIST_AVAILABILITY_V1",
      "path": "<fixed relative path>",
      "sha256": "sha256:<64hex>"
    },
    {
      "kind": "DATAYES_MD_SECURITY_DELIST_AVAILABILITY_V1",
      "path": "<fixed relative path>",
      "sha256": "sha256:<64hex>"
    }
  ],
  "calendar": {
    "source_id": "DataYes.md_trade_cal",
    "manifest_sha256": "sha256:<64hex>",
    "timezone": "Asia/Shanghai",
    "session_open": "09:30:00",
    "prediction_time_contract_sha256": "sha256:<64hex>"
  },
  "issuer_authority_path": "<fixed external-authority relative path>",
  "issuer_authority_sha256": "sha256:<64hex>",
  "issuer_authority_version": "<ASCII>",
  "valid_from": "<UTC RFC3339 Z>",
  "valid_until": "<UTC RFC3339 Z>",
  "statement_sha256": "sha256:<64hex>",
  "independent_validation_receipt": {
    "path": "<fixed relative path>",
    "sha256": "sha256:<64hex>"
  },
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/null/float拒绝；evidence exact两项/顺序。statement SHA排除statement、receipt和final
canonical字段；final canonical只排除自身。

validation receipt exact SLA001–SLA006：

- SLA001 schemas/hashes/role DAG；
- SLA002 source/availability coverage、unique/order/key digests；
- SLA003 source row/value equality；
- SLA004 every evidence ref/record hash/issuer/version；
- SLA005 timestamp/authority validity；
- SLA006 full security×date visibility replay digest。

receipt strict shape：

```json
{
  "schema_version": "qlib_peerlite_security_lifecycle_validation_receipt_v2",
  "authority_statement_sha256": "sha256:<64hex>",
  "source_projection_sha256": "sha256:<64hex>",
  "availability_rows_sha256": "sha256:<64hex>",
  "list_evidence_sha256": "sha256:<64hex>",
  "delist_evidence_sha256": "sha256:<64hex>",
  "calendar_manifest_sha256": "sha256:<64hex>",
  "validator_code_sha256": "sha256:<64hex>",
  "environment_sha256": "sha256:<64hex>",
  "visibility_replay": {
    "key_count": "<positive decimal ASCII>",
    "key_digest": "sha256:<64hex>",
    "value_digest": "sha256:<64hex>",
    "logical_digest": "sha256:<64hex>"
  },
  "checks": [
    {"check_id": "SLA001", "status": "PASS"},
    {"check_id": "SLA002", "status": "PASS"},
    {"check_id": "SLA003", "status": "PASS"},
    {"check_id": "SLA004", "status": "PASS"},
    {"check_id": "SLA005", "status": "PASS"},
    {"check_id": "SLA006", "status": "PASS"}
  ],
  "verdict": "PASS",
  "reviewer_context_id": "<ASCII>",
  "issuer_context_id": "<ASCII>",
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/null/float/extra check拒绝。receipt绑定statement、rows/source/evidence/calendar、validator
code/env及replay digests；reviewer与issuer必须不同。
slot缺失、过期、role回边、coverage/evidence/session replay不符均qualification前FAIL/HOLD。
