# M6.5 有界修复变更设计 v35

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v34；历史版本与失败审查保留。

## 1. Exact immutable bundle

v35 不继承 v34 的欠定义段。唯一规范集：

| role | file | SHA256 |
| --- | --- | --- |
| capacity | `capacity_reservation_protocol_v6.md` | `a2e2d563445a033d41b28d21328563fe12bce9b4caabd14672ce54fb110459fb` |
| transaction recovery | `nested_directory_recovery_v2.md` | `a712b0094ae1571027e0c92bd9b92a68ce3aa5708d47b5cdbc2343ba834b1bd7` |
| authority generation | `run_authority_generation_v5.md` | `71c796270908598af7aab1b5c10aaf9fc65a4db76a244b47c1b006adad0b052c` |
| M7 qualification design | `m7_change_design_v13.md` | `e907d9216334fbb00c6a0c1827bcc493c4a8c424e9c56508d890bb09bf1f37fd` |
| behavior matrix | `m7_behavior_to_test_matrix_v13.md` | `b23c66b4edb64c0d7f43cfa081e71632fd1c2cacb593b4065c6f15b584bb1f33` |

任何文件 hash 漂移使整个 bundle STALE。M6.5 只允许实现 matrix 的
`M6.5_CONTRACT_ONLY`测试与合成 fixtures；真实 authority/qualification/replay/fit均未授权。

## 2. Capacity and immutable transaction closure

Capacity V6 与 Nested Recovery V2 共同冻结：

- expected bytes/files/directories/entries 必须等于 sealed source inventory 独立重算，不允许低报；
- per-attempt及aggregate四维caps、free bytes和`f_favail` inode floor同时 admission；
- 每次目录创建、write、hardlink前后维持`next_actual<=expected<=cap`，超限在PREPARED前停止并
  owner-abort；
- fixed reservation/staging/lease/target roots与attempt-derived paths；
- reservation-local、policy-fixed upstream、target-derived transaction三类ArtifactRef slots；
- active dirs 0700，完整 RELEASED+zero staging后才seal 0550；
- fixed attempt/slot temp；只清理identical本attempt temp，unknown entry HOLD；
- receipts、PREPARED、PUBLISH_COMPLETE、sibling COMMITTED均为closed exact schemas；
- reservation→PREPARED→completion→sibling→capacity COMMITTED逐项identity/inventory equality；
- existing final必须与staging是exact `(st_dev,st_ino)` hardlink；
- malformed对象保守计费，任一维oversized orphan永久HOLD；
- PREPARED后只做same-claim recovery，永不ABORT、overwrite、delete或quarantine。

## 3. Durable authority and global budget closure

Run Authority V5 共同冻结：

- synthetic与trial registry隔离；global lock、fixed paths、连续generation、no-replace/fsync；
- generation commit的durable parent fsync是唯一activation point；
- retry只接受identical bytes，gap/duplicate/run collision/unknown entry全部HOLD；
- trial registry从M6 exact `6 candidate / 44 fit` close snapshot与ledger H0开始；
- retained purpose sequence只能`[] → [CCC] → [CCC,GATE]`，每purpose最多一次；
- CCC与Gate均要求derived contract、screening prerequisite和qualification PASS；
- FAILED、CLAIMED_INTERRUPTED、MANUAL_ABORT照常计费且无replacement；
- cumulative ceiling exact `8 candidate / 60 fit`；
- first event及每个后续event都重新验证active commit、plan cursor、upstreams和retained counts。

当前 M7 upstream fixed PASS objects 不存在，故validator只能激活
`M6_5_SYNTHETIC_TEST_ONLY`、observer-only、0/0 caps、real_fit=false authority。

## 4. Typed lifecycle closure

M7 v13 在v12 exact base上冻结：

- parser为可定位双hash ArtifactRef；
- INTEGER/FINITE_NUMBER采用唯一`QLIB_PEERLITE_CANONICAL_DECIMAL_V1`，拒绝负零、exponent、
  leading/trailing zero歧义和semantic noop；
- observations使用半开区间、same-time冲突拒绝、唯一selection；
- issuer只在receipt `verified_at`检查半开有效区间；
- evidence同时绑定artifact file SHA、record ID和record canonical SHA；
- observation逐security与sealed source row、source record SHA、LIST值及cutoff latest DELIST值
  对账；
- full Cartesian date axis在LIST observation可得前使用唯一PRE_LIST false/0 row；DELIST coverage
  仅从LIST observed_from开始；
- LIST已知后缺任何coverage直接HOLD；2023退市证券在2020选择当时null DELIST observation，
  不因final值提前剔除。

## 5. Frozen replay grain

本节完整冻结 replay identity，不依赖旧版择句。

- M6 spec file SHA：
  `469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8`
- M6 content SHA：
  `60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69`

expected 恰两份 model-level merged files：

| model | file SHA | rows |
| --- | --- | --- |
| PEERLITE_K16_MSE | `559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3` | 949014 |
| PEERLITE_K32_MSE | `008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55` | 949014 |

两份 expected exact 五列、各含exact七个nonempty folds。replay恰十四份per-fold immutable
outputs：每个`(model,fold)`唯一relative path、唯一output file SHA、exact五列，所有row
model/fold等于外层identity且只含该一个fold；不得共享model-level replay output或重复path/SHA。

outer plan恰2×7 pairs，绑定expected merged SHA、expected fold receipt file/content SHA、
checkpoint SHA、per-fold replay path/SHA；无额外/缺失/replacement。

每side先验证五列顺序，再：

1. aware datetime转Asia/Shanghai local date；naive normalize到midnight；
2. 得到canonical `YYYY-MM-DD`后才检查fold inclusive window；
3. instrument=NFC、strip不变、nonempty string，禁止数值转string；
4. score=native finite float64；
5. model/fold逐行exact；
6. unique `(date,instrument)`并按date、instrument UTF-8 bytes稳定排序。

windows：

```text
wf_2018 2018-01-09..2018-12-28
wf_2019 2019-01-09..2019-12-31
wf_2020 2020-01-09..2020-12-31
wf_2021 2021-01-11..2021-12-31
wf_2022 2022-01-11..2022-12-30
wf_2023 2023-01-10..2023-12-22
wf_2024 2024-01-09..2024-12-17
```

expected slice从merged file按已验证fold过滤；replay为singleton-fold file。投影三列后：

```text
key_row=date+"T00:00:00"||0x1f||instrument||0x0a
score_row=date+"T00:00:00"||0x1f||instrument||0x1f||float.hex||0x0a
identity_row=model||0x1f||fold||0x0a
```

比较row count、identity/key/score SHA、MultiIndex及`np.array_equal(float64)`。PASS还要求14
unique pairs、0 fit、ledger bytes/head unchanged、CUDA-only、transactions COMMITTED、
final-OOS false。

## 6. Review boundary

本轮仅请求独立 R3 design review。`PASS`也只允许进入test-design；不等于M6.5 gate PASS。
禁止真实数据、fit、replay、budget mutation、final-OOS和第七步执行。
