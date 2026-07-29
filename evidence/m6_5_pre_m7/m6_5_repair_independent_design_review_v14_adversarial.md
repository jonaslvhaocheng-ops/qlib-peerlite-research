# M6.5 canonical v14 / architecture v17 独立对抗式设计审查

## Findings

### [P1] A 的前置 authority 与 P 的 schema 没有合法、版本化的 pre-M7 producer；P 的 output-schema policy 也没有与 R/V 绑定

**Section：** v17 §1 第 24–59、76–80、119–140 行；v14 §1 第 14–33 行、§2 第 35–54 行；retained base v14 §2–3 第 15–43 行；retained v12 §1 第 11–22 行。

**Scenario：** v17 的唯一图以 “`P + activated replay-control profile`” 开始，A 又要求 typed `activation-profile` 与 `control-plane-policy` refs；但没有定义这两个 replay-only object 的 schema、role、producer、fixed selection slot、actor ACL 或 activation lifecycle。当前 repository 中唯一已定义的 control policy/profile 是 `M7ControlPlanePolicy v1` 与 `M7RunControlProfile v1`，它们必须由 frozen M7 QRC → authority → activation 产生，而 `docs/STATUS.md` 明确封存 M7 derived-contract freeze/fit。若 implementation 借用它们，M6 archival replay 的前置图反向依赖禁止中的 M7 authority；若把 “replay-control profile” 视为新对象，则它是没有 typed producer 的自由 authority selector。

同一问题出现在 P：v17 明确把 P 称为 existing `ReplayOutputNamespace v1`，却要求 `P.parent_components`、`P.resolver_profile` 和 exact created-root ACL/default-ACL policy。retained v12 的 P v1 只有 logical namespace、control-root-relative parent、owner/mode/POSIX ACL、writer、`0700`、allowed output schema 与 no-reuse；没有前述新增字段。新 canonical rules 又禁止 same-name/different-schema 和 implicit upgrade，因此无法在不 versioning P 的情况下安全满足 v17 equations。

最后，v17 只要求 `R.required_output_schema_ref == V.required_output_schema_ref`，没有要求其等于 P 的 allowed output schema。于是 P=`schema0`、R/V=`schema1` 可以满足列出的图 equations 并在所有 name/root checks 通过后产出 policy 未允许的 output schema。

**Impact：** 这不是要求抵御 hostile host 或 supervisor compromise。即使在受信根下，普通 deployment/configuration error 也会迫使 implementation 在 “隐式启用 M7 authority”、“接受未类型化 replay profile”、“静默升级 P v1” 或 “忽略 P 的 schema policy” 之间选择。当前 acceptance contract 不能拒绝这些错误，因此 M6/M7 isolation、root selection 与 output-schema authority 都未闭合，为 P1。

**Evidence：**

- v17 第 28、49、56 行使用 activated replay profile/policy，但未声明 schema names 或 allowed `ArtifactRef.role`；项目搜索除 v17/v14 外只找到 M7 policy/profile。
- base v14 第 15、35–39 行把唯一现有 policy/profile 锁在 M7 QRC/authority activation 链；`docs/STATUS.md` 第 87–92 行禁止先行 M7 derived contract/fit。
- v17 第 79、134–139 行读取 P 的 components/resolver，但 retained v12 第 11 行的 P v1 field list 没有它们；v17 第 137–140 行也缺 `P.allowed_output_schema_ref == R.required_output_schema_ref == V.required_output_schema_ref`。

**Direction：** 在 A 前定义独立的、M6-only 的 `M6ReplayControlPolicy v1` 和 `M6ReplayControlProfile v1`：它们必须从 verified M6 close/proof 的固定 replay authority 产生，拥有 exact typed roles/schema/bytes、actor ACL matrix、immutable control-evidence store/registry roots 和 fixed-slot activation，不得引用 M7 QRC/Plan/Authority/Profile。将 P 升级为 `ReplayOutputNamespace v2`，在 frozen fields 中加入 strict component list、resolver profile、allowed-output-schema typed ref、created-root owner/gid/mode/access-ACL/default-ACL policy；V9 必须拒绝 P v1，而不能 infer/upgrade。所有 phase validator 应增加 P=R=V output-schema equality，以及 replay profile/policy/A writer and root-store equality。

### [P1] `ReservationRegistry v1` 被当作单一 S ref，但实际是 interleaved transition family；没有 phase-specific predecessor graph，receipt/acceptance chain 可变成 fork、stale selection 或 hash cycle

**Section：** v17 §1 第 27–45 行、§3 第 154–206 行、§4 第 208–217 行；v14 §1 第 22–33 行、§3 第 58–82 行。

**Scenario：** 图把 `S` 放在 `V → S → O → H → receipts` 的单一节点，但实际 transaction 写入：`ISSUED S → RESERVED S → O → RECEIPTED S → H → HANDOFF_ANCHORED S → child receipt → HANDED_OFF S → EXECUTED/ACCEPTED`。新设计没有规定每个 transition 的 exact schema fields、typed predecessor ref、fixed sequence/path/role、one-child/fork rejection，或每个 downstream receipt 到底必须引用哪一个 S。

这会直接制造无法通过 “complete typed refs … S as applicable” 解决的构造选择：若 child receipt 引用 `HANDED_OFF S`，它会引用未来才由 child receipt 触发的 record；若引用较早的 `HANDOFF_ANCHORED S`，archive 又必须如何证明 `HANDED_OFF/EXECUTED` 是同一 immutable lineage？同样，ArchiveAcceptanceReceipt 若引用 `ACCEPTED S`，而 `ACCEPTED S` 需要绑定 receipt，会形成循环。若改为从 registry 当前 head/path 重新选择状态，则重新引入被 v17 禁止的 mutable/bare selector。没有 predecessor rule 的 restart/recovery 还能产生两个 locally valid `RESERVED`/`RECEIPTED` artifacts 并把 O/H/child receipt 拼接到不同分支。

**Impact：** 这属于 acceptance contract 本身的缺口，而非受信 supervisor 的实现偏好：archive 无法用 immutable typed refs 判定 reservation 是否只被线性消费、handoff 是否确实发生、还是 receipt 来自另一个 state branch。正常 crash/restart/concurrency 正是 frozen threat model 明确要求处理的情形，因此 no-reuse、quarantine 与 archive acceptance 仍为 P1 未证明。

**Evidence：**

- v17 第 156–164 行只给出 state labels；第 168–199 行把 S 的 publish 插入 O/H/child receipt 前后，但没有 `predecessor_ref`、sequence、fixed state path 或 role table。
- v17 第 210–217 行要求 all receipts contain S refs “as applicable”，却未提供 phase-to-S mapping 或 ArchiveAcceptanceReceipt 与 `S.ACCEPTED` 的 creation order。
- v14 第 71–82 行压缩同一 transaction，仍未补上 immutable transition lineage。

**Direction：** 将 generic S 拆成严格的 immutable `ReservationTransition v1` objects，且每条都含 `reservation_ref=Ref(R)`、`state_kind`、fixed `sequence_no`、typed `predecessor_ref`（ISSUED 无 predecessor）、exact V/B/R/A/P refs、expected root identity where applicable，写入 `R.sha256/<sequence>-<state>.json` 的 fixed O_EXCL path。写死无环顺序，例如：

```text
S0=ISSUED → S1=RESERVED → O → S2=RECEIPTED → H → S3=HANDOFF_ANCHORED
→ child receipt → S4=HANDED_OFF → execution receipt → S5=EXECUTED
→ ArchiveAcceptanceReceipt → S6=ACCEPTED
```

每个 object 只能引用左侧既有对象；ArchiveAcceptanceReceipt 只引用 `S5`，随后才写 `S6`。archive 必须 receive/rehash the full S0…S5 chain and reject missing, duplicate, forked, stale or wrong-role transitions; it cannot consult a mutable “current head” as an authority. Tests must build a branch splice, future-S receipt, missing predecessor and archive/S6 cycle fixture, then prove fail-closed.

## Controls verified as retained

- v17 已正确把 prior B/R name duplication 改为 B single source of truth，并定义 deterministic `m6r-…` leaf grammar；`..`、absolute、slash、Unicode/multi-component 及 generic path 入口均被明确拒绝。该部分无需回退。
- A 明确尝试替代 bare control-root digest；B 也保留 full parent-chain/root identity、FD-derived ACL、opaque handle、same-ACL substitution checks。修复时应保留这些反替换控制，只需补齐它的合法 replay-only authority root。
- O_PATH 与 sync FD 分离、同锁 `ISSUED`/root capture/receipt/handoff、crash burn/quarantine 和 no-replace fsync ordering 的方向正确；第二项 finding 要求的是把 S 的 typed lineage 补齐，不是撤销该 transaction。
- v17/v14 继续保存 complete M6 replay input/runtime closure、`14 replay / 0 fit / OOS=false`、v5/v2 M7 migration、M6 `6/44` genesis、PIT boundary、actor ACL/umask、legacy receipt fail-closed 及 final-OOS/M7 seal。
- `docs/STATUS.md` 仍正确显示 `M6.5=DESIGN_REVIEW_PENDING`，本审查没有授权 server replay、M7、CCC/Gate、PIT 新认证或 final OOS。

## Verdict

`NEEDS_CHANGES` — **0 P0、2 P1、0 P2、0 P3**。最早修复阶段为 `architecture`。在补上合法 pre-M7 replay authority/P v2 migration、完整 S transition DAG 后，必须重写 canonical change design 并取得新的独立 R3 design review；此前不得进入 test design、red/green、implementation、code review、M6 server replay、M7 derived contract/fit、CCC/Gate 或 final OOS。

## Review limits and status

- Current phase/track: `M6.5-PRE-M7-ENGINEERING-QUALITY` / `design-review`; M6 historical engineering gate remains `PASS`, M6.5 remains unpassed.
- 本审查在 frozen `research_governance_threat_model_v1.md` 下只覆盖 ordinary schema/path/TOCTOU/concurrency/crash/ACL/runtime failures；hostile runner arbitrary native code、host/control-root/kernel/ACL compromise 或 malicious loader injection 没有作为 finding。
- 未修改 product code、tests、contracts、gates、historical evidence 或 quality ledger；未运行 project code、training、M6 replay、budget consumption、PIT `CERTIFY` 或 final OOS。
- Router review-time observation: ledger revision=`97`，source digest=`sha256:a27ae6ddeb3af142ad65a6528fbfee747a1734419f53502164628cf7fb5a2b6b`。此结果只读；提交 ledger 前必须重新 route/refresh。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 97,
  "source_digest_observed": "sha256:a27ae6ddeb3af142ad65a6528fbfee747a1734419f53502164628cf7fb5a2b6b",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "REPLAY_ROOT_AUTHORITY_AND_RESERVATION_TRANSITION_DAG_NOT_CLOSED",
  "summary": "v17 fixes leaf grammar and many durability controls, but its A root depends on an undefined replay profile/incompatible P v1 and leaves P's output-schema authority unbound. Its generic S transition family has no phase-specific immutable predecessor graph, so receipt/archive lineage is not uniquely acyclic.",
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
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v14_adversarial.md"
  ],
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next --ledger .engineering-quality/changes/m6-5-pre-m7-repair/ledger.json --repo . (route inspection only)",
    "read-only inspection of v12/v13/v14/v16 retained contracts, status evidence, and current replay/governance source interfaces"
  ],
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_adversary",
    "limitations": [
      "No product/test/contract/gate/ledger/historical-evidence implementation changes.",
      "No training, M6 replay, budget consumption, real PIT certification, or final-OOS access."
    ]
  },
  "blockers": [
    "Define a replay-only, typed pre-M7 profile/policy root and version P to a schema that can satisfy every A/B/R/V equation.",
    "Define a phase-specific immutable S0…S6 transition DAG with typed predecessor references and archive acceptance ordering.",
    "Re-run independent design review before test design or implementation."
  ],
  "next_route": "architecture"
}
```
