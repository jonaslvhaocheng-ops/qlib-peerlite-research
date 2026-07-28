# True Status Card

- Master plan: `docs/MASTER_PLAN.md`
- Current phase and track: `M4-STRICT`
- Last actual action: full-input fixed PIT audit plus real-pipeline future-poison behavior audit
- Status: executed=`yes`; completed=`yes`; passed=`M3 PASS`
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
  - `data/manifests/pit_data_product_2012_2024_v3/data_product_manifest.json`:
    1,658,525 pre-OOS samples and exactly 50 frozen features
  - `evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json`:
    82,926,250/82,926,250 cells parsed; all 17 fixed checks `PASS`;
    `QUALIFIED`
  - `evidence/pit/behavior/audits/future_poison_real_feature_v1/behavior_manifest.json`:
    all four behavior checks `PASS`; 5,750 protected keys unchanged
  - local grouped executor validation: fixed suite `163/163`; behavior suite
    `18/18`
  - final-OOS market partitions opened: `false`
  - performance metrics computed: `false`
- Current blocker: none for M3. M4 must build and independently verify the Qlib
  data/recorder/backtest mechanics before any baseline is promoted to M5.
- Risk/ambiguity:
  - DataYes descriptions and snapshot hashes cannot prove vendor truth or that
    no off-system future data was consulted.
  - The separately versioned population authority is reconciled exactly but is
    derived from the verified product population; it cannot independently
    prove that the upstream vendor omitted no eligible security.
  - Behavior status is `NOVEL_CANDIDATE`: it proves this exact hash-bound replay,
    not every possible execution.
- Only permitted next action: integrate the qualified pre-OOS product into the
  Qlib Dataset/Recorder/signal/backtest loop and prove reproducibility without
  opening final OOS or reporting Alpha.
- Forbidden until later gates: baseline promotion before M4, PeerLite claims
  before M6, final-OOS access before M8 freeze, production trading and
  “top 1%” claims.

## PIT navigation

- Mode: `VERIFY`
- Target path:
  `sealed DataYes raw daily data -> fixed causal features -> CSI800 PIT universe`
- Fixed audit: `PASS / QUALIFIED`
- Behavior audit: `PASS / NOVEL_CANDIDATE`
- Project M3 decision: `PASS` for controlled development on the exact bound
  pre-OOS data product only
- Claim ceiling remains: `research mechanics`; no Alpha or investability claim
