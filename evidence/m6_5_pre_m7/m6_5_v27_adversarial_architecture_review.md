# M6.5 v27 对抗式架构审查

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/v27_adversarial`  
审查对象 SHA-256：`f05634cf07cc240a47a169922891a5ccf19b1c37145e64c8bd224a32308e7ef7`  
审查方式：只读；未编辑项目文件、未运行 replay、训练或任何 M7 工作。

## P1 findings

### 1. `no_new_privs` 与跨身份 P0→P1→P2 启动图不可同时执行

继承的 normal profile 在最终 exec 后启用 `no_new_privs`，因此 P0/P1 无法再从
setuid/file-capability helper 获得 `setresuid`、mount namespace、`pivot_root` 或 cgroup
设置需要的权限。但 v27 又要求它们按跨 uid 父子图启动下一层 helper。正常成功路径会在
启动 P1 或 P2 时失败，而不是在验证失败时 fail-closed。

### 2. P2 helper 所需的 `FD 6 / REDEEM` 没有交付路径

helper pre-exec map 必需 OD `REDEEM` endpoint；P0 的 `DISPATCH` 却只交付
permit/job/scratch 三项，P1 post-exec 图也没有 OD endpoint。因此 P1 无法完成一次性
permit redemption，P2 不能启动。

### 3. pre-run receipt 的读取时序自相矛盾

P2 必须先写 `P2ObservedRuntimeReceiptV1`，P1 读取并验证后才会 ACK，P2 才运行 raw
worker；但另一条规则又要求 P1 在 P2DrainReceipt 前不得打开任何 scratch leaf。
drain 只能在 raw worker 完成后发生，形成死锁。

## 次要但仍需定义的缺口

- `RAW_MECHANICS_LEASE` 没有可执行的释放线性点；历史 launch receipt 必须保留。
- GPU device policy 没有固定 cgroup-v1/v2 支持机制与安装前检查。
- `ODRecoveryDrainEvidenceV1` 的发行者、持久化位置和 OD 已退出后的验证输入未定义。

## 处置

这些结论证明 v27 不是可实施的 M6.5 架构。它们作为失败证据保留；不通过在实现阶段
“临时补齐”来掩盖。M6.5 主线已收敛到冻结 change request 明示的市场状态、账本、归档
验证和 M7 设计测试工作，见
`m6_5_mainline_scope_review_v1.md`。

