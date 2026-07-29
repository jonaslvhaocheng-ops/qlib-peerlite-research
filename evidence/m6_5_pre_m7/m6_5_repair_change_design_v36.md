# M6.5 有界修复变更设计 v36

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v35；v35及更早版本均为`SUPERSEDED_HISTORY`，非normative base。

## 1. Exact normative bundle

### 1.1 Direct specifications

| role | path | SHA256 |
| --- | --- | --- |
| capacity | `evidence/m6_5_pre_m7/capacity_reservation_protocol_v7.md` | `79696cfa6b071c29673a44fb85456b484fdbc5ee7eb28f65f8ba0abeb8717fbf` |
| transaction | `evidence/m6_5_pre_m7/nested_directory_recovery_v3.md` | `0e527f208826a99d04e92a4710887a2d10a4501dcf1bfbde82d494dd4f714f83` |
| authority | `evidence/m6_5_pre_m7/run_authority_generation_v6.md` | `fd3f6b5b53c6c3c5d4587626953ed6a0753579e457ab0280fb06b70256346ca2` |
| M7 qualification | `evidence/m6_5_pre_m7/m7_change_design_v14.md` | `7fa0a3798047b1427d978bdcc238f04a8afa84ff64318b1d4b9b2abcccb8100b` |
| behavior matrix | `evidence/m6_5_pre_m7/m7_behavior_to_test_matrix_v14.md` | `641a8560ec704908976023ea2bc37b5c2e1cd1605f38872ae2a9ec5f41087c76` |

### 1.2 Transitive immutable bases

| path | SHA256 |
| --- | --- |
| `evidence/m6_5_pre_m7/capacity_reservation_protocol_v6.md` | `a2e2d563445a033d41b28d21328563fe12bce9b4caabd14672ce54fb110459fb` |
| `evidence/m6_5_pre_m7/nested_directory_recovery_v2.md` | `a712b0094ae1571027e0c92bd9b92a68ce3aa5708d47b5cdbc2343ba834b1bd7` |
| `evidence/m6_5_pre_m7/run_authority_generation_v5.md` | `71c796270908598af7aab1b5c10aaf9fc65a4db76a244b47c1b006adad0b052c` |
| `evidence/m6_5_pre_m7/m7_change_design_v9.md` | `ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94` |
| `evidence/m6_5_pre_m7/m7_change_design_v10.md` | `bfa95544be056fb7d2874a072b3feabbe15f3665064775bcdace194383917bb4` |
| `evidence/m6_5_pre_m7/m7_change_design_v11.md` | `642e6e54a30c6436ae76a6da2b2e638a4fa3ac844c9f2b0f7d6dd6755e9b3add` |
| `evidence/m6_5_pre_m7/m7_change_design_v12.md` | `80240e3cd0cb6c569a35f755d187f92d51437c4da25dd617242af0fd2c911130` |
| `evidence/m6_5_pre_m7/m7_change_design_v13.md` | `e907d9216334fbb00c6a0c1827bcc493c4a8c424e9c56508d890bb09bf1f37fd` |
| `evidence/m6_5_pre_m7/m7_behavior_to_test_matrix_v9.md` | `0088cf25f5328b4c128d42d4b51772c21648609c41bfaf419fefb19c58841d58` |
| `evidence/m6_5_pre_m7/m7_behavior_to_test_matrix_v10.md` | `3dc5379980d3ac0cf20836576668ddcbe670100a2f5da4eda9a6250c4760e0a4` |
| `evidence/m6_5_pre_m7/m7_behavior_to_test_matrix_v11.md` | `75bb5106313ff5d2508d03dfaf4e8a55c67a75625efadc552a6cf1431f40bf57` |
| `evidence/m6_5_pre_m7/m7_behavior_to_test_matrix_v12.md` | `9df558dcb671facc1556ace0b53b9f855a67bc68fd80677dfbbf781c6f60d6d3` |
| `evidence/m6_5_pre_m7/m7_behavior_to_test_matrix_v13.md` | `b23c66b4edb64c0d7f43cfa081e71632fd1c2cacb593b4065c6f15b584bb1f33` |

任一direct或transitive hash漂移，bundle STALE。compatibility addendum和control pointer仅为
`INFORMATIONAL_NAVIGATION`，不进入normative bundle。

## 2. v35 findings closed

| finding | v36 closure |
| --- | --- |
| PREPARED预报未来directory inode | device/inode-free PayloadLogicalManifest；final inventory只在建成后观察 |
| 0.x金融小数被拒绝 | v14 exact grammar和正反例 |
| event ledger/digests不闭合 | authority v6 closed claim/outcome/terminal schemas和digest preimages |
| issuer time可回填 | 取消self-time claim；contract-bound append-only trust anchor |
| inventory slots不固定 | capacity v7四个exact slots |
| temp crash recovery | capacity v7完整七行state table；所有publish复用 |
| transient/control capacity漏算 | payload/filesystem分离，2 roots+21 controls worst-case reservation |
| source→staging→final可subset | inode-free path/type/size/content exact bijection |
| parser closure未绑定 | v14 closure manifest、imports/native/interpreter/env/domain table |
| historical source lineage缺失 | evidence v2逐record绑定snapshot/locator/hash/source clocks |
| orphan registration | generation全量scan、每generation唯一registration |
| matrix粒度宽 | v14逐攻击fixture+decision point+zero-side-effect |
| pointer composition冲突 | v36 direct+transitive exact table；pointer只导航 |

## 3. Capacity and transaction invariant

对logical payload `F,D,E,B`：

```text
filesystem_new_inodes_reserved = F + 2*(D+1) + 21
filesystem_new_entries_reserved = 2*(E+1) + 21
filesystem_new_bytes_reserved = B + CONTROL_BYTE_CEILING
```

`21`覆盖staging wrapper、reservation/receipts/inventories dirs、合法chain最大finals、receipts、
inventories、lease、publish lock、transaction finals及两侧同时存在的temps。sealed RELEASED
metadata继续按实际filesystem usage计费；empty payload仍预留2 roots+21 control。admission与
floor deduction在同一capacity lock线性化。

source revalidation、staging physical、payload logical、final physical通过同一logical
projection exact bijection；PREPARED不含未来directory inode。regular final只接受与staging
exact hardlink inode。

## 4. Authority and lifecycle invariant

M7 trial budget按durable generation commit一次性永久预留整个plan caps：

```text
M6 close 6/44
→ CCC commit 7/52
→ Gate commit 8/60
```

失败、中断、人工终止或从未claim均不释放，purpose无replacement。commit是唯一activation；
registration每generation恰一，claim一event恰一，terminal event partition可独立重算。
CCC与Gate均要求完整PASS qualification；当前这些upstream不存在，所以M7仍拒绝。

parser closure、issuer trust anchor、historical source records及PRE_LIST/null→date semantics由
M7 v14严格绑定。任何unbound dependency、backdated self-time、wrong source locator/hash、
clock inversion或cutoff final mismatch均在qualification前HOLD。

## 5. Frozen replay identity

- M6 spec file SHA：
  `469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8`
- M6 spec content SHA：
  `60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69`
- expected merged：
  - K16 SHA `559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3`,
    949014 rows；
  - K32 SHA `008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55`,
    949014 rows。

expected恰两份model-level merged exact五列且各含7 nonempty folds；replay恰14份唯一
singleton-fold immutable outputs。outer plan恰2×7，绑定merged/fold receipt/checkpoint/per-fold
path+SHA，无共享、重复、缺失或replacement。

每side先验证五列，再把aware datetime转Asia/Shanghai local date、naive normalize midnight，
得到canonical date后才检查inclusive window；instrument NFC/nonempty/不做数值转string；
score native finite float64；model/fold逐行exact；unique key并稳定排序。

```text
wf_2018 2018-01-09..2018-12-28
wf_2019 2019-01-09..2019-12-31
wf_2020 2020-01-09..2020-12-31
wf_2021 2021-01-11..2021-12-31
wf_2022 2022-01-11..2022-12-30
wf_2023 2023-01-10..2023-12-22
wf_2024 2024-01-09..2024-12-17
```

比较row count、identity/key/score SHA、MultiIndex及`np.array_equal(float64)`。PASS还要求
14 unique pairs、0 fit、ledger bytes/head unchanged、CUDA-only、transactions COMMITTED、
final-OOS false。

## 6. Authorization boundary

本轮仅请求独立R3 design review。通过后仅进入test-design。当前只允许未来实现
M6.5 contract-only synthetic tests；禁止真实数据、fit、replay、budget mutation、final-OOS和
第七步执行。
