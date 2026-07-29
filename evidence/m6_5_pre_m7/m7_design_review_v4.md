# M7 v4 独立设计审查

- Subjects：`m7_change_design_v4.md`、`m7_behavior_to_test_matrix_v4.md`
- Reviewers：`/root/m65_v25_design_review`、`/root/m65_v24_adversarial_review`
- Verdict：`NEEDS_CHANGES`
- Scope：design-only；不授权M7。

## 已关闭

- exact V2 lineage；
- generic Gate fail-closed与专用factory/capability；
- 固定`2*sigmoid`、encoder后/assignment前注入；
- cost/benchmark first-event prerequisites；
- 2 candidate/16 fit，到`8/60`；
- matrix owner stage。

## Blockers

1. qualification envelope缺完整production PIT/behavior predicates；
2. canonical CCC版本缺Lin CCC公式；
3. capability-scoped checkpoint reload未冻结；
4. underlying PIT protected projection、run rotation与directory transaction仍未PASS。

