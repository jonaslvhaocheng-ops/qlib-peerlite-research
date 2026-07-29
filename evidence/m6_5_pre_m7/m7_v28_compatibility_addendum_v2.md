# M7 v28/v24 兼容性附录 v2

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 当前架构：`architecture_confirmation_v28.md`
- 当前 canonical design：`m6_5_repair_change_design_v24.md`
- 取代：v1 指针；v1 保留为 v23 历史证据。

旧 M7 v2 design/test/review仅为历史 design-only reference，不能关闭 M6.5。

M6.5 live trial authority固定 fail-closed；只有在 M6.5 gate独立 `PASS` 后，未来新
derived contract才可创建并绑定固定 slot
`contracts/immutable/m7_execution_authority_v1.json`。未来 M7还必须绑定：

1. 独立 PIT audit `PASS` 的 MarketStateProduct/PreOOSAuxSnapshot；
2. live authority、registration/snapshot、one-shot FitLaunchClaim；
3. outer validator `PASS` 的 M6 14-fold archival replay；
4. CCC v2 loss/validation/early-stop/tie/singleton语义；
5. 从历史 M6 `6/44` 连续的预算。

future Gate只能由 `M7PeerLiteGateAdapter` 消费 PIT-qualified state。legacy
`market_gate=True` 保持 fail-closed，不得重新开放。

本附录不创建 M7 spec/candidate/runner/checkpoint，不授权 fit、CCC+Gate组合、选择、预算、
final-OOS、回测或交易。
