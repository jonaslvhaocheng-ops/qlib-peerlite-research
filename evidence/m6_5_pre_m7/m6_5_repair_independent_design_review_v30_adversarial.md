# M6.5 v30 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`28bab313bc07f4d9ffc838a0256f8dbc8f71fb86df320dc31f206c87e7f1746b`
- M7 v8 SHA：`9a5a3c5d1034efdb947f744d124a80e8657ee9c303f6021ffaff02dc77ebbebc`
- Matrix v8 SHA：`932ac1b4dc61e58bf1fd860402d64c5e7d39eafceb37b3563c61c6cd281a7d89`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=4 / P2=3 / P3=0`

Findings：

1. [P1] official state flatten把`feature_value_json`写为object，违反上游behavior closed schema的
   scalar要求；adapter bindings也未映射到官方既有slots。
2. [P1] AP001–AP004仍是status-only：缺per-product projection、canonical key/value/logical
   digest算法、original/probe逐产品证据与execution/report/environment receipt。
3. [P1] capacity admission未汇总active reservations，可在正常并发下超卖。
4. [P1] 超cap partial attempt要求清理，但GC又禁止处理未COMMITTED transaction，形成不可清理
   orphan；必须区分owner abort cleanup与post-commit GC。
5. [P2] security-lifecycle authority不是实现就绪closed schema。
6. [P2] review receipt的`reviewed_at > durable publication time`谓词没有可信publication receipt，
   无法机械验证。
7. [P2] `authority root hash`边界不明确；若包含稍后写入的registration会重新形成hash环。

已确认可保留：单向generation依赖、worker lease与terminal recovery、双generation、nested
durability/0440、committed staging unlink-only、`-S` bootstrap、缺lifecycle证据时HOLD、state
join/standardizer、Gate/CCC、first-event prerequisites与`6/44→max8/60`边界。

M7 v8专用结论：`NEEDS_CHANGES`。只读；未编辑文件/ledger，未运行replay、训练、真实数据、
PIT执行/认证或final-OOS。
