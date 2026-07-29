# M6.5 canonical v10 / architecture v13 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查技能：`eng-review-design`  
审查性质：独立、只读、R3。

本审查限定于冻结 `research_governance_threat_model_v1.md` 中的普通配置、启动、环境、路径、并发、崩溃与 ACL/runtime 误选。没有把 hostile runner 的任意代码执行、control root/host/ACL 被攻破或恶意 native injection 列为 finding。

未修改产品代码、测试、契约、gate 或 quality ledger；未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。

## 审查对象

- canonical change design：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v10.md`，SHA-256 `a1ef1422e0d4c247396a2b900bec60291ba4cb3b9399762755b51d204ca4f3e3`。
- canonical architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v13.md`，SHA-256 `54d8ca248206a1c702ac3fe84f708edb5223a82ae6b9c44ef67396a5f0bc0bc4`。
- frozen threat model：`evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。

## Findings

### [P1] v13 升级为 `RunnerExecutionClosure v2`，但其显式保留的 admission schema 仍只绑定 `RunnerExecutionClosure v1`

**Section：** v13 §1 第 9–13 行、§2 第 17/36 行；v12 §4 第 72 行（被 v13 §1 明确保留）；v10 §1 第 13–18 行、§3 第 41/83 行。

**Scenario：** v13 说 `RunnerExecutionClosure v2` 和 `RunnerExecutionReceipt v2` 必须携带并绑定 `PythonStartupPolicy v1` 与 `EffectiveHashPolicyReceipt v1`。但它同时把 v12 §4 原样纳入 canonical architecture；该段中 `FitAdmissionDescriptor v4` 的字段仍是 **`expected RunnerExecutionClosure v1`**。没有 migration/alias/rejection rule 说明 descriptor、claim、dispatch、prepared、terminal 和 publisher 究竟接受哪一个 schema，也没有规定旧 v1 一律拒绝。

在严格 closed-schema 的实现中，至少有三个普通实现结果：

1. descriptor parser 仍只接受 v1，正确的 v2 closure 在 claim 前被拒绝；
2. 实现把 v1/v2 静默当作同一种 closure，旧 v1 可绕过 v2 才有的 effective-hash-policy receipt；
3. 实现用未记载的 implicit upgrade，导致 expected/observed digest 虽相等却不再证明同一 schema/required field 集合。

第二种尤其会重新打开上一轮已修复的路径：一个旧 `-I`/environment-only seed closure 可被 admission 接受，而 v13 要求的有效 hash receipt 从未进入 descriptor-bound 官方结果链。

**Impact：** 这不是命名细节。M7 admission 是单次 `fit` 的授权边界；其 closure schema 不唯一会导致要么所有权威运行无故阻塞，要么旧运行时闭包被当成新闭包而终态发布。两种结果都违背“错误 launcher/runtime/environment 必须 fail closed”的冻结目标。

**Evidence：** v13 §1 只替换 v12 §5 和 §6 第二段，明确保留 v12 §4；v12 §4 明示 `expected RunnerExecutionClosure v1`。v13 §2 同时要求 v2 与 v2 receipt。v10 又以 v13 为架构依据并把 v2/v5 作为唯一 startup-policy-bearing objects。设计没有一个 canonical schema migration 来消除这组冲突。

**Direction：** 先在 architecture 层作一个单一、显式的 schema migration，再继续 test-design：

- 用新的 `FitAdmissionDescriptor v5`（或等价的完整 replacement）将 expected closure 精确限定为 `RunnerExecutionClosure v2` 的 `ArtifactRef`，并将 expected `PythonStartupPolicy`/`EffectiveHashPolicyReceipt` binding 列为 required closed fields；
- 明确 claim、dispatch、prepared、terminal、publisher 与 resolver 对 v2 的 schema/version/digest equality，且 **v1 一律在 claim/permit 前拒绝**，不得 implicit upgrade 或兼容接受；
- 对 archive 将相同的 v2/v3/v5 version edge 写成无歧义的 input-binding rule；
- 后续 test-design 至少覆盖 valid v2、v1 substitution、mixed v1/v2 receipt 和 missing effective receipt 都不能越过 claim/permit/archive acceptance。

### [P2] `umask` 被当作 exact `envp` 项列举，但没有 pre-exec 固定或可验证的有效 process-state 机制

**Section：** v10 §3.1 第 63–69 行、§3.2 第 73–79 行；v13 §2 第 22–34 行；被保留的 v12 §5/§6 第 100–110 行。

**Scenario：** 文本把 `umask` 列为 complete environment map/non-Python execution value，且要求 receipt 绑定 `umask`。但 POSIX `umask` 不是环境变量；`execveat`/`fexecve` 接收的 `envp` 不会设置它，反而会继承 helper 的 process state。设计的启动步骤只规定构造 exact `envp`、固定 cwd/flags 与 bootstrap 对 environment 的检查，未规定 helper 在 `exec` 前调用 `umask(policy_value)`，也未规定 bootstrap/receipt 如何观察并绑定已生效的值。

**Impact：** 一个普通 service/unit 配置漂移或 supervisor 启动时的错误 `umask` 会传递到 staged interpreter。这样 staging/cache/output 的实际 file mode 与 receipt/closure 所声称的值可不同；在最好的实现中晚些时候 ACL 检查才失败，在较弱实现中错误的权限或不可复现的 archive/output 已产生。它违反 v10/v13 对“exact effective runtime/environment”的闭环承诺，并削弱 runner/publisher 文件边界的可诊断性。

**Evidence：** v10 第 69 行把 `umask` 放在“complete map”内，第 73–75 行只对 `envp` 和 Python-visible state 设验证；v13 第 30/34 行同样只定义 constructed `envp` 和 environment-map bootstrap validation。没有 `umask(2)`/pre-exec setup、observed-effective value 或 mismatch rejection。

**Direction：** 将 `umask_octal` 从 environment map 拆为 `PythonStartupPolicy` 的独立 process-state 字段。FD-exec helper 必须在任何子解释器/脚本启动前无条件设置该值、记录其 effective value，并把它放入 `EffectiveHashPolicyReceipt`/execution receipts；bootstrap 在 import 前验证该值（或检测不到时 fail closed）。对 M7 与 M6 replay 使用同一规则，并在 test-design 中覆盖不同 inherited helper umask、缺失设置和 receipt substitution 都会在 claim/permit 或 archive acceptance 前失败。

## 已验证应保留的修复

除上述 finding 外，本轮没有发现新的 P0，也没有回归到以下已解决的普通错误路径：

- v10/v13 正确放弃 `-I`/`-E`，改为 exact `envp` + CPython 3.11 `-s -S -P`；这样 `PYTHONHASHSEED=0` 可在解释器初始化前生效，而 user-site、automatic `site` 和 unsafe path 仍被关闭。
- flags、canonical hash probe、stage/prefix/import-root 检查及 `EffectiveHashPolicyReceipt` 在 runner/verifier/source import 和 M7 claim/M6 root resolution 前完成；这修复了“只记录环境字符串、不证明 effective hash policy”的上一轮 P1。
- Plan/QRC 保持无反向 hash edge；`CLOSING` 和 permit consume 仍共用 linearization lock；claim 只由 post-exec worker 创建；numeric UID/GID non-alias/ACL revalidation、descriptor-bound publisher/no-replace transaction 和 replay receipt binding 均仍在 canonical composition 内。

这些控制应完整保留。当前 `NEEDS_CHANGES` 只要求消除 closure schema 版本歧义，并把 `umask` 从声明的值变成实际可观测的启动 process state；不授权增加任何新研究模型或运行范围。

## Verdict

`NEEDS_CHANGES`：**0 个 P0、1 个 P1、1 个 P2、0 个 P3**。最早修复阶段为 `architecture`，随后同步更新 canonical change design 并重新取得独立设计审查。修复前不得进入 test-design、实现、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或最终 OOS。

## 审查限制

- 只读检查 v10/v13、其明确纳入的 v9/v12 定义、冻结 threat model、质量路由和运行时版本约束；没有把设计文本当作实现通过。
- 没有运行项目代码、训练、server replay、预算消费、PIT `CERTIFY` 或真实数据动作。
- quality router 在审查时选择 `design-review`；ledger 观察 revision 为 `77`、source digest 为 `sha256:1b9043483c6a04688b885664c162fd3bbee086860308f552f47ef03ef3796c5a`。本报告不修改 ledger；主流程记录前须重新调用 router 并使用届时 revision/source digest。
- 未产生 PIT/data pass、M7 入场、Alpha、生产或最终 OOS 结论。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 77,
  "source_digest_observed": "sha256:1b9043483c6a04688b885664c162fd3bbee086860308f552f47ef03ef3796c5a",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "CLOSURE_SCHEMA_VERSION_AND_PROCESS_UMASK_NOT_CLOSED",
  "summary": "v10/v13 correctly replace the ineffective -I/PYTHONHASHSEED contract with exact envp plus -s -S -P and an effective receipt, and retain graph/dispatch/ACL/publisher/replay controls. But v13 retains a FitAdmissionDescriptor v4 that explicitly binds RunnerExecutionClosure v1 while requiring v2 elsewhere, with no migration or v1 rejection rule; it also treats umask as an envp item without setting or observing the inherited process state.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 1, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v10.md",
    "sha256": "sha256:a1ef1422e0d4c247396a2b900bec60291ba4cb3b9399762755b51d204ca4f3e3"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v13.md",
    "sha256": "sha256:54d8ca248206a1c702ac3fe84f708edb5223a82ae6b9c44ef67396a5f0bc0bc4"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next --ledger .engineering-quality/changes/m6-5-pre-m7-repair/ledger.json --repo . (route inspection only)",
    "read-only pyproject.toml and uv.lock inspection"
  ],
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_adversary",
    "limitations": [
      "No product/test/contract/gate/ledger implementation changes.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access."
    ]
  },
  "blockers": [
    "Publish a coherent closure-schema migration and an effective pre-exec umask rule, then re-run independent design review.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
