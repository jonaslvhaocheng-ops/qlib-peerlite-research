# Master Plan — Qlib PeerLite v0

## Objective

在固定 A 股日频研究契约下，比较 LightGBM、MLP 和 PeerLite，检验
PeerLite 的横截面同伴结构在扣除成本后的顺序样本外结果中是否提供
可复现的增量信息。

## Claim level

第一阶段上限为 `research alpha candidate`。在研究契约和 PIT 数据门未通过
前，上限为 `mechanics / DESIGN_ONLY`。

## Primary artifact ladder

| Gate | Artifact | Acceptance | State |
| --- | --- | --- | --- |
| M0 | environment + OSS intake | clean install and smoke tests | PASS |
| M1 | source certificate | source semantics + immutable snapshot integrity | PASS |
| M2 | frozen research contract | strict validation receipt | PASS |
| M3 | PIT data product | fixed audit + behavior audit | PASS |
| M4 | Qlib research foundation | reproducible data/model/recorder loop | PASS |
| M5 | baselines | B0 LightGBM and B1 MLP rolling scores | PASS |
| M6 | PeerLite | mechanics, frozen MSE runs and independent verification | PASS |
| M6.5 | pre-M7 engineering quality | independent design/code/test review and remediation | PASS |
| M7 | Huatai increments | CCC/Gate isolated comparisons | COMPLETE / BOTH HOLD |
| M8 | institutional evaluation | five-seed confirmation then final OOS | HOLD / OOS NOT OPENED |

## Non-negotiables

- Model output is `(datetime, instrument) -> score`.
- Prediction is after T close; execution is T+1 open.
- Target is T+1 open through T+5 close.
- Full-history adjusted inputs are forbidden in v0.
- Preprocessors fit inside each training fold.
- Candidate/trial ledger is append-only.
- Final OOS may not be used for tuning, thresholds or slice selection.
- A failed upstream gate blocks only its dependent strict branch and is retained.

## Current handoff

M7 closed with CCC and Gate both `HOLD`, leaving PeerLite K16 MSE as the active
pre-final-OOS research baseline. M8 then started the frozen five-seed
confirmation. During seed 19, an accounting defect was found: start events were
durably journaled but not imported into the authoritative ledger before
`model.fit`. The process was stopped after two completed folds and one
interrupted fit.

The exact one candidate start and three fit starts were retained atomically and
independently verified, bringing the cumulative ledger to 9 candidate
evaluations and 64 fit starts. The frozen no-retry rule makes confirmation
incomplete, so statistical, portfolio, control and final-OOS gates did not run.
M8 closes as `HOLD_OPERATIONAL_CONFIRMATION_INCOMPLETE`; final-OOS access
remains zero and no model is promoted.
