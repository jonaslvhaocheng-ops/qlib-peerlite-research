# M6.5 有界修复变更设计 v46

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v45；v45及失败审查保留。

## 1. Self-contained bounded bundle

```text
M6_5_pre_m7_quality_gate_v2.json
  609297714b832136a242cb07981e7493ec9780f49caa6f5bd6c2c3f84a0f1d13
m7_initial_screen_budget_binding_v1.json
  595abe97557c43caf99f3a0630ca9d0f443aa6d56558ca12c5a8b1a634b738b6
static_m6_archive_binding_v2.json
  a12cebd94a1bf0da6bbd607f7e95227de3573bd409d16a41ad84711faf5dfad1
m6_archival_replay_binding_v2.json
  0c01c5eb95e71ad8644df09e2eba8d56fc8cb694f8e41ace0021e7f51913aa01
m6_5_bounded_component_design_v4.md
  bcd0418a6b2c36480f7719a8dddc32cdfeaf7f7fda23463a49659baee299a55c
m6_archival_replay_contract_v4.md
  3e288bdb00ea687e406827a226db73952e52b9aeb0cd65a28f800646108a8cc7
m7_bounded_design_v4.md
  0eacdd2eb25706017901ac3e40ec8c7f6149ea90632362ad32e24ca0b9034842
m7_bounded_behavior_matrix_v4.md
  60595e4522abb98fecdf8a505eb633f5938bcfc4d33f4d37be77a1373fa62d40
m6_5_normative_closure_manifest_v4.json
  ed6c7822dc1db8ad93be1ca3f0bf08a0f692ff1da1518762a65da1251a09cf17
```

closure固定11项；v4 specs自包含，不依赖失败版本语义。

## 2. v45 findings closed without scope growth

- static binding v2通过replay binding v2 exact path/file/content SHA固定archive、source tree和
  internal manifest；static verifier仅hash检查，不import或load checkpoint；
- reconciliation在mutation前持久化immutable journal snapshot，使commit-before-receipt crash及
  later suffix恢复有唯一原snapshot；existing receipt后再suffix时直接验证并返回原bytes；
- receipt的before/after/events固定描述original minimal committed prefix，observed ledger单列；
- stable sidecar在每个定义边界核验，尤其temp fsync后紧邻replace前；precommit drift保持ledger/
  receipt未变。威胁边界明确为trusted same-UID operator/cooperative reconcilers，不伪装production
  filesystem security；
- budget roster不只校验8/60，还逐event校验family/model/seed/evaluation/fit/fold/purpose；
- coverage digest逐字段NFC/time normalization/nested length-prefix；所有`-0`规范为`+0`，每个
  binary64中间结果finite check；
- deterministic refit不比较torch container bytes，改为key/dtype/shape/raw tensor bits的canonical
  model-state digest加canonical metadata digest；
- no-fit闭包覆盖全部loaded frozen modules的public/private aliases、saved bound methods、
  partials、wrappers和closure cells，并扫描entrypoint可达call closure；
- external dependency identity绑定pyproject/uv.lock；每个实际imported non-stdlib distribution
  必须在Linux/Python3.11/qlib marker resolution中exact version，无unmapped/ambiguous transitive；
- matrix v4加入existing-receipt suffix NO_OP、lock boundary injection、source tree mutation、
  private alias/closure、unbound dependency、signed zero/overflow/time和semantic checkpoint tests。

## 3. Mainline boundary

仍只有四项：T-known market state、append-only ledger、static M6 archive、single-process no-fit
archival replay；M7仍只设计CCC和Gate两个低复杂度候选。没有新模型、服务、production control
plane或研究方向。M6=`PASS / 6/44`，M7=`NOT_RUN`，future ceiling=`8/60`。

当前只允许两份独立read-only R3 design review；不授权test execution、implementation、replay、
fit、PIT rerun、real data、budget mutation或final OOS。
