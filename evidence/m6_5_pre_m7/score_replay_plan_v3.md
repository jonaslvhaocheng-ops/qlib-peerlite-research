# ScoreReplayPlanV3

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Base：`score_replay_plan_v2.md`
- Base SHA：`f2d4fb763e744f2569f1cdd7689e0c959fdf1ae899381586317de5a9bbc6e589`
- Identity：`score_replay_identity_v3.md`
- Identity SHA：`90c169d7ac4b7001fad2b3ffcc867ced240e2f8b77614adcf01fdee957f3c7bf`
- 取代：V2全部plan、manifest、transaction、execution及receipt schemas。

## 1. Current storage policy and roots

唯一policy target schema为`qlib_peerlite_runtime_storage_policy_v5`。V2/V3/V4或任一降级
substitution均strict FAIL。plan中的`runtime_storage_policy`、全部14 invocation、activation、
output transaction、execution receipt和pair receipt必须重复同一个V5 CanonicalJsonRef。

`replay_output_root` exact等于V5
`target_parents[replay_target_parent_index]`的path/device/inode。reservation、staging、lease pool
和全部target parents必须按Capacity V10/V11 pairwise non-nested/non-alias，且全部device exact等于
V5 `filesystem_device`。每次admission及publication前重新验证root FDs与policy。

## 2. Immutable raw input manifest and committed input transaction

`ImmutableFileManifestV2` exact：

```json
{
  "schema_version": "qlib_peerlite_immutable_file_manifest_v2",
  "input_root_index": "<canonical decimal>",
  "relative_path": "<normalized safe relative path>",
  "format": "MARKDOWN|PARQUET|PYTORCH_CHECKPOINT",
  "file_device": "<canonical decimal>",
  "file_inode": "<canonical decimal>",
  "file_nlink": "1",
  "file_sha256": "sha256:<64hex>",
  "byte_count": "<positive canonical decimal>",
  "row_count": "<positive canonical decimal or null>",
  "schema_sha256": "sha256:<64hex> or null",
  "key_digest": "sha256:<64hex> or null",
  "value_digest": "sha256:<64hex> or null",
  "logical_digest": "sha256:<64hex> or null",
  "canonical_sha256": "sha256:<64hex>"
}
```

`ReplayInputTransactionV1` fixed preexisting canonical JSON exact：

```json
{
  "schema_version": "qlib_peerlite_replay_input_transaction_v1",
  "status": "COMMITTED",
  "m6_execution_spec": "<CanonicalJsonRefV1>",
  "input_roots": [
    {"path":"<fixed absolute>","device":"<decimal>","inode":"<decimal>"}
  ],
  "canonical_inputs": ["<CanonicalJsonRefV1 with fixed target schema>"],
  "raw_input_manifests": ["<CanonicalJsonRefV1 target ImmutableFileManifestV2>"],
  "canonical_input_count": "<positive canonical decimal>",
  "raw_input_manifest_count": "<positive canonical decimal>",
  "source_coverage_digest": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

roots按path UTF-8排序唯一；canonical inputs按`(target_schema_version,path)`排序唯一，raw manifests
按`(input_root_index,relative_path)`排序唯一。二者合计exact覆盖该pair需要的identity spec、
merged predictions、fold receipt、checkpoint、M6 execution spec、frozen code/archive及
pre-final-OOS product inputs。coverage rows分别加ASCII type tag `JSON`或`RAW`后按
`(tag,path)`排序，对`LP(tag)||LP(ref canonical JSON bytes)`依序concatSHA-256。input transaction
与output transaction的schema、root和role必须不同，禁止alias。

执行时每个raw input从对应root FD逐段no-follow打开，fstat必须等于manifest
device/inode/nlink=1。hash、schema/logical验证与模型读取必须复用同一open file description或其
FD duplicate；不得在验证后按path reopen。execution receipt记录每个实际消费FD identity。

## 3. Exact plan and deterministic reservation invocation

plan固定`replay-control/score-replay-plan-v3.json`，exact fields：

```text
schema_version,identity_spec,m6_execution_spec,runtime_storage_policy,
replay_target_parent_index,replay_output_root,replay_supervisor_lock,
expected_models,pairs,canonical_sha256
```

`replay_supervisor_lock` exact为预创建regular 0440
`{"path":"replay-control/replay-supervisor.lock","device":"<decimal>","inode":"<decimal>"}`，位于
output/input/ledger/OOS roots之外。schema ID为`qlib_peerlite_score_replay_plan_v3`。V2的2
expected_models、14 sorted unique pairs、model/fold equality及所有fixed source hashes继续保留。
每pair exact fields：

```text
model_id,fold_id,expected_merged_predictions,expected_fold_receipt,
expected_fold_content_sha256,checkpoint,input_transaction,runtime_storage_policy,
target_parent_index,target_name,raw_output_relative_path,output_manifest_relative_path,
reservation_invocation_slot,execution_receipt_slot,pair_receipt_slot
```

其中：

- input refs只能是对应target schema的CanonicalJsonRef；
- `target_parent_index`逐项等于plan index，`target_name`为
  `score-replay-<model_id>-<fold_id>`且14个byte unique；
- raw path exact `predictions.parquet`，manifest path exact `output-manifest.json`；
- invocation slot exact
  `replay-control/invocations/<model_id>/<fold_id>.json`；
- execution receipt slot exact
  `replay-control/executions/<model_id>/<fold_id>.json`；
- pair receipt slot exact
  `replay-control/receipts/<model_id>/<fold_id>.json`。

所有control和payload paths使用V2 safe segment/root-FD grammar且不得alias。

`ScoreReplayReservationInvocationV1`在执行前由冻结plan唯一导出，fixed invocation slot，exact：

```text
schema_version,plan,pair_index,model_id,fold_id,input_transaction,
runtime_storage_policy,target_parent_index,target_name,
source_inventory,expected_logical_bytes,expected_regular_file_count,
expected_directory_count,expected_entry_count,canonical_sha256
```

schema ID exact `qlib_peerlite_score_replay_reservation_invocation_v1`；所有字段等于plan/policy/input
transaction及独立source inventory，unknown key拒绝。Capacity `attempt_id` exact为该invocation
最终完整file bytes SHA-256 hex；same slot different bytes、different attempt ID或existing different
invocation均HOLD且不得发布RESERVED。

## 4. Fixed output payload and sibling transaction formulas

每pair：

```text
target_parent   = runtime_policy.target_parents[target_parent_index]
target_root     = target_parent/target_name
raw_output      = target_root/"predictions.parquet"
output_manifest = target_root/"output-manifest.json"
publish_lock    = target_parent/("."+target_name+".publish.lock")
prepared        = target_parent/("."+target_name+".PREPARED.json")
publish_complete= target_parent/("."+target_name+".PUBLISH_COMPLETE.json")
committed       = target_parent/("."+target_name+".COMMITTED.json")
```

PUBLISH_COMPLETE明确是target-root sibling，不是payload内文件。payload logical inventory exact只有
两个regular files：raw parquet和manifest。manifest schema
`qlib_peerlite_score_replay_output_manifest_v1`，exact fields：

```text
schema_version,plan,pair_index,model_id,fold_id,
raw_relative_path,raw_file_device,raw_file_inode,raw_file_nlink,
raw_file_sha256,byte_count,row_count,schema_sha256,key_digest,value_digest,
logical_digest,canonical_sha256
```

manifest fixed relative slot `output-manifest.json`。supervisor从同一raw staging FD在最后write后重算
全部identity，再生成manifest；raw与manifest一起进入同一个Nested Recovery V4 payload和
PAYLOAD_LOGICAL/STAGING_PHYSICAL inventories。其他manifest path/bytes、extra payload、
partial/replacement transaction均HOLD。

`ReplayOutputTransactionV1`是PairReceipt中的exact nested object：

```text
invocation,reserved,prepared,publish_complete,committed,payload_inventory
```

每项为对应target schema的CanonicalJsonRef；全链按Capacity V11/Nested Recovery V4验证
COMMITTED，且重复同一invocation/policy/attempt/target/payload refs。

## 5. Exact execution receipt

`ScoreReplayExecutionReceiptV1` fixed execution slot，只有output transaction COMMITTED且worker
tree已reap后才能durable no-replace发布。exact fields：

```text
schema_version,plan,pair_index,model_id,fold_id,
launcher,code_closure,environment_lock,argv,
python_version,torch_version,cuda_runtime_version,cuda_driver_version,
selected_device,cuda_device_uuid,cuda_compute_capability,
checkpoint,input_transaction,consumed_input_fds,
supervisor_lease_identity,worker_tree_reaped,pipe_eof,
observed_model_calls,observed_call_digest,fit_call_count,predict_call_count,
output_transaction,output_manifest,
trial_ledger_before,trial_ledger_after,final_oos_accessed,exit_code,
canonical_sha256
```

schema ID exact `qlib_peerlite_score_replay_execution_receipt_v1`。约束：

- `ReplaySupervisorLeaseV1`固定
  `replay-control/replay-supervisor-lease.json`，exact fields为
  `schema_version,plan,lock_path,lock_device,lock_inode,owner_token,canonical_sha256`；无任何
  downstream ref。supervisor先flock plan声明的precreated lock、fstat exact后发布lease，并用同一
  open file description持续持锁到aggregate result或失败receipt durable且worker tree已reap；
- launcher/code/environment均为冻结target schema refs且与architecture v28 launcher hashes相等；
- argv exact等于冻结launcher argv；版本逐项等于冻结runtime；
- `selected_device="cuda:<canonical index>"`，device UUID/capability由trusted launcher从CUDA runtime
  读取并与冻结allowlist相等；CPU/fallback/unknown device FAIL；
- consumed_input_fds按role/path排序唯一，每row exact记录manifest ref、root device/inode、FD
  device/inode/nlink/open flags，并证明hash/validate/consume使用同一open file description；
- trusted launcher instrument model APIs；observed_model_calls为按调用顺序的exact rows
  `{"seq":"<decimal>","qualified_name":"<ASCII>","argument_digest":"sha256:<64hex>"}`；
  digest为逐row canonical bytes LP concat SHA-256；
- 任何`.fit`/training/backward/optimizer-step调用使receipt FAIL；
  `fit_call_count="0"`,`predict_call_count="1"`由trace独立重算；
- supervisor lease、worker reaped和pipe EOF按RunAuthority V12/M7 V20 receipt exact证明；archival
  replay使用独立`ReplaySupervisorLeaseV1`互斥对象，它只保护本次output/control slots，不是
  live RunAuthority、event lease或预算授权；
- output transaction/manifest exact等于§4；ledger refs byte-equal，
  `final_oos_accessed=false`,`exit_code="0"`。

## 6. Pair receipt and aggregate result

`ScoreReplayPairReceiptV3` fixed pair slot，exact fields：

```text
schema_version,plan,pair_index,model_id,fold_id,
expected_merged_predictions,expected_fold_receipt,expected_fold_content_sha256,checkpoint,
input_transaction,output_transaction,execution_receipt,output_manifest,
row_count,key_digest,score_digest,identity_digest,score_equality,
fit_count,trial_ledger_before,trial_ledger_after,final_oos_accessed,canonical_sha256
```

schema ID exact `qlib_peerlite_score_replay_pair_receipt_v3`。execution receipt、input/output transaction
和output manifest refs须逐byte等于对应对象；count/digests/equality独立重算；CUDA、zero-fit、
ledger unchanged及OOS false均从execution receipt复核，PairReceipt不得覆盖。

aggregate固定`replay-control/results/score-replay-result-v3.json`，schema
`qlib_peerlite_score_replay_aggregate_result_v3`，沿用V2 exact fields与LP coverage formula，但只
接受14个V3 pair receipt。必须exact覆盖plan pairs，无extra/unknown/replacement，才可PASS。

## 7. Crash recovery

V2 crash table保留并作以下收紧：

- invocation final存在时只能接受由plan确定的identical bytes；不同bytes/attempt HOLD；
- output COMMITTED前不发布execution receipt；
- COMMITTED后从fixed raw+manifest payload、input transaction及frozen launcher重建同一execution
  receipt；若无法证明原执行CUDA/no-fit/worker-reaped evidence则不能凭output自造receipt，只能
  HOLD；
- execution receipt后才可发布pair receipt；14 pair receipts后才可发布aggregate；
- 所有existing final identical才resume，different bytes永不覆盖。

本文不授权replay、fit、真实数据、PIT、budget mutation或final-OOS。
