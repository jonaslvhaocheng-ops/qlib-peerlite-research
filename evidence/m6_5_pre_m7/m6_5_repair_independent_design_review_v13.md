# M6.5 v16/v13 独立 R3 设计审查

## Findings

未发现未解决的 P0、P1、P2 或 P3 finding。

## Verdict

`PASS`：**0 个 P0、0 个 P1、0 个 P2、0 个 P3**。

v16/v13 修复了上一轮的 namespace-parent identity 缺口，且没有重开任何 M6/M7、PIT、运行时或输出路径边界。`NamespaceParentBinding v1` 是先于 v8 创建的已有、hash-bound witness；它不把未来 output root 伪装为 `ArtifactRef`，也不引用尚未存在的 v8，因此未形成 binding hash cycle。`FreshOutputReservation v2` 只引用该 witness digest 和既有 namespace policy；最终 v8 再引用两者，依赖方向单向且可验证。

这是 **design-review gate 的 PASS**，不是实现、测试、code review、E2E、PIT certification、M6 server replay、M7 fit、CCC/Gate 实验、最终 OOS 或交易结论。后续仍必须按质量路由依次完成 test-design、实现、测试与独立 code review/E2E；在此之前，M7、server replay 和 final OOS 继续封存。

## 核对结果

### 1. Freeze → reservation → execution → handoff → archive 的 parent identity 链已闭合

- v16 §1 将 control-root 到 final parent 的完整有序 component identity chain、final parent identity、policy path、resolver 和 control-root digest 写入 `NamespaceParentBinding v1`；每个 identity 包含 directory type、device、inode、mount id、birth time、UID/GID、mode 与 access/default ACL fingerprints。
- `mtime`、`ctime`、`nlink` 被明确排除：创建子目录会改变这些父目录元数据，排除它们既不会掩盖替换，又避免正常 `mkdirat` 带来的假失败。
- binding v8 将 `NamespaceParentBinding v1 ArtifactRef` 作为既有输入，reservation v2 又包含其 digest；freeze 时必须用 root-FD/no-follow resolver 得到同一 witness 后才写 binding。该顺序避开了 parent-binding ↔ v8 的循环依赖。
- 执行阶段在 prelaunch、namespace lock 内、`mkdirat` 后分别进行完整 witness equality；handoff 仅传递 pinned FDs 和 binding/reservation/receipt digests；child receipt、supervisor receipt 与 archive 都要求相同 v8/v2/parent-binding/root identity。
- archive acceptance 再次取得 lock、重解 control-root → parent、比对 frozen witness、no-follow 打开 derived basename、比对 root identity 并 hash final inventory。因此 final parent 或任一中间 component 在 freeze 后、执行中或 handoff 后被替换，均不能形成 accepted output。

### 2. 输出对象、原子性和故障终态正确分离

- 未来 output root 明确不是 `ArtifactRef`，不会预填 SHA/bytes；只有 policy 和 parent witness 是现存、可测量的 ArtifactRef。
- `fstatat(..., AT_SYMLINK_NOFOLLOW) == ENOENT` 是冻结期 precondition，实际领取只有锁内 `mkdirat(parent_fd, basename, 0700)` 一个线性点。
- 预领取失败为 `REJECTED`；领取后任何 equality failure 或 crash 都是 `QUARANTINED_UNPUBLISHED`，并禁止 delete/recreate/promote/reuse。`EEXIST`、symlink、错误 type/ACL/owner/mode、non-empty root、stale receipt 和 caller path 都 fail closed。
- v16 的必测场景覆盖了同 UID/mode/ACL 的 D0→D1 替换、中间链替换、pre/post-`mkdirat` race、root/receipt/FD substitution、跨挂载/魔术链接和 crash，正好覆盖上一轮 P1 的同 metadata parent 替换。

### 3. M6 replay、版本迁移及继承控制没有回退

- v8 保留完整 M6 replay 输入集：transfer/archive/internal/tree、M6 spec/gate/close/historical verifier、M3 每个 consumed partition、run/candidates/14 folds/checkpoints/predictions/K16 refit、read-only ledger、sealed verifier/runtime/bootstrap/startup policy，以及 policy/parent-binding/reservation。
- 任何 caller 选择的 source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter/namespace-parent root 都被拒绝，profile 固定为 `14 replay / 0 fit / OOS=false`。
- v13 将 `NamespaceParentBinding v1`、reservation v2、binding v8、reservation receipt v2、execution receipt v7 列为唯一 authoritative 新合同；旧 v7/v1 reservation/binding 与 v6 receipt forms 均 rejection-only，禁止 silent upgrade。
- v15/v12 继承的 M7 `FitAdmissionDescriptor v5` / closure-receipt v2 链、v4/v1 fail-closed、non-alias actor ACL、`close_fds`/CLOEXEC、FD-exec、exact envp、有效 `PYTHONHASHSEED=0`、`-s -S -P` 和 helper/bootstrap 双重 `umask=0077` 观测均未被新文本放松。
- M6 `6/44` genesis、legacy `4/29` 拒绝、PIT/state/behavior handoff、public Gate denial、M7 未授权和 final OOS seal 仍由 canonical base 和状态卡维持；v16/v13 不授权任何实证行动。

## 范围、证据与限制

- 审查对象：
  - `evidence/m6_5_pre_m7/architecture_confirmation_v16.md`，SHA-256 `4a245590e8cc2a30610376167c67cbf3054d039a70fa2c7d410711f4d05992a4`；
  - `evidence/m6_5_pre_m7/m6_5_repair_change_design_v13.md`，SHA-256 `fdba160c3e22680b3ba20844966fef0e673cbcb66b9ad1a3b51b0f283dba9e8a`；
  - frozen threat model、`docs/STATUS.md` 和 retained v15/v12/v14/v11 contracts。
- 只读检查文档、版本拓扑、静态 schema/identity-flow invariants、质量 ledger snapshot 和 M6/PIT gate 元数据。未修改产品代码、测试、契约、gate、M6 历史或 quality ledger。
- 未运行训练、M6 replay、预算消费、真实 PIT `CERTIFY` 或 final OOS。
- Review 严格使用冻结威胁模型：受信 supervisor/control root/host ACL/frozen code；没有把 hostile runner、host/control-root/内核攻陷或恶意 loader 注入作为 design blocker。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 92,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "PASS",
  "reason_code": "BOUND_NAMESPACE_PARENT_V16_V13_DESIGN_COHERENT",
  "summary": "v16/v13 close the prior namespace-parent substitution gap by creating an immutable NamespaceParentBinding v1 before v8, binding its digest into FreshOutputReservation v2, and requiring exact control-root-to-parent equality at prelaunch, under-lock, post-mkdir, handoff and archive acceptance. The future output remains non-content/non-ArtifactRef, v8 retains the complete M6 replay inventory, and no PIT/M7/runtime/ACL guard regresses.",
  "issue_type": "none",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
  "artifact_paths": [
    "evidence/m6_5_pre_m7/architecture_confirmation_v16.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v13.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/architecture_confirmation_v15.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v12.md",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v12.md",
    "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "docs/STATUS.md",
    "evidence/gates/M6_peerlite_gate.json",
    "evidence/gates/M3_pit_data_gate.json"
  ],
  "commands": [
    "read-only shasum/rg/sed/nl/find/git diff/git status",
    "read-only JSON inspection of the Engineering Quality ledger snapshot and gate metadata",
    "static canonical-contract, version-topology, parent-chain identity-flow and threat-boundary assertions"
  ],
  "subject_digest": "sha256:fdba160c3e22680b3ba20844966fef0e673cbcb66b9ad1a3b51b0f283dba9e8a",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v13.md",
    "sha256": "sha256:fdba160c3e22680b3ba20844966fef0e673cbcb66b9ad1a3b51b0f283dba9e8a"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v16.md",
    "sha256": "sha256:4a245590e8cc2a30610376167c67cbf3054d039a70fa2c7d410711f4d05992a4"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "status_evidence": {
    "path": "docs/STATUS.md",
    "sha256": "sha256:0c625bb4dd01ab585bf825f3e52296520141dabdf34260dc9af6888ed476d7c5"
  },
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_lead",
    "limitations": [
      "Read-only review artifact; no product/test/contract/gate/ledger mutation.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access.",
      "This PASS approves only the R3 design gate, not implementation or empirical evidence."
    ]
  },
  "blockers": [],
  "next_route": "test-design"
}
```
