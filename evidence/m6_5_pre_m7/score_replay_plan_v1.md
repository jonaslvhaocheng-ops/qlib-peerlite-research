# ScoreReplayPlanV1

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Identity：`score_replay_identity_v1.md`
- Identity SHA：
  `ed803a7df33eb3286d28a70ecd051c11d00911f1a1535d895eac9b580843d79f`

fixed plan slot：

```text
replay-control/score-replay-plan-v1.json
```

exact schema：

```json
{
  "schema_version": "qlib_peerlite_score_replay_plan_v1",
  "identity_spec": "<ArtifactRefV1>",
  "m6_execution_spec": "<ArtifactRefV1>",
  "expected_models": [
    {"model_id":"PEERLITE_K16_MSE|PEERLITE_K32_MSE","merged_predictions":"<ArtifactRefV1>"}
  ],
  "pairs": [
    {
      "model_id": "<fixed>",
      "fold_id": "wf_2018|...|wf_2024",
      "expected_merged_predictions": "<ArtifactRefV1>",
      "expected_fold_receipt": "<ArtifactRefV1>",
      "expected_fold_content_sha256": "sha256:<64hex>",
      "checkpoint": "<ArtifactRefV1>",
      "replay_output_slot": "<unique relative path>"
    }
  ],
  "canonical_sha256": "sha256:<64hex>"
}
```

expected_models按model排序恰2行；pairs按model/fold排序恰14行并exact覆盖2×7。plan冻结前只绑定
inputs和未来unique output slots，不包含尚未生成output SHA。

每pair执行后的`ScoreReplayPairReceiptV1`固定
`replay-control/receipts/<model>/<fold>.json`，exact绑定plan、pair identity、output slot、
output ArtifactRef、row count、key/score/identity digests、0 fit、ledger before/after及
final_oos=false。十四receipt汇总到closed result；unknown/extra/replacement拒绝。
