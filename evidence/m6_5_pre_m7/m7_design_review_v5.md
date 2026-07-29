# M7 v5 独立设计审查

- Subjects：`m7_change_design_v5.md`、`m7_behavior_to_test_matrix_v5.md`
- Reviewers：`/root/m65_v25_design_review`、`/root/m65_v24_adversarial_review`
- Verdict：`NEEDS_CHANGES`
- Scope：design-only；不授权M7。

Blockers：

1. exact 17+4 check-set identity未绑定；
2. behavior official schema与test-only/issuer要求不一致；
3. current 16-fit cap不允许replacement fit；
4. underlying conditional skip与PIT protection horizon未关闭。

CCC、Gate factory/loader、first-event prerequisites和`6/44 -> 8/60`边界保留。

