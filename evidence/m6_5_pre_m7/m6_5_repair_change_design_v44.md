# M6.5 有界修复变更设计 v44

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v43；v43及失败审查保留。

## 1. Exact self-contained bundle

```text
M6_5_pre_m7_quality_gate_v2.json 609297714b832136a242cb07981e7493ec9780f49caa6f5bd6c2c3f84a0f1d13
m6_5_bounded_component_design_v2.md fea250b02703252807744d9fbe77cabd7c9f3209b87266f009747d28688224c4
m6_archival_replay_contract_v2.md 89467e69561313942270f8cf650d452fdb4edc951a84178b616d586f8c2030a5
m7_bounded_design_v2.md 519ad1864a50a132e9b8abb8fcae0bb16831364bd380f116ff75f1d52ff4e3fb
m7_bounded_behavior_matrix_v2.md a0e2e1761302255de1b0be968b205dd89482281d154f6e05f96c09981759edfc
m6_5_normative_closure_manifest_v2.json bebed2e4e72715d919b114fa718298674158dec2c11f578385d27d26c5340aa5
```

closure manifest列出全部8个normative inputs的repository-relative path与完整SHA。本文不继承v43
段落；无placeholder、无“保留现有字段”、无隐式Base或旧control-plane dependency。

## 2. v43 finding closure

- current gate v2唯一允许两份独立design review；PASS只路由test-design；
- trusted server builder固定T-close时钟、sealed PIT refs、safe normalized status allowlist、
  source manifest、float64 formulas、current-row revision和universe poison；
- M6 close prefix exact冻结为SHA、14328 bytes和6/44；
- RunIntent、journal/retained events及reconciliation receipt V3 exact schemas自包含；
- ledger使用whole-file temp+fsync+atomic replace+directory fsync，定义concurrency及
  crash-after-ledger-before-receipt恢复；
- archival replay冻结module origin/blob、historical runtime identity、实际CUDA tensors、
  no-fit AST/runtime和完整V2 receipt schema；
- CCC使用完整date batch、unique date等权objective和deterministic sampler；
- Gate statistics冻结float64、ddof0、unique training dates与float.hex serialization；
- 8/60阶段只允许SCREEN_PASS/HOLD；deterministic refit只做wf_2018复现且不参与screen；
- screening冻结weekly excess、IR、compound return、fold concat和0/5-of-7/stress边界；
- matrix v2覆盖import、PIT poison、ledger crash/concurrency、archive/import/runtime/CUDA、
  CCC partition、Gate ddof、screen boundary和静态OOS拒绝。

## 3. Mainline and boundaries

normative implementation仍只有纯market-state、append-only ledger/static archive和单进程archival
replay；不重新引入production control plane。M6保持`6/44`；M7=`NOT_RUN`；future ceiling
`8/60`。当前不授权test execution、implementation、real replay、fit、PIT rerun、real-data
extraction、budget mutation或final-OOS。
