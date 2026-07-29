# M6.5 v24 独立设计审查

- Reviewer：`/root/m65_v24_design_review`
- Author：`/root`
- 模式：独立只读 R3 design review
- Subject：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v24.md`
- Subject SHA256：
  `6a4a744aa60fbde0cd037b481f15be9c4ad573087b009e87f00d3f0f228721b6`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=4 / P2=0 / P3=0`

## Findings

### [P1] completion marker 之前的目录发布崩溃无法恢复

v24 先 `mkdir(final)`，逐个发布 payload，最后才发布
`PUBLISH_COMPLETE.json`，但恢复又依赖 marker 内的 exact inventory。若 publisher 在 marker
之前崩溃，final namespace 已占用、恢复所需 inventory 却不存在；retry、并发 publisher 与
quarantine 的所有权和锁域也没有定义。

修复要求：在任何 payload 前原子发布独立 prepared claim。claim 必须绑定 publisher
identity、target schema、完整 expected inventory 和恢复策略；相同 claim 才可恢复，不同
claim 必须冲突。完成 marker 不能是恢复 inventory 的唯一来源。

### [P1] FitLaunchClaim 不是全局 one-shot，stale-tail recovery 有放行窗口

同一 receipt/source event 可以选择不同 final path；当前只有 run ID 的 global index，没有
source event 派生的 canonical claim slot。并且旧 run 补写 receipt 后、发布
`ABANDONED` 前再次崩溃时，claim issuer 可能看到 receipt 且看不到 terminal/claim，从而放行
已经被 later tail 淘汰的 run。

修复要求：claim path/key 必须由 registration 与 source event 唯一派生。在同一
registry/run lock 临界区内完成 exact receipt、current head、terminal 与 existing claim
检查及 claim/ABANDONED 决策；若 head 已推进，直接确定性终止，不能出现 receipt-only 的
可 claim 中间状态。

### [P1] source adapter 仍允许不同合规实现得到不同 U_state(T)

`idx_cons_core` 在一个 exit clock 为 null、另一个大于等于 cutoff 时存在规则冲突；
special-status 同 known time 的 complete/incomplete 事件优先级和 null 排序未冻结；
action 的 null/duplicate 规则及 slicer 输出的 canonical schema/sort/writer 未冻结。

修复要求：为每个 clock/null/tie 组合写出真值表，冻结 complete/incomplete precedence、
equivalent/conflicting event 合并、action null/duplicate、输出 schema、排序与 canonical
logical bytes。

### [P1] attempt staging 未封印到实际消费时点

launcher 的 copy/fstat 只证明原 source 在复制期间稳定；staged regular file 在 child
打开前仍可能被同 uid cooperative process 或后续步骤修改，因此 outer receipt 描述的
measured bytes 未必等于实际 consumed bytes。

修复要求：写满后从 directory FD 重算 inventory，移除 staging subtree 写权限并 fsync；
发布 seal 后 child 才能打开，且 child 只能从 sealed tree 消费并在执行前后核对 inventory。
threat model 应明确限于 cooperative same-uid，而不声称抵御恶意进程。

## Closure status

v24 已正确保留以下方向：v28 有界单仓库边界、live M7 fail-closed、五个 Gate 入口、
historical prefix/current head 分离、M6 false-gate checkpoint 兼容、CUDA-only exact replay
及明确的 runtime/score canonicalization。上述优点不改变四个 P1 blocker。

## Review limits

本审查只读；未编辑设计、代码、测试、gate 或 ledger，未运行 replay、训练、真实数据、
PIT certification、预算消耗或 final-OOS。

