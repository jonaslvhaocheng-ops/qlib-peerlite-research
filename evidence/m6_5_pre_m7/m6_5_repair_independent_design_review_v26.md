# M6.5 v26 独立设计审查

- Reviewer：`/root/m65_v25_design_review`
- Subject SHA：`44e9a2bbf1bce5c7fbd3cc691925c072b2a78e7642e4ba578a3ae1da7b3d81f8`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=4 / P2=1 / P3=0`

## Findings

1. **[P1] Composite遗漏目录事务。** v26继续清单没有v25 §5.2，却继续调用
   `PreparedDirectoryTransactionV1`；claim schema、lock、crash recovery和completion不再
   normative。
2. **[P1] protected payload混入事后值。** `out_pub>=C,out_eff<C`、post-C status和无可得
   clock的delist原值进入protected logical digest，正确future poison也会改变digest。
3. **[P1] nullable complete status无唯一结果。** complete event的name为null/空/NFC空时，
   forbidden/unknown/fail未冻结。
4. **[P1] active-run无下一代。** fixed no-replace `active-run.json` 被R1占用后，没有R2的
   append-only generation/head transition；unused events也无canonical object。
5. **[P2] replay attempt无持久状态。** child执行后、output publication前crash时，无法判断
   是否允许重放或必须换attempt。

M7 v4已关闭V1/V2、Gate capability和test owner，但继承上述PIT projection、run rotation与
目录事务问题，专用结论仍为`NEEDS_CHANGES`。

审查只读；未编辑文件/ledger，未运行测试、replay、训练、真实数据、PIT或final-OOS。

