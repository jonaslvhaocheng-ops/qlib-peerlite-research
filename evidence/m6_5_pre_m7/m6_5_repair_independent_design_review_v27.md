# M6.5 v27 独立设计审查

- Reviewer：`/root/m65_v25_design_review`
- Subject SHA：`1517a81b731444e5c9a8528566d1e2fe97da9f183b9838441d6706a68051ced9`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=3 / P2=1 / P3=0`

## Findings

1. **[P1] poison horizon冲突。** “目标T当时不可得”允许改2022 row，但whole pre-C table
   digest要求不变；必须选cutoff-only或per-T prefix oracle。
2. **[P1] conditional retry无durable skip。** primary成功后retry未触发，但后续event要求所有
   前序有outcome；需要activation DAG与SKIPPED resolution。
3. **[P1] crash retry与16-fit cap矛盾。** 当前16 fits已用尽剩余预算；replacement必成第17
   fit。应规定任一fit crash使分支HOLD，除非新预算CR。
4. **[P2] 17+4只冻结数量。** 必须绑定exact check-set identity/IDs，无重复无额外。

M7 v5专用结论`NEEDS_CHANGES`。Gate loader、CCC和first-event prerequisites可保留。

只读审查；未编辑文件/ledger，未运行测试、replay、训练、真实数据、PIT或final-OOS。

