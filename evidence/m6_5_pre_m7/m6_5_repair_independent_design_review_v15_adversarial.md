# M6.5 canonical v15 / architecture v18 独立对抗式设计审查

## Findings

### [P1] `M6ReplayControlPolicy v1` 仍不是能独立验证的 M6 authority binding：其 provenance、P 的内容约束、slot/actor 关系以及 V 的核心 M6 输入没有闭合

**Section：** architecture v18 §1 第 14–54 行、§2 第 86–109 行；change design v15 §1 第 14–32 行、§2 第 34–46 行；frozen threat model 第 13–19、31–39 行；retained M6 inventory 为 v17 第 119–125 行。

**Scenario：** v18 现在正确引入了 M6-only policy/profile/P v2/A，并把 P=R=V 的 output schema、ACL 和 replay profile 写成等式。但 authority 根本身仍只有单向的 `P.policy_ref`：

- Policy 说 archive acceptor 在“重新验证” M6 spec/gate/close proof/historical receipt/`6/44` 后可以生成它（第 14–24 行），但没有把这些 exact typed refs、M6.5 quality-gate pass receipt 或唯一 `policy_producer` 写成 policy 的 closed required fields；同一段又分别说 archive acceptor 可 emit、policy compiler 写 slot，二者的角色与 effective Unix identity 没有一个可验证的 equality。
- P 的 closed fields 只有 `policy_ref` 和它自身的 namespace/schema/ACL/writer 内容（第 26–33 行）。Policy 只声明 policy/profile slots，并没有 policy-scoped P slot、P template/allow-list、P producer identity，或 `Policy.allowed_output_schema == P.allowed_output_schema` 的反向约束。随后 Profile/A/R/V 的列式等式也只证明这些对象都引用**同一个** P，并不能证明这个 P 是该 policy 唯一允许产生的 namespace；嵌套在 P 中的 output-schema ref 也没有明确的 M6-only allow-list。
- Profile 只明确携带 policy/P/M6-close refs（第 35–38 行）；V 虽保留完整 M6 spec/gate/close proof/historical verifier inventory（第 86–88 行及 retained v17），但第 91–103 行的完整 graph equations 没有 `Policy/Profile` 与 `V` 的 spec/gate/close-proof/historical-receipt/`6/44` equality。v15 的 `validate_m6_replay_graph_v2()` 仅要求验证“v18 equations”（第 36–40 行），因此不能自行补上该关系。

例如，在受信 host/control root/ACL 下仍可能存在两个内容正确、但属于不同 M6 close/evidence set 的历史对象 C1 和 C2。一个固定槽的 policy/profile/A 可由 C1 正常生成；另一个完整 V 则合法地携带 C2。按当前列出的关系，P/Profile/A 彼此一致，R=V 的 output constraints 一致，S0…S6 也可以完全线性，但没有一条规则会拒绝 `Policy(C1) + V(C2)`。同样，若 P 的构造入口接受一个不同但格式正确的 parent/schema，所有 P=R=V 检查仍能通过；这甚至可以把 M7-shaped output schema 经 P 的嵌套 typed ref 带入，而非直接让 policy 自己引用一个 `M7*` object。

**Impact：** 这不是 hostile runner、host/kernel 或 control-root compromise。它是在 threat model 明确需要处理的 ordinary configuration/recovery/wrong-selection 里发生的 cross-object splice：archive 不能证明 replay authority、M6 evidence inventory、namespace/root policy 和实际 writer 是同一冻结 M6-only authorization。因而 v18 的 M7 string/reference ban、`6/44` 起点和 P/R/V schema equality 还不能单独阻止错误的合法对象拼接，属于 P1。

**Evidence：**

- threat model 第 15–19 行要求防止“错误输入”及 archive/verifier/launcher/runtime/environment 绑错；第 31–39 行规定只有 authoritative runner / publisher 具备 official-result 语义，普通 library/path selection 不能成为 authority。
- v18 第 14–24 行没有给出 policy 的 closed evidence-field list、M6.5 pass evidence ref 或 archive-acceptor 与 policy-compiler 的单一 producer/identity relation；第 20–24 行只固定 policy/profile slot，而没有 P slot。
- v18 第 26–33、91–103 行可以证明 P=R=V 的 schema/ACL，以及 supervisor identity，但没有反向将 P 的 complete payload 固定到 policy，或将 policy/profile 的 M6 evidence 逐 role 对齐 V inventory。
- v15 第 28–32、36–40 行把这些未写出的约束交给未来 implementation/validator；按设计审查 contract，这会留下一个 material architecture decision，不能以实现推断补齐。

**Direction：** 将 `M6ReplayControlPolicy v1`（或其在 policy 前的 immutable `M6ReplayAuthorityBinding v1`）定义为闭合 authority record，并让 `validate_m6_replay_graph_v2()` 在 freeze、claim、prelaunch、transition/recovery 和 archive 执行以下逐 role equality：

1. exact typed M6 execution-spec/public-gate/close-proof/historical-verification/verified-`6/44` refs，外加一个不依赖未来 replay 的 M6.5 quality-gate `PASS` receipt；Policy、Profile、A（必要时）和 V 对这些 role 的 refs 必须同源相等；
2. 一个明确且唯一的 policy producer（archive acceptor **或** policy compiler，而非两者并列），其 exact UID/GID/groups/capability/ACL and fixed policy/P/profile slot ownership；Profile/A 实际 effective identity 和 FD/ACL preflight 必须等于这份 map；
3. policy-scoped、`O_EXCL` 的 P slot及完整 namespace template（parent components/resolver/writer/root ACL/allowed output schema），或等价的 closed field-by-field allow-list。P 必须由指定 producer deterministic materialize，且 `Policy.template == P == R == V`；所有嵌套 refs 使用 M6-only exact schema/role allow-list，而非只拒绝名称匹配 `M7*` 的顶层对象。

补充合成 fixture：两个 individually valid C1/C2 evidence sets 的 cross-splice、pre-quality-gate issuance、archive-acceptor/policy-compiler identity mismatch、alternate P slot/parent/schema、及 P 内嵌 M7/non-allow-listed schema ref 都必须在 freeze 前 fail closed。该修复不应改变 S0…S6 的已闭合 lineage，也不授权任何 replay、M7、PIT 或 OOS 行为。

## Controls verified as retained

- v18 关闭了此前 P v1 隐式升级问题：P v2 明确为新 schema，P v1/legacy/same-name-different-schema 均 rejection-only；P=R=V 的 output schema、root ACL、14 replay/0 fit/OOS=false 也已经明确相等。
- B 的 FD-derived parent chain、one-component leaf grammar和 `CanonicalDerive`，以及 K 不含 R/V hash 的 single-coordinate design，正确避免了原有 duplicate-name / hash-cycle 风险。`O_EXCL` claim、same-K permanent burn、validated A-rooted registry/lock identity也是正确方向。
- S0…S6 现在有固定 sequence、typed predecessor、phase-to-receipt mapping、archive-before-S6 ordering和 no-current-head scan；这解决了 v17 generic S 的 future-reference、fork、splice和 archive cycle P1。没有为该轴提出独立 finding。
- O_PATH identity witness 与独立 sync/operation FD、mkdirat 后 no-follow root witness、ACL/empty/root re-resolution、file+directory fsync、quarantine/burn、umask/runtime/PIT/legacy-ledger/final-OOS retained controls均未在本 review 中倒退。
- `docs/STATUS.md` 仍把当前阶段限定在 `M6.5-PRE-M7-ENGINEERING-QUALITY / DESIGN_REVIEW_PENDING`；本审查没有授权 server replay、M7 derived contract/fit、CCC/Gate、PIT 新认证或 final OOS。

## Verdict

`NEEDS_CHANGES` — **0 P0、1 P1、0 P2、0 P3**。最早修复阶段为 `architecture`。先把 policy→P→profile→A→V 的 typed authority / evidence / actor / slot relation闭合，再更新 canonical change design 并重新取得独立 R3 design review；此前不得进入 test design、red/green、implementation、code review、M6 server replay、M7 derived contract/fit、CCC/Gate 或 final OOS。

## Review limits and status

- Current phase/track: `M6.5-PRE-M7-ENGINEERING-QUALITY` / `design-review`; historical M6 engineering gate remains `PASS`, M6.5 remains unpassed.
- 本审查仅覆盖 frozen `research_governance_threat_model_v1.md` 内的 ordinary schema/path/TOCTOU/concurrency/crash/ACL/runtime/configuration failures；hostile runner arbitrary native code、host/control-root/kernel/ACL compromise 或 malicious loader injection 均未作为 finding。
- 未修改 product code、tests、contracts、gates、historical evidence 或 quality ledger；未运行 project code、training、M6 replay、budget consumption、PIT `CERTIFY` 或 final OOS。
- Router review-time observation: ledger revision=`102`，source digest=`sha256:9fec867cd4cac8c88b893aeb76df938df26f807cff8cca815e94dca60ef5b0cf`。此结果只读；提交 ledger 前必须重新 route/refresh。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 102,
  "source_digest_observed": "sha256:9fec867cd4cac8c88b893aeb76df938df26f807cff8cca815e94dca60ef5b0cf",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "M6_REPLAY_AUTHORITY_BINDING_NOT_CLOSED_ACROSS_POLICY_PROFILE_NAMESPACE_AND_INPUTS",
  "summary": "v18 closes P v2 migration, coordinate uniqueness and S0…S6 lineage, but the new M6 policy is not yet a closed authority binding: its exact M6 provenance/gate/producer and P template are not machine-bound, and those facts are not role-equal to the V inventory. Valid historical objects can therefore be cross-spliced under normal configuration/recovery error.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {
    "P0": 0,
    "P1": 1,
    "P2": 0,
    "P3": 0
  },
  "subject_digest": "sha256:b376d221fc2273d83db4aa608f031b8f8254789ea29ca6d10e6b3b34c23bc1b1",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v15.md",
    "sha256": "sha256:b376d221fc2273d83db4aa608f031b8f8254789ea29ca6d10e6b3b34c23bc1b1"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v18.md",
    "sha256": "sha256:690484697271b00795a26f9e22bc04704114617a567f840fc3293ef40241715b"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "status_evidence": {
    "path": "docs/STATUS.md",
    "sha256": "sha256:51fed21186ee2686f755722de00ff73f3f830991d561df2d97970a16654c5e26"
  },
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v15_adversarial.md"
  ],
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next --ledger .engineering-quality/changes/m6-5-pre-m7-repair/ledger.json --repo . (route inspection only)",
    "read-only inspection of v14/v16/v17 retained M6 replay inventory and actor/ACL controls"
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
    "Bind Policy/Profile/A/V to one exact M6 evidence set and an immutable M6.5 quality-gate PASS receipt.",
    "Define one producer/actor/ACL/slot relation and a policy-owned P template/allow-list, including nested M6-only schema roles.",
    "Re-run independent design review before test design or implementation."
  ],
  "next_route": "architecture"
}
```
