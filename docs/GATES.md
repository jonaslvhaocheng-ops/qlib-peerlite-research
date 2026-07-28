# Gate Register

| Gate | Status | What it proves | What it does not prove |
| --- | --- | --- | --- |
| M0 Environment | PASS | Locked Python/dependencies and local/server smoke tests | Data validity or Alpha |
| M1 Source | PASS | Source identity, public semantics, immutable snapshot and universe binding | PIT eligibility of derived values |
| M2 Contract | PASS | Frozen falsifiable research plan and strict validation | Training-data qualification |
| M3 PIT data | PASS | Exact full-input fixed audit plus one real-pipeline future-poison replay | Vendor truth, universal cache isolation, Alpha or deployment |
| M4 Qlib foundation | PASS | Exact pre-OOS Dataset, seven rolling folds, Recorder readback and synthetic analysis mechanics | Model edge |
| M5 Baselines | PASS | Frozen LightGBM/MLP rolling scores, exact replay and independent Recorder/output verification | PeerLite edge |
| M6 PeerLite | PASS | Frozen K16/K32 MSE rolling scores, O(NK) mechanics, exact replay and independent verification | Superiority, investability or Alpha |
| M7 Increments | NOT_RUN | Pending isolated CCC/Gate tests | Guaranteed improvement |
| M8 Evaluation | NOT_RUN | Pending frozen final OOS and institutional decision package | Production readiness |

## M3 decision boundary

M3 applies only to:

- frozen descendant contract
  `qrc-v2-5b7353756e0fded36622a6946011f77a`;
- source snapshot `source_snapshot_20260728_v1`;
- data product `pit_data_product_2012_2024_v3`;
- consumed-value view `pit_consumed_values_full_2012_2024_v2`;
- fixed audit `pit-audit-v1-08e3a3e299b530191bac7169d8b14369`;
- behavior proof `pit-behavior-c9a2bdaa48d7e6dc8077`.

The M3 pass permits controlled M4/M5 work on these exact pre-OOS inputs after
the empirical guard verifies every hash. It does not permit final-OOS access,
unregistered features, contract edits, production deployment or performance
claims beyond the later gates.

## M4 decision boundary

M4 binds:

- real-data foundation receipt
  `evidence/qlib/foundation_20260728_v2/qlib_foundation_receipt.json`;
- synthetic analysis-mechanics receipt
  `evidence/qlib/analysis_mechanics_20260728_v1/analysis_mechanics_receipt.json`;
- independent project gate
  `evidence/gates/M4_qlib_foundation_gate.json`.

The real-data run loaded the entire qualified development product and built all
seven folds, but performed zero model fits, signal evaluations and portfolio
backtests. Qlib signal-analysis and portfolio mechanics were tested only on
synthetic data. M4 therefore permits the two registered M5 baselines; it does
not establish predictive value or authorize final-OOS access.

## M5 decision boundary

M5 binds:

- repaired frozen execution spec
  `contracts/immutable/m5_baseline_execution_spec_v2.json`;
- complete JSON receipt set
  `evidence/m5/runs/m5_baselines_20260728_v2`;
- independent verification
  `evidence/m5/verifications/m5_baselines_20260728_v2`;
- project gate `evidence/gates/M5_baseline_gate.json`.

The pass covers 2 registered candidates, 15 counted v2 fits, 14 exact checkpoint
replays, one exact deterministic refit, 1,898,028 verified score rows and two
independent Qlib Recorder readbacks. The rejected v1 run remains counted, making
the cumulative budget 4 candidate evaluations and 29 fits. M5 authorizes only
M6 PeerLite mechanics and frozen pre-final-OOS research preparation; it does not
establish predictive edge, costs, capacity, final-OOS validity or investability.

## M6 decision boundary

M6 binds:

- frozen execution spec
  `contracts/immutable/m6_peerlite_execution_spec_v1.json`;
- synthetic-only invariant receipt
  `evidence/peerlite/mechanics_20260728_v2/mechanics_receipt.json`;
- complete JSON receipt set
  `evidence/m6/runs/m6_peerlite_20260728_v1`;
- independent verification
  `evidence/m6/verifications/m6_peerlite_20260728_v1`;
- project gate `evidence/gates/M6_peerlite_gate.json`.

The pass covers 2 registered PeerLite-MSE candidates, 15 counted fits, 14 exact
checkpoint replays, one exact K16 deterministic refit, 1,898,028 verified score
rows and two independent Qlib Recorder readbacks. K16 has 29,521 parameters and
K32 has 30,561; both retain O(NK) cross-sectional complexity and the unified
score interface. Cumulative budget consumption is 6 candidate evaluations and
44 fits.

M6 intentionally performs no result-based K selection and no LightGBM/MLP
comparison. It permits only separately frozen M7 CCC and market-state Gate
experiments. It does not establish predictive edge, costs, capacity,
final-OOS validity, investability or production readiness.
