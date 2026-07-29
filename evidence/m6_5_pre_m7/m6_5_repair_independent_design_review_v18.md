# M6.5 v21 / v18 独立 R3 设计审查

## Findings

### [P1] Bootstrap→QualityPass→E 的内容证明、发行 API 与 writer matrix 相互矛盾，无法机械保证唯一 `archive_acceptor` 发行 E

**Section：** `architecture_confirmation_v21.md` §1（22–51、96–103、306–309 行）；`m6_5_repair_change_design_v18.md` §3.2（118–160 行）、§3.4（219–229 行）、§4（233–244 行）。

**Scenario：** v21 正确要求 QualityPass 的内容精确引用 Bootstrap，并要求只有 Bootstrap
指定的 `archive_acceptor` 能在 E 固定槽位发布 E。可是 v18 的
`validate_bootstrap_quality_pass()` 只接收 `bootstrap` 和一个
`TypedArtifactRef`；该 ref 的 schema/path/hash 本身不能让该 API 读取并验证
QualityPass 的 canonical payload 中的 `replay_issuer_bootstrap_ref`。随后
`from_verified_inputs()` 没有定义已验证 QualityPass 内容或受限 artifact reader 的
输入/所有权。更直接地，v18 §3.4 写成“真实 E/R/V writer 只能由
`replay_supervisor` identity 经新 registry API 调用”，这与 v21 §1、§6 的
`archive_acceptor` 写 Bootstrap/E/C、`replay_supervisor` 写 P/F/A/B/Q/R/V 的
不可变 writer matrix 相反。

**Impact：** 正常发布/恢复配置可能让 replay supervisor 发行 E，或迫使实现额外发明一个
未审查的 QualityPass reader / E publisher。这样即使 Context key、root 和 runtime 均
正确，也无法证明 QualityPass 的内容实际绑定 Bootstrap，或证明 E 由唯一授权身份发布。
这是冻结威胁模型要求防止的 issuer/launcher/configuration misbinding，而不是 hostile-host
假设，因此为 P1。

**Evidence：** v21 35–47 行给出 E 的 issuer/Bootstrap 精确等式，v21 306–309 行给出
writer matrix；v18 140–142 行的 API 只有 ref，153–155 行声称但未暴露可验证
`QualityPass→Bootstrap` 输入，226–228 行又将 E writer 改为 replay supervisor。当前
`m6_archive.py` 仅为历史 M6 只读校验器（1–5、290–372 行），不存在可继承的 E
issuer implementation。

**Direction：** 在 architecture 和 change design 中定义一个不依赖 ambient path 的
`VerifiedQualityPass`（已读取 canonical bytes、hash、nested Bootstrap ref 均验证）及受限
artifact reader；单列 archive-acceptor-only 的 Bootstrap/E/C issuance API，接收受验证的
QualityPass、Bootstrap、sealed slot-parent FD 和 observed effective identity，执行
no-replace publish。registry API 必须拒绝 E/C 发布，replay supervisor 只能从已发布 E
继续 P/F/A/B/Q/R/V。对错 UID/GID/groups、仅替换 QualityPass 内 Bootstrap ref、以及
supervisor 试图发行 E 的 synthetic fixtures 必须在任何 E/R 写入前拒绝。

### [P1] 单根拓扑只闭合到 registry 子树，authority/policy/anchor 及 S0–S6/receipt/output 槽位没有可验证的 FD identity，且 lock components 的基准目录不唯一

**Section：** `architecture_confirmation_v21.md` §3（152–224 行）、§5–§6（279–313 行）；`m6_5_repair_change_design_v18.md` §3.1（90–111 行）、§3.3（180–215 行）、§4（231–250 行）。

**Scenario：** `ReplayControlRootBinding v1` 为 root、registry、claims/bindings/
pre-S0 parents 给出了 identity chain，却只把 `authority`、`policies`、`namespaces`、
`profiles`、`anchors` 写成文本 slot layout；这些 durable publisher parent 没有
`DirectoryIdentity v2` chain。S0…S6、O/H、Child/Execution/Archive receipts 和输出
root 甚至不在 slot layout 中。与此同时，`transaction_lock_components` 是从 root
开始的 `["registry", "locks", ...]`（v21 162 行），但固定流程说“从已验证 registry
解析 transaction lock”（215 行）；没有 `relative_to` 语义，实现在 registry fd 上使用
全量组件会得到 `registry/registry/locks/...`，而剥离前缀又成为隐式 policy。

**Impact：** 同一已验证 root 内一次正常 setup/recovery 的 child-directory replacement，
或锁解析基准的普通配置错误，就可能让 E/C/P/F/A 或后续 receipt/state 写入同名但未
绑定的物理父目录；也可能使两个进程锁住不同实际文件。Q/R/V 的 K 仍可正确，却失去
唯一控制平面和确定恢复位置。这是该威胁模型内的 path/concurrency/crash failure，故为
P1。

**Evidence：** v21 152–180 行的 binding 省略上述 slot-parent identities；201–218 行
只规定 root/registry/lock 后才解析 claim/binding/terminal；v21 292–309 行却要求整条
S0…S6 receipt graph 都继承该 binding。v18 180–196 行的 topology API 只返回一个泛化
descriptor，未声明每个 slot 的 base/FD chain；203–215 行仅实现 R/V/pre-S0。现有 source
中没有任何 S0…S6/receipt/reservation control-plane implementation 可补足该空白。

**Direction：** 将所有 durable role 放入一个 closed、root-relative normal form：每个 role
都必须有唯一的 `base`、component list、parent `DirectoryIdentity v2` chain、leaf rules 和
writer role。至少覆盖 Bootstrap/E/C/P/F/A、R/V/pre-S0、S0…S6、O/H、三类 receipt 和
output root。或把 components 改为 registry-relative，但必须按 schema 明示，不能在代码中
strip prefix。`VerifiedControlTopology` 应只暴露按 role 验证后的 FD/publisher，锁在获得后
重开并复验同一 root/registry/lock chain。测试须包含同 ACL 的 authority/policy/state
parent replacement、root-vs-registry component base confusion、以及同名不同 lock inode 的
拒绝。

### [P1] v18 没有将 v21 要求的 S0→S6、receipt 与输出生命周期映射到任何实现组件或稳定 API，post-S0 崩溃规则仍是声明而非可验证行为

**Section：** `architecture_confirmation_v21.md` §5–§6（289–320 行）；`m6_5_repair_change_design_v18.md` §3.3（162–215 行）、§4（233–250 行）、§7（289–304 行）。

**Scenario：** v21 的一条强制链是 `V → S0 → S1 → O → S2 → H → S3 → ChildReceipt → S4
→ ReplayExecutionReceipt → S5 → ArchiveAcceptanceReceipt → S6`，并为每个节点规定
context、writer、前驱和 archive 顺序。v18 唯一的 lifecycle module/API 只定义
`build_precommit_before_claim`、`reserve_then_bind` 和 `recover_pre_s0`；其明确 ownership
也只到 “Q/R/V lifecycle and pre-S0 recovery”。数据表把 S0…S6/receipts 交给一个
“v21 writer matrix”，而不是 module/API；ordered plan 没有补充步骤。当前 repository 的
`m6_archive.py` 只读验证历史 evidence，并没有这些 transition 或 receipt API。

**Impact：** 一个实现者在 V 之后只能直接写文件或另行设计 state/receipt publisher、
predecessor validation、S0 后 crash recovery 和 output FD capture。这会绕过刚定义的
topology/authority seam，或把关键设计决策推迟到 code review；两者均不满足 R3 的
implementation-ready 标准。尤其无法证明 S1/O/H/Child/Execution/Archive 的 fork/gap、
wrong writer、output-before-S0 或 S0 后恢复不会把结果推进至 S6，因此为 P1。

**Evidence：** v21 289–301、306–320 行要求完整单向图和 writer/FD/ACL verification；
v18 168–190、203–215 行只公开 Q/R/V/pre-S0 API；238–250 行只用抽象文字描述
S0…S6；289–304 行的 implementation plan 未出现 state/receipt/output component。`rg`
当前 source 未找到 `ReplayExecutionReceipt`、`ArchiveAcceptanceReceipt`、
`FreshOutputReservation` 或 S0 lifecycle implementation。

**Direction：** 在进入 test design 前，二选一并写死边界：

1. 若本 change 的目标是让 M6.5 gate 之后可考虑 archival replay，则增加一个受
   `VerifiedControlTopology` 约束的 lifecycle component，显式定义每个 state/receipt 的
   typed schema、fixed role slot、writer authorization、immediate predecessor、no-replace
   publish、output FD capture、lock/reopen protocol 和所有 post-S0 crash/recovery outcomes；
   或
2. 若 v18 只交付 validate-only parser，则从 architecture/status 中删除“通过后可考虑
   archival replay”的含义，并明确另一个独立、先审查的 lifecycle change 才可实现
   S0…S6。

当前主线选择的是第一种，因而 test design 必须能对整条 state graph 作 synthetic
negative/failure-path verification，且仍不得启动真实 replay。

## Verdict

`NEEDS_CHANGES` — **0 P0、3 P1、0 P2、0 P3**。最早修复阶段为
`architecture`：v21 的 slot/topology model 未覆盖所有 durable authority/state paths，
而 v18 又在 Bootstrap/E issuer 和 lifecycle component 上引入冲突或遗漏。先修订
architecture 与 bounded change design，再重新进行独立 R3 design review；此前不得进入
test design、red/green tests、implementation、code review、M6 replay、M7、CCC/Gate、PIT
新认证或 final OOS。

## Strengths to preserve

- v21 已真正修复上一轮“六项 evidence key vs family/runtime/scope”不一致：完整 Context、
  唯一 preimage 和逐项 runtime/inventory comparison 是清晰且无环的。
- `DirectoryIdentity v2` 重新明确包含 `opaque_file_handle_sha256`，K v4 直接使用 D 的
  canonical bytes，unsupported handle fail-closed；这解决了此前 v2 field-set ambiguity。
- C 的 PTemplate → 独立 P/F materialization → A 的方向仍避免 hash cycle；Q 在 R 前冻结
  complete V preimage，R/V slots 与 pre-S0 burn/quarantine 也仍是正确基础。
- 将新代码与只读 `m6_archive.py`、append-only `trial_ledger.py` 分离，并保持
  validate-only/no-M7/no-OOS 边界，是合理的低复杂度选择。

## Review limits and status

- 本审查为 distinct-subagent、独立、只读 R3 design review；范围只限冻结威胁模型中的
  普通 schema、identity、path/configuration、concurrency 和 crash/recovery failure，未将
  hostile runner、host/control-root/kernel/ACL compromise 或 malicious native injection
  作为 finding。
- 已只读检查 v21、v18、两份 v17 review、威胁模型、STATUS、现有 governance source
  与 quality ledger revision `119`。没有修改 product code、tests、contracts、gates、
  ledger 或历史 evidence；没有执行项目代码、训练、M6 replay、预算消费、PIT certification
  或 final-OOS access。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 119,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "distinct-subagent-independent-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "AUTHORITY_ISSUANCE_TOPOLOGY_AND_LIFECYCLE_NOT_IMPLEMENTABLY_CLOSED",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 3, "P2": 0, "P3": 0},
  "subject_digest": "sha256:60032bf6729373ca70471e2e083a34bd53244531b9329fe7914dec1b24631f23",
  "next_route": "architecture"
}
```
