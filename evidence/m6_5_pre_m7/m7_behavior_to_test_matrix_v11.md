# M7 behavior-to-test matrix v11

Base：v10 matrix SHA
`3dc5379980d3ac0cf20836576668ddcbe670100a2f5da4eda9a6250c4760e0a4`。
保留v10未列出的v9基础行；以下取代v10增量：

| ID | Owner | Oracle |
| --- | --- | --- |
| POISON-01 | M6.5_CONTRACT_ONLY | changed set=value diff set；clocks/identity不变；clock-only拒绝 |
| POISON-02 | M6.5_CONTRACT_ONLY | null DELIST有nonnull trusted observation time；缺证据HOLD |
| AP-01 | M6.5_CONTRACT_ONLY | closed invocation/六manifests、snapshot rebuild、非空expected axes |
| AP-02 | M6.5_CONTRACT_ONLY | AP005每metric保存official/state-product/equal并重算 |
| LIFE-01 | M6.5_CONTRACT_ONLY | parent audit/population/security/date axes exact bindings |
| LIFE-02 | M6.5_CONTRACT_ONLY | issuer authority exact授权evidence statement/file/logical digest |
| LIFE-03 | M6.5_CONTRACT_ONLY | SLA006 exact security×date records及schema/key/value/logical digest |
| RES-01 | M6.5_CONTRACT_ONLY | 五marker+absence/cleanup strict schemas及canonical publication |
| RES-02 | M6.5_CONTRACT_ONLY | malformed RESERVED保守计cap并阻止admission；RELEASED全链才免计 |
| AUTH-01 | M6.5_CONTRACT_ONLY | RunAuthority closed schema禁止registration/commit/receipt回边 |
| SCORE-01 | M6.5_CONTRACT_ONLY | 两expected merged + 十四per-fold replay outputs；canonical date后验window |

仍只实现`M6.5_CONTRACT_ONLY`；M7 implementation/fit/final-OOS未授权。
