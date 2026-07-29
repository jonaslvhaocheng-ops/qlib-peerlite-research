# M6.5 v32 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`fbc5d53c40589787c832b54585dd2a07355ba07c4539d4f2de9cc785d7335cba`
- M7 v10 SHA：`bfa95544be056fb7d2874a072b3feabbe15f3665064775bcdace194383917bb4`
- Matrix v10 SHA：`3dc5379980d3ac0cf20836576668ddcbe670100a2f5da4eda9a6250c4760e0a4`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=5 / P2=1 / P3=0`

Findings：

1. [P1] v32/M7 v10重新引用已完整替换的v31/v9段落，capacity/official/AP不自包含。
2. [P1] reservation marker schemas/canonical publication缺失；malformed RESERVED charge无定义。
3. [P1] `authority.json`自身无closed schema，可包含registration/current commit形成回边。
4. [P1] lifecycle未绑定exact parent fixed audit、population/security axis和prediction-date axis。
5. [P1] issuer→evidence签发映射/source locator及SLA006 canonical records/digests未闭合。
6. [P2] fold window必须在Shanghai canonical date后判断；merged/per-fold replay grain未冻结。

已确认封死：AP空/无关manifest主反例、official/state串包方向、owner-abort race、malformed RELEASED
原则、same-attempt并发、五列身份主漏洞、direct lifecycle role回边和M7未授权边界。

M7 v10结论：`NEEDS_CHANGES`。只读；未编辑文件/ledger，未运行replay、训练、PIT或final-OOS。
