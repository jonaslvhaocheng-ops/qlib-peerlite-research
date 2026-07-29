# M6.5 Bounded Component Design V6

- 状态：`DESIGN_ONLY`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_5_bounded_component_design_v5.md`
- 范围不变：T-known state、append-only ledger、static M6 archive。
- 不授权任何test、implementation、replay、fit、PIT、real data、budget或final OOS。

## 1. T-close state

唯一clock是交易日`T 15:00 Asia/Shanghai`。输入只来自M3 PIT sealed且date_max<2025；禁止labels、
execution state、current universe、2025+。raw fields：

```text
datetime,instrument,field,value,revision_id,source_available_time,source_row_sha256
```

available time必须aware且precision不细于microsecond（nonzero nanosecond remainder直接FAIL），先转
Asia/Shanghai canonical microsecond string，再做`<=T close`和latest选择。equal-time多行只允许
完整canonical bytes identical，否则FAIL。coverage row固定六字段NFC/time/SHA编码，每field
`uint64-be len||utf8`、每row再length-prefix，tuple排序SHA。

final key唯一，columns固定五个T-known status boolean加
`ret_mean_20,ret_std_20,ret_1d,turnover_mean_20`；禁止label/execution/halt/limit/crossover/
price-domain/feature-eligible。unknown、duplicate、extra、nonfinite FAIL。

## 2. Exact reducer and manifest

instrument NFC UTF-8排序；numeric binary64；所有±0规范+0。mean stable left-fold，median numeric
sort/even left+right/2；每操作binary64舍入并finite check，禁止vectorized/pairwise/float32。
population digest使用length-prefixed instrument；state digest绑定date/count/key digest及四值
big-endian bits。dates naive normalized ascending unique，只exact-date broadcast。

`MarketStateSourceManifestV2` exact绑定contract/calendar/PIT/sources/schema/revision selection/builder/
output/date range/OOS/content SHA。poison覆盖future revision、equal-time conflict和current universe。
任何M7 event/fit前必须绑定state product、source manifest、PIT parent、calendar、builder script和
library的exact hashes，缺失即0 event/fit。

## 3. Exact budget and event schemas

唯一budget authority是
`contracts/changes/m7_initial_screen_budget_binding_v2.json`，content SHA
`5fb21bae3c9cf14312bbc7d4605df55642fc4873d4ce5eb0e01826aec044a626`。它冻结M6
14328-byte 6/44、ceiling8/60、family、两model、seed7、evaluation IDs/purposes以及16个
fit ID/fold/purpose；仍非execution authority。

RunIntent V2、journal event V3、retained event V3都byte-identical携带budget和state bindings。
canonical JSON=UTF-8/NFC/sort_keys/compact/no-NaN/no-duplicate；source ID=`run:seq6`。每event逐字段
匹配authority roster；unlisted/duplicate/extra/replacement在write前FAIL，start即计预算。

## 4. Lock and fixed control root

lock=`<ledger>.reconcile.lock`，owner/mode0600/regular/nlink1，永不replace/unlink；ledger directory
owner exact且无group/other write。FD/path dev+inode在acquire、validation、temp fsync后紧邻replace
前、replace后、receipt前、release前验证。precommit drift保持ledger/receipt不变。flock覆盖全部
read/commit/snapshot/receipt。威胁边界为trusted same-UID/cooperative reconcilers。

control root固定：

```text
<ledger parent>/.trial_reconciliation/{snapshots,receipts}
```

三目录预存在、owner exact、mode0700、real且在ledger parent内。

## 5. ReconciliationSnapshotV3 and rebase

在锁内验证当前ledger及journal snapshot。snapshot slot现在**同时绑定ledger before**：

```text
snapshot_slot = SHA256(canonical JSON {
  run_intent_sha256,
  journal_snapshot_sha256,
  ledger_before_sha256
})
snapshot_path =
  <control root>/snapshots/reconciliation_snapshot_<snapshot_slot>.json
```

V3 exact fields：

```text
schema_version,status,snapshot_slot_sha256,
run_intent_sha256,journal_path,journal_snapshot_sha256,journal_snapshot_bytes,
event_count,source_event_ids,source_event_ids_sha256,
ledger_before_sha256,ledger_before_bytes,
candidate_evaluations_before,model_fits_before,
missing_source_event_ids,missing_source_event_ids_sha256,content_sha256
```

lists按journal contiguous order并使用length-prefix digest。snapshot atomic no-replace+fsync；same slot
different bytes FAIL。

每次调用先枚举snapshots目录中全部regular JSON files，只接受filename/content/hash/schema exact。
过滤同`run_intent_sha256+journal_snapshot_sha256`的valid snapshots并按
`ledger_before_bytes,ledger_before_sha256`排序。严格状态机：

1. 若其中恰有一个valid receipt且其commit prefix仍为current ledger byte prefix，返回该receipt
   NO_OP；多于一个receipt FAIL；
2. 若无receipt，恰有一个snapshot的missing set在其ledger-before之后连续exact commit，则恢复该
   snapshot；多个recoverable FAIL；
3. 若均未commit：current ledger必须是每个旧snapshot ledger-before的合法extension，且这些旧
   snapshots的missing source IDs在current ledger中**一个都未出现**。此时以current ledger
   SHA/bytes/counts为new before生成新slot/new immutable snapshot；旧snapshots不改；
4. 任一old missing ID出现但集合不完整/不连续/exact hash冲突时FAIL，不允许rebase掩盖partial
   commit。

因此“snapshot发布→replace前crash→另一journal合法append→原journal重试”会走3，用advanced
ledger创建新slot；不会永久阻塞，也不会改旧snapshot。同journal自身追加event会因journal SHA
变化自然进入另一slot family。

## 6. Atomic commit and receipt

对selected/new snapshot：

- current ledger exact等于snapshot before时，append its missing retained lines via full-file temp/
  fsync/precommit lock check/atomic replace/dir fsync/readback；
- current ledger已含其missing set时，只允许状态机2 recovery；
- prefix/roster/limit/source conflicts均FAIL。

求覆盖snapshot全部source IDs的minimal committed prefix及after counts。receipt：

```text
receipt_slot = SHA256(canonical JSON {
  snapshot_slot_sha256,
  committed_ledger_prefix_sha256
})
receipt_path =
  <control root>/receipts/reconciliation_receipt_<receipt_slot>.json
```

`TrialLedgerReconciliationReceiptV6` exact top-level：

```text
schema_version,status,recovery_mode,receipt_slot_sha256,
run_intent,reconciliation_snapshot,budget_limit_binding,
market_state_authority_binding,lock,ledger_commit,
ledger_observed_at_receipt,limits,committed_events,
candidate_evaluations_before,model_fits_before,
candidate_evaluations_after,model_fits_after,
all_snapshot_starts_reconciled,content_sha256
```

snapshot nested绑定path/file/content/slot/before/journal；committed events exact等于snapshot missing
set并附source/retained SHA；before取snapshot，after取minimal prefix。modes：
`APPENDED|LEDGER_ALREADY_COMMITTED|NO_OP`。existing receipt只验证并原bytes返回；later legal suffix
不重构。receipt atomic no-replace+fsync。

## 7. Static archive and imports

`static_m6_archive_binding_v2.json`唯一static authority，绑定gate/mechanics/run/verification/journal/
execution spec、9324-byte4/29、14328-byte6/44及archive/tree/internal manifest。static verifier只
hash/set/prefix，不import/load。legal suffix允许。

`data.market_state`仅schema/NumPy/Pandas；governance不importQlib/Torch/model；package root不隐式
load Torch/PeerLite；scripts不被library import。无production control plane。
