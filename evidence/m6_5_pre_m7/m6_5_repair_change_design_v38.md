# M6.5 有界修复变更设计 v38

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v37；旧canonical均为`SUPERSEDED_HISTORY`。

## 1. Exact bundle

Direct：

```text
capacity_reservation_protocol_v9.md 32f6110dd10c7b6e80da922a8c934ba4032548e97528f88ea4bb6a61599d025f
nested_directory_recovery_v4.md 57a46db7a4f4e2b142efbb5bbd0b3ea2dfa461a8817c8d675fa855d9f2760632
run_authority_generation_v8.md c5772d9f298ac6a3833fc0206f06844cffb3a7d5aa9cedf38e02d0c13d5c888e
m7_change_design_v16.md 637b167fdb651f10112971a0b4d41c86e9f5f868d427429bc6dda01e3857a978
m7_behavior_to_test_matrix_v16.md 40767b2765d5e7e1a9b37acc8d232108275af5170b82d7d870443e23f65c7a4e
```

Transitive：

```text
capacity_reservation_protocol_v6.md a2e2d563445a033d41b28d21328563fe12bce9b4caabd14672ce54fb110459fb
capacity_reservation_protocol_v7.md 79696cfa6b071c29673a44fb85456b484fdbc5ee7eb28f65f8ba0abeb8717fbf
capacity_reservation_protocol_v8.md de39c396b6b26f3e3be579db6ab94d5e3fc078da61adce72c46b6d97cb090b98
nested_directory_recovery_v2.md a712b0094ae1571027e0c92bd9b92a68ce3aa5708d47b5cdbc2343ba834b1bd7
nested_directory_recovery_v3.md 0e527f208826a99d04e92a4710887a2d10a4501dcf1bfbde82d494dd4f714f83
run_authority_generation_v5.md 71c796270908598af7aab1b5c10aaf9fc65a4db76a244b47c1b006adad0b052c
run_authority_generation_v6.md fd3f6b5b53c6c3c5d4587626953ed6a0753579e457ab0280fb06b70256346ca2
run_authority_generation_v7.md e41f6eaba2364bf6767c0d31684b6f3295081a36a3f2c5575bf2510d9022af6d
m7_change_design_v9.md ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94
m7_change_design_v10.md bfa95544be056fb7d2874a072b3feabbe15f3665064775bcdace194383917bb4
m7_change_design_v11.md 642e6e54a30c6436ae76a6da2b2e638a4fa3ac844c9f2b0f7d6dd6755e9b3add
m7_change_design_v12.md 80240e3cd0cb6c569a35f755d187f92d51437c4da25dd617242af0fd2c911130
m7_change_design_v13.md e907d9216334fbb00c6a0c1827bcc493c4a8c424e9c56508d890bb09bf1f37fd
m7_change_design_v14.md 7fa0a3798047b1427d978bdcc238f04a8afa84ff64318b1d4b9b2abcccb8100b
m7_change_design_v15.md 8ec3b876bdace09f62c323ba9c935dee3c33519f7a1dc8f14ac8276712da623a
m7_behavior_to_test_matrix_v9.md 0088cf25f5328b4c128d42d4b51772c21648609c41bfaf419fefb19c58841d58
m7_behavior_to_test_matrix_v10.md 3dc5379980d3ac0cf20836576668ddcbe670100a2f5da4eda9a6250c4760e0a4
m7_behavior_to_test_matrix_v11.md 75bb5106313ff5d2508d03dfaf4e8a55c67a75625efadc552a6cf1431f40bf57
m7_behavior_to_test_matrix_v12.md 9df558dcb671facc1556ace0b53b9f855a67bc68fd80677dfbbf781c6f60d6d3
m7_behavior_to_test_matrix_v13.md b23c66b4edb64c0d7f43cfa081e71632fd1c2cacb593b4065c6f15b584bb1f33
m7_behavior_to_test_matrix_v14.md 641a8560ec704908976023ea2bc37b5c2e1cd1605f38872ae2a9ec5f41087c76
m7_behavior_to_test_matrix_v15.md 4db214941d62962766058ee0735a23e1e7fed89e183bba21178ce6ea1bde58ac
```

所有paths相对`evidence/m6_5_pre_m7/`；任一hash漂移STALE。pointer/addendum non-normative。

## 2. v37 closure

- 所有roots和target parents强制同一device，scanner明确遍历完整集合；blocks按inode去重；
- lease pool identity直接进入唯一RESERVED activation，不再有双final crash gap；
- control exact 4 dirs+18 files=22；logical paths的staging inode必须一一唯一、初始nlink=1；
- event execution使用precreated per-event flock、lease object和owner token；claim-before-START无
  cancel/retry分支；
- result kind/schema/path/run/model/fold/seed/checkpoint均由event type唯一决定；
- trusted issuer policy SHA/root/validator/parent authorization只能由request外CLI输入；
- issuer registration/commit/freeze receipt均closed schema、prefix-safe head和durable publication；
- sandbox禁止spawn/fork/exec/subprocess/dynamic code，并由supervisor出具observed closure receipt；
- historical source改为field-revision grain，LIST/DELIST各自vendor clock，完整
  vendor→source→snapshot→observation偏序；
- evidence V3和row digest preimages完整冻结。

## 3. Replay identity

M6 spec file/content：

```text
469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8
60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69
```

expected恰2份merged exact五列：K16
`559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3`和K32
`008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55`，各949014 rows、7
nonempty folds。replay恰14 singleton-fold immutable outputs；outer plan恰2×7，无共享/重复/
缺失/replacement。

canonical date在window检查前生成；windows保持2018-01-09..2018-12-28至
2024-01-09..2024-12-17七段。instrument NFC/nonempty，score native finite float64，model/fold
逐行exact，unique key稳定排序。

```text
key_row=date+"T00:00:00"||0x1f||instrument||0x0a
score_row=date+"T00:00:00"||0x1f||instrument||0x1f||float.hex(score)||0x0a
identity_row=model||0x1f||fold||0x0a
```

分别concat后SHA256；比较row count、三SHA、MultiIndex、`np.array_equal(float64)`，并要求14
unique pairs、0 fit、ledger unchanged、CUDA-only、transactions COMMITTED、final-OOS false。

## 4. Boundary

设计PASS只允许进入test-design。当前M6 PASS、M6.5待审、M7 NOT_RUN；禁止训练、真实数据、
fit、replay、budget mutation、final-OOS和第七步执行。
