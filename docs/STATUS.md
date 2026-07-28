# True Status Card

- Master plan: `docs/MASTER_PLAN.md`
- Master plan SHA256:
  `03fb43a94ae3bd0af7ba84ee9e22fba5f164f67158f88798d42c1a9e1111aeb8`
- Current phase and track: `M6-PEERLITE-PREFLIGHT`
- Last actual action: completed and independently verified the repaired M5 v2
  LightGBM/MLP rolling baseline run
- Status: executed=`yes`; completed=`yes`; passed=`M5 PASS`
- Active frozen contract:
  - `contracts/immutable/research_contract_pit_v2.json`
  - contract ID `qrc-v2-5b7353756e0fded36622a6946011f77a`
  - canonical hash
    `5b7353756e0fded36622a6946011f77a99706ec82a9685cb2dd3c03bba37002d`
- Strongest current evidence:
  - `evidence/gates/M0_environment_gate.json`: environment `PASS`
  - `evidence/gates/M1_source_gate.json`: source/snapshot `PASS`
  - `evidence/gates/M2_contract_gate.json`: initial contract gate `PASS`
  - `evidence/gates/M3_pit_data_gate.json`: full PIT data gate `PASS`
  - `evidence/gates/M4_qlib_foundation_gate.json`: Qlib foundation gate `PASS`
  - `evidence/gates/M5_baseline_gate.json`: strict baseline gate `PASS`
  - `data/manifests/pit_data_product_2012_2024_v3/data_product_manifest.json`:
    1,658,525 pre-OOS samples and exactly 50 frozen features
  - `evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json`:
    82,926,250/82,926,250 cells parsed; all 17 fixed checks `PASS`;
    `QUALIFIED`
  - `evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json`:
    all four behavior checks `PASS`; 5,750 protected keys unchanged
  - local grouped executor validation: fixed suite `163/163`; behavior suite
    `18/18`
  - Qlib foundation: 1,658,525 rows, 50 features, seven rolling folds and one
    exact deterministic fold replay
  - Qlib Recorder: foundation and synthetic-analysis receipts downloaded with
    byte-identical hashes
  - Qlib signal/portfolio mechanics: synthetic track only
  - M5 v2: 2 candidate evaluations, 15 fits, 14 exact checkpoint replays and
    one exact B1 deterministic refit
  - verified predictions: 1,898,028 rows; unique keys; no null/non-finite score;
    latest date 2024-12-17
  - cumulative family budget including rejected v1: 4 candidate evaluations,
    29 model fits
  - real-data portfolio backtests and cost-adjusted selections: `0 / 0`
  - M5 immutable execution spec:
    `contracts/immutable/m5_baseline_execution_spec_v2.json`,
    content SHA256
    `fa8fb630fe3c1ea733d9f105ef3f7875f3b50e9fda4d6f57948dbdde46552904`
  - M5 independent verification content SHA256:
    `b8d9643f7b9eda2211e852da1f07cf0cf6e5b97646aa760356be4751f91268e6`
  - final-OOS market partitions opened: `false`
  - only pre-final-OOS signal diagnostics computed: `true`
- Current blocker: none for M6 engineering preflight.
- Risk/ambiguity:
  - DataYes descriptions and snapshot hashes cannot prove vendor truth or that
    no off-system future data was consulted.
  - The separately versioned population authority is reconciled exactly but is
    derived from the verified product population; it cannot independently
    prove that the upstream vendor omitted no eligible security.
  - Behavior status is `NOVEL_CANDIDATE`: it proves this exact hash-bound replay,
    not every possible execution.
- Only permitted next action: implement the small O(NK) PeerLite mechanism,
  pass permutation/variable-universe/mask/single-stock/checkpoint tests, and
  freeze a separately hash-bound M6 execution specification before empirical
  comparison.
- Forbidden until later gates: unregistered model or hyperparameter search,
  PeerLite claims before M6, final-OOS access before M8 freeze, production
  trading and “top 1%” claims.

## PIT navigation

- Completed mode: `CERTIFY`
- Target path:
  `sealed DataYes raw daily data -> fixed causal features -> CSI800 PIT universe`
- Fixed audit: `PASS / QUALIFIED`
- Behavior audit: `PASS / NOVEL_CANDIDATE`
- Project M3 decision: `PASS` for controlled development on the exact bound
  pre-OOS data product only
- Project M4 decision: `PASS` for Qlib foundation mechanics
- Project M5 decision: `PASS` for reproducible pre-final-OOS engineering
  baselines only
- Claim ceiling remains: `research development`; no Alpha or investability claim
