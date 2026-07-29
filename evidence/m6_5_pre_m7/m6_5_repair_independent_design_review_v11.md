# M6.5 self-contained v14 / v11 独立设计审查

## Findings

### [P1] `M6ReplayInputBinding v6` 把“尚不存在的输出根”要求为完整 `ArtifactRef`，但未定义可绑定的 absence reservation，严格 schema 下无法同时满足新输出与内容寻址

**Section：** `architecture_confirmation_v14.md` §2（第 26 行）和 §6（第 87–97 行）；`m6_5_repair_change_design_v11.md` §1（第 20 行）和 §6（第 110–120 行）。

**Scenario：** v14/v11 共同规定所有 binding entry 都是 strict `ArtifactRef v1`，其字段固定包含 `relative_path`、`schema_version`、`sha256` 和 `bytes`，并要求 root-FD 打开、类型/owner/mode/ACL/nlink/hash 验证；v14 更明确称 v6 inventory 的“every item”都是这种精确 artifact。可是 v6 的第 7 项又要求“previously/fresh nonexistent output root”。一个尚不存在的目录/根没有可验证的内容 SHA、字节数或可打开 FD；若先创建空目录来取得 identity，它已不再满足“nonexistent”，若使用空 hash、占位值或普通路径字段，又违反 closed `ArtifactRef` / no-placeholder 语义。当前合同没有 `OutputRootReservation`、`FreshOutputPolicy` 或等价的 must-not-exist schema 来表示这一时态条件。

**Impact：** 严格实现无法冻结一个同时满足 inventory 与 fresh-output 条件的 v6 binding；放松实现则必须在没有被绑定的 absence/parent identity/no-replace contract 下接受输出路径。这会在冻结 threat model 内重新留下 pre-existing output、父目录替换、名称碰撞或错误根被作为 replay output 的普通运行错误，且 v6 的“no free path / new output”保证无法机械验证。问题发生在 M6 archive replay 官方接受前，不依赖 hostile runner、host/control-root compromise 或任意 native-code execution。

**Evidence：**

- v14 §2 将 `ArtifactRef v1` 定义为含 SHA/bytes 的 content identity，并要求 FD/hash check；v11 §1 相同。
- v14 §6 将“every item”列为 exact path/SHA/bytes/schema/role，而第 7 项是 `previously nonexistent output root`；v11 §6 对应为 “Every entry is a closed ArtifactRef” 与 `fresh nonexistent output root`。
- 两份 sole canonical 文档均没有 `OutputRootReservation`、`must_not_exist`、或 output-policy object；检索仅找到 publisher 的终态 `OutputInventory` / atomic no-replace，而没有 replay binding 时可审计的 future-root reservation。

**Direction：** 将未来输出从 `ArtifactRef` inventory 中拆出为明确 versioned 的 `FreshOutputReservation v1`（或等价 closed output policy），并把该**现有的 reservation policy bytes**作为 v6 binding artifact。它至少应绑定 trusted parent `ArtifactRef`/root-FD identity、relative child name、expected directory type/owner/mode/ACL、`must_not_exist=true`、唯一 binding/activation identity、creator actor 和 `mkdirat`/`O_EXCL`/no-replace/parent-fsync sequence。replay supervisor 必须在 binding/launch 前和创建时均从 verified parent FD 重查 absence，随后由 execution/child receipt 绑定实际创建的 root 与 final `OutputInventory` tree hash；pre-existing/empty placeholder root、parent replacement、name collision、reservation substitution 或 creation failure 都 fail closed，不能退化为 caller path。若 M7 descriptor 也使用 future final-root reservation，应复用同一明确 schema，而不是隐式 path convention。

后续 synthetic tests 应覆盖：预先存在的空目录、父目录 replace/symlink、并发 reservation、creation 后崩溃、不同 reservation 指向同一 child name、错误 inventory/root 及 replay retry；每种失败都不得产生 accepted archive output 或改变 legacy ledger。

## Verdict

`NEEDS_CHANGES`：0 个 P0、1 个 P1、0 个 P2、0 个 P3。最早修复阶段为 `architecture`，之后应同步更新唯一 self-contained implementation contract 并重新获得独立设计审查。修复前不得进入 test-design、实现、server replay、M7 derived-contract freeze、真实 M7 fit、CCC/Gate 或最终 OOS。

除这一 output-reservation 缺口外，v14/v11 已正确、自包含地保留并强化了本轮要求的边界：

- 实际 M6 gate/immutable budget 证据与文档一致：`31a90…`、51 行、14,328 bytes、`6/44`，并拒绝 `8d08…`、`4/29` legacy head。
- PIT/state/behavior handoff、17 项生产审计条件、`VERIFY`/synthetic 拒绝和 public M6-only Gate/raw-market-state denial 均存在。
- `FitAdmissionDescriptor v5`、closure/receipt v2、dispatch v2/v3 与 fail-closed old-schema/no-alias 迁移修复了上一轮 v1/v2 binding ambiguity。
- exact `envp`、`PYTHONHASHSEED=0`、`-s -S -P`、禁用 `-I/-E`、pre-claim bootstrap flags/probe 与 helper+bootstrap 双重 umask observation 已构成有效的 startup contract；本机非 3.11 环境仅可 synthetic/fail closed。
- one-way Plan/QRC graph、four-actor non-alias ACL、same-lock close/permit、post-exec-only claim、publisher terminal index、完整 M6 v6 input inventory/no caller path 及 `14 replay / 0 fit / OOS=false` ceiling 都没有被遗漏。

## Scope, evidence and limits

- 审查对象：
  - `evidence/m6_5_pre_m7/architecture_confirmation_v14.md`，SHA-256 `148490b9933be0311ff7c0b8626cdc5c3c268a2070cf6a6f49e9e26ac2af410f`；
  - `evidence/m6_5_pre_m7/m6_5_repair_change_design_v11.md`，SHA-256 `cdbcbff655d7e8de152d62e1d4aa33a1fa145ebb43ad8f7efde555ac39c52a21`；
  - frozen threat model `research_governance_threat_model_v1.md`，SHA-256 `d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14`。
- 只读检查 canonical documents、M6 immutable budget/gate evidence、static cross-document invariants、repository surfaces、quality ledger 和 local non-authoritative Python capability。未修改产品、测试、契约、gate、M6 历史或 quality ledger；本报告是唯一新增审查证据。
- 未运行训练、archive replay、预算消费、真实 PIT `CERTIFY` 或最终 OOS。PIT 仅按 `VERIFY` 边界核对合同文本，不产生 PIT `PASS`、`QUALIFIED`、数据认证、M7 放行或 Alpha 结论。
- Finding 只针对冻结 research-governance threat model 内的普通 schema/path/output lifecycle；不将 hostile runner arbitrary native code、host/control-root/kernel/ACL compromise 或恶意加载器注入作为阻断理由。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 84,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "FRESH_REPLAY_OUTPUT_ROOT_CANNOT_BE_AN_EXISTING_ARTIFACTREF",
  "summary": "Self-contained v14/v11 restores the M6/PIT/Gate, v5/v2 migration, startup/umask, graph/ACL/dispatch/publisher and full replay-input constraints. But it requires every M6ReplayInputBinding v6 item to be an exact existing ArtifactRef while also requiring a fresh nonexistent output root, without an absence-reservation/output-policy schema. The replay output lifecycle is therefore not implementable as written without either rejecting every run or weakening no-free-path/new-output guarantees.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 0, "P3": 0},
  "artifact_paths": [
    "evidence/m6_5_pre_m7/architecture_confirmation_v14.md",
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v11.md"
  ],
  "evidence_paths": [
    "contracts/immutable/m6_trial_budget_start.json",
    "evidence/gates/M6_peerlite_gate.json",
    "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md"
  ],
  "commands": [
    "read-only shasum/rg/sed/nl/jq/git diff/status",
    "quality-ledger inspection only",
    "static canonical-contract/inventory assertions",
    "local non-authoritative Python capability probe without project data"
  ],
  "subject_digest": "sha256:cdbcbff655d7e8de152d62e1d4aa33a1fa145ebb43ad8f7efde555ac39c52a21",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v11.md",
    "sha256": "sha256:cdbcbff655d7e8de152d62e1d4aa33a1fa145ebb43ad8f7efde555ac39c52a21"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v14.md",
    "sha256": "sha256:148490b9933be0311ff7c0b8626cdc5c3c268a2070cf6a6f49e9e26ac2af410f"
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
    "Define and bind a strict fresh-output reservation/policy separate from existing ArtifactRef inputs, then re-review architecture and implementation contract.",
    "M7 derived-contract freeze, real M7 fit, CCC/Gate, server replay, and final OOS remain prohibited."
  ],
  "next_route": "architecture"
}
```
