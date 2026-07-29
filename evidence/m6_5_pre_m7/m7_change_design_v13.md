# M7 CCC / 市场状态 Gate 设计 v13

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v12.md`
- Base SHA：`80240e3cd0cb6c569a35f755d187f92d51437c4da25dd617242af0fd2c911130`
- 取代：M7 v12；历史版本与失败审查保留。

## 1. Exact composition

v12 除下表所列内容外逐字保留：

| v12 | v13 |
| --- | --- |
| §2.1 numeric/parser rules | 本文件§2完整替换 |
| §2.2 interval selection rules | 本文件§3完整替换；identity/payload/clocks其余内容保留 |
| §3.4 issuer time rule | 本文件§4补充并优先 |
| §3.5 observation row与reconciliation | 本文件§5完整替换row和validation rules；wrapper其余内容保留 |
| §3.6 pre-list/selection semantics | 本文件§6完整替换 |

v12其他 qualification/AP/CCC/Gate/budget/test-ownership语义不变。Run authority另由
`run_authority_generation_v5.md`冻结；两个 M7 purpose 均必须在first event前绑定完整 PASS
qualification。本文不创建authority/qualification，不运行fit/replay，不改预算，不访问
final-OOS。

## 2. Field schema, parser locator and numeric canonicalization

`FieldSchemaRegistryV2` exact：

```json
{
  "schema_version": "qlib_peerlite_field_schema_registry_v2",
  "canonical_numeric_algorithm": "QLIB_PEERLITE_CANONICAL_DECIMAL_V1",
  "fields": [
    {
      "source_id": "<ASCII>",
      "table_id": "<ASCII>",
      "field": "<ASCII>",
      "json_type": "STRING|DATE|BOOLEAN|INTEGER|FINITE_NUMBER|NULLABLE_DATE",
      "nullable": true,
      "domain_code": "<fixed parser/domain ID>",
      "production_parser": "<ArtifactRefV1>"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

fields 按 source/table/field UTF-8排序且唯一。parser ArtifactRef 必须指向已验证代码 closure，
逐文件重算 file/canonical hash；裸 SHA 不接受。

`QLIB_PEERLITE_CANONICAL_DECIMAL_V1`：

- input 必须是 JSON string 中的 ASCII decimal token，禁止 whitespace、`+`、NaN/Inf和locale；
- INTEGER grammar：`0|-?[1-9][0-9]*`，因此`-0`非法；
- FINITE_NUMBER grammar：
  `0|-?[1-9][0-9]*(?:\.[0-9]*[1-9])?`；禁止 exponent、leading zero、trailing fractional zero、
  bare decimal point和`-0`；
- 用 arbitrary-precision sign/coefficient/scale tuple exact parse，不使用 binary float或可变
  decimal context；canonical output 就是上述唯一 grammar；
- domain_code 再约束 min/max/scale/enum；越界非法；
- BOOLEAN exact `true|false`，DATE exact `YYYY-MM-DD`且Gregorian-valid，NULLABLE_DATE exact
  canonical date或`null`。

两 side 必须由同一 ArtifactRef parser 解析并获得 typed value；semantic poison 只接受合法且
canonical typed value不等。任何 byte-different semantic noop 都 FAIL。

## 3. Observation intervals and deterministic selection

每个 `(source_id,table_id,pk_json,field)` 的 observations 按
`(observed_from UTF-8, observation_id UTF-8)`排序。规则：

- interval 唯一采用半开 `[observed_from, observed_until)`；
- `field_observation_available_time == observed_from`；
- 非末条 `observed_until == 下一条 observed_from`，末条 until=null；
- 同一 observed_from 出现两条、重复 observation_id、gap、overlap、倒序均 HOLD；
- 在 prediction time `P` 的选择条件唯一是
  `observed_from <= P and (observed_until is null or P < observed_until)`；
- 满足行必须恰为一条；不得用文件顺序、最终值或额外 tie breaker；
- official clocks仍按v12；没有独立 revision/universe clock时exact等于available time。

DELIST null→date版本史继续有效。coverage 起点和 pre-list 特例由§6定义。

## 4. Issuer validity and evidence clocks

`LifecycleEvidenceIssuerAuthorityV2.valid_from/valid_until` 采用半开
`[valid_from,valid_until)`。独立 validation receipt 的 `verified_at` 是唯一 issuer
authorization evaluation time，必须满足该区间；same-time边界只有valid_from包含、
valid_until排除。

evidence record：

- `field_observation_available_time == observed_from`；
- nonnull event 必须有 nonnull `event_vendor_available_time`，且
  `event_vendor_available_time <= field_observation_available_time`；
- null DELIST 的 event vendor time 必须null；
- issuer authority/statement/source version/kind 任一不匹配即 HOLD。

receipt 必须绑定 issuer authority ArtifactRef、`verified_at` 和上述区间判定；不得以文件mtime、
当前wall clock或observation time替代。

## 5. Observation row, record hash and source reconciliation

LifecycleObservationManifest wrapper保留v12 §3.5，但 observation row exact替换为：

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
  "evidence_artifact_file_sha256": "sha256:<64hex>",
  "evidence_record_id": "<ASCII>",
  "evidence_record_canonical_sha256": "sha256:<64hex>",
  "source_record_sha256": "sha256:<64hex>"
}
```

record canonical SHA 是排除不存在的self-hash字段后，对 exact evidence record canonical JSON
bytes计算的SHA；artifact file SHA 必须等于 issuer-authorized LIST/DELIST JSONL file SHA。
`[issuer_statement_id,evidence_record_id]`在授权artifact内唯一，并通过offset-independent
full scan定位；不得把整文件SHA当record SHA。

对每个 security：

1. 所有 observation 的 security_id、source_version、source_record_sha256 必须与同一
   SecuritySourceProjectionV3 row exact相等；
2. LIST observations 的 canonical value 必须全都等于 projection.list_date；
3. 在 qualification cutoff 选择的 latest DELIST observation canonical value必须等于
   projection.delist_date（null或date）；
4. nonnull DELIST observation 的 event date必须等于 projection.delist_date；final source为
   null时不得存在nonnull history；
5. 每条 manifest row 必须与由 evidence artifact+record ID重新解析的exact record逐字段相等；
6. 任一不等、孤立record、跨security record或未授权 extra record均 HOLD。

## 6. Full Cartesian axis and PRE_LIST semantics

SLA006 仍对完整 security axis × prediction-date axis 输出exact一行。对每个 security先确定
第一条有效 LIST observation 的 `observed_from=L`。

当 prediction time `P < L` 时，状态固定为：

```json
{
  "list_observation_known": false,
  "listed_sessions": "0",
  "listing_eligible": false,
  "delist_observation_known": false,
  "delist_event_present": false,
  "delist_effective": false,
  "active": false
}
```

这称为 `PRE_LIST`，不要求 DELIST interval coverage，不构成 qualification HOLD。不得从
projection final list_date倒推已上市。

当 `P >= L`：

- LIST selection按§3必须恰一条；
- DELIST intervals必须从L连续覆盖到qualification cutoff，按§3选择恰一条；
- 缺coverage直接HOLD，不生成UNKNOWN；
- null DELIST表示known/no event；
- listed_sessions只使用截至P已知交易日历，从first open>=known list date到D inclusive；
- listing eligible为known且sessions>=60；
- delist effective为known+nonnull event，且first open>=event date 09:30不晚于P；
- active=`listing_eligible and not delist_effective`。

records按security UTF-8/date排序，count严格等于两axis笛卡尔积；四digest继续采用AP LP算法。
