# M6.5 R3 修复设计独立审查 v4

状态：`NEEDS_CHANGES`  
审查性质：独立、只读的 R3 设计审查。未修改产品代码、测试、契约、gate、账本或历史证据；未运行训练、server replay，也未访问最终 OOS。  
审查对象：

- `evidence/m6_5_pre_m7/m6_5_repair_change_design_v4.md`，SHA-256 `16ac80ae172cbedf077d9c2f3c4b74a89c6298303f8d17f30fdc14f28e0ad810`
- `evidence/m6_5_pre_m7/architecture_confirmation_v7.md`，SHA-256 `db91fab06cb271e9431de02491cae7c151e3d36c47edd7e3d093a0ad16ccb6b4`

PIT 导航模式：`VERIFY`。本审查仅验证未来生产 `CERTIFY` 和 behavior handoff 的设计消费合同；没有对任何真实数据、state artifact 或 M7 输入给出 PIT 正向认证。

## Findings

### [P1] State behavior handoff 没有冻结覆盖范围，单个无关或无 future-mutation 的 behavior receipt 可以为完整 candidate 放行

**位置：** change design v4 §3.2，第 93–121 行；architecture v7 §3.2。  
**场景：** `StateBehaviorEvidenceRef v1` 只要求一个 `pit_behavior_manifest_v1` 的 B001–B004 为 `PASS`，以及其中的 snapshots、code/query、输出和 protected-key digest 可重算。它没有要求 behavior 输出的受保护 key set 等于 `CandidateTrainingInputManifest` 中所有受 state 影响的 `(datetime, instrument, feature)` cells，也没有固定必须针对哪一个 state source、selection predicate 或未来路径执行何种 probe。根据 `pit_behavior_spec_v1`，`PREFIX_REPLAY` 是合法的单一 probe，且只要求相同 snapshot 的确定性重跑；即便使用 `FUTURE_POISON`，也可以只变更一个与 candidate state selection/aggregation 无关的 raw record。两者都可能 B001–B004 `PASS`，但不排除真正的 state builder/selection 对未来 revision、future universe 或未来值敏感。

**影响：** 固定 PIT `CERTIFY` 能证明所提交 candidate cells 的时点资格，不能替代派生代码的行为证明。当前 binding 可把一份范围过窄的 `NOVEL_CANDIDATE` behavior receipt 与完整 `FULL_TRAINING_INPUT` parent 拼接，随后 mint state descriptor；这违背 PIT skill 对“每个 derived feature 必须有 parent + behavior bundle、缺失即 `NEEDS_EVIDENCE`”的 handoff 边界，也会让 M7 fit 使用没有被实际 future-counterfactual 覆盖的 state 路径。

**证据：** v4 第 111–114 行未定义 `probe_type`、candidate-feature/key-set equality、state builder code digest equality 或 coverage set；v4 第 82–85 行定义了 candidate 的 exact joined/state digests，却没有把它们投影到 behavior outputs。PIT `behavior_spec.md` 明确每份 request 恰好一个 probe，并且该正向结果仅是 hash-bound pair 的窄结论；PIT `audit_spec.md` 也明确 fixed audit 与 behavior manifest 不能互相替代。

**方向：** 在 QRC 冻结时，额外冻结 closed `StateBehaviorCoveragePlan`（或等价并入 candidate manifest）：列出每个 state-derived feature/selection predicate 的 exact builder code/query digest、baseline/probe output key set、保护边界和 required probe 类型。生产 loader 只接受完整 coverage bundle：每个 required entry 的 behavior manifest 必须以同一 production fixed audit 为 parent、其 protected output keys/values 必须映射到 candidate state cells，且至少覆盖明确的 future-value、revision 和 universe/selection mutation 路径；若某项经语义分析确实不适用，必须由 frozen QRC 的 explicit rationale 决定，而不是 loader 默认跳过。M6.5 可只用 synthetic cases 验证遗漏、缩小 key set、错误 builder digest、`PREFIX_REPLAY` 代替必需 future probe 均 fail-closed。

### [P1] FitAdmission 的“至多一次调用”没有把模型输出的发布与 TERMINAL 状态原子绑定

**位置：** change design v4 §5，第 162–184 行；architecture v7 §5，第 122–148 行。  
**场景：** runner 已 durable `DISPATCHED`，`model.fit` 返回或在调用期间产出 checkpoint/predictions，但在写入 `TERMINAL` 前崩溃。设计要求恢复为 `ABANDONED_UNKNOWN` 并禁止再次调用，这是正确的预算语义；但 `FitAdmissionReceipt` 没有绑定每次 event 的 staging output root、预期 artifact inventory 或 final publication protocol，`ModelFitExecutionGuard` 也只被描述为“唯一 official writer”。因此该未知 event 可能留下一个路径上可读、格式正确的 checkpoint、prediction parquet 或 recorder output；之后的报告/selection 代码无法仅凭现有状态机判定它必须被隔离，contingency event 也可能与它共享逻辑 output path。

**影响：** 研究预算可保持一次计数，却出现“未 terminal 但可被消费”的模型结果。它既破坏结果审计，也可让未知执行影响后续 candidate selection；此处不能仅依赖“不把它称为 official”的约定，因为当前 `PeerLiteModel.save_checkpoint()` 会直接创建 checkpoint 目录，而当前预测产物本来就是独立 parquet 文件。

**证据：** v4 第 172–179 行仅规定 receipt/dispatch 的恢复，不规定训练输出在 `DISPATCHED`、`TERMINAL`、`ABANDONED_UNKNOWN` 间的所有权或清理；第 181–184 行要求 writer 在 guard 内，但没有 output transaction。v7 第 146–148 行同样只限定 writer 与 call-boundary count。当前 `src/qlib_peerlite/models/peerlite.py:502-524` 的 checkpoint 保存没有 admission/terminal guard，说明未来 wrapper 必须有明确、可验证的发布层，不能靠现有库行为推断。

**方向：** 将 admission 扩展为一个 output transaction：grant/plan 为每个 event 固定互不复用的 staging root 和 final immutable result root；guard 只准在 staging 写入，记录完整 artifact inventory/digests，并在 terminal result receipt fsync 后以同父原子 publish 使 final root 可发现。`ABANDONED_UNKNOWN` 必须保留 forensic staging receipt、将 staging quarantine，且所有 result discovery/model-selection/recorder 接口只接受 terminal receipt 绑定的 final root。把 output-root/inventory/terminal-result hash 纳入 admission/terminal receipt，禁止 contingency 与原 event 共享路径。必须测试“fit 前、fit 中、fit 返回后、terminal fsync/publish 前”每个 crash 点均不会产生可消费 official artifact。

### [P1] Replay 信任链没有把实际 launcher identity 绑定到 grant、activation 和 acceptance signature

**位置：** change design v4 §6.1–6.2，第 190–214 行；architecture v7 §6，第 161–179 行。  
**场景：** `M6ReplayLaunchGrant` 绑定 input binding、runtime、output、profile、trust-root key ID 与 source identities，却没有绑定 launcher bundle/path/hash；`ReplayActivationReceipt` 也未规定 launcher byte identity。设计随后要求“launcher”从 sealed FDs 启动 child，并让 acceptance service 根据 deployment、runtime、staged inputs、child receipt 和 outputs 签署结果。一个错误部署或替换后的 launcher 因此可以执行非预期 child，并产生一份字段自洽的 child receipt；acceptance service 的 re-open 只能证明现在看到的 verifier/archive/runtime/input bytes 与 output inventory 相符，不能从未绑定的 launcher identity 推出实际由经批准的 bootstrap code 启动。独立 signer 不应被降级为替 launcher 自述背书。

**影响：** v7 的“verifier、launcher、receipt 任一方不能单独证明自己”在 launcher 这一节点仍未闭合。即使 `m6_archive` 正确从 pinned trust root 验证 acceptance signature，签名的 payload 不含被授权 launcher 的 identity，无法区分“认可 launcher 启动的 replay”与“另一个 process 伪造 child receipt 后被验收服务签署”的情形。这正是此前 replay self-attestation 问题在 bootstrap 层的残留。

**证据：** v4 第 190–197 行列出的 trust objects 没有 `ReplayLauncherBundle` 或等价 hash；第 201–211 行要求验收签署 runtime/staged verifier/archive/tree/child/output/ledger identities，但未列 launcher digest、launch command/argv digest 或 bootstrap FD measurement。当前 archival verifier 自报 `Path(__file__)` 和 hash（`scripts/server/verify_m6_peerlite_archival_replay.py:354-357`），因此此次设计必须把外部 launcher 的授权身份也放在自报之外。

**方向：** 新增 immutable `ReplayLauncherBundle v1`（或把其 exact byte/tree digest、entrypoint/argv grammar、bootstrap runtime identity 并入 runtime bundle），并让 grant、activation receipt、deployment inventory、unsigned observation 和 final signed acceptance payload 全部 bind 同一 launcher digest。root-supervised launcher 必须从 activation-selected FD/immutable bundle执行；acceptance service 要以 deployment 的 sealed launcher measurement、child PID/exit/process receipt 和 fixed argv policy验证，而非接受 caller/launcher 任意 JSON。若现有 Unix 环境无法提供更强的 process attestation，应明确把该 approved root-owned launcher 作为信任根，而不能声称 acceptance signer 独立证明了未绑定的启动代码。加入 wrong-launcher、launcher-to-child argv swap、signed receipt with mismatched launcher digest、以及 launcher replaced after deployment 的拒绝 E2E。

## Verdict

`NEEDS_CHANGES`。未发现可确认的 P0：v4 已明确把 public `PeerLiteNetwork`/`PeerLiteModel` 的 raw Gate 参数和 exports 移出 M6 public surface，并把 future state 的正向序列写为 candidate → frozen QRC → production PIT `CERTIFY` → behavior/join → admission；plan 先于 QRC、registry/grant 后于 QRC 的方向也有效地避免了上一轮的 hash cycle。

但以上三个 P1 仍分别使派生 state 的实际行为覆盖、崩溃后的模型结果可见性、以及 replay launcher 的外部信任链不具备唯一、可测试的合同。它们都必须在实现前回到 `architecture` / change-design 修订；不能用测试默认值、Python 私有约定或“root supervised”字样补足。

## 应保留的设计方向

- M6 public API 固定为 no-gate，历史 replay 从独立 frozen source tree 运行；
- construction-only state 和真实生产 PIT `CERTIFY` 严格分层；
- `M7AuthorizationPlan` 先冻结、QRC 仅 bind plan/policy、activation 后生成 registry/grant 的单向链；
- `DISPATCHED` 先持久化，未知 fit 宁可消耗一个计划槽位也不可重试；
- acceptance key 从 pinned trust root 读取，不能从 receipt 或 verifier 自身获得。

## 审查范围与限制

- 已只读核对 v4/v7、v3 的独立设计审查、当前 `PeerLiteModel`/`PeerLiteNetwork`、market-state primitives、trial-ledger reconcile/locks、M6 archival verifier，以及 PIT `audit_spec.md` / `behavior_spec.md`。
- 未执行测试、server 命令、训练、真实 PIT 审计、replay 或最终 OOS。此报告是设计 gate 证据，不是实现、数据或 phase pass。
- 审查时质量 ledger revision 为 `32`；router 选择 `design-review`。主代理记录时应重新运行 `quality_ledger.py next`，并使用当时 revision/source digest。

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 32,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "read-only-independent-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "STATE_BEHAVIOR_COVERAGE_FIT_OUTPUT_TRANSACTION_AND_REPLAY_LAUNCHER_IDENTITY_INCOMPLETE",
  "summary": "v4 closes the prior public Gate, PIT parser, plan/QRC cycle and basic admission directions, but leaves behavior coverage scope, crash-safe result publication, and launcher identity outside the closed production contracts.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 3, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v4.md",
    "sha256": "16ac80ae172cbedf077d9c2f3c4b74a89c6298303f8d17f30fdc14f28e0ad810"
  },
  "architecture_evidence": [
    {
      "path": "evidence/m6_5_pre_m7/architecture_confirmation_v7.md",
      "sha256": "db91fab06cb271e9431de02491cae7c151e3d36c47edd7e3d093a0ad16ccb6b4"
    }
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v3.md",
    "src/qlib_peerlite/models/peerlite.py",
    "src/qlib_peerlite/data/market_state.py",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "scripts/server/verify_m6_peerlite_archival_replay.py",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/audit_spec.md",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/behavior_spec.md"
  ],
  "commands": [
    "read-only rg/nl/sed/sha256sum/git status",
    "quality_ledger.py next (route inspection only)"
  ],
  "independence": {
    "mode": "distinct_subagent_review",
    "reviewer_context_id": "/root/design_review_v4_lead",
    "author_context_id": "/root",
    "limitations": [
      "No product/test/contract/gate/ledger mutation except this independent review artifact.",
      "No M7 training, server replay, budget consumption, real PIT certification, or final-OOS access."
    ]
  },
  "blockers": [
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server v3 replay, and final OOS remain prohibited until a revised design passes independent review."
  ]
}
```
