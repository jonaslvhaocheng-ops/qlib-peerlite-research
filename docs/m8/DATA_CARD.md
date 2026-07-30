# Data Card — Qualified Pre-Final-OOS Research Product

## Status

`PIT_QUALIFIED_FOR_FROZEN_PRE_OOS_RESEARCH`

## Scope

Historical CSI 800 A-share daily research inputs from 2012 through 2024,
materialized with `(datetime, instrument)` as the unique key and the frozen
50-feature registry. Prediction, universe, trading-state, label and
preprocessing semantics are bound by the frozen research contract and PIT
evidence package.

## Controls

- historical point-in-time universe and trading-state handling;
- no direct use of full-history back-adjusted prices;
- five-session purge/embargo at rolling boundaries;
- training-fold-only preprocessing statistics;
- fixed and behavior-based future-poison PIT checks;
- data manifests and hashes retained outside raw Git data.

## M8 boundary

The M8 confirmation used only the qualified 2012–2024 product before it was
stopped. The final-OOS market partitions were not opened. The access-log hash
remains:

`6d9c32144fe465c0f17f7f8f3ceb5f26c51ffdb9a79c3c68b80e92a256426190`

## Limitations

PIT qualification proves eligibility and lineage for the bound product; it
does not prove vendor truth, predictive value, capacity, or live tradability.
No new final-OOS PIT certification was run because the upstream M8 confirmation
gate stopped before opening was authorized.
