# M6.5 v33 独立设计审查

- Reviewer：`/root/m65_v25_design_review`
- Subject SHA：`3db1bb4f576f0b6a557a014185c126b067395a07522cf38ee9f610595b8808d7`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=3 / P2=2 / P3=0`

Findings：

1. marker目录0550无法追加；receipt无path；parent SHA的file/canonical domain不明。
2. authority/registration重复字段未要求相等，plan只有SHA无path及purpose交叉约束。
3. delist observation不可得即active=false会造成未来退市证券历史提前剔除；availability schema缺失。
4. oversized orphan不能满足recovery RESERVED expected=cap。
5. PREPARED后的same-claim nested recovery未自包含。

已关闭：value-only poison/null clock、dual AP005、2 merged+14 per-fold、canonical window order。
M7 v11：`NEEDS_CHANGES / NOT_AUTHORIZED`。只读，无ledger/replay/训练/PIT/final-OOS。
