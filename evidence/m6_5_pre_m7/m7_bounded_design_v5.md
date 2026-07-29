# M7 Bounded CCC and Gate Design V5

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 取代：`m7_bounded_design_v4.md`
- 起点/上限：M6 `6/44`；future screen `8/60`。

## 1. Exact authority

budget authority改为`m7_initial_screen_budget_binding_v2.json`，content SHA
`5fb21bae3c9cf14312bbc7d4605df55642fc4873d4ce5eb0e01826aec044a626`，file SHA由closure固定，
且仍非execution authority。future derived contract在journal/fit前还须绑定state product/source/
PIT/calendar/builders、portfolio/calendar/benchmark/cost/order rules、M6 K16 predictions/metrics/
folds/OOS seal；缺任一0 event/fit。

只允许binding V2中两candidate、seed7、exact evaluation ID/purpose和每个fit ID/fold/purpose：
`PEERLITE_K16_CCC`与`PEERLITE_K16_MSE_GATE`，各1+8。失败/中断计预算，0 replacement。

## 2. CCC deterministic steps

input float32/objective binary64。每optimizer step exact一个完整date，禁止split/multi-date/
accumulation；每epoch dates升序、无PRNG、每date一次。date digest为length-prefixed YYYY-MM-DD。
row按instrument UTF-8排序，使用component V5 left-fold/zero/finite rules：

```text
ccc=2*cov/(var_p+var_y+(mu_p-mu_y)^2+1e-8); loss=1-ccc
```

singleton=MSE；epoch objective按date升序mean；strict `<` best，tie earliest。checkpoint绑定train/
valid date digests、one-date rule、epsilon/dtypes/reducer。

## 3. Canonical checkpoint semantics

不比较torch container bytes。dense CPU contiguous state dict keys按UTF-8排序，只允许
float32/float64/int64/bool；每entry编码key/dtype/ndim/shape/nbytes和canonical little-endian raw
bits，连接SHA。metadata canonical JSON绑定model/fold/seed/selected epoch/metric float.hex/config/
data/budget/state/date digests和model-state SHA，产生semantic SHA。unsupported/nonfinite/duplicate
FAIL。wf2018 refit必须epoch、metadata、state digest、all score bits exact，否则HOLD且不screen。

## 4. Gate and screen

Gate四列trend/vol/breadth/turnover；exact-date many-to-one，same-date state bits一致，无shift/
missing/extra，stock permutation equivariant。train unique dates升序、ddof0 binary64，std<1e-12→1；
valid/test不refit/fill。结构固定`4→64→64→sigmoid×2`，encoder后assignment前，K16/h64/heads4，
O(NK)。

weekly net/benchmark/excess按frozen mapper/cost；IR用ddof1和sqrt52，compound net excess按ratio。
calendar完整无overlap；invalid/missing FAIL。SCREEN_PASS iff combined IR delta>0、至少5/7 fold
delta>0、stress net-excess>=0且全部gates PASS。

## 5. Boundary

输出仅SCREEN_PASS/HOLD。无PROMOTE/combination/five-seed/final OOS；后续需新CR/contract/budget。
