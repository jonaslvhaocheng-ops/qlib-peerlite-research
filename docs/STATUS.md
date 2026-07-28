# True Status Card

- Master plan: `docs/MASTER_PLAN.md`
- Master plan SHA256:
  `42d9506377ad057e9246d2323e9b58cb98a40eed1d746a08160159520c19d367`
- Current phase and track: `M5-STRICT`
- Last actual action: froze and locally validated the M5 B0/B1 execution
  specification, deterministic preprocessing and checkpoint-reload path
- Status: executed=`yes`; completed=`yes`; passed=`M4 PASS / M5 PREFLIGHT PASS`
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
  - real-data model fits, signal evaluations and portfolio backtests: `0 / 0 / 0`
  - M5 immutable execution spec:
    `contracts/immutable/m5_baseline_execution_spec_v1.json`,
    content SHA256
    `d2db54c783406f4bce92f6399c6358fe90cad94d145551dea3ff37865eddcfe1`
  - M5 local regression: 32 tests pass, including exact B0/B1 checkpoint replay
    and direct Qlib DatasetH fitting
  - final-OOS market partitions opened: `false`
  - performance metrics computed: `false`
- Current blocker: none for M5 execution. The 14 declared server fits have not
  started.
- Risk/ambiguity:
  - DataYes descriptions and snapshot hashes cannot prove vendor truth or that
    no off-system future data was consulted.
  - The separately versioned population authority is reconciled exactly but is
    derived from the verified product population; it cannot independently
    prove that the upstream vendor omitted no eligible security.
  - Behavior status is `NOVEL_CANDIDATE`: it proves this exact hash-bound replay,
    not every possible execution.
- Only permitted next action: execute the frozen B0 LightGBM and B1 MLP runner
  on the seven fixed pre-OOS folds and retain every started/completed/failed fit
  in the append-only journal.
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
- Claim ceiling remains: `research development`; no Alpha or investability claim
