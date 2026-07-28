# True Status Card

- Master plan: `docs/MASTER_PLAN.md`
- Current phase and track: `M3-STRICT`
- Last actual action: strict research-contract freeze and validation
- Status: executed=`yes`; completed=`yes`; passed=`M2 PASS`
- Strongest current evidence:
  - `evidence/gates/M0_environment_gate.json`: M0 `PASS`
  - `evidence/gates/M1_source_gate.json`: M1 terminal `PASS`
  - `evidence/gates/M2_contract_gate.json`: M2 terminal `PASS`
  - `contracts/immutable/research_contract.json`: frozen contract
    `qrc-v2-26151205fba66ab185fe29ea252ecce0`
  - `contracts/immutable/contract_validation.json`: strict validator `PASS`
  - `evidence/data_sources/universe_verify_20260728_01/universe_verify.json`:
    exact CSI300/CSI500 identities and effective intervals are supported
  - `evidence/data_sources/core_universe_clock_verify_20260728_02/core_universe_clock_verify.json`:
    announcement/effective clocks supported with zero missing, late or duplicate
    membership records
  - `evidence/data_sources/datayes_public_dictionary_20260728_01/datayes_public_dictionary.json`:
    official public semantics support unadjusted 15:15 daily quotes and
    announcement/effective constituent clocks
  - `evidence/data_sources/auxiliary_source_verify_20260728_05/auxiliary_source_verify.json`:
    auxiliary source candidates, coverage and conservative status clocks pass
  - `data/manifests/source_snapshot_20260728_v1/snapshot_bundle_manifest.json`:
    all eight immutable source manifests and the CSI800 universe hash are bound
  - `evidence/data_sources/sealed_snapshot_verify_20260728_v1/sealed_snapshot_verification.json`:
    independent file-hash, row-metadata, manifest, universe and read-only checks pass
  - local and server: Ruff pass, Pytest `19 passed`
  - server RTX 4090 CUDA forward/backward pass
- Historical-only evidence: earlier database reports under
  `/Users/jonas/Documents/预期因子/outputs`; they remain historical until rebound
  into this project's source certificate.
- Current blocker: none for M2. M3 requires the exact derived training product,
  a fixed artifact audit and a behavior-based future-perturbation audit.
- Risk/ambiguity: DataYes field names, comments, coverage and `UPDATE_TIME` do
  not prove historical market availability, revision retention or PIT eligibility.
- Only permitted next action: construct the declared data product from
  `source_snapshot_20260728_v1`, preserve the final-OOS seal, and execute the
  point-in-time fixed and behavior audits.
- Forbidden until M3: empirical fitting, real backtesting, final-OOS opening and
  performance claims.

## PIT navigation

- Mode: `VERIFY`
- Target path:
  `DataYes/abmdata raw daily data -> fixed causal features -> CSI800 PIT universe`
- Target claim: eventual `MARKET_RECONSTRUCTIBLE`
- Positive ceiling now: M1 source/snapshot `PASS`; never PIT `PASS` or
  `QUALIFIED` until fixed and behavior audits pass on the derived training product
