# Quant Research Contract Decision

- Status: `PLANNED`
- Contract ID: `not assigned`
- Canonical hash: `not assigned`
- Claim level: `exploratory`
- Research family: `qlib-peerlite-a-share-daily-v0`
- Trial budget: 0 completed + 27 planned / 27 cumulative
- Scope: listed_equity / China A-share XSHG and XSHE / daily
- Prediction and horizon: T日连续竞价收盘且当日全部允许字段达到数据截止后形成信号。 / 5 eligible trading sessions
- Final OOS: 2025-01-01 to 2026-06-30 / UNTOUCHED
- Primary metric: cost_adjusted_excess_information_ratio > 0.0
- Multiplicity: exploratory_only / exploratory
- Research posture: `OPEN_WITH_GUARDRAILS`
- Current claim ceiling: `DESIGN_ONLY`

## Decision

The requested claim is not ready, but reversible exploration and evidence gathering remain open.

18 issue(s): 0 hard stop, 0 redesign, 18 evidence gap, 0 claim limit.

- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[0].snapshot_hash` — must be a non-empty string before freeze
- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[0].snapshot_id` — must be a non-empty string before freeze
- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[1].snapshot_hash` — must be a non-empty string before freeze
- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[1].snapshot_id` — must be a non-empty string before freeze
- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[2].snapshot_hash` — must be a non-empty string before freeze
- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[2].snapshot_id` — must be a non-empty string before freeze
- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[3].snapshot_hash` — must be a non-empty string before freeze
- `NEEDS_EVIDENCE` `NEEDS_EVIDENCE` `data.sources[3].snapshot_id` — must be a non-empty string before freeze
- … 10 additional issue(s); use the validator for the full list.

## Research paths

### A — Evidence or repair first (recommended)

Resolve `data.sources[0].snapshot_hash` so the decision can change. Produces: a directly reviewable definition or artifact. Does not prove: the remaining contract or alpha.

### B — Safe exploration

Allowed: source-semantic work, synthetic mechanics, or diagnostics confined to an explicitly pre-OOS sample. Prohibited: final-OOS access and confirmatory claims. Produces: candidate definitions or implementation evidence. Does not prove: out-of-sample performance.

### C — Preserve an exploratory claim

Allowed: continue under an explicit exploratory ceiling while recording open assumptions. Prohibited: promotion or discovery claims. Produces: bounded learning. Does not satisfy: freeze readiness.

## Recommended next action

Resolve `data.sources[0].snapshot_hash` so the decision can change. Produces: a directly reviewable definition or artifact. Does not prove: the remaining contract or alpha.
