# RunAuthorityGenerationV11

- 状态：`DESIGN_ONLY`
- Base：`run_authority_generation_v10.md`
- Base SHA：`8a86443ea68582d84a69f5194b64a6d07ce7081f1f392e66b9905954b06371a8`
- 取代：V10。

## 1. Lease inventory digest and worker lock lifetime

`ExecutionLeaseInventoryV1.inode_digest`逐行使用：

```text
LP(canonical ASCII decimal event_seq) ||
LP(event_key ASCII) ||
LP(path UTF-8) ||
LP(canonical ASCII decimal device) ||
LP(canonical ASCII decimal inode) ||
LP(mode ASCII)
```

`LP(x)=len(x_bytes)的8-byte unsigned big-endian || x_bytes`。rows按数值
`event_seq`升序且唯一，逐行preimage直接concat后SHA-256。本文中的`event_seq`与inventory exact
field同名；不得使用`seq`别名。

worker取得precreated event lock的exclusive flock后，必须从发布lease grant之前开始，使用同一
open file description持续持锁，直至对应OUTCOME transition entry与receipt均durable fsync。lease、
claim、STARTED、任何inner artifact、wrapper、outcome与ledger publication入口都必须在锁内对该FD
重新`fstat`并逐项验证`path/device/inode/owner_token/generation/event`。任何close、exec继承变化、
lock loss或identity变化立即撤销全部OUTPUT FD并由supervisor终止worker；失锁worker无权发布任何
bytes。reconciler只有在成功取得同一lock并完成V9全链重扫后才能发布`CLAIMED_INTERRUPTED`。

## 2. Closed immutable reference types

通用`ArtifactRefV1`不得再用于event-local raw bytes或表格。以下三种exact ref不得混用：

```json
{
  "schema_version": "qlib_peerlite_canonical_json_ref_v1",
  "path": "<fixed event-local relative regular-file path>",
  "target_schema_version": "<one fixed schema ID>",
  "file_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

```json
{
  "schema_version": "qlib_peerlite_tabular_file_ref_v1",
  "path": "<fixed event-local relative regular-file path>",
  "format": "JSONL|PARQUET",
  "file_sha256": "sha256:<64hex>",
  "byte_count": "<positive canonical decimal>",
  "row_count": "<positive canonical decimal>",
  "schema_sha256": "sha256:<64hex>",
  "key_digest": "sha256:<64hex>",
  "value_digest": "sha256:<64hex>",
  "logical_digest": "sha256:<64hex>"
}
```

```json
{
  "schema_version": "qlib_peerlite_immutable_bytes_ref_v1",
  "path": "<fixed event-local relative regular-file path>",
  "media_type": "application/x-pytorch-checkpoint",
  "file_sha256": "sha256:<64hex>",
  "byte_count": "<positive canonical decimal>"
}
```

所有path均从已验证的`runs/<g20>/results/<event_key>` root FD以逐段no-follow方式解析；必须是
normalized nonempty relative path，禁止absolute、empty segment、`.`、`..`、反斜线、NUL、
symlink、hardlink alias、其他event root或跨device对象。ref的目标regular file只能有一个link。
目标path必须等于下文唯一slot，不接受调用方提供的替代path。

## 3. Exact event-local inner schemas and slots

### Synthetic observations

```text
manifest: observations.json
rows:     observations.rows.jsonl
manifest schema: qlib_peerlite_synthetic_observations_v2
```

manifest exact fields：

```text
schema_version,event_key,rows{TabularFileRefV1},canonical_sha256
```

rows ref path必须为`observations.rows.jsonl`；其ordered schema由冻结的synthetic schema registry
唯一决定，`schema/key/value/logical` digests独立重算。

### Candidate predictions

```text
manifest: predictions.json
rows:     predictions.parquet
manifest schema: qlib_peerlite_candidate_predictions_v2
```

manifest exact fields：

```text
schema_version,event_key,run_id,model_id,fold_id,seed,
rows{TabularFileRefV1},columns,canonical_sha256
```

`columns` exact等于
`["datetime","instrument","score","model_id","fold_id"]`；rows path必须为
`predictions.parquet`，format必须为`PARQUET`。row_count及四个logical digests由严格reader重算。

### Metrics

```text
path: metrics.json
schema: qlib_peerlite_event_metrics_v2
```

exact fields：

```text
schema_version,generation_commit,event_execution_lease,claim,event_key,
run_id,evaluation_id,model_id,fold_id,seed,metric_registry,rows,canonical_sha256
```

`metric_registry`是plan冻结的policy-fixed upstream `ArtifactRefV1`，是authority input而非payload
artifact；除共同的generation/lease/claim/plan authority refs外，所有payload refs仍必须event-local。
`rows`为按`(split,name)` ASCII排序唯一的nonempty array，每row exact为
`{"split":"TRAIN|VALID|TEST","name":"<registry member>","value_float64_hex":"<finite Python float.hex>"}`。
禁止free map、NaN、Inf、unknown metric、duplicate或extra ref。path只能是`metrics.json`。

### Checkpoint

```text
manifest: checkpoint.json
bytes:    checkpoint.bin
manifest schema: qlib_peerlite_event_checkpoint_v2
```

manifest exact fields：

```text
schema_version,generation_commit,event_execution_lease,claim,event_key,
run_id,evaluation_id,model_id,fold_id,seed,
checkpoint_bytes{ImmutableBytesRefV1},canonical_sha256
```

bytes path只能是`checkpoint.bin`，regular、single-link、immutable。checkpoint manifest不得
引用training/refit receipt；DAG只能是checkpoint bytes → checkpoint manifest → receipt。

### Training and refit receipts

固定slots分别为`training-receipt.json`和`refit-receipt.json`，schemas升级为
`qlib_peerlite_model_fit_receipt_v2`及
`qlib_peerlite_deterministic_refit_receipt_v2`。二者exact fields：

```text
schema_version,event_key,run_id,evaluation_id,model_id,fold_id,seed,
checkpoint{CanonicalJsonRefV1,target checkpoint v2},
metrics{CanonicalJsonRefV1,target metrics v2},canonical_sha256
```

## 4. Content-to-inner equality and publication

四种content schema IDs exact升级为：

```text
qlib_peerlite_synthetic_observation_result_content_v2
qlib_peerlite_candidate_score_result_content_v2
qlib_peerlite_model_fit_result_content_v2
qlib_peerlite_deterministic_refit_result_content_v2
```

四类共同exact fields按顺序为：

```text
schema_version,generation_commit,event_execution_lease,claim,event_key,
run_id,evaluation_id,model_id,fold_id,seed,<kind-specific fields>,canonical_sha256
```

kind-specific fields exact为：

```text
synthetic: observations{CanonicalJsonRefV1,target synthetic observations v2}
candidate: predictions{CanonicalJsonRefV1,target candidate predictions v2},checkpoint=null
fit: checkpoint{CanonicalJsonRefV1,target checkpoint v2},
     training_receipt{CanonicalJsonRefV1,target fit receipt v2},
     metrics{CanonicalJsonRefV1,target metrics v2}
refit: checkpoint{CanonicalJsonRefV1,target checkpoint v2},
       refit_receipt{CanonicalJsonRefV1,target refit receipt v2},
       metrics{CanonicalJsonRefV1,target metrics v2}
```

synthetic content中的observations ref必须等于`observations.json`的canonical ref；candidate
content中的predictions ref必须等于`predictions.json`的canonical ref；fit/refit content中的
checkpoint及metrics refs必须byte-for-byte等于对应receipt中的refs，receipt ref必须等于对应
固定receipt的canonical ref。所有重复identity字段与wrapper、lease、claim、plan exact相等。

publication拓扑固定为raw rows/bytes → manifests/metrics → training/refit receipt → content →
wrapper → OUTCOME。每一步均在同一worker event flock内完成no-replace、fsync和重新验证。任何
foreign path、schema substitution、content/receipt不等、unknown key、extra ref、cross-event ref
或lock loss均`HOLD`，不得发布wrapper或OUTCOME。
