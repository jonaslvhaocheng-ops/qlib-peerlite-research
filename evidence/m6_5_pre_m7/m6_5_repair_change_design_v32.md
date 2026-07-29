# M6.5 有界修复变更设计 v32

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v31；历史版本与失败审查保留。

## 1. Exact composition

base为v31 exact SHA：

```text
f83f2b51861c55f2abd96b051ef6e5546a43c5eff47128aa69c4125f9c28ca87
```

| v31 | v32 |
| --- | --- |
| §1 | 本文件§1完整替换 |
| §2 | 本文件§2完整替换 |
| §3全部 | 本文件§3完整替换 |
| §4全部 | 本文件§4完整替换 |
| §5.1 | 逐字保留 |
| §5.2 | 本文件§5完整替换 |
| §6 | 本文件§6完整替换 |
| §7 | 本文件§7完整替换 |

v31未替换的normative ancestry继续有效；无“其余字段”或隐式段落选择。v32不授权产品实现、
server replay、M7、fit、budget变更或final-OOS。

## 2. Official/AP/lifecycle qualification V10

完整规范为本文件§6绑定的M7 v10：

1. `WholeRecordFieldAdapterV1`固定one-record-per-field raw grain、LP raw key、sample ID、payload、
   available/revision/universe clocks，并把supplement entry与changed raw_key一对一；
2. official request只使用原十slots，`parameters`绑定adapter和source/lifecycle/policy hashes；
3. `AuxPrefixInvocationV3`及六个`PrefixProductManifestV1` strict绑定official original/probe
   snapshots、T、projection policy、root source manifests和非空records；
4. verifier从official snapshots/source/supplement/lifecycle authority独立重建expected axes，
   不信manifest自报；
5. official baseline/probe CSV逐侧重建state records，并分别与state product的count/key/value/
   logical digest exact相等；official receipt expected keys也从独立axis重算；
6. exact AP001–AP005、三products 15 equality及全部crosscheck必须PASS/true；
7. lifecycle V2冻结无环role DAG、sealed md_security source projection、两种exact vendor evidence、
   row locator/hash、availability rows、calendar 09:30边界、60-session listing和全
   security×prediction-date SLA006 replay。

security lifecycle fixed slot当前仍不存在，所以本轮只允许negative fail-closed validator，不能
创建真实qualification。

## 3. CapacityReservationV3

### 3.1 State, locks and charge

append-only paths仍为：

```text
staging-reservations/<attempt_id>/
  RESERVED.json
  MATERIALIZING.json
  COMMITTED.json | ABORTED.json
  RELEASED.json
```

exact legal chains：

```text
RESERVED -> MATERIALIZING -> COMMITTED -> RELEASED
RESERVED -> ABORTED -> RELEASED
RESERVED -> MATERIALIZING -> ABORTED -> RELEASED
```

所有initial create、same-attempt resume、abort和recovery统一：

1. 先独占取得`attempt lease`；
2. 再取得`GC lock`；
3. 验证或发布reservation state；
4. 释放GC lock，但attempt lease从admission前一直持有到terminal及cleanup完成；
5. 无法取得attempt lease的进程不得创建/写staging、PREPARED、final或state。

需要target publication检查时再按第三层取得`target parent publish lock`；全局顺序固定
`attempt lease -> GC lock -> parent publish lock`。任何路径不得反序。正常publish只持attempt
lease→parent lock，释放parent lock后才可重新取得GC lock，绝不在parent lock内等待GC。

runtime policy固定per-attempt cap、aggregate threshold和minimum free bytes。expected在创建
staging前精确计算；actual不得超过expected。GC admission no-follow扫描所有reservations/staging。

只有`RELEASED`通过§3.2完整验证的attempt才免计费；其他全部：

```text
active_charge=max(RESERVED.expected_logical_bytes, actual_staging_logical_bytes)
```

无reservation orphan按actual计费并HOLD。aggregate和statvfs outstanding-reservation公式沿用v31
§3.2；新RESERVED在同一GC临界区发布，所以并发不可超卖。

### 3.2 RELEASED validation

scanner在免计费前必须重算完整chain：

- RESERVED存在且schema/hash/source inventory/target/path有效；
- MATERIALIZING若chain要求则正确绑定RESERVED；
- COMMITTED与ABORTED恰一存在并绑定合法前态；
- COMMITTED路径必须绑定并复核sibling COMMITTED；
- ABORTED必须绑定同临界区absence receipt；
- RELEASED绑定terminal、cleanup receipt和private staging root empty/absent；
- 当前private staging no-follow扫描必须0 entries/0 logical bytes。

任一unknown key、hash断链、非法双terminal、cleanup receipt错、RELEASED孤立或staging非空：
不免计费，按active_charge计入并HOLD；不能因一个文件名为RELEASED就释放容量。

### 3.3 Owner abort atomic absence proof

owner abort只允许在MATERIALIZING之前或之后但PREPARED尚未发布。持有attempt lease和GC lock后，
取得target parent publish lock；在**同一三锁临界区**从parent/root directory FDs no-follow验证：

```text
.<target>.PREPARED.json       ENOENT
<target>/                     ENOENT
<target>/PUBLISH_COMPLETE.json ENOENT（由target root ENOENT蕴含并显式记录）
.<target>.COMMITTED.json      ENOENT
```

absence receipt exact绑定parent device/inode、四个relative names、每次`fstatat(...,
AT_SYMLINK_NOFOLLOW)` result/errno、RESERVED/MATERIALIZING SHA、target/policy/invocation SHA和
lock identities。若任一存在或检查不稳定，禁止ABORT/cleanup，转same-claim recovery或HOLD。

在锁内no-replace发布ABORTED后释放parent lock；仍持attempt lease+GC执行private-root
directory-only chmod、no-follow unlink/rmdir。禁止chmod/truncate/write regular files。zero-entry
receipt后发布RELEASED。crash可按同锁序重入。sibling存在而root异常缺失时一定HOLD，不删staging。

### 3.4 Commit cleanup and orphan recovery

PREPARED存在后永不ABORT，只能v31继承的nested transaction recovery至COMMITTED/HOLD。sibling
COMMITTED完整验证后发布reservation COMMITTED，再做unlink-only cleanup，成功才RELEASED；
失败继续计费并可重入。

无reservation orphan只有在取得其attempt lease+GC+parent lock并产生§3.3四路径absence receipt后，
才可创建synthetic RESERVED→ABORTED并清理；否则保持charge/HOLD。不按age/PID推断，不处理final
tree或其他root。

## 4. Authority generation closed schemas

### 4.1 RegistrationV3

strict object只允许：

```json
{
  "schema_version": "qlib_peerlite_run_registration_v3",
  "generation_number": "<positive decimal ASCII>",
  "previous_generation_commit_sha256": "sha256:<64hex> or null for generation 1",
  "authority_file": {
    "path": "<generation-root>/authority.json",
    "sha256": "sha256:<64hex>"
  },
  "generation_root": "<fixed relative path>",
  "run_id": "<ASCII>",
  "linear_event_plan_sha256": "sha256:<64hex>",
  "roots": {
    "journal": "<fixed relative path>",
    "snapshot": "<fixed relative path>",
    "output": "<fixed relative path>"
  },
  "ledger_h0": "sha256:<64hex>",
  "m6_prefix": {
    "candidate_evaluations": "6",
    "model_fits": "44",
    "binding_sha256": "sha256:<64hex>"
  },
  "issuer_policy_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

unknown/null（声明允许处除外）/float拒绝。canonical hash排除自身。registration不绑定current
commit/activation receipt/root inventory。

### 4.2 AuthorityGenerationCommitV3

strict object：

```json
{
  "schema_version": "qlib_peerlite_authority_generation_commit_v3",
  "generation_number": "<positive decimal ASCII>",
  "previous_generation_commit_sha256": "sha256:<64hex> or null for generation 1",
  "registration": {
    "path": "<generation-root>/registration.json",
    "sha256": "sha256:<64hex>"
  },
  "authority_file": {
    "path": "<generation-root>/authority.json",
    "sha256": "sha256:<64hex>"
  },
  "run_id": "<ASCII>",
  "linear_event_plan_sha256": "sha256:<64hex>",
  "prior_terminal": {
    "path": "<prior-generation>/run-terminal.json",
    "sha256": "sha256:<64hex>",
    "status": "CLOSED|ABANDONED"
  },
  "ledger_h0": "sha256:<64hex>",
  "m6_prefix": {
    "candidate_evaluations": "6",
    "model_fits": "44",
    "binding_sha256": "sha256:<64hex>"
  },
  "issuer_policy_sha256": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

generation 1的`prior_terminal`必须是JSON null；之后必须是exact object。commit各字段与registration
及registry predecessor exact一致；canonical hash排除自身。global registry no-replace commit是
唯一activation。

### 4.3 ActivationReceiptV2

optional strict downstream receipt：

```json
{
  "schema_version": "qlib_peerlite_generation_activation_receipt_v2",
  "generation_commit": {"path": "<registry path>", "sha256": "sha256:<64hex>"},
  "registration_sha256": "sha256:<64hex>",
  "observed_registry_head_sha256": "sha256:<64hex>",
  "verified_at": "<UTC RFC3339 Z>",
  "canonical_sha256": "sha256:<64hex>"
}
```

commit/registration不反向绑定receipt。不存在authority-root hash、隐式字段或自引用。

## 5. ScoreReplayCanonicalV2：冻结五列身份后投影

### 5.1 Bound historical inputs

M6 execution spec file SHA：
`469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8`，
content SHA：
`60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69`。

expected candidates exact：

| model | candidate receipt file SHA | prediction SHA | rows |
| --- | --- | --- | --- |
| PEERLITE_K16_MSE | `406e5710f8af13bc58c42401a5985209915728cfe8ef61d2690d6ef17334ccf8` | `559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3` | 949014 |
| PEERLITE_K32_MSE | `ebb32c7ee01b80b9c07703eac357c8cd23cc9d089437f594750bec75569c8503` | `008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55` | 949014 |

每个expected/replay artifact必须exact五列顺序：

```text
datetime,instrument,score,model_id,fold_id
```

禁止额外/缺失列或静默drop。model artifact内`model_id`必须逐行等于外层model；fold exact集合：
`wf_2018`…`wf_2024`，各非空、无额外。

test date windows exact：

```text
wf_2018 2018-01-09..2018-12-28
wf_2019 2019-01-09..2019-12-31
wf_2020 2020-01-09..2020-12-31
wf_2021 2021-01-11..2021-12-31
wf_2022 2022-01-11..2022-12-30
wf_2023 2023-01-10..2023-12-22
wf_2024 2024-01-09..2024-12-17
```

每row date必须在其fold window；每个model恰七fold。outer replay plan绑定2×7唯一
`(model_id,fold_id)`、对应checkpoint SHA、fold receipt path/file/content SHA、expected
prediction artifact SHA和new replay output SHA；无重复/缺失/替换。

### 5.2 Per-fold canonical projection

完成五列schema/model/fold/window身份校验后，才按当前外层`(model,fold)`过滤并显式投影
`datetime,instrument,score`。两侧完全相同地：

1. datetime aware值转`Asia/Shanghai`后取local calendar date并表示为naive midnight；naive值
   直接normalize到midnight；
2. instrument必须是NFC、strip前后不变、non-empty UTF-8 string，禁止数值隐式转string；
3. score转native-endian IEEE-754 float64，null/NaN/±Inf拒绝；
4. `(datetime,instrument)` unique；按datetime、instrument UTF-8 bytes稳定升序；
5. timestamp固定`YYYY-MM-DDT00:00:00`。

逐row：

```text
key_row =
  timestamp_ascii || 0x1f || instrument_utf8 || 0x0a
score_row =
  timestamp_ascii || 0x1f || instrument_utf8 || 0x1f
  || float64_value.hex().ascii || 0x0a
key_digest   = sha256(concat(key_row))
score_digest = sha256(concat(score_row))
```

model/fold身份另计算：

```text
identity_row = model_id UTF-8 || 0x1f || fold_id UTF-8 || 0x0a
identity_digest = sha256(concat(identity_row))
```

expected/replay必须row count、identity/key/score digests、MultiIndex及float64 arrays全部exact。
PASS要求exact 14个唯一pair、0 fit、ledger bytes/head unchanged、所有max date<C、CUDA-only、
transactions COMMITTED、final-OOS false；不能重复同一fold凑14。

## 6. 当前 M7 v10 bundle

- `m7_change_design_v10.md`
  SHA `bfa95544be056fb7d2874a072b3feabbe15f3665064775bcdace194383917bb4`
- `m7_behavior_to_test_matrix_v10.md`
  SHA `3dc5379980d3ac0cf20836576668ddcbe670100a2f5da4eda9a6250c4760e0a4`

v10只增强M6.5 contract-only qualification设计；Gate/CCC/预算/first-event/M7未授权边界沿用v9。

## 7. v31 review closure

| v31 blocker | v32 closure |
| --- | --- |
| M6 five-column/fold串包 | §5五列identity、exact 2×7、窗口/receipt/prediction SHA后投影 |
| AP input/coverage/crosscheck | §2 + M7 v10 §3 closed invocation/manifests/nonempty axes/AP005 |
| attempt lease/abort publish lock | §3.1/§3.3统一锁序与四路径atomic absence |
| malformed RELEASED免计费 | §3.2完整chain+zero staging才免计 |
| generation隐式字段 | §4三个strict schemas，无旧段引用 |
| lifecycle evidence/session/role DAG | M7 v10 §4 exact source/evidence/locator/09:30/SLA006/acyclic roles |
| whole-record future poison | M7 v10 §2 one-record-per-field adapter |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。这不是M6.5 PASS；不授权实现、replay或M7。
