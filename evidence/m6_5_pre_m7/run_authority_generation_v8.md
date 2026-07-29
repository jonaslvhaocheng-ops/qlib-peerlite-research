# RunAuthorityGenerationV8

- 状态：`DESIGN_ONLY`
- Base：`run_authority_generation_v7.md`
- Base SHA：`e41f6eaba2364bf6767c0d31684b6f3295081a36a3f2c5575bf2510d9022af6d`
- 取代：V7。

## 1. Event execution lease

每generation activation前固定创建并inventory：

```text
runs/<g20>/execution-leases/<event_seq_8>.lock
```

恰与plan events一一对应；regular 0440、same policy device、固定device/inode。generation commit
绑定`ExecutionLeaseInventoryV1` ArtifactRef，commit前验证全部slots存在且无人持锁。

`EventExecutionLeaseV1` exact：

```json
{
  "schema_version": "qlib_peerlite_event_execution_lease_v1",
  "generation_commit": "<ArtifactRefV1>",
  "event_seq": "<positive decimal>",
  "event_key": "<64hex>",
  "lease_path": "<derived absolute>",
  "lease_device": "<decimal>",
  "lease_inode": "<decimal>",
  "owner_token": "<128-bit lowercase hex>",
  "claim": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

worker必须先exclusive flock该precreated slot，以FD fstat验证identity，再no-replace发布lease object；
claim、STARTED entry/receipt、result、outcome全部重复其ArtifactRef。执行入口只接受持有同一open
FD lock且owner token相等的worker。第二worker无法取得flock，不能进入observer/fit。lock丢失且
STARTED已durable、outcome缺失时才发布CLAIMED_INTERRUPTED。

claim durable但STARTED缺失时删除“external cancel”分支：recovery只能由持同一event lease者补
STARTED；无法证明合法lease时generation HOLD，不能终结、重试或执行。

## 2. Typed result payloads

event type→result kind唯一映射：

```text
SYNTHETIC_OBSERVER -> SYNTHETIC_OBSERVATION
CANDIDATE          -> CANDIDATE_SCORE
FIT                -> MODEL_FIT
DETERMINISTIC_REFIT-> DETERMINISTIC_REFIT
```

固定payload path：

```text
runs/<g20>/results/<event_key>/payload.json
```

payload wrapper exact fields：

```text
schema_version (kind-specific ID),
generation_commit,claim,event_execution_lease,event_key,
run_id,evaluation_id,model_id,fold_id,seed,
checkpoint{ArtifactRef|null},content{ArtifactRef},canonical_sha256
```

schema IDs：

```text
qlib_peerlite_synthetic_observation_result_v1
qlib_peerlite_candidate_score_result_v1
qlib_peerlite_model_fit_result_v1
qlib_peerlite_deterministic_refit_result_v1
```

synthetic/candidate checkpoint=null；fit/refit checkpoint nonnull。所有identity与plan/claim exact；
path必须是derived slot；content/checkpoint roles不得指claim/outcome/terminal或其他event。wrapper
与content file/canonical hashes全量重算后才能发布COMPLETED outcome。

## 3. Ledger equality refinements

EventClaimV3、STARTED entry、AuthorizedEventResultV2、EventOutcomeV3均新增
`event_execution_lease: ArtifactRefV1`且exact相等。RunTerminalV4逐event绑定lease ref，并验证：

- 每个attempted event恰一lease object、claim、STARTED、outcome transition；
- lease path/device/inode与activation inventory及event seq相等；
- result kind/schema/path/identity按§2唯一；
- 双workerrace最多一个lease object与一次execution-entry receipt。

run-ledger head/budget语义继续采用V7/V6。
