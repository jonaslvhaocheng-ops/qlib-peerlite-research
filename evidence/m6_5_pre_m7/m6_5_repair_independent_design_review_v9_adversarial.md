# M6.5 canonical v9 / architecture v12 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查技能：`eng-review-design`  
审查性质：独立、只读、R3。审查严格限定于冻结 `research_governance_threat_model_v1.md` 的普通 graph/config/race/path/runtime/ACL 错误；未把 hostile runner、host/control-root/ACL compromise 或恶意 native injection 作为 finding。

未修改产品代码、测试、契约、gate 或 quality ledger；未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。

## 审查对象

- canonical change design：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v9.md`，SHA-256 `11059be45e9ae8d5cc46dff2a5662e4d4001814b4b604ce862b4cb1c722d75f6`。
- canonical architecture：`evidence/m6_5_pre_m7/architecture_confirmation_v12.md`，SHA-256 `f80ca2a93ecca804f0c8c7ecc604eee26d0ad2b08f93d5b8bbf71afc26aa38ad`。
- frozen threat model：`evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。

## Finding

### [P1] 必须冻结的 `PYTHONHASHSEED` 与强制的 `python -I -S` / “reject `PYTHON*`”不兼容；receipt 可匹配而实际解释器仍随机化

**Section：** v9 §5.3（尤其第 133–137 行）和 §6（第 149 行）；v12 §5（第 100–104 行）与 §6（第 110 行）。

**Scenario：** authoritative M7 fit 和 M6 replay closure 都把 `PYTHONHASHSEED` 列为必须冻结、记录并拒绝未知值的确定性环境项；但执行方式同时固定为 `env -i ... python -I -S`，bootstrap 又拒绝 `PYTHON*`。在 CPython 中，isolated mode `-I` 隐含忽略所有 `PYTHON*` startup variables（等价包含 `-E` 的效果）。因此有两个都不正确的实现结果：

1. 将预期 `PYTHONHASHSEED` 传入 `env -i`：bootstrap 会按“reject `PYTHON*`”终止，任何权威 fit/replay 都无法启动；
2. 为了运行而给它开例外：解释器在 bootstrap 之前已经忽略该变量，hash seed 仍是随机值。receipt 的 environment digest 仍可记录正确的 `PYTHONHASHSEED=...` 字符串，但它不能证明实际解释器使用了该 seed。

这是普通 flags/environment 配置错误，不需要恶意代码。若 frozen runner 的任何特征/配置/对象遍历经过 hash-order-sensitive 标准 Python 容器，两个相同 closure 运行可产生不同训练/预测路径；M7 首次 fit 没有历史 exact-score comparator 来自动拦截这一差异，仍可能获得 terminal result。

**Read-only execution evidence：** 本机无项目数据的解释器探针执行：

```text
env PYTHONHASHSEED=0 python3 -I -c '... print(sys.flags.hash_randomization, hash("qlib-peerlite"))'
-> isolated=1, hash_randomization=1, hash=-5227435119670355562
-> isolated=1, hash_randomization=1, hash=-6330875490346374994   # second clean process

env PYTHONHASHSEED=0 python3 -c '...'
-> isolated=0, hash_randomization=0, hash=148116411214739374
```

在 `-I` 的两次进程中，`os.environ` 仍可见 `PYTHONHASHSEED=0`，但 hash 随机化已开启且值不同。这正是“receipt 环境项看似正确、有效运行语义不同”的风险。

**Impact：** current closure cannot simultaneously satisfy its deterministic-environment contract and its isolation policy. 严格实现会无故阻塞所有 authority fit/replay；放宽实现会在未记录的随机 hash seed 下运行 M7，并可能把不稳定、不可复现的输出写为 official。它也使 “expected/observed closure equality”不是有效的实际确定性证明。

**Direction：** 在继续 test-design 前做一个明确、单一的设计决定，不能用文字例外掩盖：

- 若确实需要固定 Python hash seed，使用一个已绑定的 pre-initialization launcher/embedded `PyConfig` path，在 CPython 初始化前设置 `use_hash_seed/hash_seed`；该 launcher、effective seed 和 `sys.flags` 观察值要进入 closure/receipt。保留 `-I`，但 bootstrap 的 allowlist 不能把这个已生效机制误判为外部 `PYTHON*` 注入。
- 若计划不依赖 hash seed，则从 deterministic environment contract 中移除 `PYTHONHASHSEED`，明确证明 frozen runner/replay bootstrap 不会因 set/hash-order 影响研究输入/输出（例如 deterministic ordering contract + mutation test），并禁止把一个被 `-I` 忽略的值写作确定性保证。

无论选哪条，bootstrap 需要区分“允许且已验证的启动配置”与未批准 `PYTHON*`，并将**有效** hash-randomization/seed mechanism—not merely `os.environ`—绑定到 `RunnerExecutionReceipt` / `ReplayExecutionReceipt`。

**Required evidence：** two clean staged processes with identical closure must prove the selected effective hash policy; `-I` + env-only seed must fail the closure test; unexpected `PYTHON*` remains rejected; authoritative-fit and replay fixtures using a deliberately hash-order-sensitive probe must either be deterministically equal under the chosen seed mechanism or fail before permit/acceptance.

## 已验证的修复方向

在上述 P1 之外，未发现新的 P0/P1/P2：

- v9/v12 现在清楚地将 Plan→QRC 表述为 creation order，而非 Plan 持有 QRC reference；Registry 同时精确绑定 Plan/QRC，消除了上一轮 hash cycle。
- `CLOSING` 与 permit consumption 使用同一 activation/event lock；post-exec child claim、`SO_PEERCRED`/ProcessIdentity、one-use dispatch receipt 和 fork poison 的顺序一致。
- M7 runner 已具备 FD-exec、staged closure、bootstrap-before-import、observed module/native map 与 publisher-bound `RunnerExecutionReceipt`，不再只有 replay 有执行闭环。
- numeric UID/GID、non-alias、ACL matrix、socket peer allowlist 与 permit/publish/resolve revalidation 已将 actor-alias 从约定变成配置 gate。
- replay closure 已覆盖 interpreter/package/native/GPU/CUDA/locale/thread/cache/umask 与三方 receipt agreement；在本 threat model 内没有发现额外普通 runtime substitution 路径。

这些方向应保留；该 finding 仅要求把 Python isolated-mode 的实际语义纳入同一闭环。

## Verdict

`NEEDS_CHANGES`：**0 个 P0、1 个 P1、0 个 P2、0 个 P3**。最早修复阶段为 `architecture`，随后要更新 canonical design 并重新获得独立设计审查 `PASS`。在此之前仍不得进入 test-design、实现、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或最终 OOS。

## 审查限制

- 只读检查设计/架构、冻结 threat model、质量路由与现有边界；没有把设计文本当作实现通过。
- 除上述无项目数据的 Python flags microprobe 外，没有运行项目代码、训练、replay 或真实数据动作。
- 质量 ledger 读取时 revision 为 `71`，router 选择 `design-review`；本报告不修改 ledger。主流程记录前必须再次调用 router 并使用当时 revision/source digest。
- 未执行 PIT `CERTIFY`，不产生 PIT/data pass、M7 入场、Alpha 或生产结论。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 71,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "ISOLATED_MODE_INVALIDATES_ENV_ONLY_PYTHONHASHSEED_DETERMINISM_CONTRACT",
  "summary": "v9/v12 close the prior graph, dispatch, runner-closure, ACL and replay findings, but require PYTHONHASHSEED while forcing python -I -S and rejecting PYTHON*. In isolated mode the variable is ignored before bootstrap, so a matching environment receipt can still represent a random effective hash seed; strict implementation instead blocks all execution.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v9.md",
    "sha256": "sha256:11059be45e9ae8d5cc46dff2a5662e4d4001814b4b604ce862b4cb1c722d75f6"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v12.md",
    "sha256": "sha256:f80ca2a93ecca804f0c8c7ecc604eee26d0ad2b08f93d5b8bbf71afc26aa38ad"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next (route inspection only)",
    "env PYTHONHASHSEED=0 python3 -I/-E/-c hash semantics microprobe (no project data)"
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
    "Resolve the effective Python hash-seed mechanism and re-review architecture/design before test-design.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
