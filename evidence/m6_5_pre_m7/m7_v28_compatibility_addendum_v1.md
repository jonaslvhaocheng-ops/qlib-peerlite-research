# M7 v28/v23 兼容性附录 v1

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 适用阶段：`M6.5-PRE-M7-ENGINEERING-QUALITY`
- 当前架构：`architecture_confirmation_v28.md`
- 当前变更设计：`m6_5_repair_change_design_v23.md`

## 结论

旧 `m7_change_design_v2.md`、`m7_test_plan_v2.md` 和 `m7_design_review_v2.md`
继续作为 CCC/Gate 语义与测试义务的历史 design-only 参考，但它们早于 v28/v23，
不能单独关闭当前 M6.5 gate，也不授权任何 M7 执行。

M7 只有在 `evidence/gates/M6_5_pre_m7_quality_gate.json` 变为独立验收的 `PASS` 后，
才能创建新的 derived research/execution contract。该未来 contract 必须精确绑定：

1. 经独立 PIT audit `PASS` 的 `MarketStateProduct` 及其
   `MarketStateInputBindingV1/MarketStatePolicyV1`；
2. future frozen `RunAuthorityV1`、no-replace registration/journal snapshot 和 exact-head
   reconciliation；
3. 通过 outer v2 validator 的 M6 14-fold archival replay receipt；
4. CCC v2 已声明的 loss、validation、early-stop、tie 与 singleton 规则；
5. 与历史 M6 `6/44` close prefix连续的试验预算。

未来 Gate 必须通过独立的 `M7PeerLiteGateAdapter` 消费 PIT-qualified state product。
legacy `PeerLiteModel/PeerLiteNetwork.market_gate=True` 路径在 M6.5 中保持 fail-closed，
不得被重新开放为 M7 输入捷径。

本附录不创建 M7 execution spec、candidate、runner、checkpoint 或结果；不允许真实 fit、
CCC+Gate 组合、模型选择、预算消耗、2025+ final-OOS、组合回测或交易。
