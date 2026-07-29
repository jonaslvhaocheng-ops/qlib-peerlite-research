# M6.5 v28 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`d9851b71e2688645538b03eadc282480add1706329db0583e66bd5a064f6db39`
- Reviewed revision：`175`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=4 / P2=1 / P3=0`

Findings：

1. [P1] official behavior v1每manifest只有一个protected_through，v28多T request不兼容，且需
   probe_type=FUTURE_POISON；补充字段应放外部receipt。
2. [P1] linear outcome后缺幂等terminal reconciler。
3. [P1] 两个隔离候选与“失败即run abandoned”关系未冻结。
4. [P1] M7 v6替换v5后丢失create/reload checkpoint bindings、standardizer和完整CCC dtype合同。
5. [P2] completion marker是否在inventory及其0440 mode未定义。

M7 v6专用结论`NEEDS_CHANGES`。

只读；未编辑文件/ledger，未运行replay、训练、真实数据、PIT CERTIFY或final-OOS。

