# M6.5 有界修复变更设计 v47

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v46；失败证据保留。

## 1. Self-contained bundle

```text
M6_5_pre_m7_quality_gate_v2.json
  609297714b832136a242cb07981e7493ec9780f49caa6f5bd6c2c3f84a0f1d13
m7_initial_screen_budget_binding_v2.json
  dd162de1565f887261cebbaef3eeec50c83697125a2acf5adb1546e8e819fcf4
static_m6_archive_binding_v2.json
  a12cebd94a1bf0da6bbd607f7e95227de3573bd409d16a41ad84711faf5dfad1
m6_archival_replay_binding_v2.json
  0c01c5eb95e71ad8644df09e2eba8d56fc8cb694f8e41ace0021e7f51913aa01
m6_5_bounded_component_design_v5.md
  ed8b669af6f9d300b11e22e31c21b5d69e8bdf9c1b1eb4efa701b11b833b0e8d
m6_archival_replay_contract_v5.md
  524d182fbc701cc15be6e47b8c7d7d5043991d347a53538eb5e285eda1499146
m7_bounded_design_v5.md
  de4aa33331443f7e7e97470d401a79d8d8b1e631163800c36a2ddabffe9f6715
m7_bounded_behavior_matrix_v5.md
  c964e2a0cad1e088817c30e974600cf7928b1ff59594508143a4ffc32c837fe9
m6_5_normative_closure_manifest_v5.json
  a2a2cc541133f255d1197b1c9af28c7e5f30e6841fecdb672ff5873280487973
```

## 2. Four narrow v46 closures

- snapshot slot exact由run-intent SHA+journal snapshot SHA派生，固定在ledger sibling control root；
  snapshot新增ledger-before SHA/bytes/counts、full source IDs及missing subset/digests；
- receipt slot/path exact；before取snapshot ledger-before，after取minimal committed prefix，
  committed events exact等于snapshot missing set；同journal later append产生new slots且old bytes不变；
- budget binding V2自身冻结两candidate的evaluation ID/purpose及16个fit ID/fold/purpose，reconciler
  不再从caller解释这些字段；
- source available time在任何比较前要求timezone-aware且不含nonzero submicrosecond precision；
- replay no-fit不再枚举有限alias类型，而从固定roots用`gc.get_referents`遍历全部reachable objects，
  fail-closed覆盖defaults、containers、descriptors和callable instances。

## 3. Mainline boundary

仍只有T-known state、append-only ledger、static archive、single-process no-fit replay；M7只含CCC和
Gate两个候选。无新模型、服务、生产控制面或研究方向。M6=`PASS/6/44`，M7=`NOT_RUN`，future
ceiling=`8/60`。当前只允许独立read-only design review；不授权test/implementation/replay/fit/
PIT/real data/budget/final OOS。
