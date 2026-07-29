# M6.5 R3 修复设计独立审查 v1

状态：`NEEDS_CHANGES`  
审查技能：`eng-review-design`  
审查者上下文：独立子任务 `/root/m6_5_design_review_v3`  
设计作者上下文：`/root`  
审查性质：只读设计审查。未修改产品、测试、契约或质量账本；未启动训练、未访问最终 OOS、未消耗试验预算。  
审查对象：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v1.md`，SHA256
`27a88f08714c91d5097ef876b1200c3391503b595d119bf87730f53177f6bd53`。

## Findings

### [P0] 没有把 M6 的正确关闭账本迁移为新服务器权威账本的 genesis

**Section:** 修复设计 §3.2（尤其第 116–164 行）和 §3.4（第 187–190 行）；架构确认 v3 的
“Run authority / Ledger mutation”边界。  
**Scenario:** 新 M7 run 在当前服务器 `contracts/trial_ledger.jsonl` 上注册 authority。该文件仍处于
M6 启动前的 `8d08…` head；registration 的 exact-head 检查会在错误但字节精确的 `4 candidate / 29 fit`
状态成功。  
**Impact:** M6 已实际消耗的 `2 candidate / 15 fit` 不会进入 M7 的权威预算基数。后续 global limit、
run authority 和 receipt 即使实现正确，也会从少计的余额开始，违反 M6 冻结预算并允许超出应有的试验
额度。这是预算治理和可审计顺序的直接失效。  
**Evidence:**

- `contracts/immutable/m6_trial_budget_start.json:7-25` 将 `8d08…` 定义为 M6 前的 `4/29`，并明确
  M6 成功后应为 `6/44`。
- `evidence/gates/M6_peerlite_gate.json:90-105` 将本地 close-time ledger
  `31a90d…` 和累计 `6/44` 作为 M6 PASS 的证据。
- 当前本地 `contracts/trial_ledger.jsonl` 为 51 行、`6/44`、SHA256 `31a90d…`；而
  `evidence/m6_5_pre_m7/m6_archival_replay_server_receipt_v2.json:160-164` 证明服务器 replay
  实际读取的 ledger 仍为 `8d08…`。
- 修复设计只说新记录会出现于 “closed prefix” 后（§3.4），但没有指定该 prefix 如何成为服务器
  唯一 authority 的初始字节状态，也没有拒绝 legacy `8d08…` 服务器文件。

**Direction:** 在任何 M7 authority registration 前，设计一个单次、可验证、不可覆盖的
`LedgerAuthorityGenesis` / migration artifact。它必须：

1. 绑定 M6 archive verifier 已验证的 close-time ledger SHA、字节数和 `6/44` 计数；
2. 在服务器建立一个新的 authority ledger（或将一个已验证的 close snapshot 原子安装为新的
   authority path），而不是改写 M6 历史证据；
3. 产出 migration receipt，记录源/目标 hash、字节数、计数、M6 gate/archive-proof binding 和
   server path policy；
4. 让 `register_run_authority` 只接受该 genesis 后的 exact head，并对 legacy `8d08…` fail-closed；
5. 覆盖首次迁移、重复迁移、错误 close snapshot、旧服务器 ledger、并发迁移和 crash/retry。

### [P0] market-state 来源链既没有 PIT VERIFY 所需的可审计输入，也没有由未来派生契约锚定的 consumer binding

**Section:** 修复设计 §3.1（第 69–112、98–108 行）和 §6；架构确认 v3 第 40–42、52–55 行。  
**Scenario:** `build_t_known_state_input()` 在某日对 `special_status_unknown`、membership、
`feature_eligible` 或可得时间做了未来条件化的实现错误。它仍能输出自洽的 selected
`population.parquet`（仅四个 state-source 列）和 daily digest；随后任意 self-consistent manifest
被 `load_verified_market_state_artifact(path)` 接受。此时无法从 artifact 判断哪些候选证券被何个 flag
排除，也没有受 M7 derived contract 约束的 expected artifact/snapshot/audit digest。

**Impact:** 设计要求真实 build 前执行 `point-in-time-data-audit` VERIFY，却没有定义该 VERIFY
可以消费的 state-input/eligibility/availability evidence。仅保留被选中的四列和自报 code/predicate
hash，无法对真实 `U_state(T)` 的被排除行、每个资格 flag 及其 T 时可得性做逐项复核。与此同时，
“loader 只收 artifact”不是信任根：若没有外部 expected binding，错误或错误路径上的自洽 artifact
仍可被消费。这样没有真正关闭独立审查报告指出的 future-conditioned population 漏洞。

**Evidence:**

- 修复设计第 72–82 行要求内部计算 7 个 eligibility flags，但第 89–108 行定义的对外 artifact
  只保留 selected population 的四列与 daily product；没有 pre-selection audit view、flag 值、
  availability/source-partition lineage 或 selection-reason inventory。
- `evidence/m6_5_pre_m7/m7_change_design_v2.md:65-70` 已要求 state 的 fixed audit 覆盖 source
  fields、availability clocks、population predicates、key/count/state digest；新设计没有给出这些
  输入的版本化载体和 audit interface。
- 架构确认 v3 要求 artifact verifier 验证 provenance，但只写成 `load_verified…(path)`，并未要求
  将 snapshot、audit package、builder/predicate 和 artifact manifest 的预期 hash 从未来 immutable
  contract 传入。
- 当前 `src/qlib_peerlite/data/market_state.py:75-85,144-168` 的列名检查正是此前 P0 的根因；
  设计虽转向 builder，却尚未为 builder 的真实输入/选择过程给出可独立审计的证据面。

**Direction:** 将 state 产物拆成被明确绑定的两层，并在实现前固定接口：

1. `state_input_audit`：对每个 raw 候选 `(datetime, instrument)` 保留 7 个资格 flag、四个 source
   值、确定性的 selection outcome/reason、输入 source partition/field/availability lineage、日期范围
   和哈希；它必须是 PIT VERIFY 的直接输入，不是仅供日志的摘要。
2. `market_state_population`：只能由已哈希的 audit input 推导；manifest 绑定 audit-input digest、
   selected keyset、population/daily digest、builder/feature/predicate digest 和源 snapshot binding。
3. `StateArtifactBinding`：未来 M7 derived contract 冻结并传给 loader，至少固定 snapshot bundle 与
   source-manifest hashes、PIT audit package/manifest hash、state-input hash、artifact manifest hash、
   schema、代码/谓词 hash 和 OOS date bound。loader 不得只按任意 `path` 的自报 manifest 放行。
4. `BUILT_NOT_PIT_QUALIFIED` 的 artifact 不得进入任何 real M7 Dataset；只有该 binding 和新的 PIT
   VERIFY 同时 PASS 后才可被 adapter 消费。

### [P1] RunIntent 只冻结 source-event ID 集合，未冻结实际试验计划，也未要求 initial head 与 registration precondition 相等

**Section:** 修复设计 §3.2，第 118–164 行。  
**Scenario:** 一个 intent 预留了 `run_id:000001…N`。调用者用与
`RunIntent.initial_ledger_head` 不同的 `expected_head` 注册，或在同一允许 ID 下把 model、fold、seed、
purpose、event kind 或 fit/evaluation semantic ID 换成未预注册的内容。全局数量仍可在 limits 内，因而
账本把未登记实验记录为合法 started event。

**Impact:** “exact head”与“不可挪用预算”只约束计数，不能约束本次 run 实际执行的候选、fold、seed
和模型。它保留了以已授权 ID 进行未授权模型变体或交换 candidate/fit 预算槽位的路径，也使 receipt
不能证明 authority 的 `initial_ledger_head` 就是实际注册前提。

**Evidence:**

- 设计中的 `RunIntent` 仅含 `allowed_source_event_ids`，没有每个 event 的 type、evaluation/fit ID、
  model、fold、seed、purpose 或预留计数语义；`register_run_authority(..., expected_head)` 也没有
  明文要求 `expected_head == run_intent.initial_ledger_head`。
- 现有 `src/qlib_peerlite/governance/trial_ledger.py:106-133` 的 intent 还更窄；
  `:302-366` 对 journal event 只校验 run/spec/hash 和非空 model/seed/ID，不把语义字段与一张
  frozen plan 对齐。这是独立代码审查原 P1 的相邻逃逸面。

**Direction:** 用 canonical `RunAuthority` 取代仅 ID list 的许可：

- registration 前必须验证 intent 内 `initial_ledger_head` 与传入 registration head 四元组
  （SHA、bytes、candidate、fit）完全一致；
- intent 绑定逐项 `EventPlanEntry`：seq/source ID、事件类型、强制 count flags、evaluation/fit ID、
  model ID、fold、seed、purpose，以及预声明的 candidate/fit totals 与不可挪用预算分配；
- 每个 journal event 必须与唯一 entry byte-for-byte（除已明确允许的运行时间字段）相符；
- authority record、journal event 和 receipt 都包含 authority/plan hash；并测试 head mismatch、
  allowed-ID-but-wrong-payload、candidate/fit swap、重复/替换 journal 和 crash 后 identical retry。

### [P1] archive-only 重放仍缺少外部冻结的 replay-input/verifier trust root

**Section:** 修复设计 §3.3，第 168–183 行。  
**Scenario:** 服务器以被修改的 archive 和被修改的 verifier 运行，同时在 CLI 中给出该 archive 的
新 SHA。archive-only extraction、internal manifest/tree check 和 receipt 的 self-hash 都可能彼此
自洽；若 gate 只绑定该 receipt，就无法证明实际运行的是审查过的 verifier 或原定的 M6 frozen
archive。

**Impact:** “14/14 exact replay”会重新变成自报结果，而不是对既有 M6 历史代码的独立重放证据。
这不改变 M6 历史 gate，但不能作为 M6.5 放行条件。

**Evidence:**

- 设计要求 receipt 写入 archive/manifest/tree/verifier digest，却没有定义这些**预期** digest 由哪个
  immutable artifact 提供，或让 CLI 只接受该 artifact；§3.3 的“验证 archive SHA”在 expected SHA
  可由同一调用者提供时是自洽检查而不是 anchor。
- 当前 server receipt v2 虽自报 archive 与 verifier SHA
  （`m6_archival_replay_server_receipt_v2.json:147-154,181-184`），schema 仍为 replay v1
  （第 178 行）；它不能替代该外部 binding。
- 现有 transfer manifest 使用 `qlib_peerlite_m6_frozen_source_transfer_v1`，而设计要求 archive 内部
  `qlib_peerlite_frozen_source_v1`。独立代码审查已记录此 schema/invocation 不一致，设计还未规定
  archive 生成、转换或验收的唯一格式。

**Direction:** 在 server replay 前冻结一个 `M6ReplayInputBinding v1`，并由 M6.5 gate 和
`m6_archive` receipt validator 共同验证。它应固定 archive SHA/bytes、internal manifest SHA/schema、
tree inventory digest、M6 revision/spec/gate/historical-verification hashes、预期 verifier source SHA
及允许的运行 profile。CLI 应只收 `--replay-input-binding`（而非散落的 expected hash flags）；receipt
必须回写 binding hash，并证明运行脚本与 archive 均匹配。archive producer/manifest schema 的迁移也
必须在该 binding 中唯一化并纳入 fake-archive mutation tests。

### [P2] state builder 的 I/O 允许面、资格谓词和原子发布语义仍留给实现阶段决定

**Section:** 修复设计 §3.1，第 62–104 行；§3.4，第 185–194 行。  
**Scenario:** 两个实现者对“有当日合格原始行情即为 active”作出不同解释，或 builder 从
`snapshot_dir` 的符号链接/未列入 manifest 的文件读取；另一进程在 output directory 发布中断时读取
半成品 artifact。

**Impact:** 虽然没有直接的 label leak，`U_state(T)` 仍可能不一致、来源允许面不可审计，或把不完整
产物误当成可验证 artifact。当前 `build_pit_data_product.py` 中尚没有 `is_active` 的既有定义，且
price-domain 逻辑在 label-stage 之后才出现（`:558-565`），所以不能把这些细节留作无文档实现选择。

**Direction:** 在设计中冻结 `(is_active, price_domain_valid, finite state sources)` 的逐字段布尔公式、
每个允许 source 的固定 filename/schema/columns 和 read policy；所有 reads 经 manifest allowlist
resolver（regular file、realpath containment、hash match）完成。输出使用 new-only temp directory、file
fsync、directory fsync、atomic rename，并明确拒绝 symlink/hard link/已有非空 output。将这些规则、
I/O access inventory 和 fault cases加入测试设计。

### [P2] lease 只是未来 runner 的约定，尚不是不可绕过的 pre-fit public boundary

**Section:** 修复设计 §3.2，第 156–164、196–212 行。  
**Scenario:** 后续 M7 runner 或 CLI 直接调用 reconcile/preflight helper，而不是在整个 journal →
reconcile → fit 生命周期内持有 `run_authority_lease()`；账本仍能记录 start，却不能证明该 fit 是在
独占 authority 下被允许的。

**Impact:** 设计不能把“library reconciliation 已测试”表述为“真实 fit 已被防绕过地治理”。独立测试
审计同样指出，若 M7 runner 尚未实施，这条只能标记 `NOT_IMPLEMENTED`，不能由 library unit test
替代。

**Direction:** 本变更可以继续不实现 M7 runner，但必须在设计和 M6.5 gate 中把证明范围限为
`authority library / synthetic preflight`。同时规定 M7 runner 的唯一 public path：lease context 产生
不可伪造的 capability/token，只有携带该 capability 的 preflight 才能进入 `model.fit`；M7 实现阶段
再以 multiprocess/interrupt E2E 证明该边界。否则将完整 runner 提前纳入本修复范围。

### [P3] 100% coverage 要求应保留，但需把 receipt 的测量对象固定到本次代码快照

设计 §4 已正确禁止以 exclude 或降低阈值取得通过；这点必须保留。非阻断建议是在下一 test-design
阶段固定 `coverage.py --branch` 的逐文件 include、source digest、原始 JSON report 和可重跑命令，
避免把后续未审查文件或 pytest-cov/NumPy 装载问题混入度量。现有独立测试审计已提供可复用的最小
测量矩阵；这不是降低 100% 要求的理由。

## Verdict

`NEEDS_CHANGES`。存在 **2 个 P0、2 个 P1、2 个 P2、1 个 P3**。P0/P1 直接影响 PIT 来源证明、
M6 历史预算基线和 archival replay 的可信度；在修复设计被更新并重新独立审查前，不能进入 test-design、
实施、真实 M7 fit、派生契约冻结或最终 OOS。

最早需要返回的阶段是 `change-design`：先补齐 server ledger genesis、state audit/consumer binding、
run-authority event plan 和 replay input binding；不要用更多单元测试掩盖未定义的信任边界。

## 应保留的设计优点

- 正确拒绝以列名检查或 provenance dataclass 代替 raw-source 边界。
- 将 M6 historical `LedgerPrefixBinding` 与新 run 的 exact head 语义分开，方向正确。
- 选择 archive-only temporary extraction，避免自由 `--frozen-source-root`，方向正确。
- 明确不运行 M7 fit、CCC/Gate、组合或最终 OOS，并坚持新增核心模块 100% line + branch coverage。

## 审查范围与限制

- 阅读并交叉核对了修复设计、architecture confirmation v3、两份独立审计、现有 state/ledger/archive
  实现、M6 immutable budget/gate 和新 server replay receipt。
- 没有运行训练、服务器命令或测试；本结果是设计审查，不把静态检查或既有 green tests 表述为新行为
  的通过证据。
- M6 历史 `PASS` 不被本审查撤销；本报告只决定 M6.5 是否可授权 M7，答案是否定的。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 3,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "LEDGER_GENESIS_PIT_PROVENANCE_AND_REPLAY_TRUST_ROOT_UNSPECIFIED",
  "summary": "The repair direction is sound, but it lacks a server authority genesis for the verified M6 6/44 close state, an auditable and contract-anchored state provenance chain, a semantic event plan, and an immutable replay-input/verifier trust root.",
  "issue_type": "architecture",
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v1.md",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v1.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/architecture_confirmation_v3.md",
    "evidence/m6_5_pre_m7/m6_5_remediation_independent_code_review.md",
    "evidence/m6_5_pre_m7/m6_5_independent_test_coverage_audit.md",
    "contracts/immutable/m6_trial_budget_start.json",
    "evidence/gates/M6_peerlite_gate.json",
    "contracts/trial_ledger.jsonl",
    "evidence/m6_5_pre_m7/m6_archival_replay_server_receipt_v2.json",
    "src/qlib_peerlite/data/market_state.py",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "scripts/server/verify_m6_peerlite_archival_replay.py"
  ],
  "commands": [],
  "subject_digest": "sha256:27a88f08714c91d5097ef876b1200c3391503b595d119bf87730f53177f6bd53",
  "independence": {
    "mode": "independent-agent",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/m6_5_design_review_v3",
    "limitations": [
      "Read-only design review; no production, test, contract, ledger, server, training, or final-OOS mutation."
    ]
  },
  "blockers": []
}
```
