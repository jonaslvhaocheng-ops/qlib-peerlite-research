# ScoreReplayIdentityV1

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`

## 1. Fixed sources and grain

- M6 spec file SHA：
  `469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8`
- M6 content SHA：
  `60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69`

expected恰两份model-level merged files：

| model | file SHA | rows |
| --- | --- | --- |
| PEERLITE_K16_MSE | `559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3` | 949014 |
| PEERLITE_K32_MSE | `008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55` | 949014 |

每份exact columns/order：

```text
datetime,instrument,score,model_id,fold_id
```

各含exact七个nonempty folds。replay恰十四份singleton-fold immutable outputs。outer pair identity
恰为：

```text
(PEERLITE_K16_MSE,wf_2018)..(PEERLITE_K16_MSE,wf_2024)
(PEERLITE_K32_MSE,wf_2018)..(PEERLITE_K32_MSE,wf_2024)
```

outer plan每pair exact绑定model/fold、expected merged file SHA、expected fold receipt path+
file/content SHA、checkpoint path+file SHA、per-fold replay relative path+file SHA。十四个replay
paths与SHAs分别唯一；不得共享model-level output、重复、缺失、额外或replacement。

## 2. Canonicalization and windows

每side先验证columns/order。datetime：

- timezone-aware先转`Asia/Shanghai`再取local date；
- timezone-naive必须是midnight且按naive calendar date解释，不得假定UTC；
- 生成canonical `YYYY-MM-DD`后才检查inclusive fold window。

instrument必须string、NFC、nonempty、strip前后相等，禁止numeric-to-string。score必须native
finite float64。model_id/fold_id逐行exact等于outer pair。key `(date,instrument)`唯一，按date
ASCII、instrument UTF-8 bytes稳定排序。

```text
wf_2018 2018-01-09..2018-12-28
wf_2019 2019-01-09..2019-12-31
wf_2020 2020-01-09..2020-12-31
wf_2021 2021-01-11..2021-12-31
wf_2022 2022-01-11..2022-12-30
wf_2023 2023-01-10..2023-12-22
wf_2024 2024-01-09..2024-12-17
```

expected side从merged file按已验证fold过滤；replay side只含该singleton fold。

## 3. Digests and equality

```text
key_row=date+"T00:00:00"||0x1f||instrument||0x0a
score_row=date+"T00:00:00"||0x1f||instrument||0x1f||float.hex(score)||0x0a
identity_row=model_id||0x1f||fold_id||0x0a
```

分别按稳定顺序concat全部rows后SHA256。每pair比较row count、key/score/identity SHA、exact
MultiIndex和`np.array_equal(float64)`。

整体PASS还要求14 unique pairs、0 fit、trial ledger bytes/head unchanged、CUDA-only、
input/output transactions COMMITTED、final-OOS false。本文不授权replay。
