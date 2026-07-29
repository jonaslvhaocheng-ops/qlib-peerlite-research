# RunAuthorityGenerationV10

- 状态：`DESIGN_ONLY`
- Base：`run_authority_generation_v9.md`
- Base SHA：`265962b0972dd3c38221b80e540f9ca28c3b454c68262fb3068d7a5d504cab2d`
- 取代：V9。

## 1. Lease schemas and digest

`EventExecutionLeaseV2.schema_version` exact
`qlib_peerlite_event_execution_lease_v2`；exact字段顺序为：

```text
schema_version,generation_commit,event_seq,event_key,lease_path,lease_device,
lease_inode,owner_token,canonical_sha256
```

不含claim/downstream ref。ExecutionLeaseInventory digest每字段全部LP：

```text
LP(seq)||LP(event_key)||LP(path)||LP(device)||LP(inode)||LP(mode)
```

逐seq concat后SHA256；无裸delimiter。

## 2. Distinct wrapper and content IDs

wrapper统一schema ID：

```text
qlib_peerlite_authorized_event_result_wrapper_v2
```

wrapper exact fields：

```text
schema_version,result_kind,generation_commit,event_execution_lease,claim,event_key,
run_id,evaluation_id,model_id,fold_id,seed,content,canonical_sha256
```

content IDs独立：

```text
qlib_peerlite_synthetic_observation_result_content_v1
qlib_peerlite_candidate_score_result_content_v1
qlib_peerlite_model_fit_result_content_v1
qlib_peerlite_deterministic_refit_result_content_v1
```

content fixed path仍为`runs/<g20>/results/<event_key>/content.json`。四类common identity fields与
wrapper/plan exact equality。

inner fixed slots及schemas：

```text
synthetic: runs/<g20>/results/<event_key>/observations.json
  schema qlib_peerlite_synthetic_observations_v1
  exact fields schema_version,event_key,rows{ArtifactRef,row_count,schema_sha256},canonical_sha256

candidate: runs/<g20>/results/<event_key>/predictions.json
  schema qlib_peerlite_candidate_predictions_v1
  exact fields schema_version,event_key,run_id,model_id,fold_id,seed,
  rows{ArtifactRef,row_count,columns=["datetime","instrument","score","model_id","fold_id"]},
  canonical_sha256

fit: runs/<g20>/results/<event_key>/training-receipt.json
  schema qlib_peerlite_model_fit_receipt_v1
  exact fields schema_version,event_key,run_id,model_id,fold_id,seed,checkpoint{ArtifactRef},
  metrics{ArtifactRef},canonical_sha256

refit: runs/<g20>/results/<event_key>/refit-receipt.json
  schema qlib_peerlite_deterministic_refit_receipt_v1
  exact fields schema_version,event_key,run_id,model_id,fold_id,seed,checkpoint{ArtifactRef},
  metrics{ArtifactRef},canonical_sha256
```

checkpoint object本身schema `qlib_peerlite_event_checkpoint_v1`，固定
`runs/<g20>/results/<event_key>/checkpoint.json`，exact重复generation/event/run/model/fold/seed并
绑定checkpoint bytes ArtifactRef。metrics schema固定`qlib_peerlite_event_metrics_v1`且重复同一
identity。所有inner objects禁止outcome/terminal/其他event refs；full parse+role DAG后才能wrapper。
