# M6.5 v22 / v19 独立 R3 设计审查

## Findings

### [P1] pre-Bootstrap 的 quality release policy 没有闭合其自身 quality 槽的物理身份，因此 observed-byte 链仍从一个只按路径命名的 parent 开始

**Section：** `architecture_confirmation_v22.md` §1（17–62 行）、§3（98–139 行）；
`m6_5_repair_change_design_v19.md` §3.3（116–151 行）。

**Scenario：** v22 正确要求 `VerifiedQualityInputs` 从 sealed anchor FD 观察 Bootstrap 和
PASS 的实际 bytes，而不是信任 caller ref。但作为 Bootstrap 之前唯一 trust root 的
`M6QualityGateReleasePolicy v1` 所列 closed payload 只有
`sealed_control_anchor_contract`、`["m6-replay-control"]` 和两个相对 slot 名；没有定义
control-root / `quality/` parent 的 `DirectoryIdentity v2` chains 或一个内容确定的
`QualitySlotTopology`。v22 49 行仍要求“从 policy 比较 full D v2 chains”，但前文没有给出
policy 中这些 chains 的字段或 `sealed_control_anchor_contract` 的 closed schema/equality
equation。Bootstrap 之后的 `ReplayControlRootBinding v2` 无法回头认证 Bootstrap 自己的
parent。

**Impact：** 正常 deployment/recovery 中同 ACL、同名 `quality/` child 的替换或 anchor
resolver 接到 sibling tree 时，quality issuer/reader 能在路径上读写一组自洽的
Bootstrap/PASS，并在之后产生带有该组 bytes 的 Context；现有定义没有一个 pre-E physical
identity oracle 拒绝它。这正是冻结威胁模型内的 path/configuration/half-write failure，
而不是 hostile control-root compromise，因此为 P1。

**Evidence：** v22 18–27 行以穷举形式定义 policy，45–55 行要求其创建的 capability
比较 full chains；v22 110–139 行的 exhaustive parent-chain guarantee 依赖随后才存在的
`ReplayControlRootBinding v2`。v19 123–149 行声称 `ObservedArtifact` 带 verified parent
chain，却没有让 release policy 的 public schema 提供预期 chain 或固定 QualitySlotSpec。

**Direction：** 将 pre-E policy 扩展为 closed `QualityReleaseTopology v1`：包含 sealed
anchor typed ref/identity、control-root component identity chain、以及 `QUALITY_BOOTSTRAP`
和 `QUALITY_PASS` 各自 root-relative parent components、full D v2 parent chain、fixed leaf、
schema、writer/ACL 和 publication mode。明确 `sealed_control_anchor_contract` 的 canonical
schema、ref/bytes equality，或不要以它作为未定义的代理。Quality publisher/reader 必须仅从
该 topology obtain slot FD，并在 Bootstrap/PASS 之前/之后重开比较；用 same-ACL quality
parent replacement 和 wrong-anchor fixtures 验证在任何 Bootstrap write 或 observed input
capability 创建前 fail closed。

### [P1] `F_OFD_SETLK + CLOEXEC` 不能使持锁 capability 自动“不跨 fork”，child writer exclusion 和单一状态机锁仍缺实际生命周期协议

**Section：** `architecture_confirmation_v22.md` §4（143–176 行）、§5（194–213 行）；
`m6_5_repair_change_design_v19.md` §3.1（68–83 行）、§4.1（171–187 行）、§5.1（232–237 行）。

**Scenario：** v22 声称 `LockedVerifiedControlTopology` 不能跨 fork/exec，并以
`F_OFD_SETLK` 和 `CLOEXEC` 支撑这一点。实际 OFD lock 绑定的是 open file description；
fork 复制的 descriptor 仍引用同一 open file description/同一 lock，而 `FD_CLOEXEC` 只在
exec/posix_spawn 后关闭 FD，并不在 fork 时撤销它。v19 没有声明 owner PID/process
generation check、`pthread_atfork`/`os.register_at_fork` child poison-and-close、或 launcher
必须以 `close_fds`/explicit-FD allow-list 启动的协议；`open_regular_file_from_root()` 也未
声明为 exclusive OFD lock 使用的 writable descriptor mode。

**Impact：** replay supervisor 在持锁状态启动 worker 或普通 helper 时，child 在 exec 前会
继承 lock FD 和内存中的 opaque capability；它能意外保留/释放父锁，或在实现没有明确
PID guard 时调用 lifecycle mutation。即使没有恶意 native code，这会导致普通 launch/
crash/recovery 中死锁、错误 lock-loss 判断或违反“child 没有 control-root writer
capability”和 R→V/terminal 单决策保证，因此为 P1。

**Evidence：** v22 149–158 行同时要求 OFD+CLOEXEC 与 no-cross-fork；v22 198–199、
v19 232–235 行只抽象地说 child receives sealed FDs。v19 182–187 行只说 fork/exec
failure discards capability，未规定检测/撤销机制。Linux `fcntl(2)` 对 OFD locks 的语义是
fork/dup descriptors 引用同一 open file description；close-on-exec 不处理 pre-exec fork
inheritance。

**Direction：** 把 capability 的 process lifetime 写成可实现 contract：记录 creator PID
与 generation，在每个 method entry 验证；注册 child-at-fork handler 立即 close lock/slot
FD 并 poison capability；任何 PID/generation mismatch 不写入且不解锁 parent-owned state。
`AuthorizedArchivalReplayLauncher` 必须使用 close-all/explicit-pass-FD spawning（或等价
无 fork inheritance protocol），并声明 lock FD 以 no-follow `O_RDWR|O_CLOEXEC` 打开、在
acquire/after-lock revalidation 中比较同一 `FileIdentity v1`。测试需要真实 fork fixture
证明 child 无法使用/释放 capability，且 parent 仍能安全完成或重新获取锁。

### [P2] `C → {P,F} → A → B → Q` 的 supervisor materialization 和 E/C 半写恢复没有稳定 API，仍把关键无环/恢复决定留给实现阶段

**Section：** `architecture_confirmation_v22.md` §2（88–94 行）、§6（229–244 行）；
`m6_5_repair_change_design_v19.md` §4.1（189–207 行）、§8（288–301 行）。

**Scenario：** v22 保留了 C 的 PTemplate、P/F 独立 materialization、随后 A/B/Q 的关键
dependency direction。v19 仅定义 archive acceptor 的 `issue_authority_and_control()`（E/C）
和 `ReplayReservationRegistry` 的 `build_precommit_before_claim`、`claim_and_bind`、
`recover_pre_s0`。文字称 registry “starts at P/F/A/B/Q”，但没有定义谁/how publish P/F/A/B、
如何 field-by-field validate C template、如何在 P-only/F-only/A-missing/B-missing crash residue
中重新打开同一 immutable chain，或 E 已发布而 C publication 失败时的 deterministic
recovery. `SlotResolver` 又禁止 generic open/write，故不能把这些留给 caller。

**Impact：** 最保守实现会把 pipeline 永久卡在 E/C 或 P/F/A/B partial state；较宽松实现则
必须在代码阶段自创 materializer、ordering 和 repair policy，可能把 P/F 独立性或 A 的
后置绑定重新变成未审查的选择。它不会立即允许错误 official result（可 fail closed），
但不满足 R3 implementation-ready 的无隐含 material decision 标准，因此为 P2。

**Evidence：** v22 88–94、229–236 行定义 E→C→{P,F}→A→B→Q；v19 189–194 行只处理 E/C
write，196–207 行的唯一 registry APIs 由 Q 开始，288–296 行 implementation slices 没有
materialization/recovery sub-step。

**Direction：** 在 control module 增加受 `LockedVerifiedControlTopology` 和 replay-supervisor
capability 约束的明确 API（可为一个 closed `materialize_control_chain`）：先验证 C 的
PTemplate，再独立 O_EXCL 生成/validate P 和 F，随后从二者生成 A、从 A/P 生成 B，最后
生成 Q；为 E-only/C-missing、P-only、F-only、A/B/Q 缺失定义逐项 re-open/byte-equality
recovery table，禁止生成第二个选择或 generic publisher。将这些 partial-state paths 纳入
后续 synthetic test design。

## Verdict

`NEEDS_CHANGES` — **0 P0、2 P1、1 P2、0 P3**。最早修复阶段为 `architecture`：pre-E
release policy 的 physical topology 和 fork-safe lock-capability semantics 必须先闭合；随后
同步修订 v19 的 materialization/recovery API。此前不得进入 test design、red/green tests、
implementation、code review、archival replay、M7、CCC/Gate、PIT 新认证或 final OOS。

## Strengths to preserve

- v22 的 PASS 实际 bytes → Bootstrap → `VerifiedQualityInputs` 链、独立
  `quality_gate_issuer` 与 `archive_acceptor`、以及 per-role writer matrix，已解决 v18 的
  issuer/ref-only 根问题。
- post-Bootstrap 的 root-relative `SlotSpec v1`、完整 D v2 parent chains、唯一 lock
  coordinate、Q/R/V held-lock lifecycle，清楚地修复了原先 registry-relative ambiguity 与
  V/terminal race。
- `M6ReplayLifecycle`、controlled mechanics launcher 和 `OfficialArchiveResolver` 将
  S0…S6、raw mechanics-only receipt 与 official FinalIndex resolution 明确分开；没有引入
  数据库、daemon、M7 或真实 replay 范围扩张。
- identity/authority/quality/control/lifecycle 的依赖方向总体简洁，且保留只读历史 M6 proof
  与 append-only trial ledger 的边界。

## Review limits and status

- 本审查为 distinct-subagent、独立、只读 R3 review；仅覆盖冻结威胁模型中的普通
  schema、identity、path/configuration、fork/concurrency、crash/recovery failure，没有将
  hostile runner、host/control-root/kernel/ACL compromise 或 malicious native injection
  作为发现。
- 只读检查了 v22、v19、v18 reviews、威胁模型、STATUS、当前 governance/server source 和
  quality ledger revision `127`。没有修改 product code、tests、contracts、gates、ledger、
  status 或历史 evidence；没有执行项目代码、训练、M6 replay、预算消费、PIT certification
  或 final-OOS access。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 127,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "distinct-subagent-independent-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "PRE_E_TOPOLOGY_AND_FORK_SAFE_LOCK_LIFECYCLE_NOT_CLOSED",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 1, "P3": 0},
  "subject_digest": "sha256:c6788d62318141b3a5f16e09f69e185303247910946582cb6501fad6b7b963a0",
  "next_route": "architecture"
}
```
