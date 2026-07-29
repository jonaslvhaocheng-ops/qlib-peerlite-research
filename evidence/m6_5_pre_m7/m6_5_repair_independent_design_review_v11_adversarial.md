# M6.5 canonical v11 / architecture v14 独立对抗式设计审查

审查结论：`PASS`（仅 G2 design-review）  
审查技能：`eng-review-design`  
审查性质：独立、只读、R3。

本审查严格限定于冻结 `research_governance_threat_model_v1.md` 的普通配置、并发、崩溃、schema/version、路径、ACL、startup/runtime 与 replay-input 误选。没有把 hostile runner arbitrary native-code execution、host/control-root/kernel/ACL compromise 或恶意 native/loader 注入作为 finding。

未修改产品代码、测试、契约、gate 或 quality ledger；未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。

## Findings

未发现未解决的 P0、P1、P2 或 P3 finding。

## 审查对象

- canonical change design：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v11.md`，SHA-256 `cdbcbff655d7e8de152d62e1d4aa33a1fa145ebb43ad8f7efde555ac39c52a21`。
- canonical architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v14.md`，SHA-256 `148490b9933be0311ff7c0b8626cdc5c3c268a2070cf6a6f49e9e26ac2af410f`。
- frozen threat model：`evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。

## 对抗性检查结果

### 1. v5/v2 schema migration 与 permit 前闭环

v11/v14 不再用 layered composition 隐式继承旧 schema。唯一的 M7 admission anchor 是 `FitAdmissionDescriptor v5`，它精确引用 `RunnerExecutionClosure v2`、`PythonStartupPolicy v1`、`ProcessStartupState v1`，并把 observed `RunnerExecutionReceipt v2` 列为 equality contract。`DispatchClaim v2`、`FitDispatchPermit v2`、`DispatchReceipt v3`、prepared/terminal/resolver objects 全部要求重复 descriptor/closure/startup/process/receipt digests。

关键地，旧 `FitAdmissionDescriptor v4`、closure/receipt v1、environment-only seed record 和任何 implicit alias/upgrade 都在 claim/permit 前拒绝。这样不会出现“v2 startup policy 实际已启用，但 v1 descriptor 仍为 official binding”的回退路径；当前 source 中尚未实现该 migration 不改变这个设计审查结论，后续实现/代码审查必须证明它已落地。

### 2. effective startup、hash 与实际 `umask`

`PythonStartupPolicy v1` 采用 exact `envp`、CPython 3.11、`-s -S -P`，仅允许 `PYTHONHASHSEED=0`，明确拒绝 `-I/-E` 和其它 Python/venv/loader injection variables。bootstrap 在 runner/verifier/source import、snapshot read、claim 或 replay root resolution 前核验 staged executable/prefix/argv/envp、flags 和 ABI-bound hash probe；这正确避免了此前 `-I` 忽略 environment-only hash seed 的问题。

`umask` 不再被错误地表示为 envp 项。`ProcessStartupState v1` 把它作为独立的 `umask_octal=0077`：FD-exec helper 在 `exec` 前设置并读取，发出 `LaunchStateReceipt v1`；bootstrap 再次观察并绑定该有效值。`RunnerExecutionReceipt v2` 与 `ReplayExecutionReceipt v5` 同时绑定 closure、policy、process/launch/bootstrap state，以及 argv/env/cwd/umask/probe/import/native-map/ABI/GPU facts；任何不相等必须在 M7 claim/permit 或 replay acceptance 前失败。

### 3. M6 replay v6 的完整 inventory 与 no-free-path boundary

`M6ReplayInputBinding v6` 恢复并显式列出所有原先容易丢失的输入类别，每项都要求 relative path、SHA-256、bytes、schema 与 logical role：transfer/archive/internal manifest/single root/full tree；M6 spec/gate/close proof/historical verification/frozen verifier；M3 product manifest 与每个 consumed partition；run/candidates/14 fold receipts/checkpoint metadata+state/prediction partitions/K16 deterministic-refit evidence；read-only ledger；helper/bootstrap/runtime/startup contracts；fresh output root 与固定 `14 replay / 0 fit / OOS=false` ceiling。

设计同时禁止 caller-supplied source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter roots，要求 supervisor 用 FD 验证和 staging，并让 binding、supervisor receipt 与 child receipt 三方精确一致。它因而关闭了“正确 runtime receipt 配错 archive/product/run root”的普通操作路径。当前 legacy replay script 仍有独立 CLI roots 是待实现的基线事实，不是本设计对其已经合规的声明；本 PASS 不替代之后的实现、code-review 或 E2E 证据。

### 4. authority graph、dispatch race、ACL 与 publisher/replay regression

- `M7AuthorizationPlan v1` 不持有 QRC/registry/grant/activation reference；QRC 后向绑定 Plan/policy，registry 再精确绑定两者与 M6 genesis，故 graph 不再形成 Plan↔QRC hash cycle。
- `CLOSING` 与 permit consumption 共用 activation/event lock；post-exec worker 才可按 `O_CREAT|O_EXCL` 创建 claim，supervisor 在同一锁内检查 profile/head/peer/process identity/snapshot/observed receipt，持久化 `DISPATCHED/FIT_STARTED` 并消费单次 permit 后才回应。fork poison、`CLOEXEC` 与独立 contingency event 规则仍完整保留。
- numeric UID/GID pairwise nonalias、groups/capabilities、POSIX ACL、socket `SO_PEERCRED`、root-FD/no-follow IO 和 permit/publish/resolve revalidation 一致；runner/publisher/replay actor 仍不能越过对象 class 的写权限。
- publisher 只从 `(activation_id,event_id)` 推导 sealed roots，验证 v5/v2 identity 和 regular-file inventory，随后 no-replace 终态发布；resolver 只读 terminal index。M6 replay 继续是 Linux x86_64 CUDA 的 read-only `14 replay / 0 fit / OOS=false` 合同。

## Verdict

`PASS`：**0 个 P0、0 个 P1、0 个 P2、0 个 P3**。v11/v14 为下一阶段 test-design 提供了单一、自包含、可实现且与冻结 threat model 相称的设计边界。

这不是 implementation、测试、PIT/data certification、server replay、M7 fit、Alpha、最终 OOS 或生产交易的 PASS。后续 quality gates 仍必须先通过；在此之前，真实 M7、CCC/Gate、server replay 和 final OOS 继续封存。

## 审查限制

- 只读检查 v11/v14、冻结 threat model、quality route、现有 replay/governance source 与既有 M6 evidence 的接口事实；没有把现有未实现代码当作通过。
- 当前 `scripts/server/verify_m6_peerlite_archival_replay.py` 的 caller-root CLI 是该 change 需要在后续 implementation 中替换/封闭的现状；本审查只确认 v11/v14 已经无歧义地规定目标行为。
- 没有运行项目代码、训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。
- quality router 读取时选择 `design-review`；ledger 观察 revision 为 `84`、source digest 为 `sha256:8b1163c4158020e0e9f6b5e3c79340943b804816092f840c128a820bc2e394cd`。本报告不修改 ledger；主流程记录前必须重新调用 router 并使用届时 revision/source digest。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 84,
  "source_digest_observed": "sha256:8b1163c4158020e0e9f6b5e3c79340943b804816092f840c128a820bc2e394cd",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "PASS",
  "reason_code": "SELF_CONTAINED_V11_V14_GOVERNANCE_DESIGN_COHERENT",
  "summary": "v11/v14 explicitly migrate M7 admission to descriptor v5 and closure/receipt v2 with v1 rejection, make effective seed and umask observed startup state, restore the complete M6 v6 inventory/no-free-path/triple-receipt contract, and retain graph, dispatch, ACL, publisher and replay controls. No new in-scope design defect was found.",
  "issue_type": "none",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v11.md",
    "sha256": "sha256:cdbcbff655d7e8de152d62e1d4aa33a1fa145ebb43ad8f7efde555ac39c52a21"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v14.md",
    "sha256": "sha256:148490b9933be0311ff7c0b8626cdc5c3c268a2070cf6a6f49e9e26ac2af410f"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next --ledger .engineering-quality/changes/m6-5-pre-m7-repair/ledger.json --repo . (route inspection only)",
    "read-only inspection of scripts/server/verify_m6_peerlite_archival_replay.py, governance source, immutable evidence and prior review artifacts"
  ],
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_adversary",
    "limitations": [
      "No product/test/contract/gate/ledger implementation changes.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access.",
      "This PASS approves the design gate only; it is not implementation, test, E2E, replay or empirical evidence."
    ]
  },
  "blockers": [
    "All later required quality stages remain pending; M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited until their applicable gates pass."
  ],
  "next_route": "test-design"
}
```
