# M6.5 canonical v8 / architecture v11 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查技能：`eng-review-design`  
审查性质：独立、只读、R3；仅按冻结 `research_governance_threat_model_v1.md` 审查普通配置、并发、崩溃、路径/运行时误选。未把 hostile runner、host/control-root/ACL/内核被攻破或恶意 native injection 作为本报告的 blocker。

未修改产品代码、测试、契约、gate 或 `.engineering-quality/**`；未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。

## 审查对象

- canonical change design：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v8.md`，SHA-256 `c903ec58a789607cc1f7202f8279a4c1d0d58ac786157afd1116a34666b643cf`；其纳入 v6 的 §1–§4、§7，并替代 v6 的 §5、§6。
- canonical architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v11.md`，SHA-256 `c3766c6aa50da57d0c0866d4f5542d1e227283da6a4abe5d2a15c2b67736d5f3`；其以 §3/§4 替代 v9 的对应段落和 v10 replay 段落。
- frozen threat model：`evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。

## Findings

### [P1] authority graph 同时要求 `Plan → QRC` 与 `QRC → Plan`；冻结内容哈希无法形成文中宣称的无环外部锚

**Section：** architecture v11 §3.1，第 58–60 行；v8 §5.1，第 114–130 行。

**Scenario：** v11 第 58 行明确规定 `M7AuthorizationPlan v1` “禁止引用 QRC”，并把 frozen QRC 对 plan 的精确引用作为单向 DAG 的第一条边；但第 60 行又要求 Plan “反向绑定同一 QRC”。若“绑定”是 QRC 的 content digest/ID（其他边均被定义为 exact hash/content binding），冻结 Plan 与 QRC 产生不可计算的循环。若实现为使安装能够完成而把其中一条边改为可变 selector、预先占位 hash、content-hash 排除字段或只比较自述 contract ID，原本的 external anchor 重新可被普通部署选择错误的 QRC/plan/预算/事件计划绕过。

这个问题不是 hostile control-root 修改：受信 supervisor 完全可能在两个有效草案/修订版间按错误配置选择一个“内部自洽”的组合。此时 registry/authority/grant/activation 的后续 full-equality 只会证明错误组合内部一致，无法证明它是冻结研究计划选定的那个对象图。

**Impact：** 错误 QRC/plan 可从正确 M6 `6/44` genesis 启动，却携带错误 cap、fit slot、contingency 或 namespace，并获得 profile/permit。它直接破坏研究预算与预注册选择边界。

**Evidence：** v8 的 canonical design 采用可计算的单向描述（Plan 不引用 QRC，QRC binds plan）；v11 作为当前 architecture basis 又增加了相反要求。v11 同时宣称“all hash references form an acyclic DAG”，两者不能同时成立。没有 schema 规定 “reverse bind” 只是 non-hash family consistency check，因此 implementation 仍需做一个未被批准的物料设计选择。

**Direction：** 固定唯一可计算顺序：

```text
Plan (no QRC reference)
  -> frozen QRC (exact plan SHA + policy SHA)
  -> AuthorityRegistryRoot/Registry (exact QRC SHA + Plan SHA)
  -> Authority/Grant/Activation/Profile
```

Plan 只能包含 family/contract semantic constraints，而不能包含 QRC digest。所谓“reverse validation”必须改写为 supervisor 验证 `QRC.plan_sha == sha256(plan)`、`Plan.family_id == QRC.family_id` 和 Registry 同时精确引用二者；它不得是 Plan 对 QRC 的第二个 hash edge。closed-schema / activation tests 必须拒绝 cycle、placeholder/self-hash、mutable selector、old QRC + new plan、new QRC + old plan 和同 ID 不同 bytes。

**Required evidence：** 用真实 canonical serialization 测试证明该 DAG 可被一次冻结/加载；所有上述错配在 profile 创建、journal、claim、fit、staging 和 terminal-index 之前失败。

### [P1] v8 与 v11 对 claim 与 fresh-exec 的先后/创建者相互矛盾，at-most-once fit 的唯一线性化点仍不是可实现合同

**Section：** v8 §5.2，第 143–147 行；architecture v11 §3.2，第 83–85 行。

**Scenario：** v8 规定 supervisor 先启动 `close_fds=True` 的 fresh direct-exec runner，随后 **child** 用 `O_CREAT|O_EXCL` 创建 `DispatchClaim`，最后请求一次性 permit。v11 则写成 runner 在 supervisor event lock 中创建 claim，**随后 supervisor** fresh-exec 一个 single worker。后者在只有一个 `research-runner` 的模型下顺序不可执行：尚未 exec 的 worker 不可能创建其 ProcessIdentity 绑定的 claim；若为此引入一个先存活的 runner/launcher 来创建 claim，就重新引入 pre-fork/继承/错误进程身份面。

此外，profile 的 `CLOSED`/generation 切换只在 admission 规则中被描述；permit-consume 事务没有明确再次在同一 authority/profile event lock 下验证 activation 仍为 `ACTIVE`。一个已 admission、但在发送 permit 请求前被正常关闭/替换的 activation，可能依照某种实现仍消耗 permit 并开始旧计划的 fit。

**Impact：** 这不是文档措辞问题：实现者必须在“先有 claim 再 exec”与“先 exec 再有 child claim”之间选择一个未批准的流程。错误选择可造成 stale worker 获得 permit、profile 已关闭后仍启动 fit，或让一个 pre-existing process 拥有一次性 claim，从而导致错误预算/事件计划下的实际模型调用。

**Evidence：** v8 第 143 行给出了 child-after-exec 语义；v11 第 83 行给出相反的 runner-before-exec 语义。两者都声称是唯一 canonical contract，且都没有把 `CLOSED` 与 dispatch permit 的线性化要求写入 permit transaction。

**Direction：** 选择并只保留以下一条状态机：

1. supervisor 在 authority/profile event lock 下写 `START_RETAINED`、snapshot、descriptor 和一个 **non-executing expected-worker reservation**；
2. supervisor 以 sealed FDs、`close_fds=True`、fixed exec binding 启动新的 direct-exec worker；
3. post-exec child 获取 `ProcessIdentity`，创建 immutable O_EXCL claim；
4. child 请求 permit；supervisor 在**同一事务**重读 active profile generation、reservation、claim、peer PID/start/nonce 和 logical head，原子写 `DISPATCHED` + `FIT_STARTED` + consumed permit；
5. 仅成功回应的这个 ProcessIdentity 可跨过一次 fit boundary。

`CLOSED` 必须与第 4 步用同一 lock 线性化：关闭前要么没有待 dispatch event，要么把每个未 dispatch descriptor 标成 terminal abandoned；关闭后任何 permit 必须失败。不要让 child 在 exec 前持有/创建 claim；不要用一个普通 launch helper 代替 direct-exec worker。

**Required evidence：** fresh-exec order、claim-before/after-exec、profile-close-vs-permit race、supervisor restart at each write boundary、pre-fork pool、PID reuse、fork after permit reply 和 duplicate socket request 都必须证明同一 retained event 至多一次 `model.fit()`，关闭后的 activation 没有新的 `FIT_STARTED`。

### [P1] M7 authoritative runner 只有“executable/config digest”自述，没有 replay 同等级的 executed-bytes/import/runtime closure；普通 path/env 误选仍能生成 official 模型结果

**Section：** v8 §5.2，第 141–145 行；architecture v11 §3.2，第 74–85 行；对照 v8 §6.2/architecture v11 §4.2 的 FD-exec bootstrap 规则。

**Scenario：** supervisor 已从正确 activation 创建 descriptor，但通过普通 executable path 或 Python module invocation 启动 `research-runner`。`RunnerLaunchBinding v1` 只列 “frozen executable/config digest” 和 snapshot FD identity；两份 canonical 文档没有规定 supervisor 以已打开且已 hash 的 executable/interpreter FD 直接 exec、如何清理 M7 runner 的 `PYTHONPATH`/cwd/site/import state、如何将实际 module/native closure 与 launch binding 比对，或让 permit/publisher 验证 observed runner closure。

一个普通 venv、工作目录、module search path 或部署 rotation 误配可运行旧但 ABI/receipt-compatible runner。它仍可用正确 descriptor/snapshot 请求 permit，写一份字段齐全的 `PreparedResultReceipt`，并被 publisher 依据 descriptor/claim/state/inventory 接受；publisher 无法从现有合同辨认“生成 output 的运行代码”不是 frozen launch binding 所指版本。此情景不需要 runner 恶意修改、raw syscall 或 host/control-root compromise。

**Impact：** 错误 runner 可能以错误预处理、模型配置、state 使用或 checkpoint semantics 生成 official M7 score/result；若旧 runner 仍暴露 legacy Gate，甚至可重新触及本轮要封闭的 input path。此路径违反 frozen threat model 对“authoritative runner 只运行冻结、代码审查入口”和普通路径/环境误选的承诺。

**Evidence：** replay §6 明确要求 staged interpreter FD + `execveat`/`fexecve`、`env -i`、pre-import bootstrap、closure manifest、import/native observation 与 execution receipt；M7 §5 仅提 `close_fds=True`、`frozen executable/config digest` 和 ProcessIdentity。`PreparedResultReceipt` / `TerminalPublishedReceipt` 也没有 actual runner executable/interpreter/module-closure digest 字段，因此 publisher/reolver 的全部 receipt equality 不能弥补 launch-time swap。

**Direction：** 为 authoritative M7 runner 定义比例化 `RunnerExecutionClosure v1`：至少包括 exact executable/interpreter/entrypoint/config bytes、fixed argv/env/cwd、allowed module origins and runtime ABI，或复用一个受控 staged runtime profile。Supervisor 必须从 verified FD/immutable stage 启动它（不能“hash path 后再按 path exec”），在 runner 在读取 snapshot/请求 permit 前执行一个 stdlib bootstrap/import-origin check。`FitDispatchPermit`、`DispatchReceipt`、Prepared/Terminal receipts 应绑定 observed executable/runtime/closure digest；publisher 只接受与 descriptor binding 精确相等的观察值。若该环境无法提供 required FD-exec/import invariants，则 M7 authority fit 应 fail closed，而不是降级为普通 Python path launch。

**Required evidence：** executable/venv/module-tree swap after measure、wrong `PYTHONPATH`/cwd/sitecustomize、stale compatible runner、wrong config byte, missing runner bootstrap、observed-closure mismatch 和 correct descriptor + wrong runner must all fail before fit or, at latest, before terminal publication.

### [P1] 四个“Unix identity”未被 policy 规定为可验证的非别名 UID/GID/ACL 矩阵；runner 与 publisher 的普通部署误配可绕开 terminal-only 物理边界

**Section：** v8 common control-root contract，第 98–108、128 行；architecture v11 §2，第 30–40 行与 §3.3，第 89–95 行；threat model 第 11、17、19、38 行。

**Scenario：** 由于 systemd/launchd/service 配置错误，`research-runner` 和 `result-publisher` 使用同一 Unix UID/GID，或 terminal/final/index directory 对 runner 的共享 group 仍可写。当前设计将 “actor identities”写入 profile/receipt，并要求 type/owner/mode/nlink checks，但没有定义 `M7ControlPlanePolicy` 中每个 actor 的 exact UID/GID/SELinux-or-equivalent label、pairwise non-alias rule、directory/file ACL matrix、Unix-domain socket peer allowlist，或 activation-time preflight。于是所有 object owner/mode checks 都可能与错误的、同一 UID 的 profile 一致。

在这种普通服务账户配置错误下，runner 或一个同 UID 的研究脚本可直接创建/替换 final/index object；它不需要攻破 control root，也不是 hostile native-code injection。`OfficialResultResolver` 只信 terminal index，而 index 的 OS writer boundary已经失效，staging/checkpoint/未终态 output 可以被伪装为 terminal published。

**Impact：** 这是 frozen threat model 明确要求防止的“任意研究脚本直接把 staging、checkpoint 或未终态预测当作 official result”的普通配置版本；单靠 receipt hash 和 publisher 类名不能恢复物理写权限分离。

**Evidence：** v11 第 39 行以结论式语言称 runner “不能写” final/index；v8/v11 没有任何 uid/gid/ACL schema、socket access rule 或 non-alias validation。只有 replay supervisor/runner/publisher 的逻辑角色和 opaque “actor identities”，不足以使错误部署 fail closed。

**Direction：** 将 `M7ControlPlanePolicy v1` 扩展为不可变 identity/ACL contract：四个 actor 的 distinct non-root UID/GID（或明确 label/capability）、control/admission/dispatch/claim/staging/prepared/final/terminal directory ownership+mode+ACL、socket path owner/mode/peer credential allowlist、禁止 shared writable group 和 activation-time `fstat`/ACL verification。Profile 绑定该 policy digest 和 resolved identities；任何 actor alias、group write、wrong socket ownership 或 runner final/index write bit 都在 activation 前拒绝。不要把 Unix identity isolation 解释为 hostile-host security；它是本 threat model 所依赖的正常配置前提。

**Required evidence：** runner=publisher UID、shared writable group、wrong socket owner/peer UID、runner writable final/index、publisher writable authority/admission/dispatch 和 ACL change after activation 都必须阻止 activation/permit/publish，且无法解析 official result。

## 结论与保留项

没有发现 P0。v8/v11 相比 v7 的实质进步应保留：

- M6 archive input inventory、staged runtime tree、bootstrap-before-verifier、CUDA/native map observation与三方 receipt agreement 已针对普通 runtime/import 漂移给出完整方向；
- profile-only authority resolution、sealed descriptor、permit、prepared receipt、no-replace final root 和 resolver logical lookup 是正确的收敛方式；
- synthetic-only、M7/replay/OOS 封印、6/44 genesis 和 PIT/state evidence chain 不应因本轮修复而改变。

但上述 4 个 P1 是 canonical contract 的可计算性/线性化/物理权限/实际执行身份缺口。它们不是要求防御被攻破的 host，而是在受信 host 上避免普通配置或生命周期错误把错误预算、错误模型执行或非终态输出变成权威证据。

## Verdict

`NEEDS_CHANGES`：**0 个 P0、4 个 P1、0 个 P2、0 个 P3**。最早修复阶段为 `architecture`，随后必须产生新的 canonical architecture/change design 并重新接受独立设计审查。在此之前不得进入 test-design、实现、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或最终 OOS。

## 审查限制

- 仅读取 canonical v8/v11、冻结 threat model、工程质量 ledger 路由和现有 source/evidence 边界；未把设计文本当作已实现行为。
- 质量 ledger 读取时 revision 为 `67`，router 选择 `design-review`；本报告不修改 ledger。记录前主流程须重新调用 `quality_ledger.py next` 并使用当时 revision/source digest。
- 本审查没有执行任何 PIT `CERTIFY`，不产生 PIT/data `PASS`、M7 允许、Alpha 或生产结论。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 67,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "V8_V11_LEAVE_AUTHORITY_GRAPH_DISPATCH_EXECUTION_CLOSURE_AND_IDENTITY_BOUNDARIES_UNRESOLVED",
  "summary": "Canonical v8/v11 substantially strengthen replay closure and terminal publication, but still contain a Plan↔QRC binding contradiction, incompatible claim/fresh-exec sequencing, no executed-bytes/import closure for the authoritative M7 runner, and no explicit non-alias Unix identity/ACL policy. Ordinary configuration or lifecycle errors can therefore authorize the wrong budget, execute a stale runner, or publish non-terminal output.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 4, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v8.md",
    "sha256": "sha256:c903ec58a789607cc1f7202f8279a4c1d0d58ac786157afd1116a34666b643cf"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v11.md",
    "sha256": "sha256:c3766c6aa50da57d0c0866d4f5542d1e227283da6a4abe5d2a15c2b67736d5f3"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next (route inspection only)"
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
    "Repair architecture and canonical design, then obtain a fresh independent design review before test-design.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
