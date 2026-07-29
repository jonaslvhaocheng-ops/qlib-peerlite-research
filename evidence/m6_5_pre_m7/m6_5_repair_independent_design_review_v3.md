# M6.5 R3 修复设计独立审查 v3

状态：`NEEDS_CHANGES`  
审查性质：独立、只读的 R3 设计审查；未修改产品代码、测试、契约、gate 或历史 ledger，未运行训练、服务器 replay，也未访问最终 OOS。  
审查对象：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v3.md`，SHA-256 `9ac6394aa68deee9a0572e081bdfd500b9de5b4ddfd778bd31222e1efc564ad6`；架构依据 `architecture_confirmation_v5.md`，SHA-256 `60f9352e394cd413e628ddcc02455e6112738281a25a04f4cddce62bd837bec0`，以及 `architecture_confirmation_v6.md`，SHA-256 `6ed8486527e49e25fc32cfaca1fcf88c8dc4978cbdcc76439f112137e08b7a68`。

PIT 导航模式：`VERIFY`，仅检查未来 `StateArtifactBinding` 的证据合同是否符合生产 `CERTIFY` 的消费边界；本报告不对任何数据路径给出 PIT 认证或正向数据结论。

## Findings

### [P1] `StateArtifactBinding` 没有把“CERTIFY + behavior + join”收敛为可执行的生产证据合同

**位置：** v3 §4.2，尤其第 110–122 行；v5 §4.2，第 105–117 行。

**场景：** 未来的 runner/loader 按当前文字只检查一个名为 `PITFixedCertificate` 的 canonical JSON，确认其中自述 `mode=CERTIFY`、`status=PASS`、`QUALIFIED`、`FULL_TRAINING_INPUT` 和若干 hash；再接受一个“有 fixed parent”的 behavior JSON。v3 没有要求这两个对象必须是 PIT executor 实际产出的严格 schema，也没有要求 loader 验证完整 manifest/report 与生产运行边界。于是一个自洽但非生产 audit 输出的对象可以满足列出的字段和 parent link，并为 state capability 放行。

**影响：** 这不是术语细节。PIT 的正向 handoff 需要实际 `pit_audit_manifest_v1` 的完整生产断言，而非一组同名字段：`status=PASS`、`pit_qualification=QUALIFIED`、`evidence_ceiling=PASS`、`coverage_matrix.scope=FULL_TRAINING_INPUT`、`contract_binding.adapter=quant_contract_v2`、`execution_boundary=PRODUCTION_CLI`、`test_only_adapter=false`、目标 claim、17 个 fixed checks 均为 `PASS`，以及 request 外部 runtime trust anchors。派生路径还必须消费实际 behavior manifest，锁定 exact parent audit、B001–B004、保护 key/value digest 和 baseline/probe raw、code/query、parameters、environment、outputs、perturbation ledger 的 lineage。缺这些强制解析/重算规则，原先要关闭的“自述 artifact 看似已认证”入口重新出现，真实 Gate 输入的 PIT 证据无法被证明。

**证据：** 当前合格 M3 audit 的实际字段可见于 `evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json`；其 production adapter、证据上限、运行边界、17 项检查和 runtime trust 在 v3 的 `PITFixedCertificate` 最小字段表中均未被定义为 loader 必验项。行为审计的实际 schema/lineage 在 `evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json`，其中 B001–B004 与 exact parent audit 也尚未成为 v3 的严格消费合同。PIT skill 的 `audit_spec.md` 和 `behavior_spec.md` 明确要求它们作为两个不可相互替代的 manifest/report 对。

**方向：** 定义 closed-schema 的 `PITFixedCertificateRef v1` 与 `StateBehaviorEvidenceRef v1`，前者必须以 exact `pit_audit_manifest_v1` 和报告字节/hash 为根，严格验证上述生产字段、17 项 check ID/status、claim、input lineage 和 matched external anchors；后者必须以 exact parent manifest content/audit ID 为根，严格验证 `pit_behavior_manifest_v1`、`NOVEL_CANDIDATE` 边界、B001–B004、保护集及所有双 replay lineage。`StateJoinEvidence` 还应固定已验证 supervised fold 的 product/fold/segment/key/date digest，不能只用“exact Dataset”文字描述。只有这三类实际 receipt 的固定对象都被重新解析、hash 验证和交叉绑定，loader 才能 mint capability。

### [P1] Registry/grant 缺少无循环的 bootstrap、唯一 snapshot selector 和部署授权链

**位置：** v3 §5.2，第 145–161 行；v6 §2，第 21–34 行。

**场景：** v6 的信任图要求“future FROZEN M7 derived contract → immutable `RunAuthorityRegistrySnapshot` SHA”，但 v3 又要求该 registry 内容绑定 source QRC ID/SHA。若冻结 QRC 内保存 registry snapshot SHA，则 registry 的 canonical content 又包含 QRC SHA，形成不可计算的循环；若不保存 snapshot SHA，公共 CLI 又只得到 `authority_id`，在禁止 `current.json` 的前提下没有定义它如何从多个 content-addressed registry 中选择唯一、受授权的 snapshot。实现者只能引入未说明的可变索引，或允许 caller/control-root 任取一个 registry。

**影响：** 合法 grant 可能根本无法部署；更危险的是，为了让它可运行而取消其中一条绑定后，预算、event plan、parent head 和 output path 又会退回到“可选但自洽”的 registry/grant。这样无法满足 v2 审查要求的 caller 之外的授权根。

**证据：** v3 一方面写明 registry 绑定 QRC ID/SHA（第 154–155 行），另一方面只说明 public command 接 `--authority-id`（第 157–161 行）；v6 明示 QRC 指向 registry snapshot SHA（第 21–26 行），但未给出 snapshot 的 schema、hash exclusion 规则、安装顺序或 authority-id 到 exact snapshot 的 immutable resolver。

**方向：** 先设计单向、无自引用的授权链。例如：先冻结一个不含 QRC hash 的 `M7AuthorizationPlan v1`（预算、event plan、namespace、allowed IDs）；QRC 只绑定该 plan hash。QRC 冻结后，治理端生成 registry/grant，二者绑定 QRC hash + plan hash，并由外部治理 anchor 写入一个不可变 `RegistryDeploymentReceipt`。runner 从其预先固定的 control profile 和 `(QRC hash, plan hash)` 解析唯一 deployment receipt，再取得 registry；不能由 `authority_id` 单独发现 registry。必须固定每个对象的 owner、installer 输入、expected path、原子 activation 和 hash 规则，并以 cycle/alternate-snapshot/mutable-selector 的 synthetic cases 验证 fail-closed。

### [P1] START 的账本幂等不是一次性 fit lease；重复或崩溃后的实际 fit 仍可能不计入预算

**位置：** v3 §2 表中的“registry grant → lease”，以及 §5.2，第 150–169 行；v5 §5.2，第 149–158 行。

**场景：** Event plan 含 `MODEL_FIT_STARTED` 的 source ID `F`。worker 已将 `START(F)` fsync 到 journal，并将其 append 到 ledger；随后在 `model.fit` 已开始或完成后、完成 receipt 尚未持久化前崩溃。重启时，v3 规定“完整 normalised retained payload 相同才幂等”（第 163–165 行），因此 reconcile 成为 no-op。设计没有定义一个原子取得、只可消费一次的 `RunLease`，也没有规定 ledger 导入的 `F` 是否已经被某个 worker 实际执行、崩溃后如何保守终止、或重复 worker 必须在何处被禁止。相同 authority/event 可被第二个 worker 重跑，而只保留一个 ledger start/counter。

**影响：** 真实模型拟合次数可超过 immutable event plan 与预算，而账本仍显示一次；崩溃恢复会把“已经可能执行”的 fit 误当作可安全重试。这直接破坏试验预算、可重复性和最终任何模型选择的审计性。

**证据：** v3 的写入算法只定义 `journal START → ledger batch → receipt`，没有定义 lease identity、状态机、worker ownership、lease expiry/abandon 语义或 `fit` 前的单次消费检查。测试清单覆盖 `double reconcile`、`crash retry` 和 `concurrent import`，但没有覆盖“reconcile 已幂等后再次实际调用 `model.fit`”或“fit 完成前崩溃后 retry 不得二次执行”。目前代码的 `trial_ledger.py` 也正是 event-import accounting，不具备运行 lease 状态；新设计不能依赖未声明的行为。

**方向：** 把 `RunLease v1` 定义为 ledger lock 内签发的、带 authority/event ID、pre/post exact head、worker/attempt nonce、issued/terminal state、计划 payload hash 的不可变 receipt。runner 必须在实际 `fit` 前持有尚未执行的 lease；同一 event 只能有一个 execution attempt。发生任何“已开始但是否完成不明”的崩溃时，事件保持已花费并标记 `ABANDONED/UNKNOWN`，不允许重跑；只有另一条冻结且已计数的 contingency event 才能启动新 fit。至少补充 crash-at-each-boundary、two-worker、same-authority rerun、completed/abandoned lease reuse 和 verifier call-count E2E。

### [P1] Replay 的导出签名和 runtime 仍是声明，尚非本地可验证的信任闭环

**位置：** v3 §6，第 173–193 行；v6 §3，第 48–55 行。

**场景：** `M6ReplayLaunchGrant v1` 仅固定“验收公钥指纹”。收到本地 evidence bundle 的 `m6_archive` 无法由 fingerprint 恢复或认证用来验证 detached Ed25519 signature 的实际公钥；v3 也未定义签名 payload、algorithm/key-id/version、可信 keyring 的不可变来源，或 grant/binding/deployment receipt 如何被该根授权。另一方面，launcher 只将 verifier/archive 用 same-FD hash-and-copy staging；它随后通过 pathname 启动“固定 interpreter”，却没有规定 interpreter binary、venv/site-packages/import closure 的内容树证明或 exec 前同一对象验证。`python -I` 清除环境变量，不会把已变更的 venv 或 site-package 字节变成已认证 runtime。

**影响：** 从治理 root 复制出来的 JSON 即使包含一个“签名”字段，本地仍不能独立判断签名、signer、grant 或 runtime 是否为受批准对象；runtime/path substitution 仍可让不同代码生成看似一致的 child receipt。v2 要关闭的“不是 verifier 自证”的证据问题因此仅被从 verifier 移到了未定义的 launcher/签名层。

**证据：** v3 只写 public-key fingerprint 与“签名 canonical receipt”（第 175–191 行），v6 也只写 fingerprint（第 48–55 行）。二者没有 public-key/keyring artifact、签名 schema 或签名者授权关系。v3 对 same-FD 的保证明确只覆盖 verifier/archive（第 183–185 行），没有覆盖 interpreter/venv/imported module closure；但验收清单要求检出 wrong runtime（第 191–193 行），故这是已声明但未实现的威胁面。

**方向：** 新增由 M6.5 immutable acceptance policy 锚定的 `ReplayAcceptanceTrustRoot v1`：含实际 Ed25519 public key（或版本化 keyring）、key ID、algorithm、validity/rotation policy 和 exact artifact hash。`M6ReplayLaunchGrant` 只能引用该 key ID/version；acceptance receipt 必须签 canonical payload digest，明确覆盖 grant/binding/deployment/child/output/ledger/runtime identities，`m6_archive` 以 pinned trust root 验证而非使用随 receipt 到来的 key。定义 `ReplayRuntimeBundle v1`，以 interpreter binary、venv/wheel/site-package tree inventory 或等价的受签名 OCI image digest 固定 runtime；launcher 必须在启动时重新验证实际 import closure（或将 runtime 一并受控 staging/immutable execution），并把结果纳入被独立 signer 验收的 receipt。补充 wrong-key、wrong-payload、key rotation、altered interpreter/site-package、runtime hash-to-exec 和“已签但 child linkage 不同”的 E2E。

### [P2] 旧公开 `PeerLiteNetwork` 的 raw-tensor Gate 合同未明确迁移，direct-injection 拒绝难以验收

**位置：** v3 §3.1，第 47–51 行和 §3.3，第 72–79 行。

**场景：** 当前 `src/qlib_peerlite/models/peerlite.py` 的 `PeerLiteNetwork` 仍公开接收 `market_gate` / `market_dim` 与 `market_state` tensor；`src/qlib_peerlite/models/__init__.py` 和顶层 `src/qlib_peerlite/__init__.py` 都导出它。实现者若只按 v3 禁止 `PeerLiteModel`、config、factory 与 CLI，却保留此顶层 public API，即可直接构造 Gate network 并送入从 M3 `market` 转出的 tensor。v3 写了“direct network injection”应拒绝，但没有规定这个现有 public signature、顶层 re-export 和依赖脚本如何改变。

**影响：** 受控 M7 runner 可能安全，但设计所声称的“direct network injection 在任何 fit/journal 前拒绝”没有可唯一实现的公开兼容合同，容易让遗留 raw-tensor Gate 长期残留或测试只覆盖 `PeerLiteModel`。

**证据：** 当前根包与 models 包均导出 `PeerLiteNetwork`，且该类在 `forward(..., market_state=...)` 中直接使用 tensor。v3 只提到 `models.__init__` 不导出 M7 internals，未提及根包 export，并把“不能再从公开 M6 model 接收”限定为 model-to-network 路径。

**方向：** 明确 M6 `PeerLiteNetwork` 的固定 no-gate public signature：移除 `market_gate`、`market_dim` 和 raw `market_state` 参数，并从两个公开 `__all__` 中按兼容策略处理；将 Gate-capable network 移到仅由 M7 runner 组合的独立模块，且其 state 只能由 capability 的私有解包路径提供。把 direct imports、legacy GPU/mechanics scripts、checkpoint deserialize 和 direct `forward` tensor injection 纳入拒绝/兼容测试。

## Verdict

`NEEDS_CHANGES`。v3 明确解决了上一轮 v2 的方向性问题：legacy `PeerLiteModel` fail-closed、construction 与 empirical eligibility 分离、6/44 新 namespace、registry/grant 概念、以及 FD-pinned verifier/archive launcher，均应保留。

但是上述四个 P1 都是实现前的信任/一次性执行闭合问题，不能靠补充单元测试或“受控 root”这一句补足；P2 也需要把现有公开 API 的迁移写成精确合同。最早修复阶段是 `architecture`，随后必须产出新 change design 并进行新的独立 design review。不得进入 test design、实现、server v3 replay、M7 derived contract freeze、真实 M7 fit 或 final OOS。

## 审查限制与已核对项

- 已只读核对 v3/v5/v6、v2 独立审查、当前 `PeerLiteModel`/`PeerLiteNetwork`、`market_state.py`、`trial_ledger.py`、`m6_archive.py`、CLI/config/export surface、现有 PIT fixed/behavior manifests 和工程质量 ledger 路由。
- 未执行测试、服务器命令、训练或 replay；设计审查不以旧测试或静态阅读声称实现通过。
- 审查时质量 ledger 的 `ledger_revision` 为 `22`，且 router 选择 `design-review`。记录本报告前，router 应再次执行 `quality_ledger.py next`，以当时 revision/source digest 写入正式 ledger result。

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 22,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "read-only-independent-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "PIT_EVIDENCE_CONTRACT_AUTHORITY_BOOTSTRAP_SINGLE_USE_LEASE_AND_REPLAY_TRUST_ROOT_INCOMPLETE",
  "summary": "v3 preserves the correct remediation directions but does not yet close the production PIT evidence parser, acyclic external registry deployment, single-execution budget lease, or independently verifiable replay signature/runtime chain.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 4, "P2": 1, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v3.md",
    "sha256": "9ac6394aa68deee9a0572e081bdfd500b9de5b4ddfd778bd31222e1efc564ad6"
  },
  "architecture_evidence": [
    {
      "path": "evidence/m6_5_pre_m7/architecture_confirmation_v5.md",
      "sha256": "60f9352e394cd413e628ddcc02455e6112738281a25a04f4cddce62bd837bec0"
    },
    {
      "path": "evidence/m6_5_pre_m7/architecture_confirmation_v6.md",
      "sha256": "6ed8486527e49e25fc32cfaca1fcf88c8dc4978cbdcc76439f112137e08b7a68"
    }
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v2.md",
    "src/qlib_peerlite/models/peerlite.py",
    "src/qlib_peerlite/models/__init__.py",
    "src/qlib_peerlite/__init__.py",
    "src/qlib_peerlite/governance/trial_ledger.py",
    "evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json",
    "evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json",
    "docs/STATUS.md"
  ],
  "commands": [
    "read-only rg/nl/sed/jq/sha256sum/git status",
    "quality_ledger.py next (read-only route inspection)"
  ],
  "independence": {
    "mode": "distinct_subagent_review",
    "reviewer_context_id": "/root/design_review_v3_lead",
    "author_context_id": "/root",
    "limitations": [
      "No product/test/contract/gate/ledger mutation except this independent review artifact.",
      "No M7 training, server replay, budget consumption, or final-OOS access."
    ]
  },
  "blockers": [
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server v3 replay, and final OOS remain prohibited."
  ]
}
```
