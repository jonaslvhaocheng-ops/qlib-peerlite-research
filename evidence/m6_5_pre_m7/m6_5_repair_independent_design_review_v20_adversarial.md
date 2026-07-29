# M6.5 v24 / v20 独立对抗式 R3 设计审查

## Findings

### [P1] 受 Pin/Policy 引用的 RuntimeCandidate 没有被正在执行的 inner entrypoint 自身重新观测并作精确等值绑定

**Section：** `architecture_confirmation_v24.md` §1（17–47 行）；
`m6_5_repair_change_design_v20.md` §4（102–114 行）、§7.1（211–225 行）。

**Scenario：** v24 将 `RuntimeClosureRef` 与 `AuthorizedEntrypointRef` 放入
RuntimeCandidate、Policy 和 Pin，但 release-time runtime 只被要求重新观察
`PinV1 → PolicyV2 → EvidenceBundle`。v20 的唯一入口
`observe_verified_release_policy(sealed_anchor_fd, compiled_pin, fs)` 也没有接收、产生或比较
`ObservedRuntimeCandidate`；其列出的 `m6_replay_fs` API 只观察目录/文件，
`m6_replay_authority.py` 又明确不做 I/O。因此一个正确安装的 Pin/Policy/EvidenceBundle
可以被 outer dispatcher 意外传给另一个 Python 解释器、旧的 entrypoint、错误 site-packages
闭包或错误 source manifest 的 inner process。该 process 仍能解析一致的 Pin/Policy/evidence，
再发布 Bootstrap/PASS/E/C；当前文字没有任何必须比较其实际 executable、entrypoint、source
manifest 和依赖闭包的等式。

**Impact：** 这是冻结威胁模型所列的“绑错 launcher/runtime/environment”的普通部署或
配置故障，不是 hostile-host 假设。`AuthorizedEntrypointRef` 成为未被消费者验证的声明，
从而使 quality route 所审查的 RuntimeCandidate 与实际有官方写入能力的代码分离；故为 P1。

**Evidence：**

- v24 §1 的 RuntimeCandidate 定义包含 inner entrypoint、Python runtime/dependency closure
  与 source manifest，但步骤 6 只要求重新观察 Pin/Policy/EvidenceBundle。
- v20 102–108 行仅将 runtime/entrypoint ref 作为 Pin/Policy 字段保存；110–114 行的 opaque
  token 规则不产生 observed runtime token；213–219 行的 release API 没有实际 runtime 输入。
- 当前威胁模型第 15–18 行把错误 runtime/environment 明列为 M6.5 必须防止的普通故障。

**Direction：** 在 Bootstrap/PASS 之前加入一个受控、不可由 caller mapping 伪造的
`ObservedRuntimeCandidate`：由 inner process 从确定的 executable、entrypoint module/file、
source manifest 和依赖闭包重新计算/观察，逐项匹配 Pin/Policy 的
`RuntimeClosureRef`、`AuthorizedEntrypointRef` 与 profile。把 Pin descriptor 的读取/封存
语义及该 observer 的调用点固定为 release contract，而非实现选择。对错解释器、旧 entrypoint、
错误 venv/site-packages、错误 source manifest、有效但属于另一 release 的 Pin 都必须在任何
quality/control write 前 fail closed。

### [P1] M6 close ledger prefix、当前 live ledger 与传给 legacy worker 的 staged snapshot 没有一条可执行的等值链

**Section：** `architecture_confirmation_v24.md` §1（29–32 行）、§4（140–150 行）；
`m6_5_repair_change_design_v20.md` §4（102–108 行）、§8（253–279 行）；
`scripts/server/verify_m6_peerlite_archival_replay.py`（195–235、362–377 行）；
`src/qlib_peerlite/governance/trial_ledger.py`（489–503、528–559 行）。

**Scenario：** release closure 只记述 `{ledger_identity, prefix_byte_length, prefix_sha256}`，
而 H 又笼统地“contains the observed live ledger identity and immutable prefix”。设计没有定义：

1. H 的 prefix 必须与 route closure 的哪一个 canonical 6/44 prefix 字节、长度、计数和
   authority namespace 完全相等；
2. P0 在哪个已观测 snapshot 上验证这个 prefix，并怎样把该 full snapshot 的 digest 与
   `StageInventoryV1` / staged `trial-ledger.jsonl` 强制相等；
3. live ledger 在合法 append 后 inode 被替换时，何种 identity 是稳定 authority identity，
   何种是本次 snapshot 的 `FileIdentityV1`。

未修改的 raw worker 对 `ledger_path` 只计算 before/after SHA-256；它既不知道 6/44 close
prefix，也不检查预算计数。与此同时，现有 ledger 的合法 reconciliation 用同目录
`os.replace` 发布整个新文件，所以将历史 `ledger_identity` 简单解释为当前
`FileIdentityV1` 会拒绝正常 append；不比较则可以将 legacy 4/29 或其他只读 snapshot
staging 给 worker 而仍产生 `mutated=false` 的 raw receipt。

**Impact：** 这直接落在威胁模型禁止“服务器 legacy 4/29 ledger 代替已验证 M6 close
6/44”的边界。P0 的 canonical manifest 只绑定 H/invocation hash，archive acceptor 又不再读取
scratch；因此一旦 H 和 staged bytes 的关系由实现临时选择，错误预算起点可被包装成完整
S5/FinalIndex 链。故为 P1。

**Evidence：**

- v24 29–32 行与 v20 105–108 行都只给 prefix 三元组，没有与 H、stage inventory 或
  expected 6/44 counts 的验证式。
- v24 147–150 行和 v20 277–279 行正确承认 snapshot `mutated=false` 不证明 live ledger，
  但没有补上 snapshot provenance/equality protocol。
- raw worker 211–235、362–377 行只对 caller-supplied `ledger_path` 做读取和前后 hash。
- 当前 `verify_ledger_prefix()` 已表明历史 prefix 必须按 JSONL line boundary 和
  candidate/model-fit counts 检查（`trial_ledger.py` 200–250 行），而正常 reconciliation
  用 `os.replace` 替换 inode（489–503、556–559 行）。

**Direction：** 冻结独立的 `LedgerAuthorityBinding`/`ObservedLedgerSnapshot` protocol：
固定 close proof 的 logical authority namespace、exact 6/44 prefix bytes/length/hash/counts；
在受控 ledger reader 中验证当前 full JSONL snapshot 含该 prefix，再记录当前 parent chain、
snapshot FileIdentity 和 full bytes digest。`H`、`StagedMechanicsInvocationV1` 与
`StageInventoryV1` 必须显式引用同一 observed snapshot digest，且 staged ledger bytes 必须
等于它；不得用可变化的 live FileIdentity 代替历史 prefix identity。用 legacy 4/29、错误
prefix、append/replacement race、stage-copy substitution 和 source/staged digest mismatch 作为
失败用例，并在任何 P1 dispatch 前拒绝。

### [P2] 已占用但 malformed 的 immutable rejection slot 与“发布一次 canonical rejection”规则不可同时实现

**Section：** `architecture_confirmation_v24.md` §2（75–79 行）、§5（170–185 行）；
`m6_5_repair_change_design_v20.md` §5.2（173–178 行）、§9（314–329 行）。

**Scenario：** official slot publication 是 `renameat2(RENAME_NOREPLACE)`；existing leaf 只有在
精确 bytes 相等时才是幂等读，永不覆盖。可是 archive table 仅将“existing valid rejection”
列为幂等拒绝，并要求任意 malformed/gap/wrong binding/final conflict “publish one canonical
ArchiveAcceptanceRejectionV1”。如果固定 `ARCHIVE_REJECTION` leaf 已存在但自身 malformed、
错误 context 或来自错误 release，publisher 既不能覆盖它，也不能在同一 leaf 发布该 canonical
rejection。当前 resolver 对 malformed rejection 的稳定结果/诊断关系也没有规定。

**Impact：** 错误部署残留、错误 release 遗留 slot 或一次普通文件损坏会使 post-S5 recovery
在“必须记录 canonical rejection”和“禁止替换”之间无合法操作。虽然 fail-closed resolver 可避免
错误 promote，但恢复、审计和操作结果变成实现时决定；故为 P2。

**Evidence：** v20 173–178 行规定 existing leaf 绝不覆盖；v24 175–180 行和 v20 323–324 行
对 malformed residual 却要求在同一 canonical rejection slot 发布一次对象。

**Direction：** 把该组合显式分成三种稳定状态：absent rejection slot 才可发布 canonical
rejection；exact valid rejection 幂等拒绝；occupied-but-invalid/wrong-context rejection 仅可
quarantine/fail closed（可在非官方诊断位置记录），不得尝试覆盖或冒充 canonical rejection。
Resolver、archive recovery 和 later test design 必须对三者给出同一 reason code 和 no-promote
结果。

### [P2] P1 的 non-returning / pre-lock failure 处置没有冻结，导致 held topology lock 可无限期卡住

**Section：** `architecture_confirmation_v24.md` §3（94–121 行）；
`m6_5_repair_change_design_v20.md` §6（187–205 行）、§9（297–312 行）。

**Scenario：** P1 在 P0 获锁前启动，随后在同一 P1 process 内执行可能耗时的 raw function；P0
从 S3 一直持锁到 “P1 completion”。文档没有定义 P1 不返回、GPU/I/O hang、attestation channel
不关闭、P0 获取 topology lock 失败或 S3 前异常时的 deadline、kill/reap、scratch quarantine
与 state transition。`recover_pre_s5` 对 live holder 只返回 `BUSY`，因此没有外部可执行的
正常取消路径。

**Impact：** 这不允许错误 official result，但会让一个正常运行时 hang 或 pre-lock failure
永久占住 K/session 或遗留 idle P1，阻止受控恢复，也没有可审计的 terminal outcome。R3 review
要求 failure、timeout 和 cancellation 有明确边界，故为 P2。

**Evidence：** v24 94–121 行定义 P1 lifecycle、PDEATHSIG 和 live-holder BUSY，但没有 timeout/
cancellation protocol；v20 187–205、297–312 行也只定义 completed child、P0 death 和
post-S0 recovery。

**Direction：** 固定 policy-bound liveness contract：P1 idle/dispatch/worker completion deadlines，
P0 使用 pidfd 的 cancel/kill/reap 顺序，S3 前锁失败时的 session teardown，以及只有确认 child
不再能发送有效 attestation后才能在 held lock 下写 terminal 的规则。deadline 本身和 outcome
必须有稳定 reason code；测试应覆盖 non-returning fake worker、lost IPC、P0 lock-acquire
failure、late attestation after cancellation 与 P0 crash 的 no-promote 行为。

## Verdict

`NEEDS_CHANGES` — **0 P0、2 P1、2 P2、0 P3**。v24/v20 显著收紧了 Linux FD publication、
fork-safe topology capability、P1 credential transport、legacy path-worker staging 和 post-S5
continuation；这些边界应保留。但 RuntimeCandidate self-binding 与 ledger prefix-to-snapshot
authority chain仍是 official authorization 的前置条件，必须在 architecture/design 层关闭。
immutable rejection conflict和P1 liveness虽不导致 promote，也仍是R3 implementation-ready
所需的 deterministic recovery/operability决策。

最早修复阶段为 `architecture`。在修复、重新形成 change design 并通过新的独立 R3 design
review 前，不得进入 test design、red/green tests、implementation、code review、archival replay、
M7、CCC/Gate、PIT 新认证或 final OOS。

## Strengths to preserve

- Pin 在 final anchor placement 后生成，Policy 不自引用，且 quality evidence closure 与
  official replay authority 分离。
- `m6_replay_fs.py` 的 no-follow chain、OFD lock、no-replace publication 和 Linux-only
  fail-closed boundary避免把现有通用 Path helpers 当作 authority。
- P1 在 topology lock 之前启动、fork poison/PID generation、pidfd 和 per-message
  `SCM_CREDENTIALS` 正确避免了之前的 inherited-lock 与 socketpair credential 问题。
- raw replay receipt、scratch、`M6ArchiveSummary` 和 generic PASS 明确不能直接成为
  `FinalIndex`；P0 envelope/O manifest 与 archive resolver 的分层是正确方向。

## Review limits and status

- 本审查由 distinct subagent 独立完成，只读检查 v24/v20、冻结 threat model、gate/contract、
  raw worker、M6 archive 与 trial-ledger source；结论限于普通部署、identity、TOCTOU、
  crash/concurrency、installer/DAG 与恢复故障。
- 未修改 product code、tests、contracts、gates、ledger、status 或 immutable historical evidence；
  仅写入本独立审查证据与其 router result。
- 未执行项目代码、archival replay、训练、预算消费、PIT certification 或 final-OOS access。
- 观察到的质量 ledger revision 为 `140`；路由记录前应由主任务重新读取它。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 140,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "RUNTIME_BINDING_AND_LEDGER_AUTHORITY_NOT_CLOSED",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 2, "P3": 0},
  "subject_digest": "sha256:5c89a379284e0f7397fa6a3fdabcfbb1d19187cb79fe20a999aa27527d074bd2",
  "next_route": "architecture"
}
```
