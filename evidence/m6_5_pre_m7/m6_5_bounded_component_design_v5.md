# M6.5 Bounded Component Design V5

- 状态：`DESIGN_ONLY`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_5_bounded_component_design_v4.md`
- 只含：T-known state、append-only ledger、static M6 archive。
- 不授权：test、implementation、PIT rerun、real data、replay、fit、budget mutation、final OOS。

## 1. T-close state source

唯一时钟是A股交易日`T 15:00 Asia/Shanghai`。只读M3 PIT sealed、`date_max<2025-01-01` artifacts；
禁止supervised matrix、label、execution/halt/limit/crossover、current universe、2025+。builder固定
`scripts/server/build_market_state_product.py`，只调用`data.market_state`纯函数。

raw logical fields：

```text
datetime,instrument,field,value,revision_id,source_available_time,source_row_sha256
```

`source_available_time`必须timezone-aware；底层值精度不得细于1 microsecond（pandas Timestamp要求
`nanosecond==0`），否则在eligibility/max比较前FAIL。然后转Asia/Shanghai，规范为
`YYYY-MM-DDTHH:MM:SS.ffffff+08:00`。每`(instrument,field,T)`筛
`available<=T close`并取最大时间；最大时间多行只允许完整canonical source-row bytes identical
dedup，value/revision/hash冲突FAIL。mtime/ingestion/order不能破局。

文本NFC UTF-8；date=`YYYY-MM-DD`；revision/field非空；SHA lowercase64hex。selection coverage每row
依次编码`date,instrument,field,available_time,revision_id,source_sha`，每field为
`uint64-be len||utf8`，row再为`uint64-be len||row`；按六字段UTF-8 tuple排序后SHA。manifest记录
eligible/rejected/dedup/conflict counts，conflict=0。

final `(datetime,instrument)` unique columns：

```text
universe_member,listing_age_eligible,is_active,
special_status_forbidden,special_status_unknown,
ret_mean_20,ret_std_20,ret_1d,turnover_mean_20
```

禁止`tradable,price_domain_valid,feature_eligible,corporate_action_crossover`及execution/label/
purge/split。population predicate为前三true、两个special false、四numeric finite。unknown/missing
bool、duplicate、extra、nonfinite均FAIL，不fill。

## 2. Bit-exact reducer

instrument NFC/nonempty/unique，按UTF-8 bytes排序。numeric转IEEE binary64；所有zero含`-0`规范
为`+0`。mean固定stable left fold，每add/div立即binary64舍入、finite check、zero normalize；
禁止vectorized/pairwise/float32/extended precision。median numeric ascending，zero已canonical；
even为`binary64(binary64(left+right)/2.0)`，每步finite check。任何中间NaN/Inf FAIL。

```text
trend=mean(ret_mean_20); vol=median(ret_std_20)
breadth=mean(binary64(ret_1d>0)); turnover=median(turnover_mean_20)
```

population digest连接每instrument的`uint64-be len||utf8`。state digest为date ASCII+NUL、count
uint64-be、key digest raw32、四值binary64 big-endian。daily输出四值、count、key digest、state
digest；date naive normalized ascending unique，只exact-date broadcast。

## 3. Source manifest and state authority

`MarketStateSourceManifestV2` exact：

```text
schema_version,status,prediction_clock,contract,calendar,pit_parent,
source_artifacts,input_schema,revision_selection,builder,output,
date_min,date_max,final_oos_accessed,content_sha256
```

refs为path/file/content SHA；revision selection记录fixed rule、coverage digest和counts；builder绑定
script/library；output绑定path/file/key/value digests；date_max<2025，OOS=false。poison覆盖future
row/revision、equal-time conflict、current-universe replacement，through-T bytes不变或FAIL。

首journal/fit前，future contract/RunIntent/events/checkpoint/receipt必须byte-identical绑定：

```text
MarketStateAuthorityBindingV1={
 state_product{path,file_sha256,key_digest,value_digest},
 source_manifest{path,file_sha256,content_sha256},
 pit_parent{path,file_sha256,content_sha256},
 calendar{path,file_sha256,content_sha256},
 builder_script{path,file_sha256},builder_library{path,file_sha256}
}
```

缺失/hash drift=0 event/fit。

## 4. Exact external budget roster and records

canonical JSON为UTF-8/NFC/sort_keys/compact/no-NaN/no-duplicate。ID grammar
`[A-Za-z0-9][A-Za-z0-9:._-]{0,255}`。唯一budget authority：

```text
contracts/changes/m7_initial_screen_budget_binding_v2.json
content_sha256=5fb21bae3c9cf14312bbc7d4605df55642fc4873d4ce5eb0e01826aec044a626
```

`BudgetLimitBindingV2` exact含path/file/content SHA、M6 prefix/bytes/6/44、ceiling8/60。external
仍design-only。其candidate rows权威冻结：

```text
family_id,model_id,seed,evaluation_id,evaluation_purpose,
fits[{fit_id,fold_id,purpose}]
```

`RunIntentV2`含schema/run/family/execution spec、budget binding、state binding、content SHA。
journal candidate exact含run/seq/source ID/intention SHA/event/timestamp/family/spec、两bindings、
evaluation/model/seed/flags/purpose/event SHA；fit再含fit/fold。retained V3再含source path/seq/hash、
outcome和retained SHA。event只candidate-start或fit-start；source ID=`run:seq6`。

每event必须逐字段匹配budget V2：candidate的evaluation ID/purpose，fit的ID/fold/purpose，model、
seed、family及flags。unlisted/duplicate/extra/replacement在write前FAIL；start失败/中断仍计预算。

## 5. Stable lock and deterministic snapshot slots

lock固定`<ledger>.reconcile.lock`，regular/nlink1/0600/owner exact，永不replace/unlink；directory owner
exact且无group/other write。FD/path dev+inode在acquire、journal validate后、temp fsync后紧邻
ledger replace前、replace后、receipt前、release前验证。flock从ledger read前持有到最终readback。
pre-replace drift删除temp并保证ledger/receipt不变；post-replace drift使gate FAIL且不发布receipt。
威胁边界仅trusted same-UID/cooperative reconcilers。

固定control root：

```text
<ledger parent>/.trial_reconciliation/
  snapshots/
  receipts/
```

root和两个subdir必须预存在、real directory、owner exact、mode0700、非symlink，且均在ledger
parent内；global sidecar lock保护全部slot操作。

验证journal snapshot后、mutation前，计算：

```text
snapshot_slot = SHA256(canonical JSON {
  run_intent_sha256,journal_snapshot_sha256
})
snapshot_path =
  <control root>/snapshots/reconciliation_snapshot_<snapshot_slot>.json
```

`ReconciliationSnapshotV2` exact：

```text
schema_version,status,snapshot_slot_sha256,
run_intent_sha256,journal_path,journal_snapshot_sha256,journal_snapshot_bytes,
event_count,source_event_ids,source_event_ids_sha256,
ledger_before_sha256,ledger_before_bytes,
candidate_evaluations_before,model_fits_before,
missing_source_event_ids,missing_source_event_ids_sha256,content_sha256
```

source IDs按journal contiguous order；missing list是snapshot时ledger尚未retained的exact subset，同序；
两个list digest均连接`uint64-be len||utf8`。snapshot用same-dir temp/fsync/atomic no-replace/dir fsync；
existing bytes必须exact，否则FAIL。同journal later append改变journal SHA，产生新slot；旧snapshot/
receipt bytes不变。

## 6. Commit and immutable receipt

锁内先验证bindings、M6 14328-byte 6/44、all JSONL、exact roster、8/60，然后严格三分支：

1. target receipt已存在：走下述NO_OP，不要求current ledger等于snapshot before；
2. receipt不存在且current ledger file SHA/bytes/counts exact等于snapshot before：完整
   `old+missing retained lines`写temp、flush/fsync，紧邻commit重验lock，replace/fsync/readback；
3. receipt不存在且current ledger已不同：其前`snapshot.ledger_before_bytes`必须hash等于snapshot
   before，且snapshot missing set必须在其后以exact source/retained hashes连续出现；据此走
   `LEDGER_ALREADY_COMMITTED`。找不到唯一minimal prefix或有插入/冲突即FAIL。

分支2/3都求覆盖snapshot全部source IDs的最短ledger prefix；该prefix给出after counts。

receipt slot/path：

```text
receipt_slot = SHA256(canonical JSON {
  run_intent_sha256,journal_snapshot_sha256,committed_ledger_prefix_sha256
})
receipt_path =
  <control root>/receipts/reconciliation_receipt_<receipt_slot>.json
```

`TrialLedgerReconciliationReceiptV5` exact：

```text
schema_version,status,recovery_mode,receipt_slot_sha256,
run_intent,reconciliation_snapshot,budget_limit_binding,
market_state_authority_binding,lock,ledger_commit,
ledger_observed_at_receipt,limits,committed_events,
candidate_evaluations_before,model_fits_before,
candidate_evaluations_after,model_fits_after,
all_snapshot_starts_reconciled,content_sha256
```

snapshot nested引用path/file/content/slot/journal SHA/bytes/event count；ledger commit含path/prefix SHA/
bytes/counts；observed含file SHA/bytes/counts；committed_events exact等于snapshot
`missing_source_event_ids`并附source/retained SHA。

before counts必须等于snapshot before；after counts等于minimal committed prefix。modes：

- `APPENDED`：本次append missing set；
- `LEDGER_ALREADY_COMMITTED`：crash恢复时snapshot ledger-before和missing set证明该exact set已连续
  commit，按minimal prefix发布；
- `NO_OP`：receipt已存在，验证content/slots/snapshot/current ledger仍以original commit prefix开头
  且source全覆盖，然后零写入返回原receipt。

receipt atomic no-replace+fsync。replace前crash=old；replace后完整new。相同journal重跑稳定；同一
journal追加新events使用新snapshot/receipt slots。

## 7. Static archive and imports

static authority=`static_m6_archive_binding_v2.json`，绑定gate/mechanics/run/verification/journal/
execution spec、9324-byte4/29、14328-byte6/44及replay binding中的archive/tree/internal manifest。
static verifier只hash/set/prefix，不import/load。caller不能替代expected hashes；legal suffix允许。

`data.market_state`只schema/NumPy/Pandas；governance不import Qlib/Torch/model；package root不隐式
load Torch/PeerLite；scripts不被library import。仍是trusted single-process research control。
