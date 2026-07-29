# M6.5 有界修复变更设计 v43

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v42；旧canonical与旧control-plane specs全部保留为历史证据。

## 1. Mainline correction

v43不再继承v42或任一旧change-design段落。它是基于已通过architecture v28的self-contained
replacement：

```text
trusted single-repository research server
pure market-state library
append-only trial-ledger reconciler
read-only M6 archive verifier
one trusted single-process archival replay command
bounded M7 CCC/Gate design and test matrix
```

明确排除daemon、privileged helper、multi-process supervisor/worker、FD capability passing、
syscall sandbox、generic capacity protocol、nested publication transaction和live run-authority。
这些历史规范不删除，但不再是M6.5设计、实现或测试的前置条件。

## 2. Exact normative bundle

```text
m6_5_bounded_component_design_v1.md 48ff7e36c02d9019dd6807ccdd01820f9cef483c47868781dbe0740503ccb8d7
m6_archival_replay_contract_v1.md d10272b383f3d61d565292470755bb1ae23c751c47858c92fb036d180ab2d9e8
m7_bounded_design_v1.md 9c6c2b71441b63a364f636a57e938942cbc6b883ed115a1b994af4a921d78113
m7_bounded_behavior_matrix_v1.md 0d03cc8d1ab187d4f74fdb17ec44f33267fb7b8487c1d4e118f9e9a1eda4014a
m6_5_normative_closure_manifest_v1.json 7611bbb5ce01bf9e163fa80d823029f4dac97b4fc9fb139dddb79a4d6eeb7b8c
```

closure manifest逐项冻结mainline scope、architecture、change authority、current gate和上述四个
self-contained specs的repository-relative path与完整SHA。不存在隐式Base、section inheritance或
历史path推断；任一entry hash漂移使设计STALE。

## 3. Four deliverables

1. **T-known state**：纯函数allowlist、当日population、四维state、exact-date join和
   future-poison invariance。
2. **Ledger/archive**：保持M6 `6/44` byte prefix，started-event幂等追加，static M6 chain验证。
3. **Archival replay**：单进程从只读frozen inputs加载2×7 checkpoints，CUDA predict-only exact
   score comparison，只向一个原先不存在的output directory写一个v2 receipt。
4. **M7 design**：CCC和Gate两个隔离候选，固定公式/结构/预算/晋级与组合触发；当前只做contract
   tests，不做M7 implementation或fit。

## 4. Review-to-test transition

本设计只有在两份独立R3 review均PASS后才允许进入test-design。test-design必须把bounded matrix
中的M6.5 synthetic/static/contract rows映射到具体pytest名称、fixtures、red reason和side-effect
oracle。真实CUDA archival replay保留到E2E acceptance，不作为unit test。

## 5. Boundaries

M6 PASS且prefix保持`6 candidate / 44 fit`；M7=`NOT_RUN`；future ceiling仍为`8/60`。设计PASS
不授权实现、测试执行之外的副作用、真实replay、fit、真实数据重新抽取、PIT重跑、budget mutation、
final-OOS或组合模型。
