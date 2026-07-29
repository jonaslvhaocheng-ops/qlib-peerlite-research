# M6.5 canonical v12 / architecture v15 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查技能：`eng-review-design`  
审查性质：独立、只读、R3。

本审查只覆盖冻结 `research_governance_threat_model_v1.md` 内的普通 schema/path/TOCTOU/concurrency/crash/ACL/runtime 配置错误。未将 hostile runner、host/control root/kernel/ACL compromise 或恶意 native injection 作为 finding。

未修改产品代码、测试、契约、历史证据、gate 或 quality ledger；未运行训练、M6 replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。

## Findings

### [P1] v7 reservation 冻结的是 namespace policy digest，不是 binding-time parent identity；同 metadata 的 parent replacement 无法按承诺 fail closed

**Section：** v15 §1 第 11–16 行、§2 第 32–36 行；v12 §1 第 11–22 行、§2 第 38–44 行。

**Scenario：** binding freeze 时 supervisor 从 policy/root FD 打开 namespace parent、检查 ACL 并确认 basename 不存在。可是 `ReplayOutputNamespace v1` 的 closed fields 只包含 logical namespace、control-root-relative parent path、owner/mode/POSIX ACL、writer、output schema/no-reuse；`FreshOutputReservation v1` 只绑定 namespace-policy digest。二者都没有记录 binding-time parent 的 FD identity（例如 device/inode/mount/validated parent-chain identity）并要求 execution/acceptance equality。

因此在冻结后、执行前，一个普通部署/恢复错误可以把 parent `D0` rename/replace 成同一路径的 `D1`。只要 `D1` 仍具有相同 owner/mode/ACL，执行时的 reopen/validation、absence check 和 `mkdirat(D1, basename)` 都会成功。`OutputReservationReceipt v1` 只会记录 **D1 的执行时** point-in-time identity；由于 v7 没有 D0 的预期 identity，`ReplayExecutionReceipt v6`、child receipt 和 `m6_archive` 无从比较 D1 是否就是冻结时检查过的 namespace。错误根仍可得到一个内部自洽的 reservation receipt 并被 archive acceptance 接受。

**Impact：** 这重新留下普通 parent substitution/path-rotation 错误，违背 v12/v15 自己要求的 “parent replacement … fails” 与 no-free-output-root 合同。问题不需要攻击者控制 runner 或 host：一次同 ACL 的目录替换即可让回放输出写入并接受到错误的 namespace。对于 archive replay，这等同于错误 output authority 的 P1 数据/证据完整性缺口。

**Evidence：**

- v12 §1 的 `ReplayOutputNamespace v1` 和 `FreshOutputReservation v1` field lists 没有 binding-time parent FD identity；v15 §1 同样只把 policy digest 放入 reservation。
- v15/v12 把 parent/root FD identity 首次写入 `OutputReservationReceipt v1`，它发生在 execution 的 `mkdirat` **之后**，只能描述实际使用的 parent，不能证明它等于 freeze 时的 parent。
- 文本承诺 tests 拒绝 `parent substitution`，但现有 required fields 无法区分 D0 与相同 metadata 的 D1。root-FD/no-follow 可避免路径穿越，却不能弥补缺失的跨时点 identity equality。
- v7 的 input inventory、v5/v2 M7 migration、effective startup/umask、M6 `6/44` genesis 和 final-OOS seal 在本场景中都可保持正确，故它是独立的 output-namespace binding 问题。

**Direction：** 在进入 test-design 前将 parent identity 作为冻结对象而不是仅作为 execution observation：

1. 在 v7 内新增/扩展一个 closed `ReplayNamespaceParentBinding v1`，由 binding-time root FD 产生，至少记录 policy digest、control-root-relative path、Linux parent FD identity（含 mount/device/inode 等可比较字段）、owner/mode/ACL digest 和 required parent-chain identity；其 digest 必须进入 `FreshOutputReservation v1`。
2. execution 只能从 verified control-root FD reopen parent，并在 absence check、`mkdirat`、descriptor handoff 和 `m6_archive` acceptance 前分别验证 observed parent identity 等于 frozen parent binding；`OutputReservationReceipt v1`、`ReplayExecutionReceipt v6` 与 child receipt 都重复 expected/observed parent-binding digest and equality。
3. parent rename/recreate—even with identical path, UID/GID, mode and ACL—must quarantine/fail before verifier launch; a post-creation parent/root substitution must likewise prevent archive acceptance. Preserve the reserved root FD only for the same verified binding, never as a path fallback.
4. Synthetic tests must specifically replace D0 with an identically permissioned D1 between freeze and execution, and again after `mkdirat` before acceptance; both cases must leave no accepted output and no legacy-ledger mutation.

## Controls verified as retained

除上述 P1 外，本轮未发现 v12/v15 回退以下冻结边界：

- `ArtifactRef` 与未来 output 的概念分离正确：existing `ReplayOutputNamespace v1` 仍是 measured policy artifact，而 `FreshOutputReservation v1` 不伪造 future SHA/bytes；execution-time `mkdirat` 是明确的 fresh-root linearization point，`EEXIST`、symlink/type/ACL/mode/owner/non-empty root 与 caller output root 均 fail closed。
- v7 完整保留 transfer/archive/internal manifest/tree、M6 spec/gate/close proof/historical verifier、M3 every consumed partition、run/candidates/14 folds/checkpoints/predictions/K16 refit、legacy ledger、runtime/helper/bootstrap/process-state 与 `14 replay / 0 fit / OOS=false` inventory；没有重新开放 caller source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter roots。
- v11/v14 的 M7 descriptor v5/closure-receipt v2 migration、v1/v4 fail-closed policy、Plan/QRC DAG、same-lock close/permit、post-exec claim、four-actor ACL/publisher transaction、effective hash/umask closure 和 verified M6 `6/44` genesis 均由 v15/v12 明确保留。
- `docs/STATUS.md` 正确保持 M6.5 design-review pending；M7 fit、archive replay、CCC/Gate、final OOS 与生产交易没有获得新授权。

## Verdict

`NEEDS_CHANGES`：**0 个 P0、1 个 P1、0 个 P2、0 个 P3**。最早修复阶段为 `architecture`，随后必须同步更新 canonical change design 并重新取得独立 design-review。修复前不得进入 test-design、实现、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或最终 OOS。

## 审查限制

- 只读检查 v15/v12、frozen threat model、`docs/STATUS.md`、v11/v14 retained contracts、现有 replay/governance source 的接口事实与 quality route；没有把当前未实现代码当作通过。
- 没有运行项目代码、训练、M6 replay、预算消费、PIT `CERTIFY` 或最终 OOS。
- quality router 在审查时选择 `design-review`；ledger 观察 revision 为 `88`、source digest 为 `sha256:511a211bb4cfdf5fad857d82e6b519ac5aacb0cf6b990f047b18748f1f161845`。本报告与 companion result JSON 不修改 ledger；主流程记录前必须重新调用 router 并使用届时 revision/source digest。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 88,
  "source_digest_observed": "sha256:511a211bb4cfdf5fad857d82e6b519ac5aacb0cf6b990f047b18748f1f161845",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "FROZEN_REPLAY_NAMESPACE_PARENT_IDENTITY_NOT_BOUND_TO_RESERVATION",
  "summary": "v12/v15 correctly split a future output root from existing ArtifactRef inputs and add atomic mkdirat reservation. However, FreshOutputReservation binds only the namespace-policy digest: the parent FD identity is observed only after execution mkdirat, not frozen and compared across freeze/execution/acceptance. A same-path, same-ACL parent replacement can therefore be accepted despite the promised parent-substitution rejection.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 0, "P3": 0},
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
  "status_evidence": {
    "path": "docs/STATUS.md",
    "sha256": "sha256:5db8aa7431243826db5a5fd0856c1146e33cf8a5e1d6da933000ca7d97d3dc06"
  },
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next --ledger .engineering-quality/changes/m6-5-pre-m7-repair/ledger.json --repo . (route inspection only)",
    "read-only inspection of retained v11/v14 design, current replay/governance source and status evidence"
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
    "Freeze and compare namespace-parent identity across binding, reservation, execution and archive acceptance, then re-run independent design review.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
