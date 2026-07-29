# ScoreReplayPlanV2

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Base：`score_replay_plan_v1.md`
- Base SHA：`96949101947b63b6d57d3ba963d7b7e95acc5513313eea5384f5b4418e43e145`
- Identity：`score_replay_identity_v2.md`
- Identity SHA：`135344637dd0694526f657996a2ebd957f9a93951ad528c088d1401faef3e3c6`
- 取代：V1。

## 1. Reference schemas

`CanonicalJsonRefV1` exact：

```json
{
  "schema_version": "qlib_peerlite_canonical_json_ref_v1",
  "path": "<fixed relative regular-file path>",
  "target_schema_version": "<one fixed schema ID>",
  "file_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

`ImmutableFileManifestRefV1`使用同一exact ref外形，但
`target_schema_version=qlib_peerlite_immutable_file_manifest_v1`；其目标manifest exact：

```json
{
  "schema_version": "qlib_peerlite_immutable_file_manifest_v1",
  "path": "<fixed raw regular-file path>",
  "format": "MARKDOWN|PARQUET|PYTORCH_CHECKPOINT",
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

MARKDOWN和PYTORCH_CHECKPOINT的五个tabular fields必须全部null；PARQUET必须全部nonnull。manifest
ref和raw file都要重算，target schema不得替换。identity spec必须为MARKDOWN manifest ref；M6
execution spec必须为其固定schema的CanonicalJsonRef；merged predictions与checkpoint必须分别为
PARQUET与PYTORCH_CHECKPOINT manifest ref。

## 2. Fixed roots, slots and path grammar

plan固定slot：

```text
replay-control/score-replay-plan-v2.json
```

result固定slot：

```text
replay-control/results/score-replay-result-v2.json
```

plan绑定`replay_output_root`的absolute path、device、inode及
`RuntimeStoragePolicyV2` CanonicalJsonRef。output root与所有input roots、trial-ledger root、
contract roots、PIT roots和final-OOS root必须path/ancestor/device-inode role-disjoint，且不得位于
其中任何root内。

`ReplayOutputSlotV1` exact是normalized nonempty relative UTF-8 path，segment只允许
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`，显式拒绝`.`、`..`、absolute、empty segment、反斜线、
NUL/control、trailing separator和Unicode normalization drift。slot只能由output root FD逐段
`openat2(RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS|RESOLVE_NO_XDEV)`或等价no-follow resolver派生；
所有ancestor及target重验device/inode，禁止symlink、hardlink alias及跨device。14个slot byte
unique，且不得与control/receipt/temp/transaction slot alias。

## 3. Exact plan schema

```json
{
  "schema_version": "qlib_peerlite_score_replay_plan_v2",
  "identity_spec": "<ImmutableFileManifestRefV1: MARKDOWN>",
  "m6_execution_spec": "<CanonicalJsonRefV1: fixed M6 schema>",
  "runtime_storage_policy": "<CanonicalJsonRefV1: qlib_peerlite_runtime_storage_policy_v2>",
  "replay_output_root": {
    "path": "<fixed absolute>",
    "device": "<canonical decimal>",
    "inode": "<canonical decimal>"
  },
  "expected_models": [
    {
      "model_id": "PEERLITE_K16_MSE|PEERLITE_K32_MSE",
      "merged_predictions": "<ImmutableFileManifestRefV1: PARQUET>"
    }
  ],
  "pairs": [
    {
      "model_id": "<fixed>",
      "fold_id": "wf_2018|...|wf_2024",
      "expected_merged_predictions": "<same ref as expected_models row>",
      "expected_fold_receipt": "<CanonicalJsonRefV1: fixed M6 fold receipt schema>",
      "expected_fold_content_sha256": "sha256:<64hex>",
      "checkpoint": "<ImmutableFileManifestRefV1: PYTORCH_CHECKPOINT>",
      "replay_output_slot": "<ReplayOutputSlotV1>",
      "reservation_invocation_slot": "<fixed pair-local relative JSON slot>",
      "prepared_slot": "<derived sibling PREPARED relative slot>",
      "publish_complete_slot": "<derived payload completion relative slot>",
      "committed_slot": "<derived sibling COMMITTED relative slot>",
      "pair_receipt_slot": "replay-control/receipts/<model_id>/<fold_id>.json"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

exact field order如上；unknown/duplicate key拒绝。expected_models按model ASCII排序恰2行；pairs按
`(model_id,fold_id)`排序恰14行并exact覆盖2×7。每pair merged ref必须byte-for-byte等于对应
expected_models ref。所有transaction slots由Capacity V11/Nested Recovery V4公式从pair identity
和固定output root推导，byte unique且不得由调用方替换。plan只绑定未来slots，不含未来artifact
SHA。

## 4. Exact pair receipt

`ScoreReplayPairReceiptV2`固定在plan声明的pair receipt slot，exact fields：

```text
schema_version,plan,pair_index,model_id,fold_id,
expected_merged_predictions,expected_fold_receipt,expected_fold_content_sha256,checkpoint,
replay_output_slot,output_manifest,
reservation,prepared,publish_complete,committed,
row_count,key_digest,score_digest,identity_digest,score_equality,
fit_count,trial_ledger_before,trial_ledger_after,final_oos_accessed,
canonical_sha256
```

约束：

- schema ID exact `qlib_peerlite_score_replay_pair_receipt_v2`；
- `pair_index`为plan排序后的0..13 canonical decimal；
- all repeated inputs/slot逐byte等于plan pair；
- `output_manifest`是PARQUET `ImmutableFileManifestRefV1`且raw path exact等于output slot；
- reservation/PREPARED/PUBLISH_COMPLETE/COMMITTED均为对应closed CanonicalJsonRef，按Capacity
  V11与Nested Recovery V4全链验证并全部COMMITTED；
- 四个count/digests与output manifest及V2 replay equality独立重算相等；
- `score_equality="EXACT"`,`fit_count="0"`,
  `trial_ledger_before == trial_ledger_after`,`final_oos_accessed=false`；
- unknown ref、extra output、replacement、partial transaction或non-CUDA execution均FAIL。

pair receipt canonical SHA按排除自身`canonical_sha256`后的canonical JSON SHA；只能在output
transaction COMMITTED后no-replace durable发布。

## 5. Exact aggregate result and coverage digest

`ScoreReplayAggregateResultV2`固定result slot，exact fields：

```text
schema_version,plan,pair_receipts,pair_count,pair_coverage_digest,
fit_count,trial_ledger_before,trial_ledger_after,final_oos_accessed,
verdict,canonical_sha256
```

schema ID exact `qlib_peerlite_score_replay_aggregate_result_v2`。pair_receipts是14个
CanonicalJsonRef，按pair index排序唯一。对每个receipt row构造：

```text
LP(canonical ASCII decimal pair_index) ||
LP(model_id ASCII) ||
LP(fold_id ASCII) ||
LP(receipt path UTF-8) ||
LP(receipt file SHA ASCII) ||
LP(receipt canonical SHA ASCII)
```

依序concat后SHA-256得到`pair_coverage_digest`。必须exact覆盖plan 14 pairs，无missing、extra、
duplicate、unknown output或replacement；`pair_count="14"`,`fit_count="0"`，所有pair的ledger
before/after均等于aggregate对应refs，`final_oos_accessed=false`,`verdict="PASS"`。全部验证后才
能no-replace durable发布aggregate result。

## 6. Crash and recovery table

| Crash point | Recovery |
|---|---|
| reservation前 | no output/no receipt；safe retry same plan |
| RESERVED后、PREPARED前 | Capacity V11 owner abort/cleanup；无pair receipt |
| PREPARED后、output publish前 | Nested Recovery V4唯一恢复；禁止abort/replacement |
| output publish后、COMMITTED前 | 验证payload inventory后完成同一transaction；无pair receipt |
| COMMITTED后、pair receipt前 | 从immutable plan+transaction+output重建identical receipt；different bytes HOLD |
| pair receipt后、aggregate前 | 验证全部14 receipts；缺少项不发布aggregate |
| aggregate temp/final冲突 | identical resume；different bytes HOLD |

任何阶段都禁止删除或覆盖已发布final。scanner发现plan外output、receipt、transaction或temp立即
HOLD。本文不授权执行replay、fit、真实数据、PIT、budget mutation或final-OOS。
