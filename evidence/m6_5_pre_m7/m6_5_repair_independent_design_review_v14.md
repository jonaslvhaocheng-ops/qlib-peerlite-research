# M6.5 canonical v17 / change design v14 独立 R3 设计审查

## Findings

### [P1] A 的 pre-M7 replay authority 与 P 的版本化 policy schema 未闭合，P 也没有约束 R/V 的 output schema

**Section：** `architecture_confirmation_v17.md` §1（24–59 行）、§2（76–80、119–140 行）；`m6_5_repair_change_design_v14.md` §1–2（14–54 行）；retained `architecture_confirmation_v14.md` §2–3（15–43 行）和 retained `m6_5_repair_change_design_v12.md` §1（11–20 行）。

**Scenario：** v17 的图以 “P + activated replay-control profile” 开始，A 又持有 typed activation-profile 与 control-plane-policy refs，但未定义这两个 replay-only object 的 schema/role、producer、fixed selection slot、ACL 或 activation lifecycle。当前 retained architecture 中定义了这类 policy/profile 的对象是 `M7ControlPlanePolicy v1` 和 `M7RunControlProfile v1`，它们位于 QRC → authority → activation 的 M7 graph；`docs/STATUS.md` 明确禁止在 M6.5 gate 通过前派生或启动 M7。若 implementation 借用这些 M7 objects，则 M6 archival replay 反向依赖被封存的 M7 authority；若临时新增“replay-control profile”，它又成为无 typed producer 的自由 authority selector。

同一版本问题存在于 P。v17 把 P 指定为 existing `ReplayOutputNamespace v1`，同时读取 `P.parent_components`、`P.resolver_profile`、exact created-root owner/gid/mode/access-ACL/default-ACL policy。保留的 P v1 field list 只有 logical namespace、control-root-relative parent、owner/mode/POSIX ACL、writer、`0700`、allowed output schema 和 no-reuse；它没有这些新字段。v17 自身要求 same-name/different-schema 和 implicit upgrade fail closed，因此实现不能合法地把 P v1 静默当作新 schema 使用。

最后，v17 只要求 `R.required_output_schema_ref == V.required_output_schema_ref`，没有要求该 schema 等于 P 的 allowed output schema。于是一个 P=`schema0`、R/V=`schema1` 的 composite 可满足现有列出的 A/B/R/V equations，并在 name/root/ACL checks 都通过后写出 policy 未允许的 output。

**Impact：** 这不是 hostile host 或 supervisor compromise：普通 deployment/configuration error 已迫使实现者在隐式激活 M7 authority、接受无 producer 的 replay profile、静默升级 P v1 或忽略 P 的 schema policy 之间自行选择。当前 acceptance contract 无法拒绝这些组合，M6/M7 isolation、root selection 和 P/A/B/R/V 的 output authority 均没有冻结，属于 architecture P1。

**Evidence：**

- v17 28、47–59 行使用 active replay profile/policy，但没有声明对应 replay-only schema/role/producer；retained v14 15–43 行的已定义 control policy/profile 均由 M7 QRC/authority activation 产生。
- v17 79、134–139 行要求 P 的 component/resolver/created-root policy；retained v12 11 行和 v15 13 行给出的 P v1 closed field list 不含这些字段。
- v17 137–140 行缺少 `P.allowed_output_schema_ref == R.required_output_schema_ref == V.required_output_schema_ref`（或 P allowlist membership）的 phase invariant。

**Direction：** 在 A 前定义独立、M6-only 的 replay control policy/profile：精确 typed role/schema/bytes、verified M6 close/proof 的固定 producer、fixed-slot activation、control-evidence/registry roots、actor ACL matrix，且不得引用 M7 QRC/Plan/Authority/Profile。将 P 升级为明确的 `ReplayOutputNamespace v2`（或一个等价新 version），在 closed fields 内加入 strict component list、resolver、allowed-output-schema typed ref、created-root owner/gid/mode/access/default-ACL policy；V9 必须拒绝 P v1，而不是 infer/upgrade。每个 phase 的 validator 还必须验证 P=R=V schema authority、profile/policy/A writer/root-store equality，以及 A registry path 从 A root 的 pinned resolver/identity 解析。

### [P1] `ReservationRegistry v1` 是多阶段 state family，却被当作泛化 S reference；没有 immutable predecessor chain、one-time B/R coordinate binding 或 receipt-to-state order

**Section：** `architecture_confirmation_v17.md` §1（27–45 行）、§3（154–206 行）、§4（208–217 行）；`m6_5_repair_change_design_v14.md` §1（22–33 行）、§3（58–82 行）。

**Scenario：** 图将 S 表示为单节点 `V → S → O → H → receipts`，实际 transaction 依次写入 `ISSUED`、`RESERVED`、`RECEIPTED`、`HANDOFF_ANCHORED`、`HANDED_OFF`、`EXECUTED`、`ACCEPTED`。文本只说 records “keyed by `R.sha256`”，没有定义每个 transition 的 closed fields、不可变 storage key、sequence number、typed predecessor ref、one-child/fork rejection 或 phase-to-S receipt matrix。

若把 `R.sha256` 当作唯一 no-overwrite key，ISSUED 后没有位置容纳 RESERVED；若把它解释为每 R 的 transition collection，则两个正常 crash/recovery/construction pathway 可写出 hash-valid 的 RESERVED/RECEIPTED branches。O/H 仅笼统带 S ref，无法判定 O 应锚定 RESERVED、H 应锚定 RECEIPTED、child receipt 应锚定 HANDOFF_ANCHORED，还是选择一个后来的 mutable registry head。更严重的是，若 child receipt 引用 `HANDED_OFF`，该 state 又在 child receipt 后才产生；若 ArchiveAcceptanceReceipt 引用 `ACCEPTED`，而 ACCEPTED 必须绑定 archive receipt，会形成 future-reference/hash cycle。

同一缺口也未保证 B 是 one-time coordinate/leaf authority：registry 只拒绝相同 R 的第二次 ISSUED，不拒绝另一个 R/V 重用同一 B/leaf。这样一个 ISSUED 后无 root 的 burned R 可以被新的 R 复用旧 B，而不是文档要求的 new nonce → B → R → V；这让“坐标唯一”和 no-reuse 仍依赖未写出的 registry layout。

**Impact：** archive 无法只靠 immutable typed refs 证明 reservation 被唯一、线性地消费，也无法区分正确 handoff/execution lineage 与缺 predecessor、fork、stale state 或 future-S receipt 的拼接。正常 restart/concurrency/crash 正是冻结威胁模型需处理的情形；当前 state/no-reuse/quarantine/receipt acceptance 都不是唯一可实现的 contract，因此为 P1，而非受信 supervisor 的实现偏好。

**Evidence：**

- v17 154–164 行只给 state labels；168–199 行把 S publication 穿插于 O/H/child receipt 前后，但没有 predecessor、sequence、fixed state path 或 exact state schema。
- v17 190–198、210–217 行要求 receipts 持有 S “as applicable”，但没有定义 O/H/child/execution/archive 各自的 exact S ref，也没有定义 archive receipt 与 ACCEPTED state 的无环 creation order。
- v14 58–82 行压缩了同一 transaction，仍未增加 immutable lineage、B→R one-to-one index 或 recovery 对 duplicate/gap/fork/head 的 fail-closed selection。

**Direction：** 将 generic S 替换为 closed immutable `ReservationTransition v1` chain。先以 O_EXCL issuance slot 线性化一个 B→R one-to-one mapping（或令 R ID 从 B deterministically derived），拒绝重用 B/leaf；再写固定 namespace，例如 `R.sha256/<sequence>-<state>.json`。每条 transition 至少包含 exact A/P/B/R/V refs、`state_kind`、fixed `sequence_no`、typed `predecessor_ref`（S0 ISSUED 除外）、适用的 root identity 和 transition-specific receipt ref。写死一个只向既有对象引用的顺序：

```text
S0 ISSUED → S1 RESERVED → O → S2 RECEIPTED → H → S3 HANDOFF_ANCHORED
→ child receipt → S4 HANDED_OFF → execution receipt → S5 EXECUTED
→ ArchiveAcceptanceReceipt → S6 ACCEPTED
```

O 必须精确引用 S1，H 必须精确引用 S2，child receipt 必须精确引用 S3，execution receipt 必须精确引用 S4，archive receipt 只可引用 S5，随后才可写 S6。Archive 必须重建 S0…S5 的唯一链并拒绝 missing/duplicate/fork/stale/wrong-role/future-reference state；不得用 mutable “current head” 作为 authority。恢复也必须将每一种 crash observation 映射到唯一的 ABANDONED 或 QUARANTINED terminal transition。相应 synthetic tests 应覆盖 B reuse、duplicate/gap/fork、future-S receipt、archive/S6 cycle 和每个 crash hook。

## 上轮 P1/P2 与本轮要求的闭合核查

| 核查项 | 结论 | 依据 |
| --- | --- | --- |
| canonical bytes、typed refs、A content-universe no-cycle 的设计方向 | 部分闭合 | v17 14–59 行已定义 duplicate-key-free CanonicalObject、typed `ArtifactRef` 与 A 排除 future B/R/V/S/O/H 的 universe；但 A 的上游 replay profile/policy 仍无合法 pre-M7 producer，见 P1。 |
| B 单一坐标来源与严格 single-component leaf grammar | 部分闭合 | B 独占 coordinate fields，R 不再复制 policy/name/nonce；`m6r-` canonical derivation 和 regex 已拒绝 escape/path forms。仍缺 B→R one-time issuance binding，见 P1。 |
| P/A/B/R/V 精确关系 | 未闭合 | parent/resolver/name/profile equations 已写出，但 P v1 不能提供被读取字段，且 P output schema 不绑定 R/V，见 P1。 |
| O_PATH、sync FD、lock lifetime | 已闭合，须保留 | v17 166–206 行把 O_PATH 限为 witness、使用独立 sync FD，锁覆盖 mkdir/root capture/receipt/handoff，且写明 fsync 顺序。state predecessor P1 不会撤销这些控制。 |
| ISSUED 永不复用、crash/recovery、state | 未闭合 | ISSUED-before-root 的顺序和 burn/quarantine 意图正确，但 S object chain、B/R uniqueness、head/recovery rules 缺失，见 P1。 |
| root ACL 与 receipt schema | 部分闭合 | `DirectoryIdentity v2`、ACL/default-ACL、no-follow/no-xdev 和 typed receipt 的方向充分；receipt-to-exact-S phase mapping 尚未定义，见 P1。 |
| M6/PIT/M7/umask/ACL/FD 边界 | 未倒退 | v17/v14 保留 M6 `6/44`、PIT/state/public Gate、M7 seals、seed/umask、actor ACL 与 M6 runtime controls；但不得用未定义 replay profile 偷渡 M7 authority。 |

## 应保留的强项

- A 明确替代 bare control-root digest，并要求 control-root、registry 与 ACL identity；修复时应补上其合法 M6-only producer，而不是退回 mutable tree hash。
- B/R 的 single-source-of-truth 与 deterministic ASCII leaf，full parent-chain identity、same-ACL substitution checks 和 no-follow/no-xdev 控制都应保留。
- `O_PATH` witness 与 `O_RDONLY|O_DIRECTORY` sync FD 分离、同锁 no-replace/fsync transaction、crash burn/quarantine 的方向正确。
- complete M6 replay input/runtime closure、`14 replay / 0 fit / OOS=false`、M6 `6/44` genesis、PIT、actor ACL/umask、legacy receipt fail-closed 和 final-OOS/M7 seal 均未被本审查授权放宽。

## Verdict

`NEEDS_CHANGES` — **0 P0、2 P1、0 P2、0 P3**。最早修复阶段为 `architecture`。先补齐合法的 M6-only replay authority / P version migration / P=R=V schema binding，再定义 phase-specific immutable S0…S6 transition DAG 和 B→R coordinate uniqueness；随后重写 canonical change design 并取得新的独立 R3 PASS。此前不得进入 test design、red/green tests、implementation、code review、server replay、M7 derived contract/fit、CCC/Gate、PIT certification 或 final OOS。

## 审查范围与状态

- 当前 track：`M6.5-PRE-M7-ENGINEERING-QUALITY` / `design-review`；本审查为 distinct-subagent、independent、read-only R3 review。
- 审查对象 hashes：architecture v17 `2079525e3f0c9e6746d2047da3dd201f3d2a360cbc7bcb6bb1db9759037620f8`；change design v14 `69e8373b847854e382ea4b3443eaecbeb52cca60d56210dd924173b59d2195a6`；threat model `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`；status `fd2373ef53f061b45e1ac19bf90c86b4298f81863a88c66fe19acd9aa6bbe2d3`。
- 本审查只执行静态/只读检查；未修改产品代码、tests、研究契约、gate、历史证据或 quality ledger，且未运行训练、M6 replay、PIT `CERTIFY`、预算消费或 final-OOS。
- 观测到 ledger revision=`97`。后续 router 记录前必须重新读取，不能把本报告的 revision 当作写授权。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 97,
  "source_digest_observed": "sha256:a27ae6ddeb3af142ad65a6528fbfee747a1734419f53502164628cf7fb5a2b6b",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "REPLAY_ROOT_AUTHORITY_AND_RESERVATION_TRANSITION_DAG_NOT_CLOSED",
  "summary": "v17/v14 repair the prior leaf grammar and sync-FD transaction, but A depends on an undefined pre-M7 replay authority, P v1 cannot legally satisfy the new fields and does not bind R/V output schema, and S has no phase-specific immutable lineage. M6/M7 isolation and reservation acceptance therefore remain architecture-blocked.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 0, "P3": 0},
  "subject_digest": "sha256:69e8373b847854e382ea4b3443eaecbeb52cca60d56210dd924173b59d2195a6",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v14.md",
    "sha256": "sha256:69e8373b847854e382ea4b3443eaecbeb52cca60d56210dd924173b59d2195a6"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v17.md",
    "sha256": "sha256:2079525e3f0c9e6746d2047da3dd201f3d2a360cbc7bcb6bb1db9759037620f8"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "status_evidence": {
    "path": "docs/STATUS.md",
    "sha256": "sha256:fd2373ef53f061b45e1ac19bf90c86b4298f81863a88c66fe19acd9aa6bbe2d3"
  },
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v14.md"
  ],
  "independence": {
    "mode": "distinct-subagent-independent-read-only-r3-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_lead",
    "limitations": [
      "No product, test, contract, gate, ledger, or historical-evidence changes.",
      "No training, M6 replay, PIT certification, budget consumption, or final-OOS access."
    ]
  },
  "blockers": [
    "Define a replay-only typed pre-M7 profile/policy root, version P so every required P field has a legal schema, and bind P=R=V output schema authority.",
    "Define a phase-specific immutable S0…S6 transition DAG, B-to-R/leaf one-time issuance mapping, typed predecessor references, exact receipt-to-state binding, and fail-closed recovery/head rules.",
    "Reissue architecture/change-design evidence and obtain a fresh independent R3 review before test design or implementation."
  ],
  "next_route": "architecture"
}
```
