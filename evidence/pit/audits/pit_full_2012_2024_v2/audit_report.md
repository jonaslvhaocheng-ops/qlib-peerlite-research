# Point-in-Time Data Audit

- Report schema: `pit_audit_report_v1`
- Audit ID: `pit-audit-v1-08e3a3e299b530191bac7169d8b14369`
- Manifest content SHA-256: `08e3a3e299b530191bac7169d8b14369259a6cbc8285918011cc0215c88b16d0`
- Result: **PASS**
- PIT qualification: `QUALIFIED`
- Claim: `MARKET_RECONSTRUCTIBLE`
- Coverage: `FULL_TRAINING_INPUT`
- Contract: `qrc-v2-5b7353756e0fded36622a6946011f77a`
- Contract adapter: `quant_contract_v2`
- Execution boundary: `PRODUCTION_CLI`
- Matched review-authority anchor: `8d156e0d28cc67a086b7a5fd815de38c4e5deaa1adbb211f4e9dd5c1e0114f9a`
- Matched semantic-review receipt anchor: `03c7e25ee57a8f0dd3a3e292a41f5b44bd5c875f37ffe757f7a848e817115362`
- Matched interval-authority anchor: `1ce3736738c0339d4742d08b6ce6131b3abfe83f52b082b294bda842ca3ba242`
- Rows: `82926250`

## Decision

The exact frozen input is PIT-qualified for the stated claim. This does not authorize training or trading.

## Findings

- FAIL checks: `none`
- NEEDS_EVIDENCE checks: `none`
- Total reported issues: `0`

## Lineage

| Artifact | Version | Verified SHA-256 |
| --- | --- | --- |
| `calendar` | `planned-v1` | `5386ff6e8fd380c891b8e78fbe14677b9cc59dbaabb403c4539c411dccb4be52` |
| `contract_validation` | `quant_contract_v2` | `44d37fc14e33e612e6e33670542ea90b18305ac156eaf0ba2b5f06b5e479de43` |
| `data` | `pit_consumed_values_full_2012_2024_v2:training_evidence` | `1629922761fda6fd4c2a104f652742a201e3d88c7c395fd2a0a52a4b344167b4` |
| `dictionary` | `qlib-peerlite-derived-feature-semantics-v1` | `24bb2d713f8260d5b3964b94b4fd97ec212bf51d349d5bebb6049aded7dcec55` |
| `label_definition` | `n/a` | `65a8052043903ef6ca912b933f7ec423033860810d12212482fe8438d9d4f7aa` |
| `label_interval_authority` | `1` | `1ce3736738c0339d4742d08b6ce6131b3abfe83f52b082b294bda842ca3ba242` |
| `label_schedule` | `1` | `9ccaa79abc684cfd768353662ded1474c20ca32ea50ef32517788af3b17a41dd` |
| `matrix_manifest` | `1` | `40959374b00716c8187020116b2381e24b764c75e3107d7fc7adf5cf88618e21` |
| `population_manifest` | `csi800-pit-eligible-development-population-20260728-v2` | `d4511fb2f8c668ed5d442cc09326d794e4075cb3915f7950ceb5d10caf67218a` |
| `population_source` | `csi800-pit-eligible-development-population-20260728-v2` | `151ea4f8805458f46ff8f8203d5b013b0d74f9f58790e7b0b83baaa33ee3c41f` |
| `research_contract` | `n/a` | `2f99bfb56929c732b24efe5da25c6c9d2786773ce95af347099228a521a9502c` |
| `review_authority` | `1` | `8d156e0d28cc67a086b7a5fd815de38c4e5deaa1adbb211f4e9dd5c1e0114f9a` |
| `schema` | `n/a` | `0ab043e50eef4afdcb35de39ce0f9cbb7354f375adc85f1ebcf3d21d36b22e46` |
| `time_semantics` | `n/a` | `85ac6bbe59f14464d9517edf0c8a44e49e3713372c4223ee39445ae097f4f98a` |

## Checks

| ID | Result | Rows | Issues | Evidence digest |
| --- | --- | ---: | ---: | --- |
| `I001` Input, hash, version, and coverage integrity | **PASS** | 82926250 | 0 | `78d4734f91a0110cf6a51c5fa14d92b8934ce395048438381465b06c4272f48c` |
| `I002` Frozen contract and source/label binding | **PASS** | 82926250 | 0 | `9cd1351b9753b526e9363e75d265578a8270851efe71d4df4a60dd62217f9ed9` |
| `S001` Exact schema and field-semantic coverage | **PASS** | 82926250 | 0 | `45ce29ad2450e6852a10373d9770cd1d081d464a569edeabcc612abed7bfa23a` |
| `T001` Distinct time roles, timezone, and tzdb evidence | **PASS** | 82926250 | 0 | `339d4c1d324aeb83e75419fbd707bea06a990e796c51f6ba0d6dc41fbd042c31` |
| `T002` Feature availability and execution ordering | **PASS** | 82926250 | 0 | `5fd27bfe17d784b085aa8b91c8f8d5d6d68171e6b3b8331529d9eea09694633b` |
| `T003` Revision and vintage as-of correctness | **PASS** | 82926250 | 0 | `23bb54ba57f89b0c3bd38f1024a39276325c6c767f617ec4cf58984e7c3aec92` |
| `U001` Point-in-time universe membership | **PASS** | 82926250 | 0 | `9b6c9ae014462bf20b8cf70a026eb630896466bbd599915c7e7e59eebc172a10` |
| `U002` Population, survivor, and delisting coverage | **PASS** | 82926250 | 0 | `0991cc5cba71d9d7246d356aa8d80e7765c88d2ca7577428d94cab89f412189e` |
| `C001` Versioned exchange calendar and session alignment | **PASS** | 82926250 | 0 | `5c32817f644ac1d419e709471cca153e8e224e7d4c54afa0c1a1198073f7fc9b` |
| `M001` Stable security identity and valid-time mapping | **PASS** | 82926250 | 0 | `ef76db81d64015df7a1eeb61b9ae2ef6a51bc2b5b1725d06f9921abe65f52198` |
| `A001` Corporate-action adjustment correctness | **PASS** | 82926250 | 0 | `b94656c14237d4aec0757ed05d8e0a6f2b09f6ce84f560a7a76ffd5d8b955935` |
| `H001` Halt, quote-resume, and trade-resume handling | **PASS** | 82926250 | 0 | `e384705f36fc9657e58e3caad700f9258e5eea8facfd7458a1b446d601aabed4` |
| `Q001` Primary-key, declared-grain, and matrix completeness | **PASS** | 82926250 | 0 | `84dccd5159c7b1c8b9c95dbdf9cd016b6fafea8af000b1d9387c9526d95fbcba` |
| `Q002` Required values, types, and finite numerics | **PASS** | 82926250 | 0 | `34469fbc55d9266dda2c53e008ea9d39ef975a96f1ce3250f1a8b937237d4c6b` |
| `Q003` Declared value-domain and anomaly checks | **PASS** | 82926250 | 0 | `106ff102116a2e2bb2f242d0f09689e57c198171593c7f3f0ae529467a311065` |
| `L001` Label definition, interval order, and contract hash | **PASS** | 82926250 | 0 | `d5af2673f5a6806a3147a4ce50efa4a7eccdbdf14fd76a558c00a1988ca849ad` |
| `L002` Cross-split label overlap and purge evidence | **PASS** | 82926250 | 0 | `0fb1debc9f30b51b0ddae735f8c391ecf2fca5d9e5a8ac19738e2e58611576c8` |

## Blocking evidence

No blocking evidence.
## Boundary

Data eligibility only: no model training, alpha calculation, deployment approval, or capital decision is performed.

Next action: Preserve and hand off the immutable PASS manifest.
