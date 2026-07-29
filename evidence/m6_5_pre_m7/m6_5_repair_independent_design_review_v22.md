# M6.5 v22 独立设计审查

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/m65_v22_design_review`  
审查对象：`m6_5_repair_change_design_v22.md`，SHA-256
`92ee9aab598c38d3f9d00d8d6ab4a2bfa444b08c7da5da99c7b70e6d616d28a6`  
方式：只读；未编辑产品/测试/契约/gate/ledger/status/历史证据，未运行 replay、训练、PIT
certification、预算消耗或 final-OOS access。

## Findings

### [P1] Market-state input/OOS boundary 未闭合

设计没有冻结可打开的 pre-OOS files/row groups、support history、raw-to-state field mapping、
feature-spec/code hash 及“先完整 raw causal feature、再选择 `U_state(T)`”的顺序。sealed
snapshot 中 `mkt_equd` 与 `mkt_adjf` 均含 2025+，仅在输出 manifest 写 OOS=false 不能证明
构建时没有读它们。`MarketStateInputBindingV1` 必须固定六份 source manifests、allowed
partitions/slices、output/support bounds、opened inventory、policy/code hashes和 PIT receipt binding。

### [P1] RunRegistration/journal snapshot/recovery 仍是自声明

`authority ID` 没有 immutable authority path/hash 和候选/spec/budget 授权验证；journal
snapshot 的 path/bytes/hash/fsync/no-replace 生命周期也未定义。需要
`RunAuthorityV1` 锚定 ledger/family/contract/spec/registry/caps/event plan，并定义
`JournalSnapshotV1` 与 registration/head/receipt retry 的持久状态机。

### [P1] Replay binding 未在执行前形成可独立验证的来源链

v22 允许 launcher 在执行时计算 `M6ReplayInputBindingV1`，但未要求一个 no-replace
pre-execution binding artifact；transfer manifest 也没有 canonical tree inventory/digest
算法或 root layout。binding 必须先存在并固定 M6 evidence、transfer archive、tree inventory、
launcher/raw worker、product/run/checkpoint/ledger identity；launcher只能读取并验证它。

### [P2] Gate pause 的 public entrypoints 未完整枚举

`PeerLiteNetwork` 可直接接受 `market_gate=True`，`PeerLiteModel.load_checkpoint()` 可从 config
重建 constructor。设计必须规定 `ExperimentConfig`、CLI、`PeerLiteModel`、`PeerLiteNetwork` 和
checkpoint load 的一致拒绝矩阵，同时保留 M6 false-gate checkpoint replay。

## Verdict

`NEEDS_CHANGES`，最早修复阶段为 `change-design`。v28 的 bounded data/governance/server
composition-root 架构仍可保留；不需要恢复 v27 特权 control plane。

