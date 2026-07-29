# M6.5 v7 / v6（含替换）与 v9/v10 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查技能：`eng-review-design`  
审查性质：独立、只读、R3、按冻结的 research-governance threat model 进行的反例审查。未修改产品代码、测试、契约、gate 或 ledger；未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。

## 审查对象与边界

- canonical change design：`m6_5_repair_change_design_v7.md`，SHA-256 `b2fcfad0f3e0a3fdf7a82680d5d60c38e08bb000a2f59e0e25f0093b7f55b2a4`；按其第 7 行规则，纳入 v6（SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78`）的 §1–§5 与 §7，并以 v7 §6 替代 v6 §6。
- architecture：`architecture_confirmation_v9.md`（SHA-256 `e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598`）及其 replay replacement `architecture_confirmation_v10.md`（SHA-256 `e47c62a359a81b1c9f12c4946c8b1b2a4ea223f7b04b2fb76a9cf6fd87c4db13`）。
- threat model：`research_governance_threat_model_v1.md`（SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`）。

本报告只列出在威胁模型已承诺处理的普通配置、并发、崩溃、路径或环境/导入错误下，仍可导致错误预算、重复 fit、错误 replay 或非终态结果被视为 official 的 P0/P1。没有把 runner 任意代码执行、control root/identity 被攻破、恶意 native extension 或 hostile-host 攻击作为 finding。

## Findings

### [P1] `O_EXCL` 只保证首个 claim 创建，不保证一次 retained event 至多跨越一次实际 `fit`

**Section：** v6 §5（canonical incorporation 后仍有效，第 25 行）；v9 §3（第 50–52 行）；threat model “正常并发启动、重启、崩溃”要求（第 17、36–37 行）。

**Scenario：** 一个受控但错误配置的 runner/supervisor 使用常见 pre-fork 或 `multiprocessing`/worker-pool 模式：父进程在事件的 `O_EXCL` claim 成功、`DISPATCHED` fsync 后 fork，子进程继承已验证的 admission、snapshot FD 和“我是 winner”的内存状态。因为 v6/v9 没有把 claim 绑定到 PID + process-start/boot identity，也没有规定 fork 后使 admission/FD 失效、child 必须重新打开并验证自己是唯一 winner，父子可都进入同一个冻结 runner 的 `model.fit` 调用。账本中仍只有一个 `START_RETAINED`/fit event，崩溃语义也无法区分两次真实执行。

这不是已取得 runner 任意代码执行权的恶意 raw-syscall 绕过；它是计划中的 Python 进程模型或运行配置错误。`O_EXCL` 只解决“两个进程各自创建同一文件”，不能撤销 fork 后对已创建 claim 和已打开 FD 的继承。

**Impact：** 同一冻结 event 可以发生两次真实 fit，却只消耗一次预算；随后任一子进程的 staging 还可能被错误地视为该单一 event 的输出。它直接违反 threat model 的“重复授权 fit”防线，破坏 M7 试验预算和结果可复现性。

**Evidence：** canonical v6 仅声明“stable lease + event-specific `O_EXCL` claim allows one planned worker”，没有定义 claim 内容、PID/start identity、fork policy、child invalidation、fresh reopen 或 failure transition；v9 采用同样的概述。此前非 canonical v5 曾明确列出这些必要字段与 `at_fork`/clean-spawn 约束，说明它们不是实现细节，但这些约束没有被 v6/v7 incorporation 保留。

**Direction：** 将 dispatch 设计成受 control root 管理的 durable, single-winner state machine：claim 必须绑定 admission digest、event、PID、process-start/boot identity、FD identities 和 generation；winner 在实际 `fit` 前从新打开的 claim 再验证。明确禁止 admission 后 fork，或要求 clean `spawn` 在 admission 前完成；子进程必须关闭/使 admission、lease、state、ledger FD 失效。任何 stale/pre-existing/mismatched claim 或 crash after claim 都进入不可重试的 terminal abandonment；retry 只可消耗预先计划的 contingency event。

**Required negative evidence：** parent/child fork-after-claim、pre-fork pool、fork-before/after `DISPATCHED`、inherited-FD reopen、two-process restart race 和 crash-at-each-boundary 都必须观察到同一 event 的 `fit` call count 不超过一，且无第二个 official output。

### [P1] `RunAuthority` 仍缺少从冻结 QRC/plan 到唯一 activation 的可执行外部锚；错误但内部自洽的预算/事件计划可成为权威

**Section：** v6 §3（第 15 行）与 §5（第 25 行）；v9 §3（第 46–48 行）。

**Scenario：** 服务器有两个内容正确但用途不同的 future plan/authority object（例如一个是筛选预算、另一个是确认预算，或旧 revision）。操作员将 runner/supervisor 配置到错误的 `RunAuthority`/registry root。v6 要求该对象内部冻结 genesis、ledger/head、budget/spec、journal/output 和 event plan；v9 只说 QRC “binds plan/candidate/coverage/policy”，随后 governance materializes “registry/grant/authority and one activation receipt”。两份文档均未定义：

- QRC/plan/registry/grant/authority/activation 的 closed schema、hash binding 和无循环安装顺序；
- runner 从预先固定的 control profile 如何定位唯一 activation，而非从配置或 authority ID/path 选择；
- activation 与当前 authority ledger 的 exact initial/previous head、immutable budget artifact、allowed event-plan digest、namespace/journal/output roots 的交叉校验；
- root containment、old-valid snapshot rollback、跨对象混配与 activation 后替换的 fail-closed 规则。

因此错误对象图可在内部自洽：它仍从正确 6/44 genesis 开始，却带着错误的 cap、event slot 或 output namespace，且没有一个 canonical external authorization anchor 能将其拒绝。

**Impact：** 本轮正确关闭了 legacy 4/29 作为起点的显式路径，但没有关闭“正确 6/44、错误 future budget/plan”成为官方授权的普通配置路径。真实 fit 会在错误预算基准或错误事件计划下被保留/发布，破坏试验预算和预注册约束。

**Evidence：** v6 自称“完整实施合同”，但只定义了 `Synthetic RunAuthority`；v9 的 registry/grant/activation 是架构名词，没有 resolver、schema 或 supervisor-only handoff。canonical incorporation 明确保留 v6 §3/§5，且没有把此前更精确的“plan 无 QRC reference → frozen QRC binds plan → control policy → deterministic activation receipt → supervisor passes sealed bytes, no mutable selector”合同纳入当前唯一实现依据。

**Direction：** 在 implementation-ready design 中冻结一个单向 authority chain：`M7AuthorizationPlan` 不引用 QRC；冻结 QRC 引用 plan/candidate/coverage/control-policy hashes；post-freeze installer 由受控 root 在唯一 deterministic location 创建 immutable registry/grant/authority 和 `AuthorityActivationReceipt`。该 receipt 必须从 pinned control policy（不是 caller path/ID）解析，绑定 QRC/plan/policy、genesis/close proof、authority-ledger device/inode + exact head、immutable budget/spec/event-plan digests、run namespace/journal/output roots 和 nonce。runner 只从 supervisor 传入的 validated FDs/canonical bytes读取；所有 alternate snapshot、old-but-valid activation、mixed authority/grant、budget/plan substitution 和 path traversal 必须拒绝。

**Required negative evidence：** forged-but-self-consistent authority、alternate registry snapshot、stale valid activation、QRC/plan cycle、wrong budget base、event-plan/count swap、authority/root path substitution、activation-before/after-replace 都必须在任何 journal/fit/output 前 fail。

### [P1] `result-publisher` 的 terminal 事务未定义从 admission/dispatch 到受控 index 的唯一来源；普通 job/path 误选仍可把未终态或错误 job 输出 official

**Section：** v6 §5（第 25–27 行）；v9 §3（第 54–57 行）；threat model 第 17、19、38 行。

**Scenario：** 一个独立 `result-publisher` 服务仍是受信 identity，但启动参数/队列消息错误地指向另一 event 的 staging root、一个 crash 后保留的 final root，或同一 event 的旧 terminal-job receipt。当前 contract 只要求 publisher “re-hashes staging regular files and matching terminal job receipt”，然后写 `TERMINAL_PUBLISHED`；它没有定义 terminal-job receipt 的 issuer/closed schema，也没有规定 publisher 必须从 activation-selected, supervisor-owned admission/dispatch index 取得唯一 expected staging/final roots，并验证 terminal receipt 是否绑定同一个 activation nonce、claim, `DISPATCHED` record、exact state snapshot/descriptor、event 和 expected inventory。

“matching”因而可被实现为同目录或自述 hash 相同，而非一个不可混配的事务。即使 runner 没有 final/index 写权限，错误配置的 publisher 仍能从合法但错误的 staging/receipt 对构造一条自洽 `TERMINAL_PUBLISHED` 记录。之后 resolver 仅检查该记录、root 与 inventory hash，就会把本应 quarantine 的输出视为 official。

**Impact：** 崩溃残留、staging 或另一 job 的错误 state/fit 输出可越过 terminal-only discovery，成为研究选择、Recorder readback 或报告看到的 official result。这正是 threat model 要阻止的“半成品 official result”与“任意研究脚本直接把 staging/checkpoint/未终态预测当作 official result”的普通运维版本。

**Evidence：** canonical v6/v9 均没有 `PreparedResultReceipt`、terminal issuer、publisher input resolver、expected-root derivation、publish-index durability/ownership、post-publish revalidation 或 crash state transition 的 schema。它们把 `FitAdmissionDescriptor` 的 unique roots 与 publisher 的 terminal receipt 并列描述，但没有让 publisher 重建/验证两者的同一 authoritative identity。此前 v5 的更精确 output transaction（descriptor/claim/inventory-bound prepared receipt、atomic rename、stable index、crash quarantine）未被 v6/v7 纳入。

**Direction：** 定义 result-publisher 只能根据 activation/event 的 control-root index（not caller supplied roots）读取 sealed `FitAdmissionDescriptor`、durable dispatch claim 和 runner-prepared receipt；每个对象都应 binding-identical。Prepared/terminal receipt 必须覆盖 admission/activation/event/claim/state snapshot digests、unique roots、complete inventory and content hashes。publisher 用 `openat`/FD/type/owner/mode/nlink checks 重哈希 staging，原子转移或封存 final root 后才 fsync append one signed/ACL-controlled index record；resolver 必须从该 index 以 event identity 反查，不接受 path discovery。所有 crash before-index outputs remain terminal failure/quarantine and are never promoted/reused.

**Required negative evidence：** wrong-but-valid staging root、stale receipt、valid admission + another event output、prepared receipt substitution、final-root reuse、crash after fit/before prepared/rename/index、final file swap after index 和 direct resolver path must all fail to yield an official result.

### [P1] v7/v10 只闭合 `qlib_peerlite` 的 import origin，未闭合实际 replay runtime/import closure；正确 staged verifier 仍可在错误兼容 runtime 中产生官方错误 replay

**Section：** v7 §6 replacement（第 11–15 行）；v10 §2–3（第 11–17 行）；threat model 第 18、39 行。

**Scenario：** supervisor 正确 FD-hash/copy 了 binding 中的 verifier/source/runtime marker，并在 `env -i`, fixed cwd, `python -I -S` 下启动。但是 bootstrap 只检查每个 `qlib_peerlite` import 来自 staged tree。实际 verifier 还依赖 Python interpreter/stdlib、`numpy`、`pandas`、`torch`、`qlib` 及可能的 native extensions。当前 design 没有定义 `ReplayRuntimeBundle` 的 closed inventory（interpreter executable、stdlib/site-package wheels、native dependency map or immutable image digest），也没有要求 bootstrap/launcher 对这些实际 imports 的 origin/bytes 作 allowlisted closure verification。

一个正常的 interpreter/venv/image selection error，或“staged runtime”路径上另一个兼容 Qlib/Torch/Pandas installation，即可让同样的 staged `qlib_peerlite` source 使用错误库或数值/runtime 行为。receipt 仍能记录正确的 staged verifier tree、argv、env digest、14 checkpoints/predictions identities；现有 `qlib_peerlite`-only origin test 也会通过。这个场景不要求 `LD_PRELOAD`、恶意 native injection、control-root compromise 或任意 runner code execution。

**Impact：** 14/0/OOS=false 的 M6 replay 可被错误 runtime 完成并被 `m6_archive` 接受为 official historical replay，恰好落在 threat model 的“绑错 archive/verifier/launcher/runtime/environment”禁止项内。

**Evidence：** v7/v10 将 “approved/verified staged runtime”列为 inventory role，但只给 `qlib_peerlite` import-origin checker 一个实际执行约束；`python -I -S` 清理 Python path/site 自动加载，并不把 interpreter、stdlib、third-party wheel/native closure 与 measured bytes 原子绑定。v10 的 test list 将 generic “runtime change/import origin outside staging”列为案例，却没有规定需检测的完整 import set、runtime tree/image digest 或自启动到 child 的 same-object linkage。

**Direction：** Freeze a `ReplayRuntimeBundle v1` with either (a) interpreter + stdlib + every allowlisted Python/native dependency tree/inventory and exact invocation FD, or (b) a pinned immutable OCI/runtime image digest plus measured execution identity. Stage and launch only that closure; bootstrap must enforce a closed allowlist for *all* imports used by launcher/verifier, record their origin/digest (and permitted native module identities), and bind the resulting closure digest to the supervisor receipt. The runtime binary/entrypoint must be opened/verified as the executed object, not merely rechecked by mutable pathname. This remains a normal deployment/configuration control, not a claim to solve hostile native code.

**Required negative evidence：** wrong interpreter, wrong stdlib/site-package, wrong `qlib`/`torch`/`numpy`/`pandas`, dependency tree swap after measurement, non-staged import shadow, image/runtime-digest mismatch and verifier-child closure mismatch must all reject before an accepted replay receipt.

## 未发现的 P0 与应保留方向

未发现一个在冻结 threat model 内、无需上述普通错误路径即可立即把未来标签/执行信息带入 M7 的新 P0。当前 canonical design 的以下方向应保留：

- M6 6/44 byte-exact genesis 与 legacy 4/29 显式拒绝；
- construction-only state、future `CERTIFY`、behavior coverage、join evidence 和 synthetic root denial 的分层；
- M6 replay 的 full product/run/checkpoint/prediction inventory、sealed staging、fresh output 和 no-ledger-write 要求；
- final OOS、真实 M7 fit、CCC/Gate、server replay 继续封印。

但这四个 P1 均是当前 canonical implementation contract 缺失的跨进程/跨对象边界。它们不能由后续单元测试“猜测”出来，也不应在 M7 freeze、test-design 或实现后再补。

## Verdict

`NEEDS_CHANGES`：**0 个 P0，4 个 P1**。最早修复阶段是 `architecture`，随后必须重新产出一个把 authority activation、fork-safe dispatch、publisher transaction 与 complete replay runtime closure 明确写入的 canonical change design，并接受新的独立设计审查。此前不得进入 test design、实现、server replay、M7 derived-contract freeze、真实 M7 fit 或最终 OOS。

## 审查限制

- 仅读取设计、架构、冻结 threat model、当前 status/ledger 路由和相关现有 source 作为 repository evidence；未把尚未实现的设计当作已验证行为。
- 当前质量 ledger 读取时为 revision `59`；本审查不修改 `.engineering-quality/**`。主流程记录结果前必须重新运行 router 的 `next` 并使用当时 revision/source digest。
- PIT 讨论没有执行 `CERTIFY`，不产生任何 PIT `PASS`、data certification、M7 入场许可或 Alpha 结论。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 59,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "CANONICAL_DESIGN_LEAVES_NORMAL_OPERATION_AUTHORITY_DISPATCH_PUBLICATION_AND_RUNTIME_CLOSURE_GAPS",
  "summary": "v7 closes replay input inventory/staging but the canonical v6-with-v7 design still lacks a fork-safe one-use dispatch, externally anchored authority activation, descriptor-bound terminal publication transaction, and full runtime/import closure. Normal configuration or process-model mistakes can therefore undercount fits, use the wrong budget, publish non-terminal output, or accept a wrong M6 replay.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 4, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v7.md",
    "sha256": "sha256:b2fcfad0f3e0a3fdf7a82680d5d60c38e08bb000a2f59e0e25f0093b7f55b2a4",
    "canonical_incorporates": {
      "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
      "sha256": "sha256:2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78",
      "replacement": "v6 section 6 is replaced by v7 section 6"
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
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status"
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
    "Revise architecture and canonical design; pass a fresh independent design review before test-design.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
