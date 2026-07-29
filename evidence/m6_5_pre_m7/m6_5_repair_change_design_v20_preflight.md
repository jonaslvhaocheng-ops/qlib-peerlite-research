# M6.5 v20 变更设计预检 — 退回架构修复

状态：`NEEDS_ARCHITECTURE_REPAIR`。当前路由允许开始 change-design，但对
`architecture_confirmation_v23.md` 做 Linux/Python 3.11 实现可行性核查后，发现三个会改变
公开边界和 threat model 的问题。它们不能留给实现者临时决定，因此本文件不产出 v20
implementation-ready design，也不进入 test design、tests 或 code。

## Findings

### [P1] socketpair 的 `SO_PEERCRED` 不能证明 fork/exec 后 child verifier 的实际身份

v23 规定 `CleanWorkerSession` 通过预创建的 Unix socket 接收 worker descriptors，supervisor
以 `SO_PEERCRED` 检查 child PID/uid/gid。对 Linux `socketpair` 而言，peer credentials 可在
pair 创建时绑定到父进程，不能单独证明后续 fork/exec sender。实现若照字面使用，会把父
credential 误当成 child attestation author，破坏 `ChildReceiptEnvelopeV2` 的 author/publisher
边界。

**Required architecture correction:** 固定唯一机制为 receiver `SO_PASSCRED` + one-shot
`SCM_CREDENTIALS` message（或明确 child-after-exec connect listener 的替代方案，二选一），
并定义 nonce、expected PID、`/proc` start ticks、uid/gid、`MSG_CTRUNC`/extra-FD rejection 和
message-count rules。`SO_PEERCRED` 不得作为 socketpair child-authentication oracle。

### [P1] 官方 slot publication 与 Linux identity primitives 需要独立的 fail-closed boundary

现有 `governance/artifacts.py::atomic_write_json` 是 Path + parent mkdir + `os.replace` 的一般
工具；它不满足 root-relative no-follow chain、immutable no-replace leaf 或 parent fsync。
`trial_ledger.py` 的 `flock` 也不是 OFD identity lock。v23 尚未把 Linux `renameat2`
`RENAME_NOREPLACE`、`F_OFD_SETLK` ABI、`statx/name_to_handle_at`、no-follow open 和 macOS
synthetic-only mode 固定到一个最小模块边界，实施时会被迫做未审查的系统调用/portable fallback
选择。

**Required architecture correction:** 增加 `m6_replay_fs.py`，以 Linux/Python 3.11 production
provider 独占 no-follow FD chain、identity observation、OFD lease 和 same-parent durable
no-replace publication；任何 missing kernel/filesystem primitive 返回 stable fail-closed error。
现有通用 artifact writer、raw worker 和 trial ledger 均不得复用。非 Linux 仅允许 fake
provider/unit tests，不得被视作 production validation。

### [P2] worker job 的 OS identity / ACL 前提需要明确为 release gate，而不是隐含假设

若 replay supervisor 与 child verifier 使用同一 Unix identity，child 对 private staging 的
read-only / scratch-only ACL 分界无法成为实际 isolation。v23 已要求 job parent `0700` 和 FD
handoff，但没有要求 distinct worker identity、deployment verification或缺失时的拒绝行为。

**Required architecture correction:** 封装/dispatch 前验证 child verifier 为 policy-fixed
distinct OS identity，job parent remains supervisor-only，stage read-only，scratch only child-writable；
身份/ACL/`PDEATHSIG`/parent-PID predicate 无法满足时不得启动 official worker session。合成
test double 可模拟这一边界，但不能声称真实 Linux deployment 已通过。

## Consequence

这些是 `architecture` issues，不是 test-code 或 implementation issues。v23 的其他原则仍保留：
Pin/PolicyV2、observed quality evidence、E/C/P-to-Q recovery、child attestation vs durable envelope、
raw worker staging 和 post-S5 deterministic continuation。下一步必须先发布 v24 architecture，
再重写完整 v20 change design，之后重新独立 R3 design review。

本预检只进行了 read-only source/platform inspection；没有改 product/test/contract/gate/ledger/
historical evidence，没有执行项目代码、训练、archival replay、预算消费、PIT 或 final OOS。
