# M6.5 v4 / v7 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查方式：独立、只读、对抗式设计审查；未修改产品代码、测试、契约、gate 或 ledger，未运行训练、server replay 或访问最终 OOS。  
审查对象：

- `evidence/m6_5_pre_m7/m6_5_repair_change_design_v4.md`，SHA-256 `16ac80ae172cbedf077d9c2f3c4b74a89c6298303f8d17f30fdc14f28e0ad810`
- `evidence/m6_5_pre_m7/architecture_confirmation_v7.md`，SHA-256 `db91fab06cb271e9431de02491cae7c151e3d36c47edd7e3d093a0ad16ccb6b4`

对手模型遵循 v7 §1：不假设 governance control-plane root、独立 signer 或内核被攻破；攻击者可以作普通
Python/CLI 调用、触发/利用 `fork` 或崩溃恢复、传递已取得的 descriptor/FD，并尝试路径与运行时替换。
本报告只列出证据充分的 P0/P1。

## Findings

### [P1] `FitAdmission` 没有把已认证 state 的精确消费对象固定到一次 dispatch，valid admission 可与错误 state descriptor 配对

**Section:** v4 §3.2、§5；v7 §3、§5。  
**Scenario:** 一个 event 已取得合法 `FitAdmission`。v4 只说 production loader 会“only for a current
FitAdmission”创建 sealed descriptor（第 119–122 行），但没有定义 `FitAdmission` 或其 durable
`DISPATCHED` record 必须包含 `StateArtifactBinding`、candidate manifest、三个 evidence、state bytes/row-cell
digest、fold/segment/date coverage 或 state FD 的精确 identity。相反，v4 对 admission 的明示字段只有
activation nonce、event/payload、worker nonce、journal inode/digest 与 ledger heads（第 172–179 行）；
`ModelFitExecutionGuard` 又只被要求接受一个“undispatched matching receipt”（第 175–184 行）。

因此，一个拥有合法 admission 的 runner/worker 可以把另一折的已验证 state、另一 candidate 的 descriptor，
或绕过 loader 构造的 raw state object 传给私有 executor。v7 第 55–57 行“sealed state descriptor inside one
FitAdmission”表达了正确意图，但没有成为 v4 可实现的 closed schema、FD contract 或 call-boundary assertion。
现有的“private/test-only”约定也不能替代 guard 对输入身份的核验：official artifact writer 正是唯一必须
强制该关系的位置。

**Impact:** 一个账本正确计数、签名有效的 official model-result receipt 可能不对应 frozen QRC 所认证的 exact
candidate training input。最坏情况下，construction-only 或 future-conditioned state 可在真正的 `model.fit`
边界重新进入，而不是被 `StateArtifactBinding` 的 parser 拒绝；较轻的 cross-fold swap 也足以破坏复现与
PIT evidence 的 input-to-output 链路。

**Evidence:**

- v4 第 103–122 行严格解析 state evidence，但只定义 loader 何时创建 descriptor，未定义 descriptor 到
  admission/dispatch/result 的不可替换绑定；
- v4 第 170–184 行列出的 RunLease、FitAdmissionReceipt 与 ModelFitExecutionGuard 绑定项中没有 state 或
  candidate/input identity；
- v7 第 135–148 行同样只绑定 event-plan、worker、journal、ledger head，并把 state 放在独立的流程图语句中；
- 旧 M7 design 已要求 checkpoint 记录 state product hash、schema/order 和 training-date digest
  （`m7_change_design_v2.md:79-85`），证明这些不是可省略的实现细节。

**Direction:** 在实现前将 state-to-fit 关系写成一个不可伪造、一次性的 `FitAdmission v1` contract：

1. admission 和 durable `DISPATCHED` record 必须固定 QRC/plan/event identity、`StateArtifactBinding` content
   hash、fixed/behavior/join evidence hashes、candidate manifest hash、exact state artifact/cell or row digest、
   fold/segment/date coverage、schema/order，以及由 supervisor 打开的 read-only state/input FDs 的 inode/content
   identity；
2. `ModelFitExecutionGuard` 只能从该 sealed FD/bytes 重建输入，在实际 `model.fit` 前重新核验这些 identities；
   它不得接收 caller DataFrame、tensor 或独立 descriptor。official checkpoint/prediction/result receipt 必须回写
   同一 identity set；
3. direct private import、raw tensor、synthetic descriptor、valid admission + wrong valid state、valid admission +
   wrong fold/date、post-admission descriptor/FD swap 均应在 fit call 前失败，并证明没有 official output 或额外
   ledger mutation。

### [P1] “persistent run-state lock” 没有定义 fork/继承 FD 下的唯一 dispatch claim，可能产生一次账本、两次 `model.fit`

**Section:** v4 §5；v7 §5。  
**Scenario:** runner 在取得 `RunLease`/`FitAdmission` 后、写 `DISPATCHED` 前发生普通 `fork`（例如 Python
multiprocessing、框架 worker 或错误恢复分支）。设计只要求在 persistent run-state lock 下 fsync
`DISPATCHED`，没有定义 lock primitive 的 fork semantics、admission/lock FD 在 child 中的处置、非可继承 worker
identity，或独立于锁的 atomic one-winner dispatch claim。

现有项目的 lock 基础实现使用 `fcntl.flock`（`trial_ledger.py:447-469`）。在 Unix 上，`flock` 绑定 open
file description；fork 后 parent/child 共享该 description，child 不会像一个独立竞争者那样被自己的 inherited
lock 阻塞。若新 runner 沿用该自然实现，两边均可持有同一 valid receipt、观察 `ADMISSION_ISSUED`，并在没有
compare-and-swap/O_EXCL claim 的合同下各自写出 `DISPATCHED` 后进入 `model.fit`。账本只保留一条
`START_RETAINED`，因此预算与真实调用数分离。

**Impact:** 这直接违反 v7 第 12、135–148 行“任何可能已进入 `model.fit` 的事件不可重复”与“一 event 至多
一次 observed call”的核心承诺。它不需要修改 control root、签名或 ledger；只需要在合法 runner 内继承一个
已经授予的 admission/lock FD。

**Evidence:**

- v4 第 162–184 行仅规定固定 lock filename、fsync 顺序和 crash 后 abandon；没有 fork 禁令、at-fork close、
  unique dispatch marker 或 compare-and-swap protocol；
- v7 第 135–144 行称“only the holder”可跨 call boundary，但 fork 会复制同一个 holder 的 descriptor/FD，且
  文档未定义其不可委派性；
- 当前唯一可核对的 lock implementation 正是 `flock`（`src/qlib_peerlite/governance/trial_ledger.py:447-469`），
  所以不能把独立进程的 multiprocess test 当成已覆盖 fork-after-lock 情形。

**Direction:** 将 dispatch 定义为锁之外也安全的、不可委派的一次性原子领取：

1. supervisor/runner 在 admission 后禁止 fork，或在 `os.register_at_fork` child handler 中立即关闭 admission、
   state、ledger 与 lock FDs；worker 必须在 admission 前以 clean `spawn` 创建；
2. 在 durable state root 用 `O_CREAT|O_EXCL`、`link`/`rename` CAS 或等价 single-winner primitive 创建
   event-specific dispatch claim。guard 必须从新打开的 durable state 复核 claim，不能只相信 inherited lock or
   in-memory receipt；只有 claim winner 可以跨 `model.fit`；
3. 把 worker process identity（至少 pid + boot/start identity）和 claim generation 写入 receipt；任何 child、
   lease handoff、retry 或 stale descriptor 均 fail-closed/`ABANDONED_UNKNOWN`；
4. 增加 exact `fork`-after-admission、fork-before/after-state-read、parent/child concurrent dispatch、crash
   during claim publish、inherited FD reopen 与 executor restart tests，并以 call-boundary spy 证明每个 event
   永远不超过一次 `model.fit`。

## 未发现的攻击路径与应保留方向

在既定“control root、issuer/acceptance signer 与内核未被攻破”的范围内，v4/v7 对 legacy raw Gate 的移除、
QRC→plan→signed activation 的单向授权，以及 replay 的 runtime bundle、same-FD staging、独立 acceptance
signature 已关闭上一轮可明确说明的 verifier self-attestation、path swap、unsigned copied receipt 路径。本次没有
发现足以另列 P0/P1 的普通调用方式来伪造一个会被 pinned trust root 接受的 replay receipt。

这不是对尚未实现代码的通过声明：上述两项修复前，不应进入 test design、实现、server replay、真实 M7
contract/fitting 或最终 OOS。

## Verdict

`NEEDS_CHANGES`。最早修复阶段为 `architecture`，因为两个缺口都决定 authority/state 的跨进程信任边界与
at-most-once 的实现模型，不能由后续测试临时选择。修订后需重新进行独立 design review。

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 33,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "STATE_TO_FIT_BINDING_AND_FORK_SAFE_SINGLE_DISPATCH_UNSPECIFIED",
  "summary": "v4/v7 closes the prior public Gate, QRC-registry and replay self-attestation defects, but does not yet make the certified state identity inseparable from a one-use fit admission, nor define an atomic fork-safe dispatch claim.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v4.md",
    "sha256": "16ac80ae172cbedf077d9c2f3c4b74a89c6298303f8d17f30fdc14f28e0ad810"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v7.md",
    "sha256": "db91fab06cb271e9431de02491cae7c151e3d36c47edd7e3d093a0ad16ccb6b4"
  },
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m7_change_design_v2.md",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "docs/STATUS.md"
  ],
  "commands": [
    "read-only rg/nl/sed/shasum/jq",
    "quality_ledger.py next"
  ],
  "independence": {
    "mode": "distinct_subagent_review",
    "reviewer_context_id": "/root/design_review_v4_adversary",
    "author_context_id": "/root",
    "limitations": [
      "No product/test/contract/gate/ledger mutation except this independent review artifact.",
      "No M7 training, server replay, budget consumption, or final-OOS access."
    ]
  },
  "blockers": [
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ]
}
```
