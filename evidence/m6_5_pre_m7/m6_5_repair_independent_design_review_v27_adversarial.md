# M6.5 v27 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Subject SHA：`1517a81b731444e5c9a8528566d1e2fe97da9f183b9838441d6706a68051ced9`
- Reviewed revision：`171`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=4 / P2=2 / P3=0`

## Findings

1. **[P1] PIT protection time未统一。** cutoff projection与per-T poison混用。
2. **[P1] directory transaction未定义nested dirs。** 缺directory inventory、top-down create、
   bottom-up fsync/chmod及output特殊文件拒绝。
3. **[P1] authority generation三对象无crash commit。** registration、run-index、generation
   任意中间crash无唯一恢复权威。
4. **[P1] behavior qualification要求官方manifest不存在字段。** test-only应查parent PIT；
   independence需外部review receipt，不能臆加behavior字段。
5. **[P2] nullable status sort未冻结。** 需null order/UTF-8/date ordinal。
6. **[P2] replay clean env/argv未冻结。** 需env-i等价allowlist、完整argv/env digest。

M7 v5专用结论`NEEDS_CHANGES`；CCC、Gate create/reload、first-event admission和预算可保留。

只读审查；未编辑文件/ledger，未运行replay、训练、真实数据、PIT CERTIFY或final-OOS。

