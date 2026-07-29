# M6.5 Bounded Component Design V4

- 状态：`DESIGN_ONLY`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_5_bounded_component_design_v3.md`
- 范围：T-known market state、append-only ledger reconciliation、static M6 archive。
- 不授权：测试执行、实现、PIT重跑、真实数据、replay、fit、预算变更、final OOS。

## 1. T-close source selection

唯一时钟为A股交易日`T 15:00 Asia/Shanghai`。输入仅来自M3 PIT sealed、`date_max<2025-01-01`
artifacts；禁止supervised matrix、label、execution/halt/limit/crossover、current universe和2025+
分区。single-process builder固定`scripts/server/build_market_state_product.py`，只调用
`data.market_state`纯函数。

原始候选值exact logical fields：

```text
datetime,instrument,field,value,revision_id,source_available_time,source_row_sha256
```

对每个`(instrument,field,T)`筛选`source_available_time<=T 15:00 Asia/Shanghai`，取最大available
time；该时点多行只有完整canonical source-row bytes相同才去重，否则value/revision/hash任一冲突
即FAIL。mtime、ingestion time、row order不能破局。

所有文本NFC UTF-8。date编码`YYYY-MM-DD`；available time先转Asia/Shanghai并编码
`YYYY-MM-DDTHH:MM:SS.ffffff+08:00`；revision ID与field非空；source SHA为lowercase 64hex。
selection coverage每row依次编码六字段
`date,instrument,field,available_time,revision_id,source_row_sha256`；每字段都是
`len(utf8) unsigned 8-byte big-endian || utf8`，row再以
`len(row_bytes) unsigned 8-byte big-endian || row_bytes`连接。rows按上述六字段UTF-8 tuple排序，
整体SHA-256。manifest记录digest及eligible/rejected/deduplicated/conflict counts，conflict=0。

final adapter以`(datetime,instrument)`唯一键输出：

```text
universe_member,listing_age_eligible,is_active,
special_status_forbidden,special_status_unknown,
ret_mean_20,ret_std_20,ret_1d,turnover_mean_20
```

前五列为T-known boolean；禁止
`tradable,price_domain_valid,feature_eligible,corporate_action_crossover`及任何execution/label/
purge/split字段。`U_state(T)`：

```text
universe_member & listing_age_eligible & is_active
& !special_status_forbidden & !special_status_unknown
& all four numeric sources finite
```

unknown/missing bool、duplicate final key、extra column、nonfinite均FAIL，不填充、不回补。

## 2. Bit-exact state

instrument NFC、非空、UTF-8且唯一，按UTF-8 bytes排序。numeric先转IEEE binary64；所有
`x == 0.0`（含`-0.0`）立即规范为`+0.0`。mean为该顺序左折叠：

```text
acc=binary64(+0.0)
for x: acc=binary64(acc+binary64(x)); require finite; normalize zero
result=binary64(acc/binary64(count)); require finite; normalize zero
```

禁止vectorized/pairwise/float32/扩展精度。median按numeric ascending；所有zero已为`+0.0`；奇数
取中值，偶数固定`binary64(binary64(left+right)/binary64(2.0))`，每步finite check和zero
normalization。任何输入、中间或结果NaN/Inf立即FAIL。breadth先生成binary64 0.0/1.0，再同一mean。

```text
mkt_trend_20=mean(ret_mean_20)
mkt_vol_20=median(ret_std_20)
mkt_breadth_1d=mean(ret_1d>0.0)
mkt_turnover_20=median(turnover_mean_20)
```

population key digest为sorted instrument各自
`len(utf8) uint64-be || utf8`连接后SHA。state digest preimage：

```text
date ASCII || 0x00 || count uint64-be || key digest raw32 ||
four outputs in order as IEEE binary64 big-endian
```

daily exact columns再含`population_count,population_keyset_sha256,state_sha256`；date index为
naive normalized、严格升序唯一，后续只exact-date broadcast。

## 3. Source manifest and pre-fit state authority

`MarketStateSourceManifestV2` exact top-level：

```text
schema_version,status,prediction_clock,contract,calendar,pit_parent,
source_artifacts,input_schema,revision_selection,builder,output,
date_min,date_max,final_oos_accessed,content_sha256
```

artifact ref为`{path,file_sha256,content_sha256}`，原生blob为`{path,file_sha256}`；
revision_selection exact为
`{rule,selection_coverage_sha256,eligible_rows,rejected_future_rows,
deduplicated_identical_rows,conflict_rows}`，rule固定
`LATEST_SOURCE_AVAILABLE_TIME_LTE_T_CLOSE_EQUAL_TIME_IDENTICAL_ONLY`。builder绑定script/library
SHA，output绑定path/file/key/value digests，date_max<2025-01-01，OOS=false。

poison覆盖future row/revision、equal-time conflict、current-universe replacement；through-T bytes
必须不变或FAIL。

任何future M7 derived contract、RunIntent、event、checkpoint、receipt在首个journal byte或fit前
必须byte-identical绑定：

```text
MarketStateAuthorityBindingV1={
 state_product{path,file_sha256,key_digest,value_digest},
 source_manifest{path,file_sha256,content_sha256},
 pit_parent{path,file_sha256,content_sha256},
 calendar{path,file_sha256,content_sha256},
 builder_script{path,file_sha256},
 builder_library{path,file_sha256}
}
```

缺失、替换、hash drift时0 event/0 fit。

## 4. Ledger schemas and exact budget roster

canonical JSON为UTF-8/NFC/sort_keys/compact/no-NaN/no-duplicate-key。SHA lowercase 64hex；ID grammar
`[A-Za-z0-9][A-Za-z0-9:._-]{0,255}`。external budget authority：

```text
contracts/changes/m7_initial_screen_budget_binding_v1.json
content_sha256=8937e019122b0009a92ac17ba1ad52ffd63be856e4a3faf44b44784ee917b275
```

`BudgetLimitBindingV1` exact：

```text
path,file_sha256,content_sha256,m6_prefix_sha256,m6_prefix_bytes,
m6_candidate_evaluations,m6_model_fits,
ceiling_candidate_evaluations,ceiling_model_fits
```

值为`14328/6/44/8/60`。该external file仍非execution authority。

`RunIntentV2` exact：

```text
schema_version,run_id,family_id,execution_spec_content_sha256,
budget_limit_binding,market_state_authority_binding,content_sha256
```

journal candidate event exact：

```text
schema_version,run_id,event_seq,source_event_id,run_intent_sha256,event,timestamp,
family_id,execution_spec_content_sha256,budget_limit_binding,
market_state_authority_binding,evaluation_id,model_id,seed,
counts_as_candidate_evaluation,counts_as_model_fit,purpose,event_sha256
```

fit exact新增`fit_id,fold_id`。schemas为`run_intent_v2/run_trial_event_v3`；events仅
`CANDIDATE_EVALUATION_STARTED|MODEL_FIT_STARTED`；source ID为`run_id:seq6`。

retained schema `qlib_peerlite_trial_ledger_event_v3` exact：

```text
schema_version,event,source_event_id,source_event_sha256,source_journal_relpath,
source_event_seq,source_timestamp,run_id,run_intent_sha256,family_id,
execution_spec_content_sha256,budget_limit_binding,market_state_authority_binding,
counts_as_candidate_evaluation,counts_as_model_fit,evaluation_id,model_id,seed,
outcome,purpose?,fit_id?,fold_id?,retained_event_sha256
```

每event除总cap外必须逐项匹配budget file candidate roster：family、唯一两model IDs、seed7、exact
evaluation count、7个screen fit IDs、1个refit ID、fold和purpose。unlisted model/seed/ID、额外
evaluation、replacement或重复一律在写前FAIL。失败/中断start仍计数。

## 5. Stable lock, reconciliation snapshot and atomic commit

固定lock为`<ledger>.reconcile.lock`，首用前创建，永不replace/unlink。拒绝symlink/nonregular/
nlink!=1；open FD后`fstat`必须等于path `lstat` dev/inode。ledger directory和lock须由effective
UID拥有，directory不得group/other writable，lock mode必须0600。architecture v28 threat boundary
仅含trusted same-UID operator和cooperative reconcilers，不声称抵御privileged或malicious same-UID
filesystem attacker。

flock从ledger read前持有到receipt/recovery readback后。path/FD dev+inode至少在
lock acquisition、journal validation后、temp fsync后紧邻ledger `os.replace`前、replace后、
receipt publish前和release前验证。**任何pre-replace检查失败都删除temp并在ledger/receipt未变时
FAIL**；post-replace drift使gate FAIL且不得继续发布receipt。测试注入只能发生在这些定义边界；
不扩张为production filesystem adversary protocol。

journal验证后、ledger mutation前，原子no-replace发布immutable
`ReconciliationSnapshotV1`：

```text
schema_version,status,run_intent_sha256,journal_path,
journal_snapshot_sha256,journal_snapshot_bytes,event_count,
source_event_ids_sha256,content_sha256
```

source IDs为contiguous sequence，用length-prefix digest；existing different snapshot FAIL。它是
crash recovery寻找原journal prefix的唯一authority，后来journal suffix不改变它。

锁内commit：

1. validate external bindings、snapshot、M6 prefix、all JSONL、exact roster和8/60；
2. `new=old+canonical retained lines`写same-dir private temp、flush/fsync；
3. 做紧邻commit的lock identity check；
4. `os.replace(temp,ledger)`唯一commit，fsync parent，readback exact；
5. 求覆盖snapshot全部source IDs的最短ledger prefix，记录bytes/SHA/counts；
6. 持锁原子no-replace publish/readback receipt。

replace前crash=old；replace后=完整new。相同bytes重跑NO_OP；conflict/prefix/roster/limit drift均
FAIL且old不变。

receipt slot preimage canonical JSON：

```text
{run_intent_sha256,journal_snapshot_sha256,committed_ledger_prefix_sha256}
```

`TrialLedgerReconciliationReceiptV4` top-level exact：

```text
schema_version,status,recovery_mode,receipt_slot_sha256,
run_intent,reconciliation_snapshot,budget_limit_binding,
market_state_authority_binding,lock,ledger_commit,
ledger_observed_at_receipt,limits,committed_events,
candidate_evaluations_before,model_fits_before,
candidate_evaluations_after,model_fits_after,
all_snapshot_starts_reconciled,content_sha256
```

nested exact：

```text
run_intent:{path,file_sha256,content_sha256,run_id}
reconciliation_snapshot:{path,file_sha256,content_sha256,journal_snapshot_sha256,
                         journal_snapshot_bytes,event_count}
lock:{path,device,inode,stable_through_receipt}
ledger_commit:{path,prefix_sha256,prefix_bytes,candidate_evaluations,model_fits}
ledger_observed_at_receipt:{file_sha256,bytes,candidate_evaluations,model_fits}
limits:{candidate_evaluations,model_fits}
committed_events:[{source_event_id,source_event_sha256,retained_event_sha256}]
```

`before/after`和committed_events永远描述原commit minimal prefix，不描述恢复时后来suffix。
recovery enum：

- `APPENDED`：本调用commit，committed_events非空；
- `LEDGER_ALREADY_COMMITTED`：snapshot证明原journal prefix已完整commit但receipt不存在，按原
  minimal prefix发布；observed字段记录恢复时ledger；
- `NO_OP`：slot receipt已存在；只验证receipt content/slot、snapshot、原minimal prefix仍为当前
  ledger prefix且全部source覆盖，然后**零写入直接返回既有receipt**，不得用current ledger重构。

因此receipt发布后再有合法suffix，原receipt bytes仍稳定。

## 6. Static archive

唯一authority是`static_m6_archive_binding_v2.json`，file/content SHA由closure固定。它绑定gate、
mechanics、run/verification/journal/execution spec、9324-byte 4/29、14328-byte 6/44以及
`m6_archival_replay_binding_v2.json`中的archive/tree/internal-manifest identity。static verifier
只做hash/set/prefix检查，不import、不加载checkpoint。caller不能提供替代expected hashes；合法
ledger suffix允许，任何source/artifact/prefix drift FAIL且不改历史。

## 7. Imports

`data.market_state`只import schema/NumPy/Pandas；governance不import Qlib/Torch/model；package root
不隐式加载Torch/PeerLite；scripts不得被library import。仍是trusted single-process research
control，不引入production privileged control plane。
