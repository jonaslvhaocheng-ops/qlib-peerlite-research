# M6.5 v15/v12 独立 R3 设计审查

## Findings

### [P1] `FreshOutputReservation v1` 没有把绑定期 namespace-parent 的实际身份写入 v7 binding，因此无法证明或拒绝“同 ACL 的父目录替换”

**Section：** `architecture_confirmation_v15.md` §1–§2（第 13–16、32、36 行）；`m6_5_repair_change_design_v12.md` §1–§3（第 11–22、38、44 行）。

**Scenario：** 绑定冻结时，supervisor 会用 root-FD 打开 parent、检查其 identity/ACL 并确认保留 basename 不存在。但 `ReplayOutputNamespace v1` 的闭合字段只有 policy 的 relative parent path、预期 owner/mode/ACL 等，而 `FreshOutputReservation v1` 的闭合字段也只含 namespace-policy digest、nonce/basename、absence/profile/schema；两者均不含这次绑定期实际 parent FD identity。执行阶段重新打开 parent 后，`OutputReservationReceipt v1` 才记录一个新的 point-in-time parent identity，且 archive 只被要求让 binding、reservation、supervisor 和 child 收据相互一致。

因此，一个普通的运维/恢复错误即可形成如下序列：冻结时 policy path 指向 `D0`，随后 `D0` 被替换为 owner/mode/POSIX ACL 完全相同的 `D1`；执行时对 `D1` 的 FD 校验、absence check 和 `mkdirat` 都成功，所有运行期收据也都一致地记录 `D1`。由于 binding 内没有 `D0` 的可比较身份，`parent mismatch fails` 没有可用的期望值，不能实现文档明确要求的“parent substitution 必须拒绝”测试。

**Impact：** M6 archive replay 可能在不是冻结期审计过的 namespace parent 下创建并接受输出。它没有退化为 caller path，也不需要 hostile runner、host/control-root/内核攻陷；这是冻结 threat model 所覆盖的正常路径/恢复/ACL 配置错误。`mkdirat` 仍能防止同一目录内的名称碰撞，却不能把新 `D1` 与绑定期 `D0` 区分开，因此 fresh-root、quarantine/no-reuse 和 receipt-agreement 并未闭合 parent-substitution 分支。

**Evidence：**

- v15 第 13–16 行与 v12 第 11–22 行列出的 namespace/reservation closed fields 中没有 bind-time parent identity；文字仅说“validates its identity/ACL”或“records absence”。
- v15 第 32–34 行与 v12 第 38–40 行只让运行期 receipt 携带 point-in-time parent/root identities；没有要求它们等于 binding-time parent identity。
- v15 第 36 行与 v12 第 44 行却明确把 parent substitution 列为必须拒绝的测试，且把它与 symlink、wrong owner/mode/ACL 分列。这要求覆盖同元数据、不同目录对象的替换，而不是仅重新检查 ACL。
- 前一轮 v11 P1 的修复方向也明确要求 trusted parent 的 `ArtifactRef`/root-FD identity；v15/v12 已解决 future output 不是 `ArtifactRef` 的矛盾，但遗漏了该 parent-identity 链接。

**Direction：** 在 `FreshOutputReservation v1`（或由其精确引用的不可变 parent-identity artifact）中写入 binding-freeze 时由 root-FD 取得的 namespace-parent identity，并把它纳入 v7 digest。执行前以 policy/root-FD 重新解析 parent，比较该 identity、directory type、owner/mode/ACL；锁必须附着于同一个已验证 parent，创建后和 archive acceptance 前再次证明 policy-relative parent 仍解析到同一 identity。`OutputReservationReceipt v1`、`ReplayExecutionReceipt v6`、child receipt 与 `m6_archive` 必须同时比较 expected/bound 与 observed parent/root identities，而不仅比较运行期收据彼此。synthetic coverage 需要专门替换为同 UID/GID/mode/ACL 的不同 parent，且必须在 verifier launch 和 archive acceptance 前 fail closed；不能以“ACL 未变”通过。

## Verdict

`NEEDS_CHANGES`：**0 个 P0、1 个 P1、0 个 P2、0 个 P3**。

v15/v12 已正确解决上一轮的核心矛盾：未来 output root 不再伪装为已有 `ArtifactRef`，而是由现有 policy artifact 加非内容 reservation 表达；bind-time absence、execution-time recheck、`mkdirat` 线性领取、receipt、quarantine/no-reuse 的主路径也已明确。问题仅在 parent 替换分支缺少“绑定期 identity → 执行期/验收期 equality”的闭环，因而当前声明的 parent-substitution rejection 尚不可实现。

最早修复阶段是 `architecture`，并须同步修订 v15 与 v12。修复并通过新的独立设计审查前，不得进入 test-design、实现、code review、E2E、server replay、M7 派生契约冻结/真实 fit、CCC/Gate 或 final OOS。

## 已核对且应保留的控制

- M6 replay v7 仍完整枚举 archive、M6 evidence、M3 产品分区、14 fold/checkpoint/prediction、K16 refit、只读 ledger、sealed runtime/startup 输入；没有 caller-selected source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter root，且 profile 固定为 `14 replay / 0 fit / OOS=false`。
- v15/v12 的 reservation 流程在正确 parent 前提下具备 bind-time no-follow absence、执行期重查、namespace lock、`mkdirat(..., 0700)` 的唯一线性领取、parent/root fsync、仅 FD 传给 verifier、stale receipt/reuse/crash 后 quarantine 的明确拒绝路径。
- 继承的 M6 genesis/PIT/Gate/M7 边界未被放松：M6 close 是 `6/44`，legacy `4/29` 拒绝；PIT/state handoff、public Gate denial、M7 未授权和 final OOS 封存均仍有效。
- 继承的 M7 schema 迁移仍在 claim/permit 前拒绝 descriptor v4、closure/receipt v1 和任何 implicit alias/upgrade；FD-exec、`close_fds=True`、CLOEXEC、non-alias ACL、exact envp、effective `PYTHONHASHSEED=0`、`-s -S -P`、helper/bootstrap 双重 umask 观测没有回退路径。
- v11 的全局 receipt/inventory/tree-hash 与 partial-output quarantine 要求仍由 v12 base 保留；后续 test-design/implementation 必须让 v7 输出 receipt 实际满足这些继承字段，而非把它们降为文字约定。

## 范围、证据与限制

- 审查对象：
  - `evidence/m6_5_pre_m7/architecture_confirmation_v15.md`，SHA-256 `f6dd3a7d92007cfdc8a2b863be95b9c2bd3204305d63ee5ae849f3d22776fafd`；
  - `evidence/m6_5_pre_m7/m6_5_repair_change_design_v12.md`，SHA-256 `4798192f857896147774e269900db72777ec01dd75fa1b82fc354262a12753f4`；
  - canonical bases v14/v11、冻结 threat model、`docs/STATUS.md` 与 M6/PIT gate evidence。
- 只读检查文档、静态交叉约束、质量 ledger snapshot 和现有源代码的基线接口事实；未改产品代码、测试、契约、gate、M6 历史或 quality ledger。
- 未运行训练、archive replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。本报告不是 PIT/data certification、implementation、code review、E2E、server replay 或 Alpha 结论。
- Finding 严格限于冻结 threat model 内的普通 namespace/path/recovery 误操作；没有把 hostile runner、control root/host ACL/内核攻陷或恶意 loader 注入当作阻断理由。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 88,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "RESERVATION_DOES_NOT_BIND_PARENT_IDENTITY_ACROSS_FREEZE_AND_EXECUTION",
  "summary": "v15/v12 correctly separate existing hashed inputs from a future replay output and define atomic fresh-root reservation. However, the namespace parent identity checked at binding freeze is not a field of FreshOutputReservation v1 or the v7 binding, while the receipt records only a new runtime observation. A same-ACL parent replacement can therefore satisfy all stated runtime receipt checks despite the required parent-substitution rejection.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 0, "P3": 0},
  "artifact_paths": [
    "evidence/m6_5_pre_m7/architecture_confirmation_v15.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v12.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/architecture_confirmation_v14.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v11.md",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v11.md",
    "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "docs/STATUS.md",
    "evidence/gates/M6_peerlite_gate.json",
    "evidence/gates/M3_pit_data_gate.json"
  ],
  "commands": [
    "read-only shasum/rg/sed/nl/find/git status",
    "read-only JSON inspection of the Engineering Quality ledger snapshot",
    "static canonical-contract, replay-inventory, identity-flow and threat-boundary checks"
  ],
  "subject_digest": "sha256:4798192f857896147774e269900db72777ec01dd75fa1b82fc354262a12753f4",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v12.md",
    "sha256": "sha256:4798192f857896147774e269900db72777ec01dd75fa1b82fc354262a12753f4"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v15.md",
    "sha256": "sha256:f6dd3a7d92007cfdc8a2b863be95b9c2bd3204305d63ee5ae849f3d22776fafd"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_lead",
    "limitations": [
      "Read-only review artifact; no product/test/contract/gate/ledger mutation.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access.",
      "PIT discussion is VERIFY-only and is not a PIT certification result."
    ]
  },
  "blockers": [
    "Bind the freeze-time namespace-parent identity into FreshOutputReservation v1 (or an exact immutable referenced artifact), require equality at execution and archive acceptance, then re-review v15/v12.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
