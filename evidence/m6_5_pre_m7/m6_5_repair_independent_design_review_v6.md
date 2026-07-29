# M6.5 R3 修复设计 v6 独立设计审查

审查结论：`PASS`（仅为工程设计审查）  
审查技能：`eng-review-design`  
审查性质：独立、只读、R3；未修改产品代码、测试、冻结契约、gate 或质量账本，未运行训练、server replay、真实 M7 PIT `CERTIFY`、预算消费或最终 OOS。

PIT 导航模式：`VERIFY`。本报告只核对未来生产 handoff 的证据合同是否正确引用 `CERTIFY` 和行为证明；它**不**产生任何 PIT `PASS`、`QUALIFIED`、数据认证、M7 放行或 Alpha 结论。

审查对象：

- `evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md`，SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78`；
- `evidence/m6_5_pre_m7/architecture_confirmation_v9.md`，SHA-256 `e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598`；
- `evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。

## Findings

### [P3] 将 replay 的新鲜输出根和 grant 形状在 test-design 中固定为显式字段

**Section：** v6 §6；architecture v9 §4。  
**Scenario：** 设计已要求 `output reuse` 必须失败，并把 output policy、nonce、execution receipt 与 child receipt 纳入链路；但 `ReplayExecutionReceipt` 所称的 `grant` 与“新输出根/空目录”的精确字段尚未列成最小 closed schema。若在实现时只把它们作为自由路径或习惯约定，诊断 stale-output/错误输出根会较困难。  
**Impact：** 这是实现可观测性和测试精确度问题，不是当前信任边界缺口：supervisor 是冻结威胁模型内的受信根，v6 已明确要求 binding/receipt agreement 且 output reuse fail-closed。  
**Direction：** 在后续 `test-design` 给 `M6ReplayLaunchGrant`（或等价 supervisor execution authorization）和 `ReplayExecutionReceipt` 固定 `binding_sha256`、`nonce`、唯一 `output_root`、启动前 empty/inventory digest、输出 inventory digest、owner identity 和 child-result hash；用 output-root reuse/非空启动/receipt 指向错误根的负例锁定 v6 现有要求。

除上述明确非阻断的 P3 外，未发现 P0、P1 或 P2。

## 核对结果

### 1. 已验证 M6 `6/44` genesis

v6 §3 与 architecture v9 §1 恢复了此前缺失的完整 authority 起点：`M6CloseArchiveProof v1` 绑定 M6 gate/static evidence、获批 historical verifier blob、`4/29` pre-run prefix、byte-exact 的 51 行 / 14,328 bytes / `31a90…` close snapshot、保留 ID 集和 terminal chain；`LedgerAuthorityGenesis v2` 再绑定该 proof 与 close bytes。该链与现有 immutable budget 的 `4/29 -> 6/44` 数量、M6 gate 的 full close-ledger hash 一致。

新 installer 只能在 supervisor control root 的 lock 中创建新的 policy-derived authority namespace，拒绝 server legacy `contracts/trial_ledger.jsonl`、旧 `4/29` head、unknown tail、错误 proof/path/schema/link/target 以及历史覆盖。`RunAuthority` 明确冻结 genesis、ledger/head/parent、budget/spec、journal/output 与完整事件计划；reconcile 采用 stable lock、temp/fsync/replace，并要求所有失败零修改。故此前“服务器 legacy prefix 重新成为预算起点”的 P0 已关闭。

### 2. State、PIT 与派生行为链

v6 正确区分 construction 与 empirical eligibility：`StateBuildBinding v2` 的 construction artifact 状态是 `BUILT_NOT_EMPIRICALLY_CERTIFIED`，不能导入 labels/execution/purge/M3/model/ledger，且 `CandidateTrainingInputManifest` 只是 audit-only consumed-value view，不是 Dataset 或 model-input capability。

正式绑定的顺序为 candidate → future frozen QRC/coverage/authorization plan → PIT `CERTIFY` → complete behavior bundle → audit-only join。production loader 被要求拒绝 `VERIFY`、synthetic root、test adapter、partial/fake behavior，并消费未来真实 `CERTIFY` 输出中的 production adapter、`FULL_TRAINING_INPUT`、匹配锚点及固定检查结果；这与 PIT skill 对正向 handoff 的边界一致，且并未把本轮 synthetic 测试表述为数据认证。

`StateBehaviorCoveragePlan v1` 对四个 derived sources、全部 flag/outcome/reason、population membership 和 aggregates 设 complete projection；每个适用 source/predicate/aggregate 要求 `FUTURE_POISON`、`REVISION_REPLAY`、`UNIVERSE_CANARY`，`PREFIX_REPLAY` 仅为补充，例外需 QRC 理由和替代 probe。每一 receipt 又要求同一固定 audit parent、B001–B004、完整 lineage 与 protected candidate key/value 的 equality（非 overlap）。这满足“固定 PIT audit 与独立 behavior proof 不相互替代”的合同。

### 3. 普通并发、崩溃与 official result

在冻结威胁模型限定的正常运行情形中，v6 §5/architecture v9 §3 已给出连续、可测试的边界：supervisor 先将 exact state/candidate materialize 到 job-private immutable snapshot，重新 hash/fsync/原子发布，再由 ACL/ownership 使其对 runner 只读；`FitAdmissionDescriptor` 绑定 event/budget/head、state/PIT/behavior/join/candidate hashes、snapshot、fold/segment/date/schema 和唯一 output roots。runner 只从复核后的 snapshot FDs 重建输入，caller frame/tensor/path 不能生产 official output。

稳定 lease 加 event-specific `O_EXCL` claim、claim/`DISPATCHED` fsync 后才 fit、crash 即花费 event、retry 使用独立 contingency event，足以处理本 threat model 内的正常竞争、重启和半写恢复。单次授权 worker 的恶意 raw/native fork、runner 任意代码执行及 control-root/host compromise 均由冻结威胁模型明确排除，不能被重新作为本轮 P1。

runner 只能写 unique staging；独立 Unix identity 的 `result-publisher` 是唯一 final/index writer，并重新 hash staging regular files 与 terminal job receipt 后原子发布。`OfficialResultResolver` 仅接受 publisher 的 `TERMINAL_PUBLISHED` 记录和匹配 final inventory/hash，直接路径、staging 和缺 terminal 的 final 都隔离；崩溃产物保留取证但不自动 promote/reuse。因此此前“非终态或未知输出成为 official result”的普通流程缺口已关闭。

### 4. Frozen replay binding 与 clean execution

v6 §6/architecture v9 §4 已重新建立外部冻结的 `M6ReplayInputBinding v2`，并将 transfer manifest、archive/single root、internal manifest/tree、M6 revision/spec/gate/close proof、verifier、launcher bundle、runtime、`14 replay / 0 fit / OOS=false` profile、read-only legacy ledger 与 output policy 放入同一 binding。它不再把 verifier 的自报 hash 当作唯一证据。

可信 supervisor 从 measured deployment 以固定 interpreter/runtime/argv 和 `env -i` allowlist 启动批准 launcher，拒绝 Python/dynamic-loader injection，并在 verifier/launcher 自述之外写入 `ReplayExecutionReceipt`（binding/grant、launcher/verifier/runtime FD hash、argv/environment digest、PID/start、nonce、child exit、ledger before/after）。launcher 进行 safe extraction/temp-tree import；`m6_archive` 只有在 input binding、execution receipt 与 child receipt 一致时才接受，archive/tree/verifier/launcher/runtime/environment/output reuse/ledger-write mutation 均应 fail-closed。

这在已冻结的“supervisor/control root/ACL/frozen runner 受信、host/identity compromise 不在本阶段对手模型”范围内，足以关闭此前 archive/verifier self-consistency、错误 launcher 与污染环境的 P1；它不声称 hostile-host attestation。

## 应保留的设计边界

- M6 public `PeerLiteModel` / `PeerLiteNetwork` 的 Gate/`market_state` surface 被移除；历史 archived source 仅为 M6 replay 使用，不能成为新 M7 input path。
- M6.5 只实现和测试 `SYNTHETIC_NOT_EMPIRICAL` mechanics；production loader/runner 拒绝该根。任何真实 M7 QRC freeze、`CERTIFY`、fit、CCC/Gate 实验、server replay 或 final OOS 均不在本次审查授权内。
- 本次 `PASS` 只允许质量路由器前进到 `test-design`；它不是实现、测试、代码审查、E2E、M6.5 gate 或 M7 的完成声明。

## Verdict

`PASS`。在 `research_governance_threat_model_v1.md` 所冻结的责任边界内，v6 是连贯、比例适当且可进入 test-design 的 R3 实施合同；P0/P1/P2 为零。此前 v5 的 genesis、state-to-fit、official result、replay input/launch-exec 和环境链问题均已在 v6/v9 中得到明确的架构和实现约束。P3 不阻断后续阶段，但必须在 test-design 中转为可执行的负例。

## 审查范围与限制

- 只读检查了 v6/v9/threat model、M6 immutable budget、M6 gate、server v2 replay receipt、status card、M6.5 change request、PIT audit/behavior specifications及先前 v5 reviews；
- 未运行测试、lint、类型检查、server 命令、训练、真实 PIT `CERTIFY`、replay 或最终 OOS；
- 质量 ledger 在读取时为 revision `51`，且 router 选择 `design-review`。记录本报告前，主流程必须重新执行 `quality_ledger.py next` 并使用当时的 revision/source digest；本报告不修改 ledger。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 51,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-read-only-r3-review",
  "verdict": "PASS",
  "reason_code": "DESIGN_REVIEW_PASS_UNDER_FROZEN_RESEARCH_GOVERNANCE_THREAT_MODEL",
  "summary": "Under the frozen research-governance threat model, v6 restores the verified 6/44 authority genesis, separates synthetic construction from future CERTIFY plus complete behavior evidence, defines normal-concurrency/crash and terminal-result controls, and binds replay inputs to a supervisor-owned clean execution receipt. No P0/P1/P2 remains.",
  "issue_type": "none",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 0, "P2": 0, "P3": 1},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
    "sha256": "sha256:2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v9.md",
    "sha256": "sha256:e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "evidence_paths": [
    "contracts/immutable/m6_trial_budget_start.json",
    "evidence/gates/M6_peerlite_gate.json",
    "evidence/m6_5_pre_m7/m6_archival_replay_server_receipt_v2.json",
    "contracts/changes/m6_5_pre_m7_quality_gate_v1.json",
    "docs/STATUS.md",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/SKILL.md",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/audit_spec.md",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/behavior_spec.md"
  ],
  "commands": [
    "read-only rg/nl/sed/shasum/jq",
    "quality_ledger.py next (route inspection only)"
  ],
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v6_lead",
    "limitations": [
      "Read-only design review artifact; no product/test/contract/gate/ledger mutation.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access.",
      "PIT discussion is VERIFY-only and is not a PIT certification result."
    ]
  },
  "non_blocking_follow_up": [
    "Freeze replay fresh-output-root and grant schema fields in test-design, then cover output reuse and wrong-root negatives."
  ],
  "next_route": "test-design"
}
```
