# RunAuthorityGenerationV9

- 状态：`DESIGN_ONLY`
- Base：`run_authority_generation_v8.md`
- Base SHA：`c5772d9f298ac6a3833fc0206f06844cffb3a7d5aa9cedf38e02d0c13d5c888e`
- 取代：V8。

## 1. One-way execution lease and inventory

lease chain唯一为：

```text
precreated lock -> lease grant -> claim -> STARTED -> result/outcome
```

lease grant固定path：

```text
runs/<g20>/leases/<event_key>.json
```

`EventExecutionLeaseV2`从V8 V1删除`claim`，其余字段保留；owner_token在持flock后生成。它不引用
任何downstream object。claim及后续对象单向引用它。

`ExecutionLeaseInventoryV1` exact：

```json
{
  "schema_version": "qlib_peerlite_execution_lease_inventory_v1",
  "generation_number": "<positive decimal>",
  "linear_event_plan": "<ArtifactRefV1>",
  "rows": [
    {
      "event_seq": "<positive decimal>",
      "event_key": "<64hex>",
      "path": "<derived absolute lock path>",
      "device": "<decimal>",
      "inode": "<decimal>",
      "mode": "0440"
    }
  ],
  "row_count": "<positive decimal>",
  "inode_digest": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

rows按seq且与plan一一对应。digest preimage逐行
`seq||0x1f||event_key||0x1f||path||0x1f||device||0x1f||inode||0x0a`。
固定path=`runs/<g20>/execution-lease-inventory.json`。

`AuthorityGenerationCommitV7`的exact字段为V6 commit全部字段，并在
`linear_event_plan`之后唯一新增`execution_lease_inventory: ArtifactRefV1`；schema ID改为
`qlib_peerlite_authority_generation_commit_v7`，其他字段/排序/nullability不变。registry scanner
对next generation只额外允许proposed plan绑定的唯一inventory及其exact precreated lock paths；
其他future artifact HOLD。

## 2. Result content schemas

wrapper固定`runs/<g20>/results/<event_key>/payload.json`；content固定
`runs/<g20>/results/<event_key>/content.json`。

四类content共享exact identity fields：

```text
schema_version,generation_commit,event_execution_lease,claim,event_key,
run_id,evaluation_id,model_id,fold_id,seed,canonical_sha256
```

并各自唯一新增：

```text
SYNTHETIC_OBSERVATION: observations{ArtifactRef,row_count,schema_sha256}
CANDIDATE_SCORE: predictions{ArtifactRef,row_count,columns exact five},checkpoint=null
MODEL_FIT: checkpoint{ArtifactRef},training_receipt{ArtifactRef},metrics{ArtifactRef}
DETERMINISTIC_REFIT: checkpoint{ArtifactRef},refit_receipt{ArtifactRef},metrics{ArtifactRef}
```

schema IDs与V8四IDs一致。candidate五列exact
`datetime,instrument,score,model_id,fold_id`。fit/refit checkpoint object必须反向绑定
generation/event/run/model/fold/seed及其receipt；synthetic/candidate不允许checkpoint field之外
的fit artifact。unknown/free map拒绝。validator strict解析content并重算全部refs/identity后才
接受wrapper和COMPLETED outcome。

## 3. Reconciler lease-loss sequence

reconciler发布CLAIMED_INTERRUPTED的唯一顺序：

1. exclusive flock该event预created lock，持续持有至outcome ledger receipt fsync；
2. fstat identity，读取lease grant/claim/STARTED及全ledger chain；
3. 若outcome已存在只验证；若STARTED缺失则HOLD且不发布outcome；
4. STARTED存在、outcome缺失、original owner token不再持lock，发布
   CLAIMED_INTERRUPTED outcome；
5. append OUTCOME entry/receipt，fsync后释放lock。

worker/reconciler不能同时持lock；不同token或任一state变化时重新scan/HOLD。
