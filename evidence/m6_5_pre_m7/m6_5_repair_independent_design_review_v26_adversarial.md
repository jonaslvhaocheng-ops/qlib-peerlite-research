# M6.5 v26 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`44e9a2bbf1bce5c7fbd3cc691925c072b2a78e7642e4ba578a3ae1da7b3d81f8`
- Reviewed route revision：`167`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=5 / P2=2 / P3=0`

## Findings

1. **[P1] canonical composition丢失规范。** 除目录事务外，support_start、
   MarketStatePolicyV3 identity/date/window及replay staging clauses也因模糊“对应段落”
   replacement丢失；需要自包含设计。
2. **[P1] post-C protected oracle矛盾。** pre-C不可得delist/status/exit值被保留，导致
   future-poison必然改变aux digest；必须逐表availability projection。
3. **[P1] execution lease未绑定真实worker与前序outcome。** parent死后worker可能继续，而
   recovery启动下一attempt；E2也未要求E1 durable outcome。
4. **[P1] qualification可退化为status-only。** envelope未冻结
   `QUALIFIED/PASS/PRODUCTION_CLI/test_only=false/FULL_TRAINING_INPUT/17 checks`及behavior
   四项、report/content/parent exact bindings。
5. **[P1] M7 v4丢失CCC数学公式。** 只保留dtype，未保留Lin CCC分子/分母与`1-ccc`。
6. **[P2] active-run无法轮换。** no-replace fixed slot无合法generation迁移。
7. **[P2] staging cleanup权限不可执行。** dirs `0550`后owner不能unlink children。

M7 v4专用结论为`NEEDS_CHANGES`；还需专用capability-scoped checkpoint reload。预算、
first-event screening prerequisites、V2 lineage、固定Gate和stage ownership应保留。

审查只读；未编辑文件/ledger，未运行replay、训练、真实数据、PIT CERTIFY或final-OOS。

