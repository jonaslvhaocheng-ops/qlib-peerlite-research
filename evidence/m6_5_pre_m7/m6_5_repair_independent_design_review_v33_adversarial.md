# M6.5 v33 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`3db1bb4f576f0b6a557a014185c126b067395a07522cf38ee9f610595b8808d7`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=5 / P2=2 / P3=0`

Findings：

1. reservation目录0550使append-only lifecycle不可执行。
2. staging/lease roots及attempt-derived unique paths未固定，可能并发或误删。
3. marker外部inventory/policy/receipt只有SHA无locator。
4. plan自由IDs仍可藏downstream path/hash回边。
5. lifecycle关键wrapper/availability/authority/receipt schemas和evidence digest projection未闭合。
6. synthetic purpose未限制event types/caps。
7. poison需按field dtype/domain解析并要求semantic non-noop。

已关闭：保守charge、RELEASED原则、clock-only/null、AP空输入/AP005、axes方向及score grain。
M7 v11：`NEEDS_CHANGES / NOT_AUTHORIZED`。只读，无ledger/replay/训练/PIT/final-OOS。
