# M6.5 v28 独立设计审查

- Reviewer：`/root/m65_v25_design_review`
- Subject SHA：`d9851b71e2688645538b03eadc282480add1706329db0583e66bd5a064f6db39`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=3 / P2=2 / P3=0`

Findings：

1. [P1] §6 replacement遗漏canonical receipt/claim/outcome/terminal slots及synthetic/live guard。
2. [P1] outcome后terminal没有幂等发布/recovery；CCC与Gate未明确映射到两个generation。
3. [P1] `-I`忽略PYTHONHASHSEED，env记录不等于effective seed。
4. [P2] loader可能在parent fsync前接受final目录。
5. [P2] clean env缺attempt-private TMPDIR。

M7 v6专用结论`NEEDS_CHANGES`。17+4、CCC、Gate与special loader主体可保留。

只读；未编辑文件/ledger，未运行测试、replay、训练、真实数据、PIT或final-OOS。

