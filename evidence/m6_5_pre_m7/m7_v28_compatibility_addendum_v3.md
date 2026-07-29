# M7 v28/v25 兼容性附录 v3

- 状态：`DESIGN_ONLY / M7_NOT_AUTHORIZED`
- 当前架构：`architecture_confirmation_v28.md`
- 当前 canonical design：`m6_5_repair_change_design_v25.md`
- 当前 M7 subject：`m7_change_design_v3.md`
- 当前 behavior matrix：`m7_behavior_to_test_matrix_v3.md`
- 取代：v2 指针；历史版本永久保留。

M7 v3 将当前冻结预算的最后16个fit只分配给两个隔离分支：CCC seed-7与Gate seed-7各
7 folds + 1 deterministic refit。组合、额外 seeds、确认与M8 refit均不在当前授权内，必须
另立用户批准的预算 CR。

任何 future M7 derived contract必须在 M6.5 gate PASS后绑定：

1. 独立 PIT audit PASS 的 MarketStateProduct/PreOOSAuxSnapshot；
2. live authority、registration、canonical one-shot claim与terminal；
3. outer validator PASS 的M6 14-fold archival replay；
4. M7 v3 CCC/Gate与科学screening语义；
5. M6 `6/44`连续账本及未超过 current `27 candidate / 60 fit` cap。

legacy `market_gate=True` 永久 fail-closed；future Gate只能由专用
`M7PeerLiteGateAdapter`消费 PIT-qualified state。

本附录不创建 runner/spec/authority/checkpoint，不运行fit、组合、选择、回测或final-OOS。

