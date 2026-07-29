# M6.5 v23 独立 R3 设计审查

- Reviewer context：`/root/m65_v23_design_review`
- Author context：`/root`
- Subject：`m6_5_repair_change_design_v23.md`
- Subject SHA256：`b5ba1f3cd84923911ed5c2a3b3c522da9fed8b85069bd1f63eb24b9c1bd92e8d`
- 行为：只读；未编辑仓库，未调用 quality ledger，未运行 replay/训练/真实数据，
  未消耗预算，未访问 final-OOS。

## Findings

### [P1] Reconciliation receipt 在崩溃后可被重复用于同一次 fit

**Section：** v23 §5.3.3。

`MODEL_FIT_STARTED` 已 reconciliation 且 receipt 已生成后，进程可能在 `fit()` 内崩溃。
run lease 随进程退出释放；若同一 receipt 仍代表 `FIT_ALLOWED`，重启可再次调用同一 fit，
却没有新的 `MODEL_FIT_STARTED`，从而少计失败/重试预算。

最小修复方向：增加一次性的 no-replace `FitLaunchClaimV1`。claim 必须在进入 fit 前持久化，
绑定 registration/snapshot/source event/receipt；已有 claim 的 source event 永不再次放行。
重试必须使用 authority plan 中新的 event sequence/fit attempt ID 并重新计数。

### [P1] U_state(T) 的非行情 adapter 仍保留实现者可选语义

**Section：** v23 §5.2.1–§5.2.3。

v23 没有逐源冻结进入/退出双公告时钟、null/duplicate/tie/event-transition、特殊状态解除、
第 60 日 inclusive convention 和 exact expected output calendar。两个实现可以都满足
manifest/future-poison，却得到不同 population。

最小修复方向：增加 `MarketStateSourceAdapterPolicyV1`，冻结 exact columns/mapping、
日期归一化、XSHG/XSHE 日历一致性、输出交易日域、进入/退出公告规则、listing 第 60 日、
active/delist/null/duplicate、特殊状态排序与 forbidden/解除规则，并把 policy/code hash
绑定到 input binding。

### [P2] M6 replay 的 executable/runtime 与 canonical bytes 未全部冻结

**Section：** v23 §5.4。

binding 未冻结 bound Python 与期望 Python/Torch/CUDA/cuDNN/device identity；
`mode_without_write_variance` 没有 exact bitmask；exact score bytes 没有排序、dtype、
endianness 与 digest 算法。issuer、child 和 outer validator可能无法独立复算同一结果。

最小修复方向：绑定 executable/runtime expectations，明确 inventory mode 规则或删除该字段，
并冻结 score key/order/dtype/little-endian byte/digest 算法。

## Verdict

`NEEDS_CHANGES`

- P0：0
- P1：2
- P2：1
- P3：0
- 最早修复阶段：`change-design`
- Reason：`FIT_AUTHORIZATION_REUSABLE_AND_STATE_REPLAY_BINDINGS_INCOMPLETE`

## 应保留

- 2011–2024 行情物理 allowlist、2011-09 support、2012–2024 output 和 60-session mask。
- 五个 public Gate 入口 fail-closed 与 M6 false-gate checkpoint/lazy import 兼容。
- historical prefix/current head 分离、registration/snapshot no-replace 和 receipt recovery方向。
- archive 不接受 free child input、重新解压复算 tree、outer v2 receipt 才可验收。
- M7 继续 `NOT_RUN`，不恢复 v27 privileged control plane。

## Residual risks

实际 `mkt_adjf` row-group、CUDA runtime、archive/checkpoint 仍未运行验证；source snapshot/hash
不能证明 vendor history 完整。final-OOS 必须继续 sealed。
