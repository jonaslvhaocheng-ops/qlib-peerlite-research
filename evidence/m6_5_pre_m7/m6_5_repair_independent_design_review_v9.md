# M6.5 canonical v9 / architecture v12 独立设计审查

## Findings

### [P1] 固定 `PYTHONHASHSEED` 的确定性合同与 `python -I -S` / 拒绝 `PYTHON*` 的启动合同不能同时成立

**Section：** `m6_5_repair_change_design_v9.md` §5.3（第 133–137 行）及 §6；`architecture_confirmation_v12.md` §5（第 100–104 行）及 §6（第 110 行）。

**Scenario：** 两份 canonical 文档都把 `PYTHONHASHSEED` 列为必须冻结、记录的确定性环境项，同时规定 `env -i ... python -I -S`，并让 bootstrap 拒绝 `PYTHON*`。CPython 的 `-I` 隐含 `-E`，会在 bootstrap 运行前忽略所有 `PYTHON*` 启动变量。因此把预期 seed 放入 `env -i` 有两种普通、均不正确的结果：严格按 bootstrap 的规则会拒绝该环境；给它开例外则 `os.environ` 仍可显示正确字符串，但解释器已经以随机 hash seed 初始化。

**Impact：** 当前 closure 无法既满足隔离启动合同又证明实际 hash-seed 语义。严格实现会让 authoritative M7 fit 与 M6 replay 无法启动；宽松实现则可把环境 receipt 与 closure digest 均写成匹配、但实际 hash randomization 仍开启的运行结果发布为 official。若冻结代码中的容器/配置/特征路径依赖 hash 顺序，同一 closure 可产生不稳定的训练或预测路径。这是冻结威胁模型内的普通 flags/environment 配置错误，不需要 hostile runner、host、control root、ACL 或 native-code compromise。

**Evidence：**

- v9 明确列出 `PYTHONHASHSEED`，随后要求 `-I -S` 并拒绝 `PYTHON*`；v12 对 M7 closure 与 M6 replay 保留相同组合。
- 只读 CPython probe：`python3 -I -h` 明确说明 `-I` “implies -E and -s”。两次独立执行 `PYTHONHASHSEED=0 python3 -I -S -c ...` 都得到 `sys.flags.hash_randomization == 1` 且 `hash("qlib-peerlite")` 不同；无 `-I` 的对照进程得到 `hash_randomization == 0`。在 isolated 进程中 `os.environ["PYTHONHASHSEED"]` 仍是 `'0'`，所以仅记录环境键值不能证明实际 seed。
- bootstrap 位于解释器初始化之后，不能补救已被 `-I` 忽略的启动变量；现有 expected/observed closure 字段也没有要求记录并校验有效 hash-seed mechanism / `sys.flags`。

**Direction：** 在进入 test-design 前作出一个单一、可测的架构决定，而非为该变量留下文字例外：

1. 若必须固定 Python hash seed，使用已绑定、在 CPython 初始化前生效的机制（例如受控 launcher/`PyConfig`），或采用不含 `-E` 的严格启动配置；只允许该明确声明的 seed 输入，并继续以 `env -i`、固定 cwd/argv、关闭 site/user-path、origin guard 和 closure checks 保持隔离。
2. 若不依赖固定 seed，则从确定性合同删除 `PYTHONHASHSEED`，明确规定并证明所有输入、特征、配置与输出路径不依赖 set/dict hash iteration order。

无论选择哪条，`RunnerExecutionReceipt` 和 `ReplayExecutionReceipt` 都必须绑定并验证**有效** hash policy（而不只是 `os.environ` 内容）；bootstrap 必须区分经批准的启动机制与任意未批准的 `PYTHON*` 注入。后续 synthetic tests 应证明：`-I` + env-only seed 被拒绝；两个 fresh staged processes 的有效 policy 一致；意外 `PYTHON*` 仍拒绝；刻意 hash-order-sensitive probe 要么稳定一致，要么在 permit/acceptance 前失败。

## Verdict

`NEEDS_CHANGES`：0 个 P0、1 个 P1、0 个 P2、0 个 P3。最早修复阶段为 `architecture`；随后必须更新唯一 canonical change design，并重新进行独立设计审查。修复前不得进入 test-design、实现、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或最终 OOS。

上一轮 v8 的两个 P1 及本轮要求的其余边界已经在当前文本中一致闭合，应在修复时保留：

- `M7AuthorizationPlan` 不再持有 QRC 引用；QRC 绑定 Plan，而 registry 在下游配对二者，因此不存在内容哈希环。
- 只有 fresh direct-exec 的 post-exec worker 能创建 `DispatchClaim v1`；同一 activation/event lock 线性化 close 与 permit consumption，且 receipt 先持久化后才允许一次 `model.fit()`。
- M7 runner 在 claim 前完成 staged FD-exec、bootstrap、module/native-map 的 observed closure 验证；publisher 也绑定该 execution receipt。
- QRC-bound policy 对四个非 root、pairwise non-alias writer identities 定义 numeric UID/GID、supplementary-group/capability、socket peer 与 closed ACL matrix，并在 activation/permit/publish/resolve 时重检。
- M6 `6/44` genesis、PIT/behavior/state handoff、synthetic-only boundary、legacy M6 evidence immutability 和 final-OOS seal 没有被削弱。

## Scope, evidence and limits

- 审查对象：
  - `evidence/m6_5_pre_m7/m6_5_repair_change_design_v9.md`，SHA-256 `11059be45e9ae8d5cc46dff2a5662e4d4001814b4b604ce862b4cb1c722d75f6`；
  - `evidence/m6_5_pre_m7/architecture_confirmation_v12.md`，SHA-256 `f80ca2a93ecca804f0c8c7ecc604eee26d0ad2b08f93d5b8bbf71afc26aa38ad`；
  - `evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md`，SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78`；
  - `evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。
- 只读使用 `shasum`、`rg`、`sed`、`nl`、`jq`、`git diff/status`、quality-ledger inspection 和无项目数据的 CPython flags microprobe。未修改产品代码、测试、契约、gate、M6 历史或 quality ledger；本报告本身是独立审查证据。
- 未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。PIT 仅以 `VERIFY` 方式核对已保留的 handoff 合同；不产生 PIT `PASS`、`QUALIFIED`、数据认证、M7 放行或 Alpha 结论。
- Finding 严格限于冻结威胁模型的普通运行时配置语义；不把 hostile runner arbitrary native-code execution、host/control-root/kernel/ACL compromise 或恶意注入作为阻断理由。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 72,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "ISOLATED_MODE_INVALIDATES_ENV_ONLY_PYTHONHASHSEED_DETERMINISM_CONTRACT",
  "summary": "v9/v12 resolve the prior authority-graph, post-exec dispatch, measured M7 closure, ACL, and replay-closure gaps, but require PYTHONHASHSEED while forcing python -I -S and rejecting PYTHON*. Isolated mode ignores that startup variable before bootstrap, so an environment receipt can match while the effective hash seed remains random.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 0, "P3": 0},
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v9.md",
    "evidence/m6_5_pre_m7/architecture_confirmation_v12.md"
  ],
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
    "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v8.md",
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v9_adversarial.md"
  ],
  "commands": [
    "read-only shasum/rg/sed/nl/jq/git diff/status",
    "quality-ledger inspection only",
    "PYTHONHASHSEED=0 python3 -I -S flags/hash microprobe (no project data)"
  ],
  "subject_digest": "sha256:11059be45e9ae8d5cc46dff2a5662e4d4001814b4b604ce862b4cb1c722d75f6",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v9.md",
    "sha256": "sha256:11059be45e9ae8d5cc46dff2a5662e4d4001814b4b604ce862b4cb1c722d75f6",
    "incorporated_base": {
      "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
      "sha256": "sha256:2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78",
      "retained_sections": ["1", "2", "3", "4", "7"]
    }
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v12.md",
    "sha256": "sha256:f80ca2a93ecca804f0c8c7ecc604eee26d0ad2b08f93d5b8bbf71afc26aa38ad"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_lead",
    "limitations": [
      "Read-only review artifact; no product/test/contract/gate/ledger mutation.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access.",
      "PIT discussion is VERIFY-only and is not a PIT certification result."
    ]
  },
  "blockers": [
    "Resolve and bind the effective Python hash-seed/startup mechanism, then independently re-review architecture and canonical design.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
