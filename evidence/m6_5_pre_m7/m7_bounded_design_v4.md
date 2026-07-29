# M7 Bounded CCC and Market-State Gate Design V4

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 取代：`m7_bounded_design_v3.md`
- 起点/上限：M6 `6/44`；future screen `8/60`。

## 1. Authorities and exact candidate roster

budget binding固定
`contracts/changes/m7_initial_screen_budget_binding_v1.json`，content SHA
`8937e019122b0009a92ac17ba1ad52ffd63be856e4a3faf44b44784ee917b275`，file SHA由closure固定；它
不是execution authority。未来derived contract独立过gate后，必须在任何journal/fit前绑定：

```text
budget binding
market-state product/source manifest/PIT parent/calendar/builder script+library
portfolio mapper/trading calendar/benchmark PIT
base+stress costs/order+participation+cap rules
M6 K16 predictions/metrics/folds/final-OOS seal
```

exact state六项组成`MarketStateAuthorityBindingV1`；缺失/替换/hash drift=0 event/0 fit。

只允许seed7的`PEERLITE_K16_CCC`和`PEERLITE_K16_MSE_GATE`。每候选1 evaluation、7 rolling fits、
1 wf_2018 deterministic refit，exact IDs来自budget binding；逐event校验model/seed/ID/fold/purpose。
失败/中断计预算且HOLD，0 replacement。

## 2. One date per CCC optimizer step

input float32，objective binary64。每optimizer step exact一个完整date；禁止split、multi-date step、
cross-date accumulation。每epoch normalized dates严格升序，无PRNG/shuffle，每date一次。checkpoint
metadata绑定：

```text
train_date_order_sha256,valid_date_order_sha256,one_date_per_step=true,
sampler_rule=ASCENDING_COMPLETE_DATE_NO_SHUFFLE,epsilon=1e-8,
input_dtype=float32,objective_dtype=float64,reducer_version
```

date digest用每个`YYYY-MM-DD`的`uint64-be length||ASCII`连接。每date rows按NFC instrument UTF-8
排序，使用component V4的binary64 left-fold、zero normalization和每步finite check：

```text
mu_p=mean(p); mu_y=mean(y)
var_p=mean((p-mu_p)^2); var_y=mean((y-mu_y)^2)
cov=mean((p-mu_p)*(y-mu_y))
ccc=2*cov/(var_p+var_y+(mu_p-mu_y)^2+1e-8)
loss=1-ccc
```

singleton用binary64 MSE。epoch train/valid objective为date loss升序left-fold mean。strict `<`
更新best，tie保留最早，nonfinite FAIL。

## 3. Canonical model checkpoint digest

不比较`torch.save`容器bytes。`ModelCheckpointDigestV1`只接受dense strided CPU materialization且
dtype属于`float32,float64,int64,bool`。state-dict keys须NFC string、唯一，按UTF-8 bytes排序。
每tensor先`detach().cpu().contiguous()`；numeric bits不转换，按little-endian规范化。entry preimage：

```text
len(key_utf8) uint64-be || key_utf8 ||
len(dtype_ascii) uint64-be || dtype_ascii ||
ndim uint64-be || each dimension uint64-be ||
nbytes uint64-be || C-order raw tensor bytes in canonical little-endian
```

所有entries连接后SHA-256=`model_state_sha256`。metadata只含：

```text
schema_version,model_id,fold_id,seed,selected_epoch,
selected_validation_metric_float_hex,model_config_sha256,
data_contract_sha256,budget_binding_sha256,state_authority_sha256,
train_date_order_sha256,valid_date_order_sha256,model_state_sha256
```

以canonical JSON hash得`checkpoint_semantic_sha256`。unsupported/sparse/quantized tensor、nonfinite
floating tensor、duplicate key均FAIL。deterministic refit必须selected epoch、metadata hash、
model-state digest和all score binary64 bits exact；checkpoint file/container bytes不作oracle。
refit不进入screen，任何不等即HOLD。

## 4. Gate alignment, stats and structure

state exact columns：

```text
mkt_trend_20,mkt_vol_20,mkt_breadth_1d,mkt_turnover_20
```

model keys唯一；state date唯一；exact-date many-to-one join后同date每只股票四值bits一致，无
cross-date shift/missing/extra。股票顺序置换后反置换output bitwise一致。

只用fold unique train dates升序，每date等权，以component V4 reducer计算population mean/std
`ddof=0`；`std<1e-12 -> 1.0`。mean/scale用column-order float.hex canonical JSON绑定train-date
digest和state authority。valid/test只transform，不refit/fill。

```text
state[4] -> Linear(4,64) -> GELU -> Linear(64,64) -> Sigmoid
gate=2*output
encoder_hidden*=gate[date]
```

注入encoder后、assignment前；K16/hidden64/heads4，O(NK)。checkpoint绑定全部authority、
stats/date/model/data/runtime/code hashes。

## 5. Weekly screening

每周：

```text
strategy_net = realized portfolio return - all frozen costs
benchmark = frozen benchmark total return
excess = strategy_net - benchmark
IR=mean(excess)/std(excess,ddof=1)*sqrt(52)
net_excess=prod(1+strategy_net)/prod(1+benchmark)-1
```

weeks按calendar exact、无missing/duplicate/overlap，每周等权；n<2、std=0、return<=-1均FAIL。
`SCREEN_PASS` iff base-cost combined IR delta>0、至少5/7 fold IR delta>0、stress net-excess>=0，
且PIT/engineering/refit/budget全PASS。0不满足`>`，exact5/7满足，stress0满足。

## 6. No promotion

8/60阶段只能`SCREEN_PASS|HOLD`，不得PROMOTE/COMBINATION。五seed确认、4/5、60% folds、
bootstrap及组合均需新CR/contract/budget。本文不授权test、fit、budget mutation或final OOS。
