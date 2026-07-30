# Model Card — PeerLite K16 MSE

## Status

`ACTIVE_PRE_FINAL_OOS_RESEARCH_BASELINE / NOT_PROMOTED`

## Intended use

Research-only A-share daily cross-sectional scoring under the frozen contract.
Output is `(datetime, instrument) -> score`. The score is intended for the
frozen weekly top-decile portfolio research mapping, not direct order routing.

## Structure

Fifty causal daily features feed a 64-dimensional encoder, 16 peer prototypes,
one four-head peer-attention layer, and an MSE prediction head. The model has
29,521 parameters and O(NK) cross-sectional complexity.

## Training and evaluation boundary

- prediction: after T close;
- execution assumption: T+1 open;
- label: T+1 open through T+5 close;
- development data: qualified 2012–2024 PIT product;
- final OOS: 2025-01-01 through 2026-06-30, not opened;
- confirmation seeds: incomplete because M8 closed after a retained accounting
  incident.

## Validated properties

M6 validated model mechanics, variable cross-section handling, permutation
equivariance, missing masks, exact checkpoint replay, rolling score production,
and Qlib integration. M7 established that CCC and the market-state Gate did not
pass their isolated screens.

## Limitations

No completed five-seed superiority test exists. No final-OOS, investability,
capacity-at-scale, live execution, monitoring, or production evidence exists.
The two completed M8 folds are not performance evidence.

