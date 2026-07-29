# M6.5 canonical v10 / architecture v13 独立设计审查

## Findings

### [P1] 被保留的 admission descriptor 仍要求 `RunnerExecutionClosure v1`，而新 hash-policy 只存在于 `RunnerExecutionClosure v2`，导致 pre-permit binding 没有唯一可实现的 schema

**Section：** `architecture_confirmation_v13.md` §1（明确保留 `architecture_confirmation_v12.md` §4）和 §2；被保留的 v12 §4.1（第 72 行）；`m6_5_repair_change_design_v10.md` §1、§3.1–§3.2。

**Scenario：** v13 明确将 v12 §4 原样纳入 canonical architecture；该段规定 `FitAdmissionDescriptor v4` 绑定的是 `expected RunnerExecutionClosure v1`。但 v13 §2 和 v10 §3 将能承载 `PythonStartupPolicy v1`、effective hash receipt 的 authoritative object 改为 `RunnerExecutionClosure v2`，并将 receipt 改为 `RunnerExecutionReceipt v2`。因此严格 closed-schema implementation 有两个错误选择：接受 v1 descriptor 时不能把 v2 policy/receipt 作为其预期 closure；或把 v1/v2 视为可替代/在 v4 内原地改变字段语义，从而又允许旧的 environment-only closure 跨越 claim/permit。

**Impact：** 这不是命名细节。descriptor 是 runner 启动前、permit 前的 immutable anchor；它必须精确选择包含 effective startup policy 的 closure。当前文字要么让所有 v2 runner 因 v1 类型不匹配而拒绝，要么需要实现者放宽 version/equality check。后者直接重新打开 v9 P1 所防的“receipt 看似匹配、有效 hash policy 未被绑定”的普通配置路径，并令 claim/dispatch/publisher 的 receipt propagation 没有单一 schema。

**Evidence：**

- v13 §1 的 composition 保留 v12 §4；v12 §4.1 明写 `FitAdmissionDescriptor v4` 的 expected object 是 `RunnerExecutionClosure v1`。
- v13 §2 和 v10 §3.1 明写 `RunnerExecutionClosure v2`、`RunnerExecutionReceipt v2`；新增的 `PythonStartupPolicy v1` / `EffectiveHashPolicyReceipt v1` 只在 v2 链中出现。
- 静态交叉检查同时得到：`v12_descriptor_requires_closure_v1=True`、`v13_retains_v12_section4=True`、`v13_defines_closure_v2=True`、`v10_defines_closure_v2=True`。
- 该问题只依赖正常的 schema/version/activation 选择，不假设 hostile runner、host、control root、ACL 或 native-code compromise。

**Direction：** 在 architecture 与 canonical design 中发布单一、严格的 schema evolution matrix。推荐以新 `FitAdmissionDescriptor` version（或明确且完整的 v4 replacement，而不是同名字段的隐式重解释）精确引用 `RunnerExecutionClosure v2`、其 `PythonStartupPolicy v1` digest 和预期 effective-policy receipt contract；随后明确 claim/dispatch/prepared/terminal/resolver 分别绑定 `RunnerExecutionReceipt v2` / effective receipt 的哪个 immutable digest。旧 v1 descriptor/closure/receipt 必须 fail closed，不能 alias、降级或自动升级。测试必须覆盖 v1 descriptor + v2 closure、v2 descriptor + v1 closure、正确 closure + substituted effective receipt 以及 stale descriptor 的拒绝。

### [P1] “完整替代” M6 replay 段落时没有实际保留 `M6ReplayInputBinding v5` 的完整输入 inventory 与 no-free-path 合同

**Section：** `m6_5_repair_change_design_v10.md` Canonical incorporation（第 13–18 行）及 §3–§4；`architecture_confirmation_v13.md` §1（第 9–13 行）；被替代的 `m6_5_repair_change_design_v9.md` §6 和 v12 §6 第二段。

**Scenario：** v10 规定其 §4 **完整替代** v9 §6；v13 又规定其 §2 完整替代 v12 §6 的 M6 replay 第二段。被替代段落是 `M6ReplayInputBinding v5` 的唯一明确来源：它枚举 transfer/archive/internal manifest、M3 consumed partitions、M6 run/candidates/14 fold/checkpoints/predictions/K16 receipt、只读 ledger/new output、verifier/bootstrap/FD-exec helper/runtime，并禁止 caller-provided source/product/run/checkpoint/prediction/ledger/output/runtime roots。v10/v13 的新段落只定义 runtime startup / effective receipt；它们没有重新声明该 binding、完整 role inventory、no-free-path rule 或三方 binding 关系，尽管摘要文字声称 “M6 v5 input inventory / M6 input binding requirements” 被保留。

**Impact：** canonical composition 出现直接矛盾：按“complete replacement”字面实现，M6 replay 可以拥有正确的 CPython seed/flags/runtime receipt，却不再被要求绑定正确的 archive/product/run/checkpoint/prediction input universe。这重新打开先前已关闭的普通错误根选择/错误 archive replay 路径，且无法从新文字判断 `ReplayRuntimeClosure v3` 应该由哪个 immutable input binding 选择。

**Evidence：**

- v9 §6 的 `M6ReplayInputBinding v5` 与 no caller paths 是明确、可检查的输入合同；v12 §6 第二段也保留同一 binding 语义。
- v10 明写 “§4 完整替代 v9 §6”，v13 明写替代 v12 的 M6 replay 第二段；两个 replacement 都未出现 `M6ReplayInputBinding v5` 或等价的 closed inventory。
- 静态交叉检查结果：`v9_has_m6_input_binding_v5=True`、`v10_says_complete_replace_v9_section6=True`、`v10_restates_m6_input_binding_v5=False`、`v13_replaces_v12_m6_paragraph=True`、`v13_restates_m6_input_binding_v5=False`。

**Direction：** 明确保留 v5 的所有 input roles/no-free-path/three-way agreement，或发布一个新 version（例如 `M6ReplayInputBinding v6`）将该完整 inventory 与 `ReplayRuntimeClosure v3`、`PythonStartupPolicy v1`、bootstrap/helper 和 `ReplayExecutionReceipt v5` 一并精确绑定。architecture 的 composition 必须逐项说明：旧 M6 段落中哪些 input requirements 原样保留，哪些 runtime fields 被替换；不能只用摘要性 “requirements remain” 覆盖完整替代。后续 synthetic matrix 应单独拒绝每一种缺失/替换 input role、任何 caller path flag、v2/v3 runtime 混用和正确 startup receipt 配合错误 input binding 的情况。

## Verdict

`NEEDS_CHANGES`：0 个 P0、2 个 P1、0 个 P2、0 个 P3。最早修复阶段为 `architecture`，随后需同步修订唯一 canonical change design 并完成新的独立设计审查。修复前不得进入 test-design、实现、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或最终 OOS。

`PythonStartupPolicy v1` 的**启动语义本身**正确解决了 v9 的 `-I` 问题：它在 CPython 初始化前构造 exact `envp`，只允许 `PYTHONHASHSEED=0`，禁用 `-I/-E`，使用 `-s -S -P`，并在任何 runner/verifier import 或 M7 claim 前检查 flags、probe、module origins 后传播 effective receipt。该方向应保留。当前本机 Python 3.9.6 不支持 `-P`，与文档所述“非 CPython 3.11 只可 synthetic/fail closed”一致；本审查没有把本机当成 authority runtime。

以下既有治理边界也应保留：无环 Plan/QRC DAG、post-exec-only `DispatchClaim v1`、CLOSING/permit 同锁线性化、non-alias UID/GID/ACL/socket checks、publisher-only terminal index、M6 `6/44` genesis、PIT/behavior/state handoff、synthetic-only boundary、M6 history immutability 与 final-OOS seal。它们未构成本报告的新 finding；上述两个 cross-version/canonical-composition 断裂必须先修复，才能证明这些边界仍由同一闭合链执行。

## Scope, evidence and limits

- 审查对象：
  - `evidence/m6_5_pre_m7/m6_5_repair_change_design_v10.md`，SHA-256 `a1ef1422e0d4c247396a2b900bec60291ba4cb3b9399762755b51d204ca4f3e3`；
  - `evidence/m6_5_pre_m7/architecture_confirmation_v13.md`，SHA-256 `54d8ca248206a1c702ac3fe84f708edb5223a82ae6b9c44ef67396a5f0bc0bc4`；
  - retained evidence: v6 SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78`、v9/v12 canonical documents 和 frozen threat model SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。
- 只读使用 `shasum`、`rg`、`sed`、`nl`、`jq`、`git diff/status`、静态 cross-document assertions、quality-ledger inspection，及无项目数据的 local Python flags capability probe。未修改产品、测试、契约、gate、M6 历史或 quality ledger；本报告本身是独立审查证据。
- 未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。PIT 仅以 `VERIFY` 模式核对已保留的 handoff 合同，不产生 PIT `PASS`、`QUALIFIED`、数据认证、M7 放行或 Alpha 结论。
- Findings 限于冻结研究治理 threat model 内的普通 canonical composition、schema evolution、runtime/input binding 语义；不把 hostile runner arbitrary native code、host/control-root/kernel/ACL compromise 或恶意注入当作阻断理由。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 76,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "CLOSURE_SCHEMA_VERSION_AND_M6_INPUT_BINDING_CONTINUITY_BROKEN",
  "summary": "The new exact-envp, no--I/no--E, -s -S -P startup policy correctly addresses the effective PYTHONHASHSEED problem in isolation. But canonical composition retains a descriptor that types its expected closure as v1 while the policy exists only in v2, and complete replacement of the M6 replay section drops the explicit M6ReplayInputBinding inventory/no-free-path contract. Both are normal-operation P1 binding gaps.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 0, "P3": 0},
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v10.md",
    "evidence/m6_5_pre_m7/architecture_confirmation_v13.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v9.md",
    "evidence/m6_5_pre_m7/architecture_confirmation_v12.md",
    "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md"
  ],
  "commands": [
    "read-only shasum/rg/sed/nl/jq/git diff/status",
    "quality-ledger inspection only",
    "static cross-document version/inventory assertions",
    "local Python flags capability probe without project data"
  ],
  "subject_digest": "sha256:a1ef1422e0d4c247396a2b900bec60291ba4cb3b9399762755b51d204ca4f3e3",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v10.md",
    "sha256": "sha256:a1ef1422e0d4c247396a2b900bec60291ba4cb3b9399762755b51d204ca4f3e3",
    "incorporated_base": {
      "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
      "sha256": "sha256:2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78",
      "retained_sections": ["1", "2", "3", "4", "7"]
    }
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v13.md",
    "sha256": "sha256:54d8ca248206a1c702ac3fe84f708edb5223a82ae6b9c44ef67396a5f0bc0bc4"
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
    "Publish an unambiguous schema-version/reference matrix for v2 M7 closure/receipt propagation and reject all v1 aliases.",
    "Restore or version-forward the complete M6 input binding/no-free-path contract together with ReplayRuntimeClosure v3 and ReplayExecutionReceipt v5.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
