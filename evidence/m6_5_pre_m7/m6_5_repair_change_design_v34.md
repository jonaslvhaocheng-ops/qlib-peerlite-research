# M6.5 有界修复变更设计 v34

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v33；历史版本与失败审查保留。

## 1. Exact composition

base为v33 SHA
`3db1bb4f576f0b6a557a014185c126b067395a07522cf38ee9f610595b8808d7`。

| v33 | v34 |
| --- | --- |
| §1 | 本文件§1 |
| §2–§4全部 | 本文件§2–§4 |
| §5全部 | 逐字保留 |
| §6 | 本文件§5 |
| §7 | 本文件§6 |

v34把capacity、nested recovery和authority generation拆为三个exact-SHA独立规范；不再依赖任何
被替换段。v33 §5的两merged expected+十四per-fold replay及canonical-date-before-window完整
保留。不授权实现、replay、M7、fit、budget或final-OOS。

## 2. Capacity and PREPARED recovery

唯一capacity规范：

- `capacity_reservation_protocol_v5.md`
- SHA `88a89838f6df0b85930fadcadb966fb44e969c2d6ef9a8b8feaae2e8fe4bb7f4`

唯一PREPARED后recovery规范：

- `nested_directory_recovery_v1.md`
- SHA `c353228c7778d85dc114045b35b70aad5ca3c3f94d4beb3925241f5017cd28d1`

两者共同冻结：

- active dirs 0700，RELEASED全链fsync后才seal 0550；
- fixed marker/receipt slots；
- ArtifactRef同时区分file/canonical SHA；
- runtime policy固定reservation/staging/lease/target roots的path/device/inode；
- attempt-derived唯一staging/lease paths与root separation；
- malformed/missing RESERVED按cap保守计费；
- oversized orphan永久HOLD；
- PREPARED后完整same-claim recovery，永不abort。

M6.5实现必须逐字采用这两个规范；不能从v33 §3择句。

## 3. Run authority and generation

唯一规范：

- `run_authority_generation_v4.md`
- SHA `3e2d106b944f2aebfab72422b8a74f53f271aae12e601f2e98bb4c73808fe44d`

它自包含safe IDs、plan ArtifactRef、purpose/event/caps matrix、RunAuthorityV4、
RegistrationV4、GenerationCommitV4、ActivationReceiptV3、authority→registration equality及
全role DAG。

当前M6.5只接受synthetic purpose、SYNTHETIC_OBSERVER-only plan、0 candidate/fit caps、
real_fit=false。M7 upstream slots不存在，所以M7 purpose仍拒绝。

## 4. M7 qualification v12

- `m7_change_design_v12.md`
  SHA `80240e3cd0cb6c569a35f755d187f92d51437c4da25dd617242af0fd2c911130`
- `m7_behavior_to_test_matrix_v12.md`
  SHA `9df558dcb671facc1556ace0b53b9f855a67bc68fd80677dfbbf781c6f60d6d3`

v12冻结typed semantic poison、versioned field observations、null→date DELIST历史、全部lifecycle
wrapper schemas、issuer evidence key/value/logical projection和full SLA006。

qualified positive path要求DELIST observation intervals连续覆盖；2023退市证券在2020使用当时
null observation并保持active（若listing eligible）。缺历史coverage直接HOLD，不能从final value
倒推。

## 5. Bound companion set

```text
canonical v34
capacity reservation v5
nested recovery v1
run authority generation v4
M7 v12
M7 matrix v12
```

上述SHA形成唯一bundle。M6.5只实现matrix中contract-only项；真实authority/qualification/replay/
fit均未授权。

## 6. v33 closure

| v33 finding | closure |
| --- | --- |
| active 0550/receipt locator/hash domain | capacity v5 §1–§4 |
| staging/lease identity | capacity v5 §1 derived roots/paths |
| oversized orphan | capacity v5 §5 permanent HOLD |
| PREPARED recovery悬空 | nested recovery v1 full state machine |
| authority-registration mismatch/plan locator | authority generation v4 §§1–4 |
| purpose/event/caps conflict | authority generation v4 §2 |
| plan/downstream回边 | safe IDs + full role DAG |
| typed semantic poison | M7 v12 §2 |
| future delist historical exclusion | versioned observation history + full coverage |
| lifecycle wrappers/issuer/SLA digest | M7 v12 §3 exact objects/projections |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。仍不是M6.5 PASS，不授权测试设计之后的动作。
