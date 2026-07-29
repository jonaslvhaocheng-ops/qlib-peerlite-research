# ScoreReplayIdentityV2

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Base：`score_replay_identity_v1.md`
- Base SHA：`ed803a7df33eb3286d28a70ecd051c11d00911f1a1535d895eac9b580843d79f`
- 取代：V1中“执行前绑定replay output file SHA”的冲突表述。

## 1. Pre-execution and post-execution identities

V1的M6 spec/content SHA、两个model-level merged files、949014 row counts、五列顺序、七个fold
window、datetime/instrument/score canonicalization、14 pair集合及key/score/identity比较规则全部
保留。

执行前immutable plan对每pair只绑定：

```text
model_id,fold_id,
expected merged predictions immutable-file manifest ref,
expected fold receipt canonical-JSON ref,
expected fold content SHA,
checkpoint immutable-file manifest ref,
safe replay output relative slot
```

执行前不得声明尚未产生的replay output file SHA、logical digest或receipt SHA。每pair的
`expected_merged_predictions`必须byte-for-byte等于对应`expected_models[model_id]`中的ref。

执行后身份仅进入该pair的`ScoreReplayPairReceiptV2`：

```text
output immutable-file manifest ref,
row_count,key_digest,score_digest,identity_digest,
exact score equality verdict,
input/output transaction refs,
zero_fit proof,ledger before/after refs,final_oos=false
```

AggregateResultV2只引用14个已durable pair receipts，并以精确coverage digest证明pair集合与plan
一致；不得把运行后SHA反写或替换冻结plan。

## 2. Reference classes

Replay中只允许：

1. `CanonicalJsonRefV1`：path、target schema ID、file SHA、canonical SHA；
2. `ImmutableFileManifestRefV1`：指向exact canonical JSON manifest，该manifest固定raw file path、
   format、file SHA、byte count、row count、schema/key/value/logical digests；
3. `ReplayOutputSlotV1`：执行前安全relative path，不含任何file SHA。

三者不得混用。Markdown identity spec只通过`ImmutableFileManifestRefV1`包装其raw file bytes，
M6 execution spec JSON使用`CanonicalJsonRefV1`，Parquet/checkpoint使用各自
`ImmutableFileManifestRefV1`。每个plan字段只接受唯一ref class和唯一target schema。

## 3. Boundary

本规范解决identity/plan时间顺序；不授权replay。V1的`0 fit`、trial ledger bytes/head unchanged、
CUDA-only、transactions COMMITTED及`final_oos=false`条件继续强制。
