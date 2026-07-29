# M6.5 R3 修复设计独立审查 v5

状态：`NEEDS_CHANGES`  
审查技能：`eng-review-design`  
PIT 导航模式：`VERIFY`（仅审查未来 `CERTIFY` / behavior handoff 的设计合同；不产生 PIT 认证或 M7 放行）。  
审查性质：独立、只读的 R3 设计审查。未修改产品代码、测试、契约、gate 或质量账本；未运行训练、server replay、真实 PIT 认证或最终 OOS 访问。

审查对象：

- `evidence/m6_5_pre_m7/m6_5_repair_change_design_v5.md`，SHA-256 `6936ab070bdb5bc2045d1fac479300a7b1ba0964c49c5e16abd7d5824ac6275b`；
- `evidence/m6_5_pre_m7/architecture_confirmation_v8.md`，SHA-256 `ff63cb6791743ec57207b19fd27fd33891e772c95c3991215d78272dc6bc2b5e`。

v5 正确闭合了上一轮的若干**方向**：冻结的完整 state behavior coverage、QRC 后才允许
`CERTIFY`、candidate/fold identity 进入 admission、`O_CREAT|O_EXCL` 单赢家 claim、terminal-only
resolver，以及 launcher bundle identity 的全链字段。可是它在将 v4 声明为“唯一实现依据”时，丢失了
早期拒绝意见中若干不可省略的信任根。以下问题使它仍不能进入 test-design 或实现。

## Findings

### [P0] 唯一实现依据丢失 M6 `6/44` authority genesis，旧服务器 `4/29` ledger 可以重新成为 M7 预算起点

**Section:** v5 §3–§4（尤其 `M7AuthorizationPlan`、activation、ledger heads）及 architecture v8；v5
第 6 行明确它取代 v4 作为唯一实现依据。  
**Scenario:** governance 为一个 M7 run 安装自洽的 plan / registry / grant / authority / activation。由于 v5
没有要求 `LedgerAuthorityGenesis`、close-proof、new authority namespace 或 first-head predicate，安装器可以把
现有服务器 `contracts/trial_ledger.jsonl` 当作 authoritative ledger。该服务器文件仍是 M6 前的
`8d08…` / `4 candidate, 29 fit` prefix；其后的 activation、claim 与 terminal receipts 仍可彼此完全一致。
**Impact:** M6 已消耗的 2 个 candidate 和 15 个 fit 不进入 M7 的不可挪用预算基数。任何后续“预算内”
run 都会从错误余额起算，直接破坏已冻结的试验预算和 M7 结果的审计有效性。这是此前 P0 的实质回归，而
不是文档措辞缺失。  
**Evidence:**

- `contracts/immutable/m6_trial_budget_start.json:7-25` 固定 M6 前 `8d08…`、`4/29`，并固定 M6 成功后
  应为 `6/44`；
- `evidence/gates/M6_peerlite_gate.json:90-105` 固定 close ledger
  `31a90d1f…1992de93` 和累计 `6/44`；
- `evidence/m6_5_pre_m7/m6_archival_replay_server_receipt_v2.json:160-164` 证明服务器仍读取
  `8d08…` legacy 文件；
- v5 §3 仅列计划、budget/spec、namespace/journal/output 与“ledger heads”，v5 §4 仅规定 dispatch
  claim；v8 也没有 genesis、close snapshot、legacy path deny 或 authority-ledger installer。全文检索
  `genesis`、`6/44`、`M6ReplayInputBinding` 均无命中。相反，已被 v5 取代的 v3
  `§5.1–§5.2` 明确规定了 `M6CloseArchiveProof`、`LedgerAuthorityGenesis`、new authority ledger 和
  legacy reject。

**Direction:** 恢复并使 v5 明确继承一个闭合的 `M6CloseArchiveProof -> LedgerAuthorityGenesis -> new
authority ledger` 合同：

1. genesis 必须绑定 M6 gate、独立 close proof、byte-exact close snapshot 的 SHA/bytes、`6/44` counts 和
   `31a90…` close head；
2. 唯一 installer 仅从治理 control root 创建一个新的 authority namespace，原子写入 close bytes + genesis
   record；它必须拒绝历史 `contracts/trial_ledger.jsonl`、`8d08…`、unknown tail、错误 target 与覆盖写；
3. plan / registry / grant / authority / activation 均绑定 genesis ID、authority-ledger identity 和首次 exact
   head；runner 不得从 caller 或 legacy path 推导它；
4. synthetic tests 必须覆盖正确 `6/44` install、`8d08` reject、错误 close proof、并发/崩溃/重试与 source
   ID 预算不可挪用。

### [P1] 重放链不再有外部冻结的 M6 replay-input binding，获批 launcher 仍可诚实地重放错误 archive/verifier/input tree

**Section:** v5 §6，architecture v8 §5。  
**Scenario:** 一个正确测量的 `ReplayLauncherBundle` 和 runtime 启动了一个与它的 source inventory 自洽、但不属于
M6 freeze 的 archive / verifier / input tree。acceptance service 可以重新检查**当前部署**中的
verifier/archive/tree 并为其签名；因为 grant、activation、acceptance 和 `m6_archive` 没有被要求引用同一个
独立 `M6ReplayInputBinding`，它们无从把实际对象与原定 M6 revision、archive、internal manifest、tree 和历史
gate 进行比较。
**Impact:** “14/14 exact replay”可再次只证明某个被测量 launcher 执行了一组自洽输入，而非证明它执行了
已审查的 M6 frozen inputs。它重新打开了 v1/v3 的 archive/verifier self-consistency 路径。  
**Evidence:** v5 §6 只冻结 launcher bundle、runtime 与 argv policy，并说 acceptance 检查 staged
verifier/archive/tree；没有定义或要求 `M6ReplayInputBinding` 的 archive SHA/bytes、transfer/internal manifest
schema/hash、canonical tree digest、M6 gate/spec/historical-verification/revision/verifier identity 和 immutable
output profile。已取代的 v3 `§6:173-189` 明确要求这些内容，并要求 grant、deployment、launcher 和
`m6_archive` 都验证该 binding。当前 archival verifier 仍接受 caller-provided archive/hash/path
(`scripts/server/verify_m6_peerlite_archival_replay.py:195-230`)，因此不能把它的自报 receipt 当作该缺失
binding 的替代。

**Direction:** 恢复 closed `M6ReplayInputBinding v2`（或同等的、外部冻结对象），并使 launch grant、activation,
deployment inventory、runtime launcher、acceptance payload 和 `m6_archive` 都 rehash/parse 同一 binding。它应
锁定 archive/transfer/internal-manifest/tree、M6 execution spec/gate/historical verification、frozen revision、
approved verifier、profile（14 replay / 0 fit / no final OOS / legacy ledger readonly）和唯一 new output root；
任何未在 binding 内的 input 或替代 schema 均在 child 启动前 fail-closed。

### [P1] “read-only sealed FDs”没有定义不可变封存语义，state-to-fit 仍存在 rehash 后的内容 TOCTOU

**Section:** v5 §1、§3，architecture v8 §3。  
**Scenario:** supervisor 用 `O_RDONLY` 打开一个已认证 state/candidate regular file 并计算 descriptor 的
device/inode/SHA。另一同机进程（或仍拥有该文件写权限的 worker/thread）在 guard 的 rehash 之后、解析或
`model.fit` 之前/期间修改相同 inode 的字节。FD 自身是 read-only，device/inode 也没有变化；guard 可能把
受攻击的数据重建成输入，却仍发出绑定旧 digest 的 official receipt。
**Impact:** v5 所承诺的“post-admission state mutation、FD swap、wrong valid state/fold 在 model call 前失败”
不是由所述机制保证的。此处会使 exact certified state/candidate 到一次 fit 的不可替换关系退化为一次
可竞争的 pathname/inode 检查。  
**Evidence:** v5 第 11–14 行的 `openat/O_NOFOLLOW/fstat/owner/mode/nlink` 是读取时的路径完整性检查；第
92、96–101 行仅要求 read-only FD、fstat、rehash 和自行重建。它没有规定 inputs 对 runner 不可写、没有
kernel seal / immutable-copy primitive、没有明确 supervisor/runner UID 权限关系，也没有规定 hash 的同一
byte snapshot 就是 parser/model 消费的唯一 byte source。architecture v8 第 55–60 行的“sealed read-only
FDs (or content-addressed copied bytes)”仍把真正安全的 copy 方案列为可选而非 mandatory。

**Direction:** 将 `sealed` 变成 closed operational contract，而非描述词：例如 supervisor 在验证后把一次读取的
bytes 放入 private immutable buffer 或 Linux `memfd` 并施加 write/grow/shrink seals，或以不同 Unix identity
提供不可写的 immutable content-addressed object；descriptor 必须记录 `seal_kind`、sealed-byte SHA、FD
identity、creator/consumer identity 和 close-on-exec/inheritance policy。`ModelFitExecutionGuard` 只能从该
sealed byte snapshot 解析，受支持平台无法提供等价保护时拒绝 dispatch。测试必须在 rehash 后、parse 中及
fit 前尝试同 inode mutation，而不是只测试 admission 前的 pathname replacement。

### [P1] launcher identity 被写入 payload，但没有独立的历史 exec-to-child attestation 来证明获批 bytes 实际启动了 child

**Section:** v5 §6，architecture v8 §5。  
**Scenario:** 受控路径上的 launcher 被错误替换，或非批准 launcher 伪造包含正确 bundle digest 的 unsigned
observation / child record。acceptance service 在 child 结束后重新读取当前 deployment，可以证明现在的
launcher bytes、argv policy、archive 和输出相符，却不能仅从 launcher 自报或当前 pathname 证明当时发生的
`exec` 使用了 activation-selected sealed bundle FD。被签名 payload 中出现 launcher digest 只证明该 digest
被声明，不能证明执行来源。
**Impact:** v5 未完成它自己声称的“measured launcher process identity/exit/argv”边界；独立 acceptance signer
可能无意中为 launcher 的自述背书。即使修复上一个 input-binding 问题，这条缺口仍允许“正确静态 digest +
错误实际 bootstrap”产生看似可信的 server replay receipt。  
**Evidence:** v5 第 139–142 行要求 launcher *unsigned observation*，第 146–148 行说 acceptance service
检查“measured launcher process identity/exit/argv”，但未定义 measurement 的 trusted producer、签名/credential、
PID start/boot identity、FD-to-exec linkage 或 child linkage schema。architecture v8 第 93–101 行同样只列
`launcher observation` 与 child record。先前 v4 的 `fexecve`/same-FD staging 是正确方向，但 v5 没有给
acceptance service 一个不可由 launcher 自制的实际执行回执。

**Direction:** 在 grant/input binding 之外新增 `ReplayLaunchExecutionReceipt v1`（或由 acceptance service
在运行期直接产生等价记录）。它必须由受信 supervisor 的独立 Unix identity/密钥在 launch 时产生，并绑定
grant/activation nonce、sealed launcher FD/bundle digest/entrypoint、runtime FD、canonical argv、PID + boot/start
identity、child PID/start/exit、staged verifier/archive/tree digests 和 output/ledger identity。acceptance service
只有在重新验证该 receipt 与活跃/已结束 child 的不可伪造 linkage 后才可签名；无此 receipt、launcher replacement、
argv swap 或 digest-only copied JSON 都必须拒绝。

## 已确认应保留的部分

- `StateBehaviorCoveragePlan v1` 明确覆盖 derived sources、predicate、aggregate 与完整 candidate projection，且
  要求 `FUTURE_POISON`、`REVISION_REPLAY`、`UNIVERSE_CANARY`，比此前单一或无关 behavior receipt 明显更严谨；
- 固定 PIT `CERTIFY`、完整 `FULL_TRAINING_INPUT`、production adapter、17 checks 和 `NOVEL_CANDIDATE`
  behavior boundary 的区分符合 PIT skill；
- `FitAdmissionDescriptor` 对 state/candidate/fold/schema/output roots 的内容绑定、O_EXCL winner claim，以及
  terminal index 后才允许发现结果，是正确的 fail-closed 方向；
- 继续把真实 M7 QRC/fit、CCC/Gate、server replay 与最终 OOS 排除在本轮之外，符合 M6.5 gate 的范围。

## P2/P3

本次没有新增、独立于以上阻断问题的 P2 或 P3。以上 P0/P1 修复后仍需重新进行独立设计审查；本报告不把
设计文字、旧 green tests 或 synthetic fixtures 表述为实现、数据或 M6.5 gate 的通过证据。

## Verdict

`NEEDS_CHANGES`。存在 **1 个 P0、3 个 P1、0 个 P2、0 个 P3**。最早应回到 `architecture`：这些问题决定
authority ledger、replay input/exec trust roots 和 sealed-input 的跨进程边界，不能由 test design 或实现阶段
临时选择。M7 derived-contract freeze、真实 M7 fit、CCC/Gate 实验、server v3 replay 和最终 OOS 继续禁止。

## 审查范围与限制

- 已只读核对 v5/v8、v1–v4 独立审查及其被 v5 取代前的 genesis/replay contracts、现有
  `trial_ledger.py`/`market_state.py`/archival verifier、M6 frozen budget/gate/server replay receipt，以及 PIT
  `audit_spec.md` 与 `behavior_spec.md`；
- 未执行测试、server 命令、训练、真实 PIT 认证、replay 或最终 OOS 访问；
- 审查时质量 ledger revision 为 `43`，router 选择 `design-review`。主代理记录本结果前必须再次运行
  `quality_ledger.py next`，并使用当时的 revision/source digest。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 43,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "LEDGER_GENESIS_REPLAY_INPUT_EXEC_ATTESTATION_AND_SEALED_INPUT_INCOMPLETE",
  "summary": "v5 improves behavior coverage, admission, dispatch and terminal-only publication, but its stated sole implementation basis drops the verified M6 6/44 ledger genesis and frozen replay-input contract, and does not close input-byte sealing or historical launcher-exec attestation.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 1, "P1": 3, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v5.md",
    "sha256": "sha256:6936ab070bdb5bc2045d1fac479300a7b1ba0964c49c5e16abd7d5824ac6275b"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v8.md",
    "sha256": "sha256:ff63cb6791743ec57207b19fd27fd33891e772c95c3991215d78272dc6bc2b5e"
  },
  "evidence_paths": [
    "contracts/immutable/m6_trial_budget_start.json",
    "evidence/gates/M6_peerlite_gate.json",
    "evidence/m6_5_pre_m7/m6_archival_replay_server_receipt_v2.json",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v3.md",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "scripts/server/verify_m6_peerlite_archival_replay.py",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/audit_spec.md",
    "/Users/jonas/.codex/skills/point-in-time-data-audit/references/behavior_spec.md"
  ],
  "commands": [
    "read-only rg/nl/sed/shasum/git status",
    "quality_ledger.py next (route inspection only)"
  ],
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v5_lead",
    "limitations": [
      "Read-only review artifact only; no product/test/contract/gate/ledger mutation.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access."
    ]
  },
  "blockers": [
    "Return to architecture/change-design before test design or implementation.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server v3 replay, and final OOS remain prohibited."
  ]
}
```
