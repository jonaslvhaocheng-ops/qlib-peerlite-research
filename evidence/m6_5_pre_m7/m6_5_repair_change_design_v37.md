# M6.5 有界修复变更设计 v37

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v36；v36及更早canonical均为`SUPERSEDED_HISTORY`。

## 1. Exact normative bundle

### Direct

| role | path | SHA256 |
| --- | --- | --- |
| capacity | `evidence/m6_5_pre_m7/capacity_reservation_protocol_v8.md` | `de39c396b6b26f3e3be579db6ab94d5e3fc078da61adce72c46b6d97cb090b98` |
| transaction | `evidence/m6_5_pre_m7/nested_directory_recovery_v4.md` | `57a46db7a4f4e2b142efbb5bbd0b3ea2dfa461a8817c8d675fa855d9f2760632` |
| authority | `evidence/m6_5_pre_m7/run_authority_generation_v7.md` | `e41f6eaba2364bf6767c0d31684b6f3295081a36a3f2c5575bf2510d9022af6d` |
| M7 qualification | `evidence/m6_5_pre_m7/m7_change_design_v15.md` | `8ec3b876bdace09f62c323ba9c935dee3c33519f7a1dc8f14ac8276712da623a` |
| behavior matrix | `evidence/m6_5_pre_m7/m7_behavior_to_test_matrix_v15.md` | `4db214941d62962766058ee0735a23e1e7fed89e183bba21178ce6ea1bde58ac` |

### Transitive immutable bases

```text
capacity_reservation_protocol_v6.md a2e2d563445a033d41b28d21328563fe12bce9b4caabd14672ce54fb110459fb
capacity_reservation_protocol_v7.md 79696cfa6b071c29673a44fb85456b484fdbc5ee7eb28f65f8ba0abeb8717fbf
nested_directory_recovery_v2.md a712b0094ae1571027e0c92bd9b92a68ce3aa5708d47b5cdbc2343ba834b1bd7
nested_directory_recovery_v3.md 0e527f208826a99d04e92a4710887a2d10a4501dcf1bfbde82d494dd4f714f83
run_authority_generation_v5.md 71c796270908598af7aab1b5c10aaf9fc65a4db76a244b47c1b006adad0b052c
run_authority_generation_v6.md fd3f6b5b53c6c3c5d4587626953ed6a0753579e457ab0280fb06b70256346ca2
m7_change_design_v9.md ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94
m7_change_design_v10.md bfa95544be056fb7d2874a072b3feabbe15f3665064775bcdace194383917bb4
m7_change_design_v11.md 642e6e54a30c6436ae76a6da2b2e638a4fa3ac844c9f2b0f7d6dd6755e9b3add
m7_change_design_v12.md 80240e3cd0cb6c569a35f755d187f92d51437c4da25dd617242af0fd2c911130
m7_change_design_v13.md e907d9216334fbb00c6a0c1827bcc493c4a8c424e9c56508d890bb09bf1f37fd
m7_change_design_v14.md 7fa0a3798047b1427d978bdcc238f04a8afa84ff64318b1d4b9b2abcccb8100b
m7_behavior_to_test_matrix_v9.md 0088cf25f5328b4c128d42d4b51772c21648609c41bfaf419fefb19c58841d58
m7_behavior_to_test_matrix_v10.md 3dc5379980d3ac0cf20836576668ddcbe670100a2f5da4eda9a6250c4760e0a4
m7_behavior_to_test_matrix_v11.md 75bb5106313ff5d2508d03dfaf4e8a55c67a75625efadc552a6cf1431f40bf57
m7_behavior_to_test_matrix_v12.md 9df558dcb671facc1556ace0b53b9f855a67bc68fd80677dfbbf781c6f60d6d3
m7_behavior_to_test_matrix_v13.md b23c66b4edb64c0d7f43cfa081e71632fd1c2cacb593b4065c6f15b584bb1f33
m7_behavior_to_test_matrix_v14.md 641a8560ec704908976023ea2bc37b5c2e1cd1605f38872ae2a9ec5f41087c76
```

所有transitive paths相对`evidence/m6_5_pre_m7/`。任一hash漂移bundle STALE。pointer/addendum
仍仅`INFORMATIONAL_NAVIGATION`。

## 2. v36 findings closed

| finding | closure |
| --- | --- |
| logical bytes低估disk blocks | fragment/overhead/directory ceiling的physical block reservation |
| lease先用inode后admission | precreated bounded lease pool；GC内bind+reserve |
| 21与18 slots冲突 | exact 4 dirs+19 named files=`23` |
| FINAL inventory立刻过期 | PRE_SEAL→0550 SEALED→POST_CLEANUP_LINK三phase |
| final-root control ambiguity | completion改为sibling；root exact payload only |
| event ledger heads自报 | immutable entry/receipt chain及head recurrence |
| result可foreign | AuthorizedEventResult反向绑定generation/claim/event |
| issuer cycle/private registry | parent QRC external policy；anchor不含derived contract；freeze receipt |
| source resolver不闭合 | exact historical manifest/row/locator/resolver closure和clock偏序 |
| FieldRegistry欠schema | V4 exact wrapper、referential integrity |
| chmod未durable | chmod后再次fsync temp inode |
| event key collision | source ID unique且key加入seq |
| replay digest preimage丢失 | 本文件§3完整重述 |
| matrix gaps | V15新增17个独立负例 |

## 3. Frozen replay identity and digest preimages

- M6 spec file SHA：
  `469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8`
- M6 content SHA：
  `60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69`
- K16 merged SHA：
  `559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3`，
  949014 rows；
- K32 merged SHA：
  `008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55`，
  949014 rows。

expected恰2份model-level merged exact五列、各7 nonempty folds；replay恰14份唯一
singleton-fold immutable outputs。outer plan恰2×7，绑定merged/fold receipt/checkpoint/per-fold
path+SHA，无共享、重复、缺失或replacement。

每side先验证五列；aware datetime转Asia/Shanghai local date、naive normalize midnight；得到
canonical date后才检查inclusive window；instrument NFC/nonempty且禁止数值转string；score native
finite float64；model/fold逐行exact；unique key稳定排序。

```text
wf_2018 2018-01-09..2018-12-28
wf_2019 2019-01-09..2019-12-31
wf_2020 2020-01-09..2020-12-31
wf_2021 2021-01-11..2021-12-31
wf_2022 2022-01-11..2022-12-30
wf_2023 2023-01-10..2023-12-22
wf_2024 2024-01-09..2024-12-17
```

投影后逐行preimage exact：

```text
key_row=date+"T00:00:00"||0x1f||instrument||0x0a
score_row=date+"T00:00:00"||0x1f||instrument||0x1f||float.hex(score)||0x0a
identity_row=model||0x1f||fold||0x0a
```

key/score/identity SHA分别为按稳定顺序concat全部对应rows后的SHA256。比较row count、三SHA、
MultiIndex及`np.array_equal(float64)`。PASS还要求14 unique pairs、0 fit、ledger bytes/head
unchanged、CUDA-only、transactions COMMITTED、final-OOS false。

## 4. Authorization boundary

当前M6 PASS、M6.5仍待独立review、M7 NOT_RUN。即便v37 design PASS，也只允许进入test-design。
禁止训练、真实数据、fit、replay、budget mutation、final-OOS和第七步执行。
