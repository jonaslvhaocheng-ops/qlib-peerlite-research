# M6.5 v31 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`f83f2b51861c55f2abd96b051ef6e5546a43c5eff47128aa69c4125f9c28ca87`
- M7 v9 SHA：`ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94`
- Matrix v9 SHA：`0088cf25f5328b4c128d42d4b51772c21648609c41bfaf419fefb19c58841d58`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=5 / P2=2 / P3=0`

Findings：

1. [P1] 三列ScoreReplay可拒绝合法五列输入或允许model/fold串包；还需exact七fold集合/窗口/SHA。
2. [P1] AP V2缺closed invocation/product manifests、official snapshot parent edges、非空/expected
   coverage及official CSV→state product cross-check，可对相同空/无关manifests伪PASS。
3. [P1] lifecycle positive fixture缺source projection、row evidence preimage/locator、key digest、
   calendar/session boundary及exact prediction-time population。
4. [P1] lifecycle statement内issuer/evidence paths未禁止指回authority/receipt/container，角色间仍
   可造跨artifact hash环。
5. [P1] owner-abort未持target parent publish lock，也未在同一临界区验证PREPARED/final/internal/
   sibling全部不存在，可能误删可恢复staging。
6. [P2] RELEASED必须验证完整hash chain/cleanup/zero-staging；malformed marker不能免计费。
7. [P2] official FUTURE_POISON whole-record `available_time`与逐field supplement未映射；需冻结
   raw record grain/key/sample/available-time adapter。

已确认通过：cooperative reservation不超卖、未RELEASED持续计费、main generation DAG、
official scalar/slots、review hash DAG及M7未授权边界。

M7 v9专用结论：`NEEDS_CHANGES`。只读；未编辑文件/ledger，未运行replay、训练、真实数据、
PIT executor/CERTIFY或final-OOS。
