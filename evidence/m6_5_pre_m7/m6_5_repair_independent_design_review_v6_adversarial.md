# M6.5 v6 / v9 独立对抗式设计审查（冻结研究治理威胁模型）

审查结论：`NEEDS_CHANGES`

审查方式：独立、只读、对抗式 R3 设计审查。严格以
`research_governance_threat_model_v1.md` 为边界：受信 governance supervisor、control root、ACL、冻结 runner
均未被攻破；只考察正常部署/路径选择、并发、崩溃和半成品恢复。没有把 hostile native code、`ctypes`/raw
fork、root/内核/签名密钥攻破当作本轮 finding。

审查对象：

- `evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md`，SHA-256
  `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78`；
- `evidence/m6_5_pre_m7/architecture_confirmation_v9.md`，SHA-256
  `e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598`；
- 约束：`evidence/m6_5_pre_m7/research_governance_threat_model_v1.md`，SHA-256
  `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。

## Findings

### [P1] `M6ReplayInputBinding v2` 没有闭合实际被重放的 M6 product/run/checkpoint/prediction 输入集

**位置：** design v6 §6（第 29–31 行）；architecture v9 §4（第 59–69 行）。

**场景：** governance supervisor、launcher 和 interpreter 都是受信且未被篡改的。一次正常的运维路径选择却把
一个仍然结构完整、日期截止也在 2025 前的 staging/旧 product 目录与一个同样结构完整的旧 run 目录传给 replay。
该目录包含两组候选、14 个 checkpoint 和对应 prediction parquet；因此 frozen verifier 可以对这个**错误但内部自洽**
的 product/run 对完成 14 次 exact checkpoint replay。它不需要改 archive、verifier、launcher、runtime、ledger 或
任何签名。

v6/v9 列举的 binding 覆盖 transfer archive、source tree、spec/gate/close proof、verifier、launcher、runtime、
profile、ledger 与 output policy，却没有规定必须内容寻址并由 binding 派生以下实际读取对象：

- PIT data-product manifest 与全部被消费分区/文件 inventory；
- historical run manifest、两个 candidate 的 saved prediction parquet；
- 14 个 fold receipt 与每个 checkpoint 的 metadata/state-dict inventory；
- historical verification/deterministic-refit receipt，以及它们和 M6 gate/static proof 的精确关系。

`M6CloseArchiveProof` 只声明绑定 M6 gate/static evidence；现有 M6 gate 的 `evidence` 根只有 execution spec、
mechanics、run manifest、verification、run journal 与 ledger，不能替代 product 分区和 replay 所需的所有
checkpoint/prediction inventory。因而在设计规定的 `binding + execution receipt + child receipt agreement` 下，
三个对象可以对错误 product/run 对彼此自洽，而没有外部冻结对象能把它们判为非 M6 原件。

**影响：** 错误的 M6 历史 replay 能以 `14 replay / 0 fit / OOS=false` 形式成为官方 M6 工程证据。它看起来满足
读取 ledger、无 fit、无 OOS 的限制，却不证明原始 M6 结果可复现，正落入冻结威胁模型要求防止的“绑错 archive/
verifier/launcher/runtime/environment 的只读 M6 replay”的同类路径。

**证据：**

- `scripts/server/verify_m6_peerlite_archival_replay.py:195-207` 的 replay API 将
  `product_dir`、`run_dir`、`historical_verification`、`ledger_path` 和 `output_dir` 作为独立输入；
  `:211-218` 独立解析它们；`:237-324` 随后使用 product、fold checkpoint、prediction 与 run 目录完成重放。
- `evidence/m6/runs/m6_peerlite_20260728_v1/run_manifest.json` 仅把 product manifest SHA 记录在历史 manifest；
  `evidence/gates/M6_peerlite_gate.json` 的静态 evidence 本身不列出重放时所有 product 分区、checkpoint 和
  prediction 的可验证输入 inventory。
- 当前 v2 server receipt 同时显示 replay 实际依赖独立的 `product.path`、`run.path`、historical verification 与
  verifier 路径，说明这些是不可省略的 execution inputs，而不是 source archive 的隐含部分。

**方向：** 将外部冻结的 `M6ReplayInputBinding v2` 扩充为 closed `M6ReplayEvidenceInventory`（或让
`M6CloseArchiveProof` 明确、逐项承诺同一 inventory）。它至少应 content-bind M6 data-product manifest 和被用
分区、run manifest、两个 prediction 文件、14 个 fold receipt、28 个 checkpoint 文件、deterministic-refit/
historical-verification receipts、各自的 relative path/root policy 与 date ceiling。supervisor/launcher 只能从
binding 派生这些 root 的 sealed read-only FDs；child 与 `ReplayExecutionReceipt` 都必须回写同一 inventory digest。
加入 synthetic red tests：替换一个有效但错误的 product、run root、prediction、checkpoint、fold receipt 或
historical verification 都必须在 child 启动前（或至少在任何 PASS receipt 写入前）fail closed。

### [P1] replay 的“已测量 bundle”尚未与实际 exec 与 Python import closure 形成一次不可替换的运行事务

**位置：** design v6 §6（第 31 行）；architecture v9 §4（第 65–69 行）。

**场景：** supervisor 正确读取并哈希 approved launcher/verifier/runtime，随后发生一次普通部署轮换、错误 cwd
选择或 Python module shadow。没有人攻破 supervisor 或 ACL，也没有人修改已测量文件：launcher 在 hash 与实际
`execve` 之间通过 pathname 取到另一个版本，或者正确的 launcher script 在启动时从 cwd/site path/预载模块中
导入了错误的 `qlib_peerlite` module。child receipt 仍可记录正确的 launcher/verifier **文件** hash，而实际重放
逻辑已不是 input binding 要求的 frozen code/runtime closure。

`env -i` 与 argv digest 只清理环境变量，不能固定 cwd、`sys.modules`、import origin、site path，或保证被 hash 的
FD 就是实际执行的 launcher/verifier。v6/v9 没有规定 same-FD staging/exec、content-addressed immutable launch
root、fixed cwd、isolated interpreter flags、import-origin inventory，亦没有让 supervisor receipt 绑定 child 的实际
module closure。`ReplayExecutionReceipt` 中的 launcher/verifier/runtime “FD hashes”也不足以证明这些 FD 与后来
启动的 executable 和其 import graph 是同一个对象。

**影响：** 一个正常的路径/环境误选可让“正确的静态测量 + 受信 supervisor receipt”对应错误的实际 replay，从而使
错误 M6 replay 通过 `m6_archive`。这不是 hostile-host 攻击；正是冻结威胁模型明确要求处理的 runtime/environment
绑定错误。

**证据：**

- v6 §6/v9 §4 只写“validate/measured deployment 后运行 launcher”、固定 runtime/argv 和 `env -i`，没有定义
  verified bytes 到 exec/import 的 atomic linkage。
- 当前 archival verifier 的 `:237-243` 将 frozen `src` 插进 `sys.path` 后通过普通 Python import 取得
  `qlib_peerlite` modules；它说明未来 control plane 必须验证 import provenance，而不能只记录
  `Path(__file__)` 的 verifier hash（`:354-357`）。当前脚本是待替换对象，本 finding 针对 v6 的缺失合同，
  不是把旧实现当作 v6 已实现功能。

**方向：** 冻结 `ReplayLauncherBundle` 时同时冻结一个可执行的 `ReplayExecutionClosure`：launcher、verifier、
archive-extracted module tree、interpreter/runtime、entrypoint、fixed cwd、argv、环境 allowlist 与每个受控 import
origin。supervisor 必须先以 `openat(O_NOFOLLOW)` 打开并 rehash，再从同一 FD 私有 stage/copy 并用该 staged object
启动（或提供等价的 FD-pinned execution）；禁止 mutable path 复查后执行。用 isolated interpreter、受控 cwd 与
显式 import-origin checks 防止 cwd/site/预载 module shadow；把 staged file/tree/import-closure digest、child PID/
start identity 与 child receipt hash 写入 supervisor-owned execution receipt。红测需覆盖 hash-to-exec deployment
swap、cwd shadow、`PYTHONPATH`/sitecustomize、pre-imported module、错误 entrypoint/runtime，并要求没有可接受 PASS
receipt。

## 应保留的设计方向

- 6/44 M6 close snapshot、new authority namespace、legacy `4/29` 拒绝和 crash-spends-event 已把本轮预算起点的
  正常并发/重启风险清楚地放入协议；本审查没有发现新的 P0/P1 去推翻该方向。
- data chain 正确区分 construction-only、未来 QRC 后的 PIT `CERTIFY`、完整 behavior bundle 与 immutable job
  snapshot；本审查没有把 `VERIFY`、原始 Gate 或 hostile runner 绕过作为额外 finding。
- separate `result-publisher`、terminal-only resolver、unique staging/final roots 与 quarantine 对“未终态结果
  不得 official”的正常 crash 语义是正确方向。

## Verdict

`NEEDS_CHANGES`：**0 个 P0，2 个 P1**。两个 finding 都是 M6 replay 的受信 input/execution closure，最早修复
阶段应回到 `architecture` / `change-design`，先把 binding 与 launcher trust boundary 写成 closed schemas 和可观察
协议；不能由后续 unit test 临时选择。修订并经新的独立 review 通过前，M7 derived-contract freeze、真实 M7 fit、
CCC/Gate、server v3 replay 与 final OOS 继续禁止。

## 审查范围与限制

- 只读审阅 v6/v9、冻结威胁模型、M6 gate/run/verification/replay receipt，以及现有 archival replay source；
- 未修改产品代码、测试、契约、gate、M6 history 或 Engineering Quality ledger；
- 未运行训练、server replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 50,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "M6_REPLAY_INPUT_AND_EXECUTION_CLOSURE_INCOMPLETE",
  "summary": "Under the frozen research-governance threat model, v6/v9 still leave the M6 replay product/run/checkpoint/prediction closure and measured-bytes-to-exec/import closure unspecified, so normal path/deployment mistakes can produce an official but wrong replay.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v6.md",
    "sha256": "sha256:2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v9.md",
    "sha256": "sha256:e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598"
  },
  "evidence_paths": [
    "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "evidence/gates/M6_peerlite_gate.json",
    "evidence/m6/runs/m6_peerlite_20260728_v1/run_manifest.json",
    "evidence/m6/verifications/m6_peerlite_20260728_v1/verification_receipt.json",
    "evidence/m6_5_pre_m7/m6_archival_replay_server_receipt_v2.json",
    "scripts/server/verify_m6_peerlite_archival_replay.py"
  ],
  "commands": [
    "read-only rg/nl/sed/jq/shasum",
    "quality_ledger.py next (route inspection only)"
  ],
  "independence": {
    "mode": "distinct-subagent-adversarial-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v6_adversary",
    "limitations": [
      "Read-only review artifact only; no product/test/contract/gate/ledger mutation.",
      "No training, server replay, budget consumption, real PIT certification, or final-OOS access.",
      "Hostile native-code, runner-identity, control-root, kernel, and signing-key compromise are explicitly out of scope under the frozen threat model."
    ]
  },
  "blockers": [
    "Return to architecture/change-design before test design or implementation.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ]
}
```
