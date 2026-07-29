# M6.5 有界修复变更设计 v45

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v44；v44及其`NEEDS_CHANGES`审查永久保留。

## 1. Self-contained normative bundle

```text
M6_5_pre_m7_quality_gate_v2.json
  609297714b832136a242cb07981e7493ec9780f49caa6f5bd6c2c3f84a0f1d13
m7_initial_screen_budget_binding_v1.json
  595abe97557c43caf99f3a0630ca9d0f443aa6d56558ca12c5a8b1a634b738b6
static_m6_archive_binding_v1.json
  eb960cde71af349336fb26a0094161495a7ebe2a11901f96ce08d788f32e894f
m6_archival_replay_binding_v1.json
  b2474a6b5e76f39e79bfb3a3e412decd5bcae46b1603cc4e5a3c2d6e863fa4ae
m6_5_bounded_component_design_v3.md
  710e4085c2f32693239b74de2f7024ecd0ed03936f014b5312b392867d1b1073
m6_archival_replay_contract_v3.md
  5c5d8ba622fdf2bc16f2a75875e83683344183e3da5cf3d260af63058c00d9dc
m7_bounded_design_v3.md
  b91ff4af6050a3077333a252e170b8b587a77f6af84c7d5c2d9c9ec75ebfba25
m7_bounded_behavior_matrix_v3.md
  fdfe1aadda52f8248a85a99840f1c7aec7814e69e98f958d9976e6069b334eb6
m6_5_normative_closure_manifest_v3.json
  178c65868f252f0d6bd18666a5602832d9264d59c90d696242a020771f32c661
```

closure manifest逐项固定11个normative inputs。本文不隐式继承v44文字；v3 specs与三个external
bindings构成完整实现设计。

## 2. v44 findings closed

- stable lock固定为永不replace/unlink的`<ledger>.reconcile.lock`；以FD/path dev+inode验证，
  从ledger read前持有至commit、receipt或recovery readback后，避免ledger inode replace竞态；
- `BudgetLimitBindingV1`把external path/file/content SHA和M6 `14328 bytes, 6/44`、future
  `8/60`绑定进RunIntent、journal、retained event及typed receipt；
- `StaticM6ArchiveBindingV1`固定gate、mechanics、manifest、verification、journal、execution
  spec以及9324-byte `4/29`和14328-byte `6/44`两个prefix；
- `M6ArchivalReplayBindingV1`固定archive/source tree/internal manifest、M6 execution spec、
  Python/packages/CUDA/RTX4090及historical receipts；CLI不再接受caller-paired expected hashes；
- replay验证full extracted tree、全部transitive project module origins、exact dependency
  versions，并在checkpoint load前安装fit及alias fail-fast guard；
- reconciliation receipt slot由run-intent SHA、journal snapshot SHA及最小committed ledger
  prefix SHA派生；后来journal append不改变原commit/recovery identity；
- market-state revision选择取`available_time <= T close`的latest，equal-time只允许byte-identical
  dedup；selection coverage digest固定revision/time/source hash；
- future derived contract/RunIntent/events/checkpoint必须在首event前绑定state product、source
  manifest、PIT parent、calendar和两个builder hashes；
- reducer固定stable instrument-order IEEE binary64 left fold、每步舍入、numeric median和
  length-prefixed instrument digest；
- CCC固定一个完整date对应一个optimizer step、每epochdate升序无PRNG，checkpoint/refit绑定
  date-order digest且bitwise exact；
- matrix v3增加state substitution、eligible revision conflict、stable-lock third contender、
  later-suffix recovery、wrong caller pairing、transitive imports、fit alias、last-bit reducer、
  one-date step、refit bitwise及Gate permutation/alignment负例。

## 3. Mainline and authority boundary

normative implementation仍只有纯market-state、append-only ledger/static archive和单进程archival
replay；不重新引入privileged/multi-process production control plane。M6保持`PASS / 6/44`；
M7=`NOT_RUN`，future ceiling=`8/60`。所有新binding均标记design-only，不是执行authority。

当前只授权两份新的独立read-only R3 design review。不得执行测试、修改产品实现、真实replay、
fit、PIT rerun、real-data extraction、budget mutation或final-OOS。
