# M6.5 v21 / v18 独立对抗式 R3 设计审查

## Findings

### [P1] v18 把 Bootstrap/E/C 的唯一发行者重新变成互相矛盾的角色，且没有一条能按 v21 发布 E 的 durable writer 路径

**Section：** `architecture_confirmation_v21.md` §1 第 35–47 行、§6 第 304–309 行；`m6_5_repair_change_design_v18.md` §3.2 第 153–160 行、§3.3 第 162–215 行、§3.4 第 217–229 行、§4 第 231–240 行。

**Scenario：** v21 明确指定 `archive_acceptor` 是 Bootstrap/E/C 的唯一实际写入者，`replay_supervisor` 只能从 P 开始写入。v18 却同时规定：

- §3.4 说“真实 E/R/V writer 只能由 `replay_supervisor` identity 经 registry API 调用”；
- §4 的 owner 表又把 `C/P/F/A/B/Q` 都分配给 `replay_supervisor`，因而 C 与 v21 冲突；
- 同一表把 Bootstrap / QualityPass / E Context 标为“quality pipeline / archive acceptor”，并非一个可校验的唯一 effective identity；
- authority 模块宣称是纯 parser/graph validator、不创建目录，registry 的公开生命周期只定义 Q/R/V，validate-only entry 又明确不写 E/R/V。

因此没有一个模块/API 能以 v21 所要求的 archive-acceptor 身份，在 Bootstrap 固定的 authority slot 做 E 的 no-replace durable publish；实现者只能选择“按 v18 让 supervisor 写 E/C”、“绕过已经声明的模块边界另写 publisher”，或让系统始终不能构造 E。第一种会把 root authority 的实际 peer/FD ACL 与 Bootstrap 的 `archive_acceptor_identity` 分离，第二种则留下未审查的 writer/slot 路径。

**Impact：** 这不是 hostile-host 假设。它是普通 release/identity wiring 或实现分工错误，正落在威胁模型要求防止的 authority/runtime/路径绑定范围。若为使流程可运行而放松 actual-writer check，replay supervisor 可以发行本应由 archive acceptor 单独发行的 authority；若不放松，则 canonical path 不可实现。两者都会使 E→C 的 authority 边界不能机械验证，故为 P1。

**Evidence：**

- v21 §1 和 §6 的 writer matrix 是 exhaustiveness-style：archive acceptor 写 Bootstrap/E/C，supervisor 从 P/F/A/B/Q/R/V 开始。
- v18 §3.4 对 E/R/V 的 supervisor-only 说法与其直接相反；v18 §4 又将 C 给 supervisor，且没有说明 archive acceptor 与 quality pipeline 是同一 pinned identity/capability。
- v18 中列出的 `M6ReplayAuthorityBindingV3.from_verified_inputs()` 仅构造对象；它没有 writer identity、slot FD、no-replace publication 或 receipt/ACL check contract。registry 的 `reserve_then_bind()` 同样只覆盖 R/V。

**Direction：** 在下一版建立一个闭合、逐对象的 writer/owner/effective-identity/FD-ACL/slot matrix，并使它与 v21 byte-for-byte 一致：quality pipeline 若参与必须明确为 archive acceptor 的同一 pinned identity或一个前置、不可混淆的 QualityPass producer；archive acceptor 必须拥有唯一的 Bootstrap/E/C publish API 和固定 slot/atomic publish contract；replay supervisor 从 P 开始。让 authority/registry public APIs 接受并验证不可伪造的 effective-actor/validated-slot capability，而不是在注释中宣称角色。必须加入“正确 bytes、错误 effective identity”的 Bootstrap、E、C、R、V 负例，以及 E/C 从 supervisor 发出的拒绝例。

### [P1] QualityPass→Bootstrap 的信任链在 v18 的 public contract 中只有 ref 标签，没有受信字节观察/解析路径，不能证明 E 真正来自那个 M6.5 PASS

**Section：** `architecture_confirmation_v21.md` §1 第 22–47 行、§2 第 55–103 行；`m6_5_repair_change_design_v18.md` §3.2 第 113–160 行、§3.4 第 217–229 行、§5 第 254–269 行。

**Scenario：** v21 要求 `M6_5_ENGINEERING_QUALITY_GATE v1 PASS` 的实际 canonical content 以 complete typed ref 绑定 Bootstrap，并要求 E 验证 `QualityPass.replay_issuer_bootstrap_ref == Ref(Bootstrap)`。但 v18 唯一列出的 API 是：

```python
def validate_bootstrap_quality_pass(
    bootstrap: M6ReplayAuthorityBootstrapV1, quality_pass: TypedArtifactRef
) -> None: ...
```

`TypedArtifactRef` 只是 schema/role/version/path/hash 的声明；v18 没有一个 `M6QualityGatePass` parsed record、受信 immutable evidence reader、固定 PASS slot/anchor，或把 observed canonical PASS bytes 与该 ref 的 hash 绑定的 API。authority 模块又声明自己不创建目录，validate-only entry 只笼统地“接收 release/quality pipeline 提供的 Bootstrap、QualityPass 和 sealed anchor descriptor contract”。

于是普通 pipeline/configuration 错误可以传入一个格式正确的 PASS ref，但实现没有指定如何读取并验证其 body 中的 Bootstrap ref；也可以让一个外部 caller 先解析另一个 self-consistent quality document，再只把其 ref 交给 authority validator。`from_verified_inputs()` 的省略签名不能替代这个 trust/byte-observation contract。Context key 会稳定地哈希错误 ref，却不能证明该 ref 所指 bytes 是已完成质量路由的那个 PASS。

**Impact：** E 的唯一发行起点会退化为“调用方说它有一个 PASS ref”，无法防止 release pipeline 绑错 PASS、错读 same-schema artifact 或在隐式 resolver 中选择错误 store。该问题属于普通部署/路径/配置失配，不依赖攻击者控制 host、ACL 或 native code；它允许未被实际质量 gate 授权的 Bootstrap/E chain 看起来字段自洽，故为 P1。

**Evidence：**

- v21 的关键等式比较的是 `QualityPass` 内部字段，而不仅是其 ArtifactRef；Context 还要求 quality PASS 与 `replay_issuer_bootstrap_ref` 都指向同一 Bootstrap。
- v18 的 `TypedArtifactRef` contract只定义 ref 的 parse，没有定义 ref 到 observed canonical bytes/parsed PASS 的 trusted resolution；所列的 validator 接口也没有 PASS object 或 artifact-reader capability。
- v18 §3.4 / §5 禁止 ambient config 和自由 path，却没有用可验证的 sealed input manifest、FD/root-bound reader 或实际 PASS slot 填补该输入来源。

**Direction：** 为 PASS 引入一个 closed parsed `M6EngineeringQualityGatePassV1`（或等价 verified record）和一个显式、root-bound、no-follow artifact-observation capability。E construction 必须接收 observed PASS bytes + observed typed ref + Bootstrap bytes/ref，先检查实际 PASS schema/role/hash/slot、其 `replay_issuer_bootstrap_ref` 与 observed Bootstrap ref，再允许 Context/E materialization；不得仅信任 caller-provided ref 或从环境/任意 repository path 解析。相同机制应覆盖 Context 的 `research_contract_ref` 和其他需要读取内容以验证语义的 typed refs。测试应固定 PASS ref 而替换其 observed bytes、固定 bytes 而替换 slot/ref、以及让 PASS 指向不同 Bootstrap，均在 E 之前拒绝。

### [P1] registry API 没有把“已验证且持有的 transaction lock”表达为不可绕过的能力，Q/R/V 与 recovery 仍可在普通竞争中形成 terminal/V 并存

**Section：** `architecture_confirmation_v21.md` §3 第 201–224 行、§5 第 277–302 行；`m6_5_repair_change_design_v18.md` §3.3 第 162–215 行、§4 第 242–250 行。

**Scenario：** v21 要求每个 freeze/claim/recovery/scan 先重验 topology，然后才 acquire lock 并继续状态。但 v18 的 `reopen_and_validate_control_topology()` 只返回一个 `VerifiedControlTopology`；公开 API 没有 acquire/hold/release lock 操作或 `LockedVerifiedControlTopology`/lock token。`reserve_then_bind(topology, precommit)` 和 `recover_pre_s0(..., topology)` 都接受相同的 unlocked-looking topology，文字只说它们在“已验证 transaction lock 内”。

例如进程 A 先以 R 的 `O_EXCL` 成功发布 claim，因调度延迟尚未发布 V；进程 B 重新验证 topology 后恢复，看到 R 无 V，写入固定 terminal；A 随后继续发布 V。V 与 terminal 使用不同 O_EXCL slots，单靠各自的 no-replace 并不能阻止二者同时成功。v21 要求 terminal 一旦存在就永久拒绝 V，而 v18 没有写明一个跨 R→V 或 R→terminal 的独占 guard、发布前 terminal recheck，或在 crash/lock-loss 后必须重新开始验证的规则。

**Impact：** 这正是冻结威胁模型内的正常并发、重启和半写故障。产生 `R + valid V + terminal` 的矛盾残留后，恢复/scan 的唯一决定性被破坏；后续实现只能临时选择相信 V 或 terminal，或额外创建未设计的 quarantine。虽然 O_EXCL 避免覆写，它不能替代互斥状态机，因此为 P1。

**Evidence：**

- v21 §3 第 217–218 行将“获取 lock”列为拓扑验证后的独立步骤；§5 又让 terminal 和 V 处于不同 fixed slots。
- v18 的 registry public contracts没有锁 guard、lock acquisition primitive、lock scope、lost-lock/crash revalidation 或能够证明 mutation 只在持锁期间执行的参数类型；`VerifiedControlTopology` 的 frozen dataclass 也不表示 ownership。
- v18 §4 只给出 `ALREADY_CLAIMED`，不能处理“同一 claim 的 V 发布与 recovery terminal”这一不同文件槽的竞争。

**Direction：** 将所有可变 registry 操作收敛为一个不可公开构造的 `LockedVerifiedControlTopology`（或等价 capability）：同一 registry API 必须以 verified lock FD 获取明确的 advisory/OFD lock，获取后重新验证 topology/slot parents，再 scan、判定和执行一个完整的 R→V 或 R→terminal decision。持锁 capability 的生命周期、close/crash semantics、fork/exec prohibition、每次 publish 前的 terminal/predecessor recheck和 release ordering必须写明；任何 lock acquisition failure/loss 都应不写入并要求从 reopen/validate 开始。测试应以两个真实进程竞争 R/V/recovery terminal，证明最多一个路径发布且不会留下 V 与 terminal 并存。

### [P2] root-relative component lists 与 registry-relative resolution 的基准不一致，当前 FD API 无法无歧义地解析并证明 lock/slot 的物理路径

**Section：** `architecture_confirmation_v21.md` §3 第 152–180、201–219 行；`m6_5_repair_change_design_v18.md` §3.1 第 90–99 行、§3.3 第 180–196 行。

**Scenario：** `ReplayControlRootBinding` 把 `transaction_lock_components` 定义为 root-relative-looking `['registry', 'locks', 'm6-replay-transaction.lock']`，claims/bindings/terminal parents 也都以 `['registry', ...]` 表示；但 v21 第 215 行又要求“从已验证 registry 解析 transaction lock”。v18 只暴露 `resolve_dir_components(parent_fd, components)`，没有 file-component resolver，也没有说明每个 component list 的 anchor（control root、registry FD 还是其余父目录）。严格按文字从 `registry_fd` 解析该完整 list 会访问 `registry/registry/locks/...`；改为从 root FD 解析则是另一条未被 API/contract标注的语义。

**Impact：** 实现者必须自行选择 path-coordinate system，导致 topology proof、lock identity和 fixed slot derivation不再是同一可测试规则。最保守实现会无故失败，宽松实现则可能悄悄删掉一个 `registry` component；这会削弱 v21 所追求的 no-free-path/one-root property。它目前仍可通过明确规范修复，故为 P2。

**Direction：** 对每个 component list 增加不可省略的 `relative_to`/anchor identity，或把 registry-relative lists改成 suffixes（例如 lock `['locks', 'm6-replay-transaction.lock']`）。补充 no-follow directory/file resolver interfaces，明确它们返回的 FD、每级 identity comparison和最终 FileIdentity comparison；固定 slot derivation也必须以同一 coordinate rule实施。测试应覆盖 root-vs-registry double-prefix、错误 anchor、symlink和同名 sibling，不允许任何 implicit stripping/prefixing。

## Verdict

`NEEDS_CHANGES` — **0 P0、3 P1、1 P2、0 P3**。最早修复阶段为 `architecture`。v21/v18 已解决上一轮的完整 Context preimage、E→A root identity 和 DirectoryIdentity v2 opaque-handle 问题，但当前的 issuer/writer、quality-PASS evidence observation、锁生命周期和 path-coordinate contract仍留下实现无法安全自行补全的 material decisions。未闭合前不得进入 test design、red/green tests、implementation、code review、server archival replay、M7、CCC/Gate、PIT 新认证或 final OOS。

## Retained strengths

- Context v1 将 family、scope、14/0/OOS profile、六项 M6 evidence、七项 runtime/startup inputs、Bootstrap、root binding、actor matrix和 allow-list 放入同一个 canonical preimage；这实质修复了 v20 的 six-role-only key mismatch。
- Bootstrap→E 的 future-free issuance model、single root/registry/lock identity equations与完整 `DirectoryIdentity v2`（包括 opaque handle 和 fail-closed helper）正确强化了普通 runtime/path replacement 防线。
- C 的 PTemplate→P/F→A 无环 materialization、Q-before-R complete V preimage、flat O_EXCL K slots、pre-S0 terminal和 S0…S6 left-only lineage仍是合适且低复杂度的主线。
- M6 historical evidence、trial ledger、PIT/data product、M7、CCC/Gate和 final-OOS 的边界保持封锁；本审查没有要求扩大范围或引入服务/数据库。

## Review limits and status

- 这是 distinct-subagent 的只读对抗式 R3 review。只检查冻结威胁模型内的普通 schema/path/TOCTOU/concurrency/crash/runtime/identity failure；没有把 hostile runner、host/control-root/kernel/ACL compromise 或恶意 native injection 作为发现。
- 未修改产品代码、tests、contracts、gates、ledger、状态卡或历史证据；未运行项目代码、训练、M6 replay、trial-budget 消耗、PIT `CERTIFY` 或 final-OOS。
- 审查时只读观察 ledger revision=`119`；review subject 为 v18，architecture evidence 为 v21。路由记录前必须由主流程重新读取 ledger。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 119,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "AUTHORITY_ISSUANCE_TRUST_CHAIN_AND_LOCK_LIFECYCLE_NOT_CLOSED",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 3, "P2": 1, "P3": 0},
  "subject_digest": "sha256:60032bf6729373ca70471e2e083a34bd53244531b9329fe7914dec1b24631f23",
  "next_route": "architecture"
}
```
