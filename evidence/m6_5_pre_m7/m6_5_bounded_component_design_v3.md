# M6.5 Bounded Component Design V3

- 状态：`DESIGN_ONLY`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_5_bounded_component_design_v2.md`
- 范围：T-known market-state product、append-only trial-ledger reconciliation、static M6 archive。
- 边界：本文不授权测试执行、实现、PIT重跑、真实数据读取、replay、fit、预算变更或final OOS。

## 1. T-known source rows and prediction clock

唯一prediction clock是A股交易日`T 15:00 Asia/Shanghai`收盘后。输入只能来自已通过M3 PIT且
`date_max < 2025-01-01`的sealed artifacts；禁止M3 supervised matrix、label、未来执行状态、
current constituent snapshot及2025+分区。trusted single-process builder固定为：

```text
scripts/server/build_market_state_product.py
```

每个原始候选值至少有：

```text
datetime,instrument,field,value,revision_id,source_available_time,source_row_sha256
```

对每个`(instrument,field,T)`只保留`source_available_time <= T 15:00 Asia/Shanghai`的记录，
选择其中最大available time。最大时间相同的多行只有在完整canonical source-row bytes一致时才可
去重；value、revision_id、source hash或其他字段冲突立即FAIL。不得用ingestion time、文件mtime
或row order破局。

selection coverage按`date/instrument/field`、available time、revision ID和source-row SHA稳定
排序；每项用8-byte big-endian长度前缀编码后连接并SHA-256。manifest必须记录
`selection_coverage_sha256`、eligible/rejected/deduplicated/conflict counts。

builder adapter最后输出以`(datetime,instrument)`为唯一键的exact columns：

```text
universe_member
listing_age_eligible
is_active
special_status_forbidden
special_status_unknown
ret_mean_20
ret_std_20
ret_1d
turnover_mean_20
```

前五列是当时点历史记录规范化的boolean。禁止
`tradable,price_domain_valid,feature_eligible,corporate_action_crossover`以及
halt/resume/limit/execution/label/purge/split字段。`U_state(T)`为：

```text
universe_member
& listing_age_eligible
& is_active
& !special_status_forbidden
& !special_status_unknown
& all four numeric sources finite at T
```

missing/unknown boolean、duplicate key、extra column、nonfinite source均使该日FAIL，不填充、不
向未来回补。

## 2. Bit-exact state reducer and identity

instrument先NFC，必须非空且UTF-8编码；排序键为其UTF-8 bytes且必须唯一。所有numeric values先
转换为IEEE-754 binary64，拒绝NaN/Inf。mean reducer固定为稳定instrument顺序上的左折叠：

```text
acc = binary64(+0.0)
for x in ordered_values:
    acc = binary64(acc + binary64(x))
mean = binary64(acc / binary64(count))
```

每次加法和除法都立即舍入到binary64；禁止NumPy/Pandas/BLAS向量化sum、float32、扩展精度或
pairwise reducer。median先按numeric ascending排序；奇数取中值；偶数固定
`binary64(binary64(left + right) / binary64(2.0))`。`ret_1d > binary64(0.0)`先生成0.0/1.0，
再使用相同left-fold mean。四个结果：

```text
mkt_trend_20    = mean(ret_mean_20)
mkt_vol_20      = median(ret_std_20)
mkt_breadth_1d  = mean(ret_1d > 0.0)
mkt_turnover_20 = median(turnover_mean_20)
```

`population_keyset_sha256` preimage为每个sorted instrument的
`len(utf8) unsigned 8-byte big-endian || utf8`连接；因此instrument内任何control byte不产生
分隔歧义。`state_sha256` preimage为：

```text
date YYYY-MM-DD ASCII || 0x00 ||
population_count unsigned 8-byte big-endian ||
population_keyset_sha256 raw 32 bytes ||
four values in stated order as IEEE-754 big-endian binary64
```

daily output exact columns：

```text
mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20,
population_count,population_keyset_sha256,state_sha256
```

index为timezone-naive normalized date、严格升序唯一；后续只能exact-date broadcast。

## 3. MarketStateSourceManifestV2 and future authority

fixed sibling=`market_state_source_manifest.json`，schema ID
`qlib_peerlite_market_state_source_manifest_v2`，exact fields：

```text
schema_version,status,prediction_clock,contract,calendar,pit_parent,
source_artifacts,input_schema,revision_selection,builder,output,
date_min,date_max,final_oos_accessed,content_sha256
```

所有artifact ref exact为`{path,file_sha256,content_sha256}`；无content hash的原生blob只允许
`{path,file_sha256}`。`revision_selection` exact为：

```text
rule,selection_coverage_sha256,eligible_rows,rejected_future_rows,
deduplicated_identical_rows,conflict_rows
```

rule固定`LATEST_SOURCE_AVAILABLE_TIME_LTE_T_CLOSE_EQUAL_TIME_IDENTICAL_ONLY`，conflict_rows必须0。
builder绑定script与pure library file SHA。output exact为
`{path,file_sha256,row_count,key_digest,value_digest}`。date_max必须`<2025-01-01`且
final_oos_accessed=false。

future-poison必须覆盖`>T` row、同T key future revision、equal-time conflicting revision及
current-universe substitution；所有`<=T` outputs/counts/digests必须byte-identical或FAIL。

任何未来M7 derived contract、RunIntent、candidate event、fit event、checkpoint和receipt在首个
journal byte或fit前，必须绑定同一`MarketStateAuthorityBindingV1`：

```text
state_product{path,file_sha256,key_digest,value_digest}
source_manifest{path,file_sha256,content_sha256}
pit_parent{path,file_sha256,content_sha256}
calendar{path,file_sha256,content_sha256}
builder_script{path,file_sha256}
builder_library{path,file_sha256}
```

六项任一缺失、替换或hash不一致时不得写journal、不得fit。

## 4. Canonical ledger records and external budget binding

canonical JSON统一UTF-8/NFC、sort_keys、separators`,`/`:`、禁止NaN和duplicate keys。所有SHA为
lowercase 64hex。ID grammar为`[A-Za-z0-9][A-Za-z0-9:._-]{0,255}`。

唯一预算外部authority为：

```text
contracts/changes/m7_initial_screen_budget_binding_v1.json
file_sha256=<由closure manifest固定>
content_sha256=8937e019122b0009a92ac17ba1ad52ffd63be856e4a3faf44b44784ee917b275
```

`BudgetLimitBindingV1` exact为：

```text
path,file_sha256,content_sha256,m6_prefix_sha256,m6_prefix_bytes,
m6_candidate_evaluations,m6_model_fits,
ceiling_candidate_evaluations,ceiling_model_fits
```

值必须等于external file的`14328 / 6 / 44 / 8 / 60`。external file仍是
`DESIGN_ONLY_NOT_EXECUTION_AUTHORITY`；只有未来独立通过的derived contract才能授权event。

M6 close prefix exact：

```text
sha256=31a90d1ff506d9dfae48ab8bd191bf8ee9bbcbdc261c8f1acde9c3741992de93
bytes=14328
candidate_evaluations=6
model_fits=44
```

`RunIntentV2` exact fields：

```text
schema_version,run_id,family_id,execution_spec_content_sha256,
budget_limit_binding,market_state_authority_binding,content_sha256
```

schema ID=`qlib_peerlite_run_intent_v2`；两binding为本文exact schemas。

Journal candidate event exact fields：

```text
schema_version,run_id,event_seq,source_event_id,run_intent_sha256,event,timestamp,
family_id,execution_spec_content_sha256,budget_limit_binding,
market_state_authority_binding,evaluation_id,model_id,seed,
counts_as_candidate_evaluation,counts_as_model_fit,purpose,event_sha256
```

fit event exact新增`fit_id,fold_id`。schema ID=`qlib_peerlite_run_trial_event_v3`；event enum仅
`CANDIDATE_EVALUATION_STARTED|MODEL_FIT_STARTED`；source ID exact
`<run_id>:<event_seq zero-padded 6>`；flags与event kind相符。event/run-intent/content SHA均排除
自身后canonical hash。

Reconciled ledger schema ID=`qlib_peerlite_trial_ledger_event_v3`，exact fields：

```text
schema_version,event,source_event_id,source_event_sha256,source_journal_relpath,
source_event_seq,source_timestamp,run_id,run_intent_sha256,family_id,
execution_spec_content_sha256,budget_limit_binding,market_state_authority_binding,
counts_as_candidate_evaluation,counts_as_model_fit,evaluation_id,model_id,seed,
outcome,purpose?,fit_id?,fold_id?,retained_event_sha256
```

candidate outcome=`CANDIDATE_STARTED_RETAINED`；fit outcome=
`STARTED_OR_INTERRUPTED_RETAINED`；optional fields只按kind出现。

## 5. Stable lock, atomic commit and recovery

固定锁是ledger sibling：

```text
<ledger filename>.reconcile.lock
```

它在首个reconcile前创建，之后永不replace/unlink。每次必须拒绝symlink/non-regular/multi-link；
open FD后比较`fstat(fd).(st_dev,st_ino)`与`lstat(path)`，记录lock path/dev/inode。锁从读取ledger
之前一直持有到ledger replace/readback、receipt publish/readback及recovery完成；释放前再次确认
path仍指向同一dev/inode。绝不锁ledger inode，因为`os.replace`会改变它。

锁内算法：

1. snapshot并严格验证run intent和journal完整bytes/SHA/newline/contiguous event_seq；
2. 读取ledger，验证M6 14328-byte prefix、6/44和全部JSONL；
3. 验证两external bindings、root containment、source hashes、semantic uniqueness及8/60；
4. 构造`new_bytes=old_bytes+canonical retained lines`；
5. 完整写same-directory private temp，flush/fsync，`os.replace(temp,ledger)`，fsync parent；
6. readback exact bytes/SHA，求本次**最小committed prefix**：从byte 0到本journal最后一个连续
   retained source event所在行末；记录其bytes/SHA/counts；
7. 在仍持锁时原子发布并readback receipt。

replace前crash保留old；replace后只能完整new。相同source bytes重跑NO_OP；相同ID不同bytes、
语义重复、prefix/authority drift、limit overflow均FAIL且不改ledger。

receipt slot ID preimage为canonical JSON：

```text
{run_intent_sha256,journal_snapshot_sha256,committed_ledger_prefix_sha256}
```

slot filename=`reconciliation_receipt_<SHA256(preimage)>.json`。如果ledger commit后receipt前crash，
恢复必须从ledger定位覆盖原始journal完整连续source sequence的**最短**prefix；后来其他journal
合法append不改变该prefix或slot。若不存在唯一最短prefix即FAIL。receipt另记录当前observed
ledger identity，不把它误当原commit identity。

`TrialLedgerReconciliationReceiptV4` exact top-level：

```text
schema_version,status,recovery_mode,receipt_slot_sha256,
run_intent,journal,budget_limit_binding,market_state_authority_binding,
lock,ledger_commit,current_ledger,limits,appended_events,
candidate_evaluations_before,model_fits_before,
candidate_evaluations_after,model_fits_after,
all_journal_starts_reconciled,content_sha256
```

exact nested types：

```text
run_intent:{path:string,file_sha256:hex,content_sha256:hex,run_id:string}
journal:{path:string,snapshot_sha256:hex,snapshot_bytes:uint,event_count:uint}
lock:{path:string,device:uint,inode:uint,stable_before_after:boolean}
ledger_commit:{path:string,prefix_sha256:hex,prefix_bytes:uint,
               candidate_evaluations:uint,model_fits:uint}
current_ledger:{file_sha256:hex,bytes:uint,
                candidate_evaluations:uint,model_fits:uint}
limits:{candidate_evaluations:uint,model_fits:uint}
appended_events:[{source_event_id:string,source_event_sha256:hex,
                  retained_event_sha256:hex}]
```

recovery enum=`APPENDED|NO_OP|LEDGER_ALREADY_COMMITTED`。APPENDED要求appended_events非空；
NO_OP表示receipt已存在且bytes exact；LEDGER_ALREADY_COMMITTED表示原prefix存在但slot尚未发布。
status固定PASS，all reconciled=true，nested binding与RunIntent/event byte-identical。

## 6. Static M6 archive binding

唯一static archive authority为
`evidence/m6_5_pre_m7/static_m6_archive_binding_v1.json`，其file/content SHA由closure manifest固定。
verifier不得接受调用者自报的替代expected hashes。它逐项验证M6 gate、mechanics、run manifest、
verification、journal、execution spec、pre-run 9324-byte `4/29` prefix及close 14328-byte `6/44`
prefix，并验证journal-start到retained-ID exact集合。合法ledger suffix允许；任一prefix、artifact、
source set或binding hash漂移均FAIL，绝不重写历史。

## 7. Dependency boundary

`data.market_state`只能import schema/NumPy/Pandas；governance不得import Qlib/Torch/model；package
root不得隐式加载Torch/PeerLite；`scripts/**`不得被library import。本文仍只描述trusted operator
单Python进程内的research-quality controls，不重新引入production privileged control plane。
