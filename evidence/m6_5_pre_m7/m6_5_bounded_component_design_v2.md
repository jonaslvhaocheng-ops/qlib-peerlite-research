# M6.5 Bounded Component Design V2

- 状态：`DESIGN_ONLY`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_5_bounded_component_design_v1.md`
- 范围：T-known market-state product、trial-ledger reconciliation和static M6 archive verification。

## 1. T-known builder and prediction clock

唯一prediction clock为A股交易日`T 15:00 Asia/Shanghai`收盘后。每个输入值必须具有
`source_available_time <= T 15:00`，并来自已通过M3 PIT的sealed pre-final-OOS artifacts。trusted
server composition root固定为：

```text
scripts/server/build_market_state_product.py
```

它只调用`data.market_state`纯函数并只写product和source manifest；不得读取M3 supervised
matrix、label、execution/purge条件、current constituent snapshot或2025+数据。

builder adapter输出以`(datetime,instrument)`为唯一键的exact columns：

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

前五列是从sealed PIT universe/listing/ST/delisting历史记录在T时点规范化出的boolean，不含原始
event字段。明确禁止`tradable,price_domain_valid,feature_eligible,
corporate_action_crossover`及任何halt/resume/limit/execution/label/purge/split字段；这些字段可能
受未来执行窗口或模型样本条件影响，不能进入`U_state(T)`。

`U_state(T)` exact predicate：

```text
universe_member
& listing_age_eligible
& is_active
& !special_status_forbidden
& !special_status_unknown
& all four state sources finite at T
```

任何missing/unknown boolean、duplicate key、extra column或nonfinite source使该日构建失败，不做
填充或从未来回补。

## 2. State formulas and canonical identity

每个date先按NFC instrument UTF-8 bytes稳定排序，四列转IEEE-754 float64。确定性聚合：

```text
mkt_trend_20    = float64 arithmetic mean(ret_mean_20)
mkt_vol_20      = float64 median(ret_std_20)
mkt_breadth_1d  = float64 mean(ret_1d > 0.0)
mkt_turnover_20 = float64 median(turnover_mean_20)
```

median：奇数取排序中值，偶数取两个中值的float64 arithmetic mean。每次reduction按上述稳定顺序；
禁止float32累积。daily output exact columns：

```text
mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20,
population_count,population_keyset_sha256,state_sha256
```

`population_keyset_sha256=SHA256(concat(instrument UTF-8 || 0x00))`。`state_sha256` preimage：

```text
date YYYY-MM-DD ASCII || 0x00 ||
population_count unsigned 8-byte big-endian ||
population_keyset_sha256 raw 32 bytes ||
four values in column order as IEEE-754 big-endian float64
```

state index是timezone-naive normalized date、严格升序唯一。join只能exact-date broadcast。

## 3. MarketStateSourceManifestV1

fixed output sibling`market_state_source_manifest.json`，exact fields：

```text
schema_version,status,prediction_clock,contract,calendar,
pit_parent,source_artifacts,input_schema,builder,output,
date_min,date_max,final_oos_accessed,content_sha256
```

约束：

- schema ID=`qlib_peerlite_market_state_source_manifest_v1`，status=`PASS`；
- prediction_clock exact=`T_CLOSE_15_00_ASIA_SHANGHAI`；
- contract/calendar/PIT parent和source artifacts各为
  `{path,file_sha256,content_sha256}`，按path排序唯一；
- input_schema exact绑定§1 columns/dtypes及availability rule；
- builder=`{path,file_sha256}`，同时绑定pure library file SHA；
- output=`{path,file_sha256,row_count,key_digest,value_digest}`；
- date_max `<2025-01-01`，`final_oos_accessed=false`；
- `content_sha256`为排除自身后、UTF-8、NFC、sort_keys、无空格、禁止NaN的canonical JSON SHA。

future-poison至少覆盖三类：`>T` row、同一T key的future revision、current-universe替换。只有
availability合法的T snapshot可以参与；任一poison后所有`<=T` keys/counts/values/digests必须
byte-identical，否则FAIL。

## 4. Exact ledger identities

canonical JSON统一为UTF-8/NFC、sort_keys、separators `,`/`:`、禁止NaN与duplicate key。SHA均为
lowercase 64hex，无`sha256:`前缀。ID grammar为
`[A-Za-z0-9][A-Za-z0-9:._-]{0,255}`。

M6 close prefix exact：

```text
prefix_sha256=31a90d1ff506d9dfae48ab8bd191bf8ee9bbcbdc261c8f1acde9c3741992de93
prefix_bytes=14328
candidate_evaluations=6
model_fits=44
```

`RunIntentV1` exact：

```text
schema_version,run_id,family_id,execution_spec_content_sha256,content_sha256
```

schema ID=`qlib_peerlite_run_intent_v1`；content SHA排除自身后canonical hash。

Journal candidate event exact fields：

```text
schema_version,run_id,event_seq,source_event_id,run_intent_sha256,event,timestamp,
family_id,execution_spec_content_sha256,evaluation_id,model_id,seed,
counts_as_candidate_evaluation,counts_as_model_fit,purpose,event_sha256
```

fit event在此基础上exact新增`fit_id,fold_id`。schema ID
`qlib_peerlite_run_trial_event_v2`；event enum仅
`CANDIDATE_EVALUATION_STARTED|MODEL_FIT_STARTED`；source ID exact
`<run_id>:<event_seq zero-padded 6>`；count flags必须与event kind相符；event SHA排除自身后
canonical hash。

Reconciled ledger record schema ID=`qlib_peerlite_trial_ledger_event_v2`，exact fields为：

```text
schema_version,event,source_event_id,source_event_sha256,source_journal_relpath,
source_event_seq,source_timestamp,run_id,run_intent_sha256,family_id,
execution_spec_content_sha256,counts_as_candidate_evaluation,counts_as_model_fit,
evaluation_id,model_id,seed,outcome,purpose?,fit_id?,fold_id?,retained_event_sha256
```

optional fields只按kind出现；candidate outcome=`CANDIDATE_STARTED_RETAINED`，fit outcome=
`STARTED_OR_INTERRUPTED_RETAINED`。retained hash排除自身后canonical hash。

## 5. Atomic reconciliation and receipt

唯一写算法：

1. 取得same-directory ledger flock；
2. 读取完整ledger bytes，要求newline终止和每行strict JSON；
3. 在byte 14328重验M6 exact prefix、6/44 counts；
4. 验证journal root containment、全部source hashes、semantic evaluation/fit uniqueness及limits；
5. 构造`new_bytes = old_bytes + canonical event lines`；
6. 将**完整new_bytes**写入same-directory private temp，flush/fsync；
7. `os.replace(temp,ledger)`作为唯一commit point，再fsync parent directory；
8. 重新读取并验证完整ledger与预期SHA。

crash在replace前保持old ledger；replace后得到完整new ledger，永不产生partial JSONL。残留temp不是
authority。两个reconciler由同一flock串行；第二个重扫后对相同source bytes no-op，对冲突bytes
FAIL。limit在同一lock内按commit后总数预检。

crash-after-ledger-before-receipt时，重跑发现全部source records exact存在，生成
`recovery_mode=LEDGER_ALREADY_COMMITTED`的receipt，不重复追加。正常为`APPENDED|NO_OP`。

`TrialLedgerReconciliationReceiptV3` exact fields：

```text
schema_version,status,recovery_mode,run_intent,journal,ledger,
expected_historical_prefix,limits,appended_events,
candidate_evaluations_before,model_fits_before,
candidate_evaluations_after,model_fits_after,
all_journal_starts_reconciled,content_sha256
```

run_intent exact引用V1 fields；journal/ledger分别含absolute server path和file SHA before/after；
historical prefix固定§4；limits为future frozen total caps；status PASS且all reconciled true。
receipt使用same-directory temp+fsync+atomic replace+parent fsync；existing different receipt FAIL。

## 6. Static archive and imports

`verify_archived_m6_evidence`必须验证M6 gate、run manifest、mechanics、verification receipt、frozen
source blobs、pre-run 4/29 prefix、close 6/44 prefix和journal-start→retained-ID exact集合。合法
ledger suffix允许，prefix tamper、journal set差异或static evidence hash差异均FAIL。

`data.market_state`只能import schema/NumPy/Pandas；governance不能importQlib/Torch/model；
package root不得隐式加载Torch/PeerLite；`scripts/**`不得被library import。本文不授权执行。
