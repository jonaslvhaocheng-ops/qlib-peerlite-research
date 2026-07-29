# RunAuthorityGenerationV7

- 状态：`DESIGN_ONLY`
- Base：`run_authority_generation_v6.md`
- Base SHA：`fd3f6b5b53c6c3c5d4587626953ed6a0753579e457ab0280fb06b70256346ca2`
- 取代：V6。

## 1. Exact composition

V6 commit-time permanent budget、registry scans、dual qualification、activation和terminal partition
保留。V6 event identity、claim/outcome ledger fields及result binding由本文件完整替换。

每个LinearEventPlan内`source_event_id`必须UTF-8 byte唯一。event key改为：

```text
sha256(
  registration.canonical_sha256 ASCII || 0x1f
  || zero_padded_seq_8 ASCII || 0x1f
  || source_event_id UTF-8
).hexdigest()
```

重复source_event_id、seq或event_key在activation前拒绝。

## 2. Immutable run-ledger slots and head recurrence

每generation固定：

```text
runs/<g20>/ledger/entries/<transition_seq_8>.json
runs/<g20>/ledger/receipts/<transition_seq_8>.json
runs/<g20>/claims/<event_key>.json
runs/<g20>/results/<event_key>.json
runs/<g20>/outcomes/<event_key>.json
runs/<g20>/run-terminal.json
```

run-ledger genesis：

```text
H0 = sha256(
  LP(generation_commit.canonical_sha256 ASCII)
  || LP(registration.canonical_sha256 ASCII)
)
```

`RunLedgerEntryV1` exact：

```json
{
  "schema_version": "qlib_peerlite_run_ledger_entry_v1",
  "transition_seq": "<positive decimal>",
  "generation_commit": "<ArtifactRefV1>",
  "previous_transition_receipt": "<ArtifactRefV1 or null>",
  "previous_head": "sha256:<64hex>",
  "event_seq": "<positive decimal>",
  "event_key": "<64hex>",
  "phase": "STARTED|OUTCOME",
  "claim": "<ArtifactRefV1>",
  "outcome": "<ArtifactRefV1 or null>",
  "canonical_sha256": "sha256:<64hex>"
}
```

STARTED的outcome=null；OUTCOME必须nonnull。`RunLedgerTransitionReceiptV1` exact：

```json
{
  "schema_version": "qlib_peerlite_run_ledger_transition_receipt_v1",
  "transition_seq": "<positive decimal>",
  "entry": "<ArtifactRefV1>",
  "previous_transition_receipt": "<ArtifactRefV1 or null>",
  "previous_head": "sha256:<64hex>",
  "new_head": "sha256:<64hex>",
  "directory_fsync_complete": true,
  "canonical_sha256": "sha256:<64hex>"
}
```

```text
new_head = sha256(
  bytes.fromhex(previous_head without prefix)
  || LP(bytes.fromhex(entry.canonical_sha256 without prefix))
)
```

第一entry previous receipt=null、previous head=H0；之后previous receipt指exact前一receipt，
previous head=前一new head。entry/receipt按seq连续、no-replace/fsync，任何gap/fork/duplicate HOLD。

## 3. Claim, STARTED-before-execution, result and outcome

`EventClaimV2`采用V6 claim字段但删除`ledger_head_before`。claim no-replace durable后，必须append
exact STARTED entry并发布transition receipt；只有STARTED receipt durable且全链valid，worker才可
执行observer/fit。claim存在但STARTED缺失证明未获执行许可；recovery只补STARTED或在外部取消，
不能假定已执行。

`AuthorizedEventResultV1` exact：

```json
{
  "schema_version": "qlib_peerlite_authorized_event_result_v1",
  "generation_commit": "<ArtifactRefV1>",
  "claim": "<ArtifactRefV1>",
  "event_key": "<64hex>",
  "result_kind": "SYNTHETIC_OBSERVATION|CANDIDATE_SCORE|MODEL_FIT|DETERMINISTIC_REFIT",
  "payload": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

result的generation/claim/event/type必须与plan和claim exact equality；foreign result拒绝。

`EventOutcomeV2`采用V6 outcome字段但删除`ledger_head_after`；COMPLETED result必须是上述wrapper，
其他status result=null。outcome durable后append OUTCOME entry/receipt；同event的STARTED必须是
其直接或经已完成前event transitions的合法前序。下一event claim只在前event OUTCOME receipt
durable且status COMPLETED后允许。

claim+STARTED后worker lease丢失且无outcome时，reconciler发布CLAIMED_INTERRUPTED outcome及其
OUTCOME transition，永不重执行。

## 4. Terminal equality

RunTerminalV3以V6 V2为base，删除自由`final_ledger_head`，新增：

```text
last_transition_receipt: ArtifactRefV1
run_ledger_head: sha256
run_ledger_transition_count: decimal
```

terminal全量扫描entries/receipts，重算H0及每步head，要求：

- 每个attempted event恰一STARTED和一OUTCOME，顺序正确；
- claim/result/outcome/event全部identity相等；
- no skipped STARTED、foreign result、out-of-order next claim；
- terminal last receipt exact为最后receipt，head exact为其new_head；
- terminal event partition digest按V6 preimage重算。

budget ledger仍唯一来自durable generation commits；run ledger证明执行次序与一次性，不释放或
改变commit-time caps。
