# M6.5 R3 修复设计 v8 独立设计审查

## Findings

### [P1] QRC 与 AuthorizationPlan 的引用方向自相矛盾，既破坏 acyclic graph，也无法得到可验证的 content-hash freeze 顺序

**Section：** `m6_5_repair_change_design_v8.md` §5.1，第 114–130 行；`architecture_confirmation_v11.md` §3.1，第 58–70 行。  
**Scenario：** v8 明确规定 `M7AuthorizationPlan v1 (does NOT reference QRC) -> frozen QRC (binds plan + control policy)`，并以此作为无环 authority graph 的首段；这也是上一轮审查要求的单向 freeze 顺序。然而 v11 随后要求 `M7AuthorizationPlan v1 必须反向绑定同一 QRC`。若“反向绑定”是 content digest/reference（文档其余部分的 binding 语义），Plan 与 QRC 必须互相包含对方的最终 hash，无法先后冻结，也不再是 v8/v11 声称的无环 DAG。

**Impact：** 在正常 control-root 和 supervisor 都受信的条件下，安装器无法同时满足两份 canonical 文档：要么先生成一个不带最终 QRC hash 的 Plan，要么引入可变/两阶段 reference，要么放宽 equality check。后两种做法都会重新允许错误但内部自洽的 plan/QRC pair 绕过 external activation anchor，正是本轮要关闭的预算和 event-plan substitution 风险。

**Evidence：**

- v8 第 117–126 行将 Plan 不引用 QRC、QRC 绑定 Plan 写为明确的顺序；
- v11 第 58–60 行先重申 Plan 禁止引用 QRC，紧接着又要求 Plan 反向绑定同一 QRC；
- `ArtifactRef v1` 及各处 “full equality / exact digest” 语义均是最终 content identity，而非可延迟解析的逻辑标签；
- 此 finding 只涉及 frozen object 的正常构造顺序，不依赖 hostile runner、host、control root 或原生代码攻击。

**Direction：** 选定唯一的无环模型并在 v8/v11 同步：`M7AuthorizationPlan` 只绑定 family、budget、event plan、M6 genesis 与 control-policy **identity**，绝不绑定 QRC；frozen QRC 绑定 Plan digest；`AuthorityRegistryRoot` / profile 再同时绑定精确 QRC + Plan + policy + genesis。若业务上确实需要 QRC 预期身份，必须新增一个在 QRC freeze 后、独立于 Plan 的 downstream pair-binding object，而不能令两个 immutable content object 互指。测试必须拒绝 QRC↔Plan cycle、draft/placeholder hash、plan/QRC substitution、以及任何 install-before-both-frozen 路径。

### [P1] dispatch claim 的创建者、实际 direct-exec worker 与 ProcessIdentity 的时序在 v8 和 v11 不一致，at-most-once fit 边界无法按单一状态机实现

**Section：** v8 §5.2，第 143–147 行；v11 §3.2，第 81–85 行。  
**Scenario：** v8 的实现顺序是 supervisor 先启动 fresh direct-exec runner，实际 child 再以自己的 `ProcessIdentity` 创建 `DispatchClaim v1`，随后向 supervisor 请求 permit。v11 则写成 runner 先创建 `FitDispatchClaim v2`，随后 supervisor 再 fresh-exec “actual child”。这会把 claim 中的 PID/start-ticks/runner nonce 归属到 exec 前进程，而 permit peer-credential 校验的却是 exec 后 worker；两者要么天然不匹配，要么实现者只能放松 ProcessIdentity equality。

**Impact：** 前者导致每个合法 job 都被错误拒绝；后者重新留下 fork/inherited-FD/second-worker 以相同 retained event 跨越 `model.fit()` 的普通进程模型漏洞。该顺序亦决定 crash-after-claim、claim ownership、permit consumer、receipt correlation 和 test seam，不能留给实现阶段解释。

**Evidence：**

- v8 使用 `DispatchClaim v1`、`RunnerLaunchBinding v1`，并明确 “Supervisor launches … runner; child creates … claim”；
- v11 使用名称/版本不同的 `FitDispatchClaim v2`，且明确 “runner … creates … claim，随后 supervisor … fresh exec … worker”；
- 两份文档都把 exact `ProcessIdentity = boot_id + pid + start_ticks + nonce` 当作 fork-safe permit 的核心校验，所以这不是可忽略的命名差异；
- 当前仓库仅有 `flock`/ledger mechanics，没有一个可默认吸收这两个不同状态机的现有 dispatch abstraction。

**Direction：** 在 v8/v11 固定一个 schema 名称/版本和唯一时序。推荐：supervisor 在 sealed admission 后仅 spawn 一个 direct-exec worker；**该实际 worker** 在加载 model 前以自身 ProcessIdentity 创建 write-once claim；supervisor 只接受该 claim 的 fresh socket request，并在同一短事务中持久化 `FIT_STARTED`、consume permit、返回 success。不存在“claim 后再另起一个 actual child”的分支。将 `PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> CLAIMED -> DISPATCHED` 的 owner、allowed PID、crash outcome 与 immutable receipt 明确到同一 schema。测试应对该确切时序覆盖 fork-before/after-claim、PID/start mismatch、pre-fork pool、socket reconnect、permit reply loss、crash-after-consume 和双 worker race，并用 call-boundary spy 证明每 retained event 至多一次 `fit`。

## 审查结论与保留项

审查结论：`NEEDS_CHANGES`（0 P0、2 P1）。

v8 对上一轮四个实质边界已有明显、正确的补强，以下部分应保留：

- v8 纳入 v6 的 SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78` 与实际文件一致；M6 `6/44` close genesis、legacy `4/29` 拒绝、PIT/behavior/state chain、synthetic-only 及 M7/OOS 封印均未被删除。
- 除上述 QRC/Plan cycle 外，registry → grant → activation → fixed profile 的 external-anchor 思路、ledger logical-head、descriptor-bound snapshot、conservative `START_RETAINED` 和 publisher-only terminal index 能够覆盖上一轮 authority/publication 缺口。
- `M6ReplayInputBinding v4` 继续列举 M3 product 每个 consumed partition、M6 run/candidates/14 fold receipts/checkpoint metadata+state/predictions/K16 refit，并新增 interpreter、stdlib、`lib-dynload`、site packages、extension/native library、host ABI/CUDA/GPU 和 observed import/native-map closure。bootstrap-before-verifier、FD-exec、`env -i`、`-I -S`、no free paths 与三方 receipt agreement 正确解决了上一轮 “only qlib_peerlite origin” 的 P1。
- production PIT handoff 仍是 future frozen QRC → fixed PIT `CERTIFY` (`FULL_TRAINING_INPUT` / production adapter / 17 checks) → complete behavior bundle → join / state binding → immutable job snapshot；本审查未把 synthetic mechanics 或本次文档核对表述为 PIT certification。

这两项 P1 都处于冻结威胁模型已经要求处理的普通 object construction、process launch、restart/fork/identity 语义中；本报告没有把 hostile runner arbitrary native code、host/control-root/kernel/ACL compromise 或恶意 loader injection 当作 finding。

最早修复阶段：`architecture`，随后更新唯一 canonical change-design 并进行新的独立 design review。修复前不得进入 test-design、implementation、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或 final OOS。

## Scope、证据与限制

- 审查对象：
  - `evidence/m6_5_pre_m7/m6_5_repair_change_design_v8.md`，SHA-256 `c903ec58a789607cc1f7202f8279a4c1d0d58ac786157afd1116a34666b643cf`；
  - `evidence/m6_5_pre_m7/architecture_confirmation_v11.md`，SHA-256 `c3766c6aa50da57d0c0866d4f5542d1e227283da6a4abe5d2a15c2b67736d5f3`；
  - `evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。
- 只读检查了上述文档、v6 incorporation hash、上轮对抗审查、quality ledger route，以及当前 `trial_ledger.py`、archive verifier、public PeerLite surface 和依赖锁作为 repository evidence。
- 未改动产品/测试/契约/gate/ledger；未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或 final OOS。
- 本轮 PIT 讨论是 `VERIFY`-only 的证据合同核对，不产生 PIT `PASS`、`QUALIFIED`、数据认证、M7 放行或 Alpha 结论。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 66,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "PLAN_QRC_CYCLE_AND_DISPATCH_IDENTITY_SEQUENCE_CONTRADICTION",
  "summary": "v8/v11 preserve the verified 6/44 and PIT/state boundaries and substantially close authority, publication, and replay-runtime gaps. But the documents conflict on Plan-to-QRC reference direction and on the claim/exec-worker sequence, so the immutable authority DAG and fork-safe at-most-once fit state machine are not implementation-ready.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v8.md",
    "sha256": "sha256:c903ec58a789607cc1f7202f8279a4c1d0d58ac786157afd1116a34666b643cf",
    "incorporated_base": {
      "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
      "sha256": "sha256:2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78",
      "retained_sections": ["1", "2", "3", "4", "7"]
    }
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v11.md",
    "sha256": "sha256:c3766c6aa50da57d0c0866d4f5542d1e227283da6a4abe5d2a15c2b67736d5f3"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "evidence_paths": [
    "contracts/immutable/m6_trial_budget_start.json",
    "evidence/gates/M6_peerlite_gate.json",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "scripts/server/verify_m6_peerlite_archival_replay.py",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v7_adversarial.md"
  ],
  "commands": [
    "read-only shasum/rg/sed/nl/jq",
    "quality_ledger.py next (route inspection only)"
  ],
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
    "Remove the Plan-QRC cycle and normalize the single dispatch schema/launch sequence, then re-review.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
