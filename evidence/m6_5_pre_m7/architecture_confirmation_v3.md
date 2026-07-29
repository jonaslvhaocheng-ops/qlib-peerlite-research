# M6.5 架构确认 v3 — M7 前质量修复

状态：`PASS — bounded architecture confirmation`  
范围：仅关闭 M6.5 审查发现的来源证明、账本运行身份和 archival replay 证据绑定缺口；不执行 M7
训练、不构建真实 state product、不访问 2025+ 最终 OOS。  
风险：`R3`（研究数据完整性、预算治理与模型决策边界）。

## 当前架构证据

- `src/qlib_peerlite/data/market_state.py` 已是独立的四维日度 state 聚合 primitive，但它只按列名
  验证 DataFrame，不能证明输入来自 sealed raw snapshot。
- `src/qlib_peerlite/governance/trial_ledger.py` 负责 journal-to-ledger 的原子同步，但当前
  `LedgerPrefixBinding` 只证明历史前缀仍存在，不能把新的 run 锁定在一次精确的启动 head 上。
- `scripts/server/verify_m6_peerlite_archival_replay.py` 已逐 checkpoint 重放，但冻结源码 archive、
  解压 source tree、manifest 与 verifier 自身尚未形成一条不可替换的证据链。
- M6 历史证据、immutable spec、历史 ledger 行和最终 OOS 封印均保持为既有所有者；本变更不得
  改写它们。

## 确认后的边界与所有权

```text
sealed raw snapshot manifest + raw partitions
        │ (server-only builder; no M3 supervised product accepted)
        ▼
data/state_population artifact + provenance receipt
        │ (artifact verifier validates digest/inventory/allowed source kind)
        ▼
market_state aggregation primitive ──► M7 dataset adapter ──► future M7 wrapper

frozen run-intent artifact + exact authoritative ledger head
        │
        ▼
server journal ──► governance trial ledger ──► future model.fit preflight

frozen source archive ──► isolated extracted tree ──► M6 archival replay receipt
```

| Boundary | Owner | Required rule |
| --- | --- | --- |
| Sealed raw state input | server builder / state artifact | The builder accepts only a named sealed raw snapshot manifest and its raw partitions. It never accepts an M3 supervised product, Qlib `market` colset, or a caller-projected DataFrame. |
| State aggregation | `data` | It receives a verified state-population artifact, validates its provenance binding, then computes only the fixed 4D daily state. It does not know labels, execution eligibility, budget, or model results. |
| Model join | future M7 data adapter | It may consume only the verified daily artifact and exact-date join it to M3 model rows. It cannot manufacture a state population. |
| Run authority | `governance` | One immutable run-authority/intent binds `run_id`, journal relative path, output root, execution spec, allowed start IDs, and the exact pre-run ledger head. The server is the sole authoritative writer. |
| Ledger mutation | `governance` + server CLI | First non-no-op reconciliation requires the current ledger to equal the bound head byte-for-byte. Later same-journal idempotent reconciliation is allowed; another journal or changed authority for the same run ID fails closed. |
| M6 replay evidence | server verifier | The verifier imports only a tree proved to be the archive's complete manifest inventory and writes archive, manifest/tree, verifier and historical receipt bindings into its new receipt. |

## Dependency rules and enforcement

1. `data` may depend on `data.schema` and artifact-hash helpers, but not on `governance`, portfolio evaluation,
   model selection or OOS access logic.
2. `governance` may validate state/run artifact hashes, but never write a state product or change raw data.
3. `scripts/server` are composition roots: they may combine `data` and `governance`, but their public CLI must
   fail closed on provenance/head/archive mismatch.
4. `M3 supervised product -> market_state population` is a forbidden directed edge. It is tested through a
   projected future-conditioned frame regression, not merely forbidden column-name matching.
5. Historical M6 replay imports only a temporary extract of the accepted archive; an arbitrary source directory
   cannot satisfy the replay interface.

## Fit with existing repository

The repair stays within existing `data`, `governance`, `scripts/server`, and `tests` ownership. It introduces no
service, dependency, database, public research model, new Qlib data product, or M7 execution spec. The existing
package layout therefore contains the change without a repository-wide redesign.

## Required rollout and rollback

- Rollout is test-only and archival-replay-only for M6.5. M7 stays disabled until this quality change, the
  subsequent PIT VERIFY, and a separate frozen M7 derived contract all pass.
- Rollback is removal of this uncommitted M6.5 repair namespace; immutable M6 artifacts and data are untouched.
- Any failed provenance, exact-head, archive-tree, checkpoint, or coverage test produces `NEEDS_CHANGES` and
  blocks M7 rather than falling back to a weaker check.

## Architectural decision

`PASS`: a bounded repair can safely use the existing package boundaries, provided its change design makes the
state provenance artifact and run-authority artifact first-class inputs. The implementation must not treat a
Python DataFrame schema or a historical prefix lookup as a security/data-integrity boundary.
