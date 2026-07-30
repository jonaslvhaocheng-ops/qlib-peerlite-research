# M7 isolated increments — independent R3 design review v1

- Reviewed design SHA256:
  `15d30f9fb46f1cec6099cf7fedf72d44cbff18ac7d2d5cc29122e12e5aceed2d`
- Author: `/root`
- Reviewer: `/root/m65_v25_design_review`
- Review mode: independent, read-only
- Verdict: `NEEDS_CHANGES`
- Findings: `P0=0 / P1=2 / P2=2 / P3=0`

## [P1] Screening cost and benchmark are not yet frozen

The design makes cost-adjusted excess IR and stress net excess decisive, while
`contracts/cost_spec.json` and `contracts/benchmark_spec.json` remain planned.
Without a mandatory immutable screening prerequisite bundle, the 16
non-replaceable fits could be consumed before the decision is computable, or
fees/benchmark semantics could be chosen after results.

Direction: freeze external fee evidence, benchmark source/PIT/return semantics,
score-to-portfolio mapping, calendar, unfilled-order/capacity/cost code,
reference M6 portfolio products, and metric/input hashes before the first
candidate or fit event.

## [P1] Authorization roster and consumed-budget state are conflated

The design says 2/16 is atomically reserved, started events consume budget,
CCC runs before Gate, and any failed fit stops the run. If CCC fails early, the
legal state of unstarted Gate slots and Gate's terminal result is ambiguous.

Direction: define an exact state machine for immutable authorization,
candidate/fit start and terminal events, run terminal state, recovery, rerun
and no-op. Rename “reservation” if it is only an authorization roster.

## [P2] Gate values and PIT provenance can be supplied independently

The model sees a four-column frame while checkpoint provenance can be supplied
as separate hashes. A caller could pair values from one product with identity
from another.

Direction: define an immutable `VerifiedMarketStateBinding` created only by a
controlled adapter that verifies the product, broadcasts exact dates,
recomputes final dataset value digests, and carries the same binding into the
model and checkpoint.

## [P2] CCC numerical and checkpoint semantics are incomplete

The design does not fully freeze calculation dtype, population
variance/covariance, return/gradient dtype, early-stop threshold/tie-break, or
checkpoint recording of training objective versus validation monitor.

Direction: freeze these semantics, including the existing M6 comparison
`valid_mse < best_loss - 1e-10`, and bind a numerical-contract version into the
checkpoint.

## Preserved strengths

- CCC and Gate remain isolated.
- K16, seed 7, seven folds plus one refit remain fixed.
- Gate uses only four exact state fields and rejects legacy `market`.
- M6 checkpoints remain readable.
- No combination, replacement, final OOS, promotion, or Alpha claim.

## Required route

`change-design / contract`

No M7 candidate, fit, real training, or budget event is authorized before all
four findings are corrected and independently re-reviewed.
