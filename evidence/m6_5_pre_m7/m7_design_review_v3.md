# M7 v3 独立设计审查

- Subjects：
  - `m7_change_design_v3.md`
  - `m7_behavior_to_test_matrix_v3.md`
- Reviewers：
  - `/root/m65_v25_design_review`
  - `/root/m65_v24_adversarial_review`
- Verdict：`NEEDS_CHANGES`
- Scope：design-only；不授权implementation、fit、预算或final-OOS。

## Blockers

1. M7 v3引用已被canonical v25取代的PreOOSAuxSnapshotV1。
2. fixed PIT + behavior receipt qualification envelope和verified-product handoff未定义。
3. 专用Gate factory/capability、`2*sigmoid`结构、注入点与checkpoint schema未冻结。
4. claim-to-outcome execution ownership与crash terminal不完整。
5. benchmark/cost证书未成为first-fit admission前置。
6. CCC production dtype未冻结。
7. behavior matrix没有区分M6.5 contract tests、M7 implementation tests和real acceptance。

预算边界 `6/44 -> +2 candidate/+16 fit -> 8/60` 本身可保留；任何组合或额外fit继续要求新的
用户预算CR。

