# M6.5 R3 修复设计独立审查 v2

状态：`NEEDS_CHANGES`  
审查性质：独立、只读的设计审查；未修改产品代码、测试、契约、gate 或历史 ledger，未执行训练、服务器 replay 或最终 OOS 访问。  
审查对象：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v2.md`，SHA-256 `0550c0330add31ea9327f0d99a43832d14b295bae9d03f9bc8d274d4b7581d7a`；配套架构确认 `architecture_confirmation_v4.md`，SHA-256 `3cf28947ab7eff5b1c9e94d6caf571203a572daafb5855fcd72ff754ab8556fa`。  
审查者上下文：`/root/m6_5_design_review_v2`。  
审查模式：PIT `VERIFY`（设计/证据链核验，不产生 PIT 认证或 M7 放行）。

## 结论

v2 正确吸收了 v1/fast 否决中的四个结构性方向：以新的 `6/44` genesis 取代服务器 legacy
`4/29` 起点、在选择前保存 state audit、把 journal 语义收进 event plan、以及在 replay 前声明
archive/tree/verifier binding。尤其是「复制 M6 close prefix 到新 authority namespace、绝不改写 M6
历史」的方向是正确的。

不过，当前设计仍不能作为 `IMPLEMENTATION_READY` 的 M6.5 R3 放行依据：存在 **2 个 P0、2 个
P1、1 个 P2**。其中 P0 同时涉及 M3 future-conditioned state 的实际消费入口，以及把 PIT
`VERIFY` 错当成可正向放行的证据。P1 分别保留了可自制 `RunAuthority` 的预算/计划替换面，和
replay verifier 的自证明启动面。因此 M6.5 继续 `NEEDS_CHANGES`，M7 derived contract freeze、真实
fit 和最终 OOS 均不得推进。

## 已核对的边界与证据

| 主题 | 已直接核对的事实 | 审查判断 |
| --- | --- | --- |
| M6 历史与 genesis | `M6_peerlite_gate.json` 是 `PASS`；本地 `contracts/trial_ledger.jsonl` 为 51 行、14,328 bytes、SHA `31a90d…2de93`、累计 `6/44`；M6 预算起点仍为 `8d08…f133`、`4/29`。server replay v2 receipt 也记录其服务器 ledger 是 `8d08…`。 | v2 §2.1 的「新 authority ledger + copy of verified close prefix」能正确避免改写 M6 历史，也不会把 server legacy 文件误当 M7 预算基线。 |
| state data plane | v2 §2.2/v4 B 引入 build binding、选择前 audit、外部 consumer binding。当前 `market_state.py` 仍只是 DataFrame primitive；它不能自行证明上游行未被未来条件筛过。 | 新 builder/audit/loader 方向必要，但还没有封住现有 Gate 消费入口，且其 PIT 正向条件不符合项目 PIT 协议。 |
| RunAuthority | v2 event plan 冻结 type/count/evaluation/fit/model/fold/seed/purpose，且取消 CLI `--expected-head-*` / `--limit-*`。 | 内部一致性检查足以阻止旧 H0/H1/slot-swap 形式；但没有定义谁在外部授权某一份 authority/budget/plan。 |
| archive replay | v2 同时声明 transfer manifest、archive、internal manifest、tree digest、historical evidence、verifier 和 profile。 | 输入声明覆盖面正确；但 verifier 自验 SHA 不能证明实际启动的 verifier 字节，需要独立可信启动与部署证明。 |

当前 M6.5 gate 本身仍是 `NEEDS_CHANGES`，明确禁止 M7 derived contract、真实 M7 fit、CCC+Gate 和
2025+ OOS（`evidence/gates/M6_5_pre_m7_quality_gate.json:3-10,71-78`）。本报告不改变 M6 历史
`PASS`，也不把设计、已有测试或历史 receipt 升级为新的实现/数据 `PASS`。

## Findings

### [P0] 旧 Gate 公共入口仍可绕过 StateBuild/StateArtifactBinding，直接读取含未来标签的 M3 `market`

**位置：** v2 §2.2 仅规定未来 consumer API 为
`load_verified_market_state_artifact(artifact_dir, binding)`（第 109–119 行），但没有指定 legacy
`PeerLiteModel`/Qlib Dataset/CLI 的强制迁移或拒绝规则。当前
`src/qlib_peerlite/models/peerlite.py:263-269` 在 `market_gate=True` 时无条件调用
`dataset.prepare(segment, col_set="market")`；而
`src/qlib_peerlite/data/qlib_dataset.py:15-25,166-202` 定义并加载的 M3 `MARKET_COLUMNS` 含
`label_open` 与 `label_close`。M6 只因 immutable spec 明确 `market_gate=false` 才未走此路径
（`src/qlib_peerlite/governance/m6_spec.py:193-205,221-230`）。

**精确触发：** 在 M7 runner 之外直接构造
`PeerLiteModel(..., market_gate=True)`，对 `build_qlib_fold()` 产生的 M3 Dataset 调用 `fit()`；或者通过
配置把 `market_gate: true` 传给现有 CLI/model builder。模型不会调用新的 state builder、state audit 或
binding loader，且会把 M3 的旧 `market` 组送入 Gate。

**影响：** 即便新 artifact 自身完美，仍存在另一条真实的 public consumer path，能够把
`label_open/label_close` 及由 M3 label/execution/purge 条件决定的横截面直接用于 Gate。这使
v2 §3 所称「M3 manifest/path/projected DataFrame 不能满足 consumer binding」在实际模型入口上不成立，
重新打开本质量变更要关闭的 P0 future-conditioned 路径。

**修复方向：**

1. 在 v2 中把 legacy `market` 明确定义为 **M6 历史只读组**；`PeerLiteModel`、配置和任何通用 CLI
   必须在 `market_gate=True` 时 fail-closed，不能回退到 `col_set="market"`。
2. 定义 M7 Gate 的唯一公共入口：它只能接收由
   `load_verified_market_state_artifact(..., StateArtifactBinding)` 重新校验后产生的受限 state handle
   （或等效 capability），并强制固定 4D schema/order、同日常量性和 artifact/binding identity。
   `m7_peerlite.py`/wrapper 不能只是推荐路径。
3. 增加 public-boundary tests：直接 `PeerLiteModel(market_gate=True)`、旧 M3 Dataset、伪造
   `market_state` col_set、手工构造 DataFrame、以及缺/错 binding 都必须在训练前失败且不写 ledger；
   只有绑定的 state handle 才可到达 Gate。

### [P0] `VERIFY` 被写成可放行条件，且 StateArtifactBinding 漏绑派生特征的 fixed+behavior 双证据

**位置：** v2 §1/§6 将真实数据路径留给 PIT `VERIFY`（第 24–25、229–235 行），并在 §2.2 规定
「bound passing VERIFY package」可把 artifact 交给 M7 Dataset（第 109–119 行）；v4 B 也将
「passing PIT verification package」作为 Dataset enable 条件（第 64–70 行）。它只列一个
`PIT VERIFY package/manifest SHA`，未列独立 behavior manifest。相反，仍有效的 M7 design v2
明确要求 real M7 fit 前同时有 fixed audit、future label/execution/future action behavior audit 和 join
audit（`m7_change_design_v2.md:65-73`）。

**精确触发：** 对新的 state population 只运行样本/诊断性 `VERIFY`，或把若干局部检查均为真误标为
“passing”；随后把该 package SHA 写入 `StateArtifactBinding`。四个 state source
`ret_mean_20`、`ret_std_20`、`ret_1d`、`turnover_mean_20` 是派生路径，资格 flags/causal-feature
实现也可能对 future raw revision、future action 或间接 label 条件敏感；仅 audit parquet 的 flags、
code hash 和一个 self-consistent package 无法形成正向证明。

**影响：** 项目 PIT 协议中，`VERIFY` 的正向上限是“支持下一决策/`NEEDS_EVIDENCE`”，不能产生
`PASS` 或 `QUALIFIED`；只有 `CERTIFY` 的完整训练输入、外部 trust anchors 与 17 个 fixed checks 才能
形成可复用的 PIT `PASS`。派生特征还必须保留与该 fixed audit parent 精确相连的 behavior manifest；
behavior `PASS` 也只是补充性的 `NOVEL_CANDIDATE` 负证据，不能被折叠为 fixed audit。若继续把
`VERIFY` 当 enable 条件，M3 future-conditioned 来源没有被真正关闭，只是被换成了不具认证资格的
artifact 名称。

**修复方向：**

1. 将 `StateBuildBinding` 明确限定为 construction-only；任何 `VERIFY` 输出、合成 fixture 或
   `BUILT_NOT_PIT_QUALIFIED` artifact 永远不能开启 Dataset。
2. 将 `StateArtifactBinding` 的正向条件改为精确的 production `CERTIFY` fixed-audit identity：绑定
   audit manifest/report SHA、`status: PASS`、`pit_qualification: QUALIFIED`、
   `FULL_TRAINING_INPUT`、`quant_contract_v2`、runtime trust-anchor match，以及 state audit/manifest 的
   完整 parent links。缺任一项必须 fail-closed，而非把 `VERIFY` 解释为通过。
3. 单列并绑定 behavior request/manifest/report：其 parent 必须是上述 exact fixed audit，且必须对
   future label、execution eligibility、future action、revision 与 universe canary 做实际 raw-snapshot
   对照；保护面至少覆盖所有 `state_input_audit` selection outcome、population key/count 和
   `daily_state` digest 在 cutoff 及以前的值。该 receipt 保持 `NOVEL_CANDIDATE` 的边界，不升级
   fixed PIT claim。
4. 明确 M7 wrapper 还须完成 v2 M7 design 已要求的 join audit；没有这些 immutable links 时不能
   由任何 loader/capability 产生可训练 Dataset。

### [P1] RunAuthority 取消自由 CLI 参数，但其自身尚无外部授权注册信任根

**位置：** v2 §2.3（第 125–161 行）和 v4 C（第 80–98 行）。二者要求 authority 内含 genesis/head、
budget/spec、journal/output 和完整 event plan，且 receipt chain 从 previous receipt 续接；但都没有
定义一个位于 `RunAuthority` 之外、由 server 强制读取的 registry/grant，来固定某个 authority SHA、
允许的 budget artifact、计划和命名空间。

**精确触发：** 调用方生成一份语法和 canonical hash 都正确的新 `RunAuthority`，复制可信 genesis
ID/SHA 与当前允许的 head，但替换其 immutable-budget binding/fixed limits 或 EventPlan，再通过
`--run-authority` 和 authority root 提交。设计所列的 head、receipt、event-payload 对比都可在这份新
对象内部自洽；没有指定外部 registry 就无法区分“治理预先批准的 authority”和“调用方新写的
authority”。

**影响：** `--limit-*` 与 `--expected-head-*` 虽被删除，权威输入却从散落 flags 移到了可替换的
authority 文件。这样仍可能扩张可用预算、替换模型/fold/seed/purpose plan，或改变 journal/output
绑定，而 receipt chain 只能证明该替代物的内部连续性，不能证明其得到授权。

**修复方向：** 在实现前增加 request-external `RunAuthorityRegistry`/grant（或由 genesis policy
直接维护的 allowlist）：

1. registry 应固定 authority ID/content SHA、authority-ledger ID/genesis SHA、唯一 parent receipt
   或 initial head、execution-spec hash、不可变预算 artifact 的 path/SHA/content hash 与最大 counts、
   journal/output logical paths 和 event-plan SHA；其自身由受控 server authority root/hash pin。
2. server CLI 仅按受控 root 中的 authority ID 解析，重新计算 authority 与 registry/budget artifact
   的 bytes/hash；绝不能把 caller 提供的自述 path/hash 当授权。path grammar、root containment、
   symlink policy 与 authority-id uniqueness 都须闭合。
3. 追加 forged-valid-authority、registry substitution、budget/plan mutation、authority path traversal 和
   pre/post-head mismatch tests；每个拒绝场景都要求 ledger 零字节变化。

### [P1] replay input binding 是正确的声明，但 verifier 自验自身 SHA 不是可信启动/部署证明

**位置：** v2 §2.4（第 165–186 行）和 v4 D（第 102–111 行）。设计要求 verifier 比较自身 SHA、
archive 与 binding，再把 digest 写入 receipt；`m6_archive` 再比较 receipt 与 frozen binding。这里没有
定义在 verifier **之外**、在 exec 前重新哈希并实际启动冻结 verifier bytes 的 trusted launcher，
也没有定义独立的 deployment/launch receipt。

**精确触发：** 在 binding 冻结后替换 server 上的 verifier。替代脚本可以跳过自己的 SHA 比较，使用
不同 archive/tree，或在 receipt 中回填 binding 内预期的 verifier/archive digest。若
`m6_archive` 只消费该 receipt fields，它不能从 self-report 判定“实际执行的文件”是否等于绑定的
verifier。类似 TOCTOU 也可发生在 hash 后、exec 前的 verifier/archive 替换。

**影响：** archive/tree 的输入声明和 receipt 内部一致性不足以证明 14-fold replay 由已批准的
verifier 和 archive 产生，仍落入 fast review 明确拒绝的 receipt-only 信任模型。它不会篡改 M6
历史 gate，但不能作为 M6.5 的独立 server replay 放行证据。

**修复方向：**

1. 增设并 pin 一个不属于 replay verifier 的 trusted launcher/acceptance tool。它从受控 binding
   root 读取 binding，在 exec 前验证 binding bytes、verifier bytes、archive bytes、single root、
   internal manifest 和 tree inventory；将已验证 verifier 复制/打开为不可替换的临时执行对象后再启动，
   以消除 hash→exec TOCTOU。
2. launcher 产出 canonical launch receipt，记录 launcher identity/hash、binding SHA、实际执行
   verifier SHA、archive/tree digests、sanitized argv/environment、output identity 和 pre/post
   read-only ledger hash。`m6_archive` 必须重新验证此 receipt（或独立重算其指向的受控文件），不能
   只信 verifier 的 JSON 字段。
3. 将 verifier/archive/tree post-bind mutation、fake self-report receipt、hash-to-exec swap、wrong
   launcher、pre-import module decoy 和 deployment-root substitution 写入 mutation/E2E matrix；任何一种
   均不得产生 acceptance receipt。

### [P2] genesis 的 archive-proof 与 server target 约束尚未成为可执行、可定位的完整 schema

**位置：** v2 genesis 示例只有
`m6_evidence: {gate_sha256, archive_proof_sha256}`（第 41–51 行），installer 却被要求验证
“M6 gate/archive verifier bindings”（第 54–62 行）。v4 A 同样只写 archive-verifier evidence hash
（第 44–56 行）。当前 server replay receipt v2 不能直接填补该位置：它记录的 server ledger 是
`8d08…` 而不是 M6 close `31a90…`。

**精确触发：** 实现 installer 时仅凭一个 `archive_proof_sha256` 无法确定应读取哪个 artifact、
其 schema/claim 是什么、它如何绑定 close snapshot 的 bytes/counts、以及 verifier identity。若实现者
改由调用者额外提供 proof path，便重新引入非 canonically pinned input；若只比 M6 gate hash，则
`archive_proof_sha256` 变成无法验证的装饰字段。

**影响：** v2 的核心 6/44 方向仍可由 gate snapshot hash 支撑而 fail-closed，但 genesis 不是完整的
implementation contract：不同实现可对 archive proof 作出不同解释，或无法重跑同一 install decision。

**修复方向：** 固定一个版本化、可定位的 `M6CloseArchiveProof`，至少含 relative path、file SHA、
schema/version、M6 gate SHA、verified close ledger SHA/bytes/6/44、被批准 verifier blob identity 与
proof content hash；genesis 必须绑定该对象的全部 identity。installer 只从 controlled root 解析经
canonical path/symlink checks 的 proof，并同时验证它与 close snapshot、M6 gate 的对应关系。测试应
拒绝 v2 server receipt、错误 schema/path、重算自哈希的错误 proof 和 `authority_relpath` 的 traversal/
link escape，且历史 M6 文件保持完全未写。

## 通过条件与最小返回路径

本设计不能以补充测试替代上述缺失的信任边界。最小返回路径是先修订 current canonical design：

1. 加入 legacy Gate 的不可绕过 consumer migration/deny rule；
2. 把 state positive gate 改为 `CERTIFY` fixed audit + 独立 behavior bundle + join audit，而非
   “passing VERIFY”；
3. 为 RunAuthority 增加外部 registry/grant；
4. 为 replay 增加 trusted launch/deployment attestation；
5. 令 genesis archive proof 和 target path policy 成为闭合 schema。

之后再按修订版先写 P0/P1 mutation tests、synthetic CLI E2E、coverage receipt 和 fresh server replay，
再进行新的独立 design/code/test review。M6.5 gate 仍拥有阶段转移权；本审查不授权直接修改 ledger、
冻结 M7 contract、训练或 OOS 访问。

## 审查限制

- 当前工作树有未提交的 M6.5 文件；本报告固定的是上方列出的文件 SHA，而不是声称某个 Git commit
  已通过。
- 未运行测试或 server 命令；本结论基于只读的设计、M6/M6.5 gate/ledger/receipt 和当前源码交叉核对。
- `LedgerAuthorityGenesis` 的“新 namespace、原子安装、不改历史”设计方向被确认；本报告所列 P2
  是其 proof schema/implementation determinism 缺口，而非要求重写 M6 历史。

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "stage_id": "design-review-v2",
  "skill": "independent-design-review",
  "mode": "read-only-verify",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "LEGACY_GATE_BYPASS_PIT_CERTIFICATION_AUTHORITY_REGISTRY_AND_TRUSTED_REPLAY_LAUNCH_MISSING",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 2, "P1": 2, "P2": 1, "P3": 0},
  "subject": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v2.md",
    "sha256": "0550c0330add31ea9327f0d99a43832d14b295bae9d03f9bc8d274d4b7581d7a"
  },
  "architecture": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v4.md",
    "sha256": "3cf28947ab7eff5b1c9e94d6caf571203a572daafb5855fcd72ff754ab8556fa"
  },
  "evidence_paths": [
    "docs/MASTER_PLAN.md",
    "docs/STATUS.md",
    "evidence/gates/M6_peerlite_gate.json",
    "evidence/gates/M6_5_pre_m7_quality_gate.json",
    "contracts/immutable/m6_trial_budget_start.json",
    "contracts/trial_ledger.jsonl",
    "evidence/m6_5_pre_m7/m6_archival_replay_server_receipt_v2.json",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v1.md",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_fast.md",
    "src/qlib_peerlite/data/market_state.py",
    "src/qlib_peerlite/data/qlib_dataset.py",
    "src/qlib_peerlite/models/peerlite.py",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "src/qlib_peerlite/governance/m6_archive.py",
    "scripts/server/verify_m6_peerlite_archival_replay.py"
  ],
  "commands": ["read-only rg/find/nl/jq/shasum/git-status"],
  "independence": {
    "reviewer_context_id": "/root/m6_5_design_review_v2",
    "author_context_id": "/root",
    "limitations": [
      "No product/test/contract/gate/ledger mutation except this independent review artifact.",
      "No M7 training, server replay, budget consumption, or final-OOS access."
    ]
  }
}
```
