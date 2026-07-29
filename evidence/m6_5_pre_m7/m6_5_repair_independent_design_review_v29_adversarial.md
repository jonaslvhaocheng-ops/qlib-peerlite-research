# M6.5 v29 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`be21d2301fd8911f1dcc620ade824d4e6e2fc6b0dcc9ddb85965024836fc4d1e`
- Reviewed revision：`179`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=2 / P2=2 / P3=1`

Findings：

1. [P1] official B004没有aux/population/state prefix的可执行证明面；需canonical flattening或独立
   aux-prefix verifier。
2. [P1] BehaviorAvailabilitySupplementV1与IndependentReviewReceiptV1缺closed schema。
3. [P2] md_security list/delist只有不定时availability，不能从event date推断；缺证据应禁止
   qualification。
4. [P2] staging cleanup/capacity在v29替换中丢失。
5. [P3] sibling COMMITTED未固定0440。

M7 v7专用结论`NEEDS_CHANGES`。

只读；未编辑文件/ledger，未运行replay、训练、真实数据、PIT CERTIFY或final-OOS。

