# M6.5 R3 修复设计 v7 独立设计审查

审查结论：`NEEDS_CHANGES`

审查技能：`eng-review-design`  
审查性质：独立、只读、R3。本审查未修改产品代码、测试、冻结契约、M6 历史、gate 或质量账本；未运行训练、server replay、真实 M7 PIT `CERTIFY`、预算消费或最终 OOS。

PIT 导航模式：`VERIFY`。这里只核对 v7 对未来生产 PIT/行为 handoff 的合同保留情况；**不**产生 PIT `PASS`、`QUALIFIED`、数据认证、M7 放行或 Alpha 结论。

审查对象：

- `evidence/m6_5_pre_m7/m6_5_repair_change_design_v7.md`，SHA-256 `b2fcfad0f3e0a3fdf7a82680d5d60c38e08bb000a2f59e0e25f0093b7f55b2a4`；
- v7 明确纳入的 `evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md`，SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78`；
- `evidence/m6_5_pre_m7/architecture_confirmation_v9.md`，SHA-256 `e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598`；
- `evidence/m6_5_pre_m7/architecture_confirmation_v10.md`，SHA-256 `e47c62a359a81b1c9f12c4946c8b1b2a4ea223f7b04b2fb76a9cf6fd87c4db13`；
- `evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。

## Findings

### [P1] “staged bytes = 实际执行/import closure”仍只覆盖 `qlib_peerlite`，未闭合真实 runtime 与依赖导入图

**Section：** v7 §6 replacement，第 11–15 行；architecture v10 §2，第 11–13 行。  
**Scenario：** 这是冻结威胁模型内的普通部署/路径选择错误，不假设 hostile runner、host、control root、`LD_PRELOAD` 或任意 native code execution。supervisor 正确 stage 了 archive、verifier、`qlib_peerlite` source 和一个被称为 `runtime` 的 bundle；但该解释器的 prefix、stdlib、`lib-dynload`、site package、C extension 或其共享库仍解析到一个未绑定的正常安装版本。例如当前 archival verifier 在 module top level 已导入 `numpy`、`pandas`（`scripts/server/verify_m6_peerlite_archival_replay.py:21-22`），随后 frozen `PeerLiteModel` 还会导入 `torch`；这些都不是 `qlib_peerlite` origin check 能覆盖的对象。

`env -i` 消除环境变量，`python -I -S` 缩小 Python path，但两者均不把 `sys.executable`、`sys.prefix`/`base_prefix`、stdlib/`lib-dynload`、wheel/package tree、extension module 与其解析到的 shared-object map 内容寻址到 binding。v7 也没有规定 bootstrap 必须在导入 verifier 及其 top-level third-party imports **之前**执行全闭包检查。因此一个与 binding 中 launcher/verifier/`qlib_peerlite` 文件都一致、但实际使用错误 `numpy`/`pandas`/`torch`/`pyarrow` 或其 native dependency 的 replay 可以完成并生成字段自洽 receipt。

**Impact：** 这直接留下威胁模型要求防止的“绑错 runtime/environment 的只读 M6 replay”路径，也使 v7/v10 的“deployment rotation or module shadow cannot change actual replay after measurement”不能由合同推出。错误 replay 仍可能是 14 replay / 0 fit / OOS=false，却不是绑定的 M6 execution closure；不能作为官方 M6 archival replay 证据。

**Evidence：**

- v7 与 v10 只要求 bootstrap 验证每个 `qlib_peerlite` import origin 位于 staged tree，未定义或验证全部非标准库模块、解释器本体、native extension 及动态库的 closure；
- 当前 verifier 的顶层 `numpy`/`pandas` imports 发生在其业务 replay 函数和 frozen-source import 之前，证明完整 closure 不是仅检查 `qlib_peerlite` 即可推断；
- 项目依赖锁明确包含 `numpy`、`pandas`、`pyarrow`、`torch`、`lightgbm` 等运行时组件（`pyproject.toml`、`uv.lock`）；
- threat model 第 17–19、39 行把路径/环境误选和 runtime/environment 绑定明确置于 M6.5 必防范围，而第 21–29 行排除的 hostile host/runner 情形并非本 finding 的前提。

**Direction：** 在 architecture/change-design 中加入闭合的 `ReplayRuntimeClosure v1`（可作为 `M6ReplayInputBinding v3` 的 required sub-object），至少固定并验证：

1. staged interpreter、ABI/platform、`sys.prefix`/`sys.base_prefix`、stdlib 与 `lib-dynload` roots；
2. 所有非标准库 Python package/bytecode、所有 extension module、其解析 shared library identity，以及启动后允许的 import origin inventory；
3. bootstrap 的执行顺序：先验证 closure，再加载 verifier 或任何会触发 third-party import 的 module；
4. staged runtime 的实际 `sys.path`、`sys.meta_path`、已加载模块及 native-object map 必须完全落入 staged/runtime allowlist，任何外部、缺失、额外或替代 origin 都在比较/receipt 前 fail closed；
5. supervisor execution receipt 与 child receipt 都绑定并复核同一 observed-closure digest。

相应 synthetic red/E2E 必须覆盖：top-level `numpy`/`pandas` 在 closure gate 前解析、`pyvenv.cfg`/prefix 指向外部 package、staged third-party package 或 extension 在测量后被替换、以及外部 native library/extra import origin。上述测试不得运行真实 server replay。

## 已核对且应保留的部分

### 1. Canonical 继承与 M6 `6/44` genesis 没有被 v7 丢失

v7 第 7 行的被纳入 v6 SHA 与实际文件一致，且只替换 v6 §6。因此 v6 §3 的 `M6CloseArchiveProof v1 -> LedgerAuthorityGenesis v2 -> 新 authority namespace` 仍是完整合同。它继续要求 byte-exact close snapshot：51 行、14,328 bytes、SHA `31a90…`、6 candidate / 44 fit，并拒绝 server legacy `8d08…` / 4 candidate / 29 fit。该逻辑亦与 immutable M6 budget 和 M6 gate 的历史事实一致。没有发现 v7 将旧 server ledger 重新提升为 authority 的路径。

### 2. PIT、behavior、state、job 与 official-result 链没有被 §6 replacement 削弱

因为 v7 hash-bound 地保留 v6 §1–§5 与 §7，以下约束仍在：

- `StateBuildBinding v2` 是 construction-only / `BUILT_NOT_EMPIRICALLY_CERTIFIED`；synthetic root 和 `VERIFY` 不得成为模型输入；
- 真正生产 handoff 的顺序仍是 frozen QRC/authorization plan → PIT `CERTIFY`（`FULL_TRAINING_INPUT`、production adapter、17 checks）→ 完整 `StateBehaviorCoveragePlan` bundle → audit-only join；
- 四个 derived state sources、selection flag/outcome、population/aggregate 仍须有 `FUTURE_POISON`、`REVISION_REPLAY`、`UNIVERSE_CANARY` 覆盖，且 candidate projection 的 keys/values 是 equality 而非 overlap；这符合 PIT behavior proof 仅为补充而不替代 fixed audit 的边界；
- `FitAdmissionDescriptor`、immutable job snapshot、rechecked FDs、单次 dispatch、独立 `result-publisher`、`TERMINAL_PUBLISHED` 和 `OfficialResultResolver` 仍保留，故 staging/checkpoint/non-terminal output 不会成为 official result。

这些是文档合同核对，不是数据/PIT 认证或 M7 训练许可。

### 3. M6ReplayInputBinding v3 已补齐历史 product/run/checkpoint/prediction 输入枚举

v7 第 11 行和 architecture v10 第 7 行明确要求 closed inventory 覆盖：M3 product manifest 与每个 consumed partition、M6 run manifest/candidates、14 fold receipts、每个 checkpoint 的 metadata/state、每个 candidate prediction partition、K16 deterministic-refit receipt，及 historical verification、spec/gate/close proof、archive/internal manifest/tree、legacy read-only ledger、launcher/runtime 与输出策略。每项均需 relative path、SHA、bytes、schema、role；verifier 不再接收 caller-provided product/run/checkpoint/prediction/ledger/output paths。由此，前一轮“错但自洽的 product/run root”P1 已被 v7 正确修复。

## Verdict

`NEEDS_CHANGES`。没有 P0；M6 `6/44` genesis、PIT/behavior/state/job/result continuity 和 historical input inventory 均通过本次设计核对。唯一未关闭的 P1 是 runtime/import closure：现有文字只能把已 stage 的对象与 `qlib_peerlite` origins 连起来，不能证明实际 Python/native dependency closure 就是 binding 中的 bytes。

最早修复阶段：`architecture`（随后重做 canonical change-design 并独立 re-review）。在该 P1 被修复并通过新的独立设计审查前，test-design、implementation、M7 derived-contract freeze、真实 M7 fit、CCC/Gate、server replay 和最终 OOS 均不得推进。

## Scope、证据与限制

- 只读使用 `shasum`、`rg`、`sed`、`nl`、`jq` 和 quality router 的 route inspection；
- 已核对 M6 immutable budget / M6 gate 的 4/29 与 6/44 binding、当前 verifier 的 imports，以及 `pyproject.toml` / lock 中的 runtime dependencies；
- 未运行产品代码、测试、lint、typecheck、训练、server command、real PIT `CERTIFY`、replay 或 final OOS；
- 本 finding 严格以 `research_governance_threat_model_v1.md` 为界，不把 hostile native execution、恶意 runner、host/control-root/kernel/signing-key compromise 当作阻断理由。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 60,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "REPLAY_RUNTIME_IMPORT_CLOSURE_NOT_CONTENT_BOUND",
  "summary": "v7 correctly preserves the verified 6/44 genesis and the PIT/state/job/result chain, and closes the product/run/checkpoint/prediction inventory gap. It does not yet bind and verify the full interpreter/package/native import closure actually executed by replay; only qlib_peerlite origins are checked.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v7.md",
    "sha256": "sha256:b2fcfad0f3e0a3fdf7a82680d5d60c38e08bb000a2f59e0e25f0093b7f55b2a4",
    "incorporated_base": {
      "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
      "sha256": "sha256:2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78"
    }
  },
  "architecture_evidence": [
    {
      "path": "evidence/m6_5_pre_m7/architecture_confirmation_v9.md",
      "sha256": "sha256:e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598"
    },
    {
      "path": "evidence/m6_5_pre_m7/architecture_confirmation_v10.md",
      "sha256": "sha256:e47c62a359a81b1c9f12c4946c8b1b2a4ea223f7b04b2fb76a9cf6fd87c4db13"
    }
  ],
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "evidence_paths": [
    "contracts/immutable/m6_trial_budget_start.json",
    "evidence/gates/M6_peerlite_gate.json",
    "scripts/server/verify_m6_peerlite_archival_replay.py",
    "pyproject.toml",
    "uv.lock",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/SKILL.md",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/audit_spec.md",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/behavior_spec.md"
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
    "Add a closed, staged ReplayRuntimeClosure and re-review architecture/change design.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
