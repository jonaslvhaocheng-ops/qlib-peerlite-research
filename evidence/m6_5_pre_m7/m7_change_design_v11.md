# M7 CCC / 市场状态 Gate 设计 v11

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v10.md`
- Base SHA：`bfa95544be056fb7d2874a072b3feabbe15f3665064775bcdace194383917bb4`
- 取代：M7 v10；历史版本与失败审查保留。

## 1. Exact composition

v10 composite的ancestry base是M7 v9 SHA
`ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94`。
逐字保留v9 §1、§2.1、§2.3、§2.5、§2.7及§3–§6。仅替换v10文件自己新增的三个顶层段：

| v10 | v11 |
| --- | --- |
| v10本文件§2全部 | 本文件§2完整替换 |
| v10本文件§3全部 | 本文件§3完整替换 |
| v10本文件§4全部 | 本文件§4完整替换 |

这里的“v10本文件§N”指`m7_change_design_v10.md`的同名顶层段，不指v9 ancestry。本文件不
创建authority/qualification，不运行fit，不改变预算，不访问final-OOS。

## 2. Official WholeRecordFieldAdapterV2

### 2.1 Existing official slots and state output

一T一official FUTURE_POISON request/manifest，exact B001–B004。request只含official十slots：

```text
baseline_raw_snapshot,probe_raw_snapshot,code_or_query,parameters,environment,
baseline_output,probe_output,pit_audit_manifest,perturbation_ledger,pipeline_receipt
```

`code_or_query`=adapter exact source；`parameters`=adapter spec/SHA、T、四列、source/lifecycle/
projection hashes；`environment`=runtime closure；其余按名称映射。不得增加private key。

state output CSV exact header：

```text
sample_id,prediction_time,feature_name,feature_value_json
```

每date<=T四行；sample ID=`market_state|YYYY-MM-DD`；prediction time=contract-bound UTC六位小数Z；
feature按四列顺序；value是`float(value).hex()`的JSON string scalar。按official canonical key稳定
排序。

### 2.2 Field records

每个source row的每个audited field恰一record。定义：

```text
LP(x)=uint64 big-endian len(x)||x
pk_json=canonical UTF-8 JSON array（NFC、`,`/`:`、无空格）
tuple=LP(source_id)||LP(table_id)||LP(pk_json)||LP(field)
raw_key=sha256(tuple).hexdigest()
sample_id=source_id+"|"+table_id+"|"+sha256(pk_json).hexdigest()
```

record exact official shape；payload exact：

```json
{
  "source_id": "<ASCII>",
  "table_id": "<ASCII>",
  "primary_key_json": "<canonical JSON array encoded as string>",
  "field": "<ASCII>",
  "value_json": "<canonical JSON scalar encoded as string>"
}
```

三个official clock均nonnull UTC RFC3339 Z：

- `available_time`=`field_observation_available_time`；
- 有独立revision/universe clock则用证据值；
- 否则等于available_time，且parameters exact声明fallback。

LIST/DELIST clocks来自§4 authority。null DELIST不使用null event clock；authority必须提供nonnull
`delist_observation_available_time`，表示“该null observation最早被可信观察”的时间。若缺证据，
qualification HOLD，不能编造。

### 2.3 Valid poison construction

baseline/probe使用相同record key set；每个changed record：

- raw_key/sample_id/source/table/pk/field及三个clocks byte-identical；
- 仅payload `value_json`不同；
- baseline/probe value UTF-8 SHA必须不同；
- observation available_time>T；
- supplement raw_key/field/time/baseline/probe hashes一对一exact匹配。

changed set必须exact等于value_json diff set且非空；clock-only、key-only、payload metadata-only
diff均FAIL。未变化record exact byte-identical。parameters绑定
`qlib_peerlite_whole_record_field_adapter_v2`及LP/canonical/source allow-list/lifecycle hashes。

## 3. AuxPrefixBehaviorVerificationV4

### 3.1 Canonical product records

对每side和T：

- aux：五表`membership,security,calendar,status,action`；按可得性投影。record key=
  `[table,primary-key canonical array,field]`，value=canonical scalar；
- population：date<=T的member key=`["member",date,instrument]`, value=true；count key=
  `["count",date]`, value=decimal string；
- state：date<=T的key=`["state",date,column]`，value=`float(value).hex()` string。

dates=`YYYY-MM-DD`，strings NFC，禁止nonfinite；stable UTF-8 key order、unique、每product非空。

```text
key_bytes=canonical JSON(record key)
value_bytes=canonical JSON scalar(record value)
schema_bytes=canonical exact schema JSON
key_digest=sha256(concat(LP(key_bytes)))
value_digest=sha256(concat(LP(key_bytes)||LP(value_bytes)))
logical_digest=sha256(LP(schema_bytes)||concat(LP(key_bytes)||LP(value_bytes)))
```

### 3.2 Closed invocation and product manifests

`AuxPrefixInvocationV4` exact fields：

```text
schema_version,invocation_id,protected_through,
official_request_sha256,official_manifest_sha256,official_report_sha256,
official_baseline_snapshot_sha256,official_probe_snapshot_sha256,
official_baseline_output_sha256,official_probe_output_sha256,
official_expected_keys_sha256,supplement_sha256,projection_policy_sha256,
products{aux/population/state:{baseline{path,sha256},probe{path,sha256}}},
verifier_code_sha256,environment_sha256,canonical_sha256
```

无其他key/null/float。每个`PrefixProductManifestV2` strict：

```text
schema_version,product,side,protected_through,
official_raw_snapshot_sha256,
root_source_manifest{path,sha256},
projection_policy_sha256,schema_sha256,
records{path,sha256,row_count},
key_count,key_digest,value_digest,logical_digest,canonical_sha256
```

row_count/key_count为positive decimal strings且必须相等。product/side/T/snapshot/policy/root与
invocation exact匹配。verifier从root source重建whole-record official snapshot并exact比对，再从
source/supplement/lifecycle/policy独立构造expected product records，验证record bytes/coverage/
digests；空或无关manifest失败。

### 3.3 Dual-sided AP005

official CSV每侧独立转为§3.1 state records。每个metric receipt exact保存：

```json
{"official":"<value>","state_product":"<value>","equal":true}
```

metrics恰为：

```text
row_count,key_count,key_digest,value_digest,logical_digest
```

count用positive decimal string，digest用sha256。另保存official receipt expected key
count/digest与independent derived count/digest的双侧comparison。所有equal必须true。

### 3.4 V4 receipt

strict fields：

```text
schema_version,verification_id,invocation_sha256,verifier_code_sha256,
environment_sha256,report_sha256,official_behavior_manifest_sha256,
supplement_sha256,protected_through,
products{aux,population,state},
official_state_crosscheck{baseline,probe,expected_keys},
checks,canonical_sha256
```

每product comparison对schema/key_count/key_digest/value_digest/logical_digest分别保存
baseline/probe/equal。crosscheck按§3.3保存双侧值。checks exact：

```text
AP001 input lineage/schema/coverage
AP002 key count/digest
AP003 value digest
AP004 logical digest
AP005 official/state/expected-key crosscheck
```

全部PASS、无额外/重复。qualification validator必须重算V4；report只是deterministic view，不替代
receipt双侧证据。

## 4. SecurityLifecycleAvailabilityAuthorityV3

### 4.1 Exact trust and axes

authority statement exact绑定：

- parent fixed PIT audit manifest file SHA、content SHA及exact fixed17；
- frozen contract SHA；
- `PreOOSAuxSnapshotV2` population authority path/SHA及expected security key count/digest；
- sealed md_security source snapshot path/SHA/version；
- `SecuritySourceProjectionV2` path/SHA；
- `PredictionDateAxisV1` path/SHA；
- two vendor evidence artifacts；
- external issuer authority；
- md_trade_cal manifest SHA、timezone/session rules。

`SecuritySourceProjectionV2` rows exact：

```json
{
  "security_id": "<NFC>",
  "source_row_locator": "security_id=<percent-encoded UTF-8>",
  "list_date": "YYYY-MM-DD",
  "delist_date": "YYYY-MM-DD or null",
  "source_record_sha256": "sha256:<64hex>"
}
```

source record preimage exact
`{"DELIST_DATE":...,"LIST_DATE":...,"SECURITY_ID":...}` canonical JSON。projection security key
count/digest必须等于population authority expected axis。

`PredictionDateAxisV1`由bound md_trade_cal和contract重算，rows exact：

```json
{"prediction_date":"YYYY-MM-DD","prediction_time":"<UTC RFC3339 Z>"}
```

覆盖2012-01-01 inclusive至2025-01-01 exclusive内所有contract prediction sessions，按date排序，
positive count；key digest=`sha256(concat(LP(date ASCII)))`。

### 4.2 Issuer and evidence

external `LifecycleEvidenceIssuerAuthorityV1` strict：

```text
schema_version,issuer_id,issuer_version,valid_from,valid_until,
authorized_statements[
 {statement_id,kind,path,sha256,record_count,records_logical_digest}
],
canonical_sha256
```

kind exact为LIST或DELIST两种，array按kind排序、恰两项。issuer schema不含下游role字段。

evidence JSONL record exact：

```json
{
  "evidence_record_id": "<ASCII>",
  "issuer_statement_id": "<authorized statement_id>",
  "security_id": "<NFC>",
  "field": "LIST_DATE|DELIST_DATE",
  "event_value": "YYYY-MM-DD or null",
  "field_observation_available_time": "<nonnull UTC RFC3339 Z>",
  "event_vendor_available_time": "<UTC RFC3339 Z or null>",
  "source_version": "<ASCII>"
}
```

record canonical SHA及artifact logical digest使用LP(key/value)算法。每record的statement ID/kind/
artifact path/SHA/count/logical digest必须由issuer authority exact授权且在有效期内。

availability rows exact绑定source record及list/delist evidence record ID/SHA。LIST observation和
event time均nonnull。DELIST observation永远nonnull；若event null，则event time null；若event
present则event time nonnull。whole-record adapter使用observation time。

role DAG固定
`issuer+fixed audit+population+source+calendar+evidence -> statement -> validation receipt ->
final authority -> qualification`。path/SHA两两角色分离，禁止self/ancestor/container/downstream边。

### 4.3 Session logic and SLA006 records

calendar为bound XSHG/XSHE equal open sessions；timezone=`Asia/Shanghai`；event session boundary=
首个>=event date的open session 09:30；prediction time来自date axis。

每个security×prediction-date输出一条record：

```json
{
  "key": ["<security_id>", "YYYY-MM-DD"],
  "value": {
    "list_observation_known": true,
    "listed_sessions": "<decimal ASCII>",
    "listing_eligible": true,
    "delist_observation_known": true,
    "delist_event_present": false,
    "delist_effective": false,
    "active": true
  }
}
```

booleans按公式真实取值，不固定为示例。list observation known iff observation time<=prediction；
listed_sessions从first open>=list_date至prediction date inclusive；eligible=known且>=60。delist
observation known同理；event present由observed value；effective=known+present且event session
boundary<=prediction；active=eligible且not effective。observation尚不可得时对应security-date
为UNKNOWN并`active=false`。

records按security UTF-8/date排序，exact count=`security_count*date_count`。key bytes=
canonical JSON key，value bytes=canonical JSON value；schema/key/value/logical digest按§3.1 LP算法。
SLA006 receipt保存axis counts/digests及这些四digests，validator全量重算。

### 4.4 Authority/receipt

final authority strict绑定§4.1所有parent path/SHA/count/digests、§4.2 issuer/evidence、
availability rows、calendar/session rules、validity、statement SHA、validation receipt ref和final
canonical SHA。statement SHA排除receipt/final fields；receipt只绑定statement；final再绑定receipt。

validation receipt exact SLA001–SLA006并绑定：

```text
statement SHA,parent audit file/content SHA,contract SHA,population authority SHA,
security/date axis count+key digests,source/evidence/calendar SHAs,
validator code/env,SLA006 schema/key/value/logical digests,
reviewer/issuer contexts,verdict,canonical SHA
```

SLA001 schema/hash/DAG；SLA002 axes coverage；SLA003 source equality；SLA004 issuer/evidence lookup；
SLA005 clocks/validity；SLA006 full replay。任一缺失/回边/axis错/证据错即qualification前HOLD。
