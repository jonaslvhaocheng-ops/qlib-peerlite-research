# M6.5 canonical v18 / change design v15 独立 R3 设计审查

## Findings

### [P1] 唯一 coordinate key K 没有规范绑定 B 的实际 final-parent identity，仍可将同一物理 leaf 分裂为多个 claim namespace

**Section：** `architecture_confirmation_v18.md` §2（62–84、91–110 行）及 §4（157–159 行）；`m6_5_repair_change_design_v15.md` §2（36–46 行）。

**Scenario：** B v3 被说明为保留 v17 的完整、FD-derived parent identity chain；但 K 使用新字段 `B.parent_identity_digest`。当前 v18 没有把该字段列为 B v3 的 closed field，也没有定义它是 `B.parent_identity` 的哪一种 canonical bytes/hash，更没有在 §2 的 phase equations 或 105–110 行的 resolver checks 中要求重新计算并比较它。

因此，若实现把它作为新字段，两个 B 可以解析到同一个真实 final parent、使用同一个 A/P/id/nonce/basename，却带不同的未约束 `parent_identity_digest`。所有 B parent-chain/ACL revalidation 都仍可成功，但 K0 与 K1 不同，R0/R1 写入不同 `registry/claims/<K>/` 路径，`O_EXCL` 不会冲突。特别是在 R0/S0 后尚未创建 root 而被 `ABANDONED_BURNED` 的正常 crash/recovery 场景，B1/R1 可以重新取得同一物理 leaf，而不是被“burned coordinate”阻止。若该 digest 不是 B 的字段，则 K 本身没有可唯一实现的 source。

**Impact：** 这是受信 host/control-root/ACL 条件下普通 constructor、recovery 或 schema interpretation 造成的 coordinate-reuse 漏洞，不需要 hostile runner。v18 的“second R for the same K”只保护 digest key，不保护真正的 `(A, P, actual parent identity, leaf)`，故会重新引入上轮要求排除的 free/duplicate output-root authority，属于 P1。

**Evidence：**

- v18 69–75 行仅在 K formula 中出现 `B.parent_identity_digest`；v18 62–64 行只笼统说 B 保留 full identity，v18 91–103 行的 exact equations 没有 `parent_identity_digest == CanonicalDigest(B.parent_identity)`。
- v18 105–110 行只要求 resolve 后的 B parent-chain/ACL identity checks，未要求 K input digest 与已观察的 `DirectoryIdentity` canonical bytes 相等。
- v15 42–46 行重复“path derived only from A/P/B parent identity/leaf”的结论，但未定义或验证这个 digest；v18 169–173 行的 duplicate-coordinate test 也没有要求用相同实际 parent/leaf、不同 identity-digest 的 fixture。

**Direction：** 删除自由的 `B.parent_identity_digest`，或把它定义为 `sha256(CanonicalObject-v1(B.parent_identity))` 的严格 derived field，并在 freeze、claim、prelaunch、recovery、archive 以已解析的 complete `DirectoryIdentity v2` bytes 重新计算。K 应直接使用该 canonical digest（或 B 的 normalized coordinate subobject），R 必须同时保存并验证它；不得允许 B 只因一个未绑定 digest 而改变 K。补充相同 actual parent/leaf + altered digest、duplicate B/recovery-after-burn 和 registry-path collision fixtures。

### [P2] R 已 durable 而 V 尚未冻结的 crash window 没有闭合的 recovery/terminal contract

**Section：** `architecture_confirmation_v18.md` §2（78–88、101 行）、§3（117–123、142–146 行）、§4（157–159 行）；`m6_5_repair_change_design_v15.md` §2（42–46 行）、§4（77–81 行）。

**Scenario：** 事务先 `O_EXCL` + fsync 发布 R，随后才 freeze V；但每个 `ReservationTransition v1`（包括 terminal transition）都要求 exact A/P/B/R/**V** refs。若进程在 R durable 与 V frozen 之间崩溃，就没有 V 可写 S0 或 `ABANDONED_BURNED`/`QUARANTINED_UNPUBLISHED` terminal。文本也没有为 R→V 指定 fixed O_EXCL binding slot、唯一 V mapping、R-only terminal record，或 R-only recovery 决策。与此同时 §4 说发布 R 前“revalidates all §2 equations”，但这些 equations 已包含尚不存在的 V，按文字无法执行。

**Impact：** R-v4 的唯一 claim 意图是正确的，但该窗口使 implementation 必须自行决定：恢复时重建/替换 V、留下没有可审计终态的永久 claim，或写出违反 own-schema 的 terminal transition。它直接落在冻结威胁模型要求处理的 crash/restart/half-written control 状态内，且不具备唯一实现语义，为 P2。

**Evidence：**

- v18 78–84 行明确 R 不持有 V；86–88 行说明 V 之后才引用 R；157–159 行明确 R publication precedes V freeze。
- v18 117–121 行要求 transitions 拥有 exact V ref，144–145 行又要求 recovery append terminal transition；没有例外或 pre-V state schema。
- v15 42–46、77–81 行保留相同 R-before-V order，未增加 crash point 或 recovery mapping；其 test commitments 也未列 R-publish→V-freeze crash fixture。

**Direction：** 在 R 和 S0 之间增加一个 immutable、A-rooted one-time V binding / pre-transition lifecycle contract。它必须明确：V 的 fixed O_EXCL path and exact R ref；R-only crash 是永久 burn 还是可由唯一、reconstructed V 完成；若 burn，采用不要求 V 的 dedicated R-terminal record；若继续，限定唯一 V bytes/slot 且先验证所有 V equations。将 §4 拆成 “pre-R equations → R claim → V-binding equations → S0”，并给每个 crash point（R publish、V publish、S0 publish）指定唯一 recover/terminal outcome。

### [P2] policy 与 receipt 的 writer/actor matrix 仍有冲突和缺口，无法对每个 authoritative object 执行唯一 ACL/role check

**Section：** `architecture_confirmation_v18.md` §1（14–24、35–47 行）、§3（125–153 行）；`m6_5_repair_change_design_v15.md` §1（28–32 行）、§3（58–61 行）；frozen threat model（31–39 行）。

**Scenario：** v18 15 行说 `M6ReplayControlPolicy v1` “may be emitted only by the M6 archive acceptor”，22–24 行又说 `policy_compiler` emits the fixed policy slot；这两个被列为不同 actor，且没有声明 one is a component/identity of the other。S matrix 还在 S4 与 S5 之间插入 `ReplayExecutionReceipt v9`，但 149–153 行只分配 S/O/H、ChildReceipt、ArchiveAcceptanceReceipt/S6 的 writers；没有为 execution receipt 指定 author role/effective identity。v15 重复这张不完整 matrix。

**Impact：** 普通 implementation 必须自行选择哪个 UID/ACL 写 policy，和哪个 identity 写 execution receipt；这会使“正确-looking but wrong-role”拒绝规则无法机械执行。冻结威胁模型明确把 replay supervisor 的独立 execution receipt 视为受保护控制，因此这不是 hostile-host 假设，而是 authoritative ownership contract 的 P2 缺口。

**Evidence：**

- v18 19–24 行在同一 policy actor map 中同时出现 `policy_compiler` 和 `archive_acceptor`，却给两者相互冲突的 policy issuance 语义；v15 28–32 行没有消除二义性。
- v18 136–137 行要求 execution receipt 先于 S5，149–153 行的 exhaustive-style “Only P-authorized identities may write these phases”没有为该 receipt 指派 writer；v15 58–61 行同样省略。
- threat model 39 行要求 replay supervisor 产生可独立验证的 execution receipt，说明它不能作为一个无 owner 的 implicit artifact。

**Direction：** 发布一个完整、closed 的 artifact→writer-role→effective-identity→ACL/path matrix：至少覆盖 policy、P、Profile、A、B、R、V、S0…S6、O、H、ChildReceipt、ReplayExecutionReceipt 和 ArchiveAcceptanceReceipt。为 policy 选择唯一 writer（或明确 archive acceptor 与 policy compiler 是同一 pinned identity/capability，并在 bytes/ACL 中绑定）；为 execution receipt 明确 replay-supervisor writer。每个 validator/receipt 需比较 exact role and identity，tests 必须尝试正确 bytes 但 wrong role/UID 的 policy、execution receipt 和 transition。

## 上轮 P1 / 专项审计与保留边界核查

| 核查项 | 结论 | 依据 |
| --- | --- | --- |
| M6-only policy → P v2 → profile → A，且不依赖 M7/隐式 P 升级 | 主链已闭合 | v18 14–58、v15 14–32 行定义 M6-only typed policy、P v2 rejection-only migration、fixed-profile/A order，并拒绝 M7/QRC/Plan/Authority refs。policy writer matrix 仍有本轮 P2。 |
| P=R=V output schema / root ACL / writer equality | 已闭合 | v18 92–103 行明确 schema、ACL 和 effective supervisor equations；P v2 提供所需 closed fields。 |
| A-rooted registry 与 transaction lock | 已闭合 | v18 40–47、105–110 行固定 A root、registry/lock components、identity chains 和 pinned resolver，禁止 caller path/head。 |
| S0…S6 left-only predecessor/receipt graph、无 fork/cycle/stale head | 已闭合 | v18 114–147、v15 48–73 行给出 fixed sequence/path, predecessor refs, scan rejection 和 archive-before-S6 order。R→V pre-S0 crash state与 writer matrix仍有本轮 P2。 |
| R 的唯一物理 coordinate claim | 未闭合 | K 的 final-parent identity input 未规范绑定，见 P1。 |
| O_PATH/sync FD、root ACL、M6/PIT/M7/umask/FD/ACL 边界 | 未倒退 | v18 155–173、v15 75–88 行保留 O_PATH witness + sync FD、root ACL/identity and fsync; headers、threat model和 STATUS 均保持 M6/PIT/M7/final-OOS seals。未运行任何 replay/训练/PIT/OOS。 |

## 应保留的强项

- M6-only authority 把 previous M7-dependent profile ambiguity 移出 replay path，并把 P v1 改为 rejection-only。
- P=R=V schema/ACL equality、A-rooted registry/lock resolver 与 strict leaf/no-caller-path controls 方向正确。
- S0…S6 的 left-only receipt ordering、archive receipt before S6 与 no-mutable-head rule 正确解决了上轮 state cycle/fork 核心问题。
- `O_PATH` 仅作 identity witness、独立 sync FD、no-replace + fsync publication、M6 `6/44`、PIT、seed/umask、actor ACL、runtime/final-OOS controls 必须原样保留。

## Verdict

`NEEDS_CHANGES` — **0 P0、1 P1、2 P2、0 P3**。最早修复阶段为 `architecture`。先将 K 绑定到 canonical observed parent identity，并闭合 R→V pre-S0 crash state和完整 writer matrix；随后同步更新 change design 并重新独立审查。此前不得进入 test design、red/green tests、implementation、code review、server replay、M7、CCC/Gate、PIT certification 或 final OOS。

## 审查范围与状态

- 当前 track：`M6.5-PRE-M7-ENGINEERING-QUALITY` / `design-review`；本审查为 distinct-subagent、independent、read-only R3 review。
- 审查对象 hashes：architecture v18 `690484697271b00795a26f9e22bc04704114617a567f840fc3293ef40241715b`；change design v15 `b376d221fc2273d83db4aa608f031b8f8254789ea29ca6d10e6b3b34c23bc1b1`；threat model `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`；status `51fed21186ee2686f755722de00ff73f3f830991d561df2d97970a16654c5e26`。
- 未修改产品代码、tests、研究契约、gate、历史证据或 quality ledger；未运行项目代码、训练、M6 replay、PIT `CERTIFY`、预算消费或 final-OOS。
- 只读观测 ledger revision=`102`、source digest=`sha256:9fec867cd4cac8c88b893aeb76df938df26f807cff8cca815e94dca60ef5b0cf`；router 记录前必须重新读取。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 102,
  "source_digest_observed": "sha256:9fec867cd4cac8c88b893aeb76df938df26f807cff8cca815e94dca60ef5b0cf",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "COORDINATE_IDENTITY_BINDING_AND_PRETRANSITION_LIFECYCLE_NOT_CLOSED",
  "summary": "v18/v15 close the prior M6-only authority/P-v2 and S0…S6 structural findings, but K is not canonically tied to B's observed final-parent identity, R→V has no recoverable pre-S0 terminal/binding state, and the actor matrix conflicts on policy issuance while omitting ReplayExecutionReceipt ownership.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 2, "P3": 0},
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
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v15.md"
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
    "Bind K to an exact canonical digest of B's observed final-parent identity and test duplicate physical coordinates with a substituted digest.",
    "Define the durable R→V binding or R-only terminal state and a crash/recovery mapping before S0.",
    "Publish one complete artifact writer/role/identity/ACL matrix, resolving policy compiler versus archive acceptor and naming the ReplayExecutionReceipt writer.",
    "Reissue architecture/change-design evidence and obtain a fresh independent R3 review before test design or implementation."
  ],
  "next_route": "architecture"
}
```
