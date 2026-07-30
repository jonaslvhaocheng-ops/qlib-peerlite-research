# Quant Research Contract Decision

- Status: `FROZEN`
- Contract ID: `qrc-v2-441150f0695d61a1709ca348fd55ea1c`
- Canonical hash: `441150f0695d61a1709ca348fd55ea1c9fb6d6721e8154266ef495d19fb01750`
- Claim level: `exploratory`
- Research family: `qlib-peerlite-a-share-daily-v0`
- Trial budget: 0 completed + 27 planned / 27 cumulative
- Scope: listed_equity / China A-share XSHG and XSHE / daily
- Prediction and horizon: T日连续竞价收盘且当日全部允许字段达到数据截止后形成信号。 / 5 eligible trading sessions
- Final OOS: 2025-01-01 to 2026-06-30 / UNTOUCHED
- Primary metric: cost_adjusted_excess_information_ratio > 0.0
- Multiplicity: exploratory_only / exploratory
- Research posture: `FROZEN_READY_FOR_NEXT_AUDIT`
- Current claim ceiling: `EXPLORATORY`

## Decision

The frozen contract is internally intact and ready for its next evidence-producing audit.

Schema and declared invariants pass. This is not evidence of alpha or real PIT correctness.

## Research paths

### A — Run the next named evidence audit (recommended)

Allowed: verify the exact frozen inputs. Prohibited: silently changing them. Produces: evidence for the next gate. Does not prove: investability.

### B — Propose a pre-outcome change

Allowed: create one bound change request if the design must change. Prohibited: editing the frozen parent. Produces: explicit lineage. Does not preserve: an OOS already used for selection.

## Recommended next action

Allowed: verify the exact frozen inputs. Prohibited: silently changing them. Produces: evidence for the next gate. Does not prove: investability.
