# M6.5 v24 / v20 独立 R3 设计审查

## Findings

### [P1] 已冻结的 writer matrix 需要不同 Unix identity，但 P0 无法按设计启动 P1，S5 之后也没有 archive-acceptor 的独立进程与锁交接协议

**Section：** `m6_5_repair_change_design_v20.md` §6（187–205 行）、§9（297–324 行）、§13（384–389 行）；
`architecture_confirmation_v24.md` §3（87–121 行）；
`architecture_confirmation_v23.md` §2（159–168 行）和 §3（217–233 行）；
冻结 threat model（9–11、33–39 行）。

**Scenario：** v20 的唯一 P1 启动操作是 P0 执行
`python -m qlib_peerlite.governance.m6_replay_worker_session`。普通 `fork`/`exec` 会保留 P0
的 effective uid/gid/groups；设计既禁止用未审查的 `preexec_fn`，也没有声明一个已冻结的
setuid helper、外层 dispatcher spawn protocol、权限能力、身份降级时点或失败语义。因此实现者
只能让 P1 与 P0 同身份运行，或在实现阶段自行引入一个新的特权/identity-transition component。

同一个缺口也存在于 S5 之后。writer matrix 要求 `archive_acceptor` 作为 E/C 及
ArchiveAcceptanceReceipt/S6/FinalIndex 的唯一 durable publisher，但 `M6ReplayLifecycle` 只说
“handed exclusively to archive acceptor”。`LockedVerifiedControlTopology` 又是 PID/generation/actor
绑定的 capability，P0 取得的 token 不能被另一个 Unix identity 直接复用；设计没有定义
archive acceptor 如何从 sealed descriptor 重建 context、以自己的 actor capability 获取新 OFD
lease、以及 P0 在何时释放其 S3–S5 lease。

**Impact：** 这是冻结威胁模型明确覆盖的正常部署/ACL/configuration failure，不是 hostile host。
它会使 P1 的 child-verifier identity separation 仅是声明，或使 S5 正常完成后无法由规定的
result publisher 继续；实现者还可能错误地用 P0 身份写 acceptance/index。这样 physical writer
matrix、独立 result-publisher 与 lock-owner invariant 都不可验证，故为 P1。

**Evidence：** v20 §6 只固定了 Python module、socket FD、`env -i`、pidfd 和 peer credential；
没有 uid/gid transition mechanism。v24 §3 要求 P1 与 P0 identity distinct，同时说明不使用
unsafe `preexec_fn`。v20 §9 的 `ArchiveAcceptor.accept_or_resume_post_s5(locked, k)` 接收一个
process-bound `locked` token，却没有对应的 archive process/entrypoint/lease-acquisition lifecycle。
而 threat model 把 runner 与 result-publisher 的受控 Unix identity boundary 列为 trust root。

**Direction：** 在架构中冻结唯一可部署的 actor-launch graph：由哪一个受信 outer dispatcher
以什么已绑定 hash 的 helper/exec 启动 P0、P1 和 archive acceptor；P1 的 UID/GID/groups/
capabilities 的切换与验证、socket/FD allow-list、`PDEATHSIG` parent relationship、失败时的
fail-closed code；以及 S5 后 P0 release → archive acceptor re-observe sealed descriptor/context
→ independently acquire/revalidate topology lease → publish/continue 的精确顺序。明确 archive
acceptor 不接受 P0 capability。后续 Linux integration tests 必须验证 wrong/same UID、identity
transition failure、P0 token cross-process use、S5-to-archive crash/restart 与 wrong publisher。

### [P1] path-only raw worker 与“不允许 P1 search worker-job parent”的 ACL 及 Python import 模型不兼容，已验证的 frozen source 不能保证实际执行的模块来源

**Section：** `m6_5_repair_change_design_v20.md` §6（201–205 行）、§8（253–293 行）；
`architecture_confirmation_v24.md` §3–§4（94–100、123–158 行）；
`architecture_confirmation_v23.md` §2（191–195 行）和 §5（275–321 行）；
`scripts/server/verify_m6_peerlite_archival_replay.py`（195–252 行）。

**Scenario：** 设计要求 P1 从收到的 job FD `fchdir`，给 unchanged worker 传 stage-relative
arguments，同时要求 supervisor-only job parent 对 P1 “not searchable”。真实 `run()` 立即对七个
输入和 `output_dir` 调用 `Path.resolve()`（脚本 211–217 行），随后全部按所得绝对 pathname
打开/创建对象（例如 218–252 行）。若 parent 真无 search/execute permission，resolved absolute
path 无法再次 traverse；若为了运行而开放 parent execute permission，则设计未定义它如何只允许
该 job、不能越界到 sibling/control paths，也未规定 re-open identity check 的时点。

此外，P1 自身是以
`python -m qlib_peerlite.governance.m6_replay_worker_session` 启动，因而 live runtime 的
`qlib_peerlite` parent package 已进入 `sys.modules`。raw worker 仅在 237–242 行把 staged
`frozen_source_root/src` 插到 `sys.path` 后导入 `qlib_peerlite.*`。Python 会复用已加载的 parent
package/path，故这些 imports 可以来自 live runtime 而非 staged frozen source；当前 design 没有
清理/隔离 `sys.modules` 或逐模块 provenance verification。

**Impact：** 正常 ACL 配置下 worker 可能根本无法运行；为了修通而临时改 ACL/path 则会绕开
FD-only staging model。更严重的是，形式上 hash-verified 的 stage 可能与实际 `build_qlib_fold` /
`PeerLiteModel` 导入来源不同，导致 raw receipt 对“frozen source replay”的主张不再可审计。
这正是 threat model 所列 wrong launcher/runtime/environment binding，故为 P1。

**Evidence：** v20 §8 同时要求 stage path derived after `fchdir` 和 parent not searchable；
v23 §2 将 parent 固定为 supervisor-only `0700`。未改变的 worker 显式 `.resolve()` 所有 path，
并通过 `sys.path.insert(0, frozen_src)` 之后使用 package imports；它没有接收 FD 或 namespace
isolation interface。v24 保留“P1 dynamically loads staged raw-worker as a function”，但没有
处理 P1 启动时已导入的 package namespace。

**Direction：** 冻结一个可运行的 adapter contract，而不是让实现选择：明确 child-visible
absolute staging namespace 的每一层 ACL（可 search 但不可 list 的精确 parent/ancestor policy）、
per-job identity check 与 no-follow re-open rules；或明确一个等价的 mount/namespace mechanism。
同时采用不预加载 `qlib_peerlite` 的 neutral bootstrap，或定义安全的 module purge/import plan，
并在 dispatch 前后证明所有 `qlib_peerlite.*` modules 的 `__file__`/hash 都属于 StageInventory。
不得以 caller path、`/proc/self/fd` fallback 或修改 historical worker 代替。测试须覆盖 inaccessible
parent、sibling traversal、path swap、同名 live package preloaded 与 staged-module provenance。

### [P1] ArchiveAcceptor 需要复核的 staged invocation / normalized result 没有确定的 durable slot 或内嵌 schema，S5 后恢复会失去官方可重建的证据对象

**Section：** `architecture_confirmation_v24.md` §4（152–158 行）；
`m6_5_repair_change_design_v20.md` §4（90–100 行）、§8（281–293 行）和 §9（314–336 行）；
`architecture_confirmation_v23.md` §2（176–195 行）。

**Scenario：** v24 规定 `ReplayOutputManifestV1` 含 `staged invocation ref`，S5 引用 manifest，
ArchiveAcceptor 仅 re-open O 而不读取 worker scratch。v20 也列出
`StagedMechanicsInvocationV1` 与 `NormalizedMechanicsResultV1`，并要求 manifest bind invocation /
normalized result；但没有为 invocation 或 normalized object 定义 root-relative `SlotSpec`、O 内固定
leaf、sole durable publisher、canonical serialized form、publication order 或 recovery equality。
v23 只新增了 `WORKER_JOB`、`CHILD_RECEIPT_ENVELOPE` 和 `ARCHIVE_REJECTION` slots。

**Impact：** 如果 “invocation ref” 指向 worker job/stage，archive recovery 违反 “scratch is
forensic-only / not a prerequisite” 的承诺，而且 job 可在 pre-S5 recovery 中 quarantine；如果它只是
digest，ArchiveAcceptor 无法在 receipt→S6 或 S6→FinalIndex crash window 重建并验证它；如果它是
inline bytes，实现者仍必须临时决定 envelope/manifest schema 和 equality semantics。结果是
normal crash/restart 时无法按宣称独立复核 `Context/H/envelope/invocation`，或需要未审查的证据
trust shortcut，故为 P1。

**Evidence：** v24 明确使用 “staged invocation ref” 并要求 archive independently recompute，
v20 §9 又要求 archive revalidate `O/H/manifest and all slots`。但 v20 §8 只写 P0 publishes one
envelope and one manifest；没有说明 ref 的 immutable target，且 §4 的 DTO list 不等同于 slot
ownership/persistence contract。

**Direction：** 选择且冻结一种唯一模型：例如 P0 在 O 的 fixed, root-relative no-replace leaves
durably publishes canonical `StagedMechanicsInvocationV1` 与 `NormalizedMechanicsResultV1`，然后
manifest/envelope use exact refs; 或把完整 canonical bytes 以明确 field/equality rules 内嵌到
envelope/manifest。无论哪种，都要写清 writer、parent identity、fsync/publication order、S5
predecessor relation、archive re-open algorithm、quarantine/retention policy 和 no-path guarantee。
后续 tests 需覆盖 job removal/quarantine、S5 restart、receipt-only and S6-only continuation，以及
ref/digest substitution。

### [P2] FS-layer import rule 与 `SlotSpecV1` 的归属相互矛盾，实施会迫使未审查的向上依赖或 duplicate policy

**Section：** `m6_5_repair_change_design_v20.md` §3（56–82 行）、§4（86–100 行）和 §5.2
（162–178 行）；`architecture_confirmation_v24.md` §2（57–83 行）与 §6（187–210 行）。

**Scenario：** design 要求 `m6_replay_fs.py` 只 import pure identity types，且 “no lower module
imports a higher one”。但它的 public `publish_immutable_cjson(... expected: SlotSpecV1)` API 需要
`SlotSpecV1`，而 v20 只把 `SlotSpecV1` 定义在更高层的 `m6_replay_authority.py`。没有 lower-level
protocol/field projection 的定义。

**Impact：** 实现者必须引入 upward import/cycle、在 FS 复制 slot policy，或临时 duck-type a
security-relevant object，均会损害已经很重要的 filesystem boundary 可审计性。这不立即授权错误
result，但不满足 R3 “no hidden material design decision”，故为 P2。

**Direction：** 把 immutable publication requirements 移到 identity/fs-owned pure DTO，或冻结一个
lower-layer `PublicationSlotView` protocol（exact fields, canonical validation, ownership and import
direction），并要求 authority’s SlotSpec adapt to it. 在 implementation/test-design 前加入 import
graph check 与 protocol-substitution tests。

## Verdict

`NEEDS_CHANGES` — **0 P0、3 P1、1 P2、0 P3**。最早修复阶段为 `architecture`：identity process
graph、path-only worker adapter 的 executable boundary，以及 durable output-evidence topology 都会
改变 physical publisher / trust / recovery contracts，不能留给 test-design 或 implementation 决定。
在架构与变更设计重新闭合并取得新的独立 R3 `PASS` 前，不得进入 test design、red/green tests、
implementation、code review、archival replay、M7、CCC/Gate、PIT 新认证或 final OOS。

## Strengths to preserve

- v24 的 release Pin 安装 DAG、observed Policy/Evidence closure、quality Bootstrap/PASS byte binding
  和 immutable prefix，已比 v19 更好地关住 pre-E policy substitution。
- Linux-only no-follow/identity/OFD/no-replace boundary 与 generic artifact writer、trial ledger、raw
  receipt 的隔离是正确且必要的；不要回退到 `flock`/`os.replace`/Path authority。
- child IPC 的 `SO_PASSCRED`/nonce/pidfd/start-tick model、S3–S5 held lock、raw mechanics-only
  receipt、post-S5 receipt/S6/index continuation 与 rejection-first resolver 均应保留。
- 本审查认可模型/数据/M6 historical proof、trial budget、PIT、M7/final-OOS 均保持在本次 scope
  之外；没有建议扩大为 hostile-host 或 production trading system。

## Review limits and status

- 本审查是 distinct-subagent、独立、只读 R3 design review；只检查冻结 threat model 内的
  deployment identity、ACL/path, import provenance, durable evidence, crash/recovery 与 module
  boundary。没有把 compromised host/control root/kernel/ACL 或 malicious in-process native code
  作为 finding。
- 只读检查了 v24/v20、v19 两份独立审查、冻结 threat model、历史 raw worker、generic artifact
  writer、M6 archive、trial ledger 与 Python 3.11 project metadata。没有修改 product/test/contract/
  gate/ledger/status 或 historical evidence；没有执行 project code、training、M6 replay、budget
  consumption、PIT certification 或 final-OOS access。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 140,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "PROCESS_IDENTITY_AND_WORKER_PROVENANCE_NOT_CLOSED",
  "issue_type": "architecture",
  "subject_digest": "sha256:5c89a379284e0f7397fa6a3fdabcfbb1d19187cb79fe20a999aa27527d074bd2",
  "summary": "Three architecture-level normal-failure paths remain: actor launch/handoff, executable frozen-worker provenance, and durable invocation/result evidence.",
  "artifact_paths": ["evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v20.md"],
  "evidence_paths": ["evidence/m6_5_pre_m7/architecture_confirmation_v24.md", "evidence/m6_5_pre_m7/m6_5_repair_change_design_v20.md"],
  "commands": [],
  "blockers": ["Reissue architecture and change design, then obtain a new independent R3 design-review PASS before implementation."]
}
```
