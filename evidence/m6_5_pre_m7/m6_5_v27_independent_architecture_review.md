# M6.5 v27 独立架构审查

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/v27_arch_review`  
审查对象：`architecture_confirmation_v27.md`  
审查方式：只读；未编辑项目文件、未运行 replay、训练或任何 M7 工作。

## 结论

v27 不能从 architecture 路由至 change-design。它确实补充了 P1 的无 `site`
启动、旧根拆离及 raw worker 的 `Path.resolve()` 可达性，但其固定 FD 图、能力链和
全局 raw-worker 生命周期仍无法在声明的拓扑中实际运行。

## P1 findings

### 1. P2 的固定 FD 图无法启动

v27 声明 P0 只向 P1 传递 `P2_PERMIT`、worker-job `O_PATH` 和 scratch `O_PATH`；
但 P2 helper 的 pre-exec 图还需要 P2 专属 RoleView、OD `REDEEM` endpoint 和 P2 的
event peer。P1 不持有这些能力，且 `close_range`/extra-FD rejection 排除了隐式继承。
因此 P1 无法构造 P2 的允许输入，P2 不能被启动。

### 2. Invocation 与 P0 终态读取没有能力链

P1 必须将 P2 receipt 与 Invocation、stage inventory、runtime closure 和 DeviceView
比对，但后执行 FD 图没有这些可验证的 canonical bytes 或 hash-bound dispatch bundle。
同时 P0 在 P1 退出后必须做 final equality，表中却没有给 P0 重新打开最终 scratch 的
job-root 能力。这使 attest/finalize 路径依赖未定义的隐式路径访问。

### 3. 全局 raw 排他与 cgroup 拓扑/lease 生命周期冲突

P2 被放在 session 的子 cgroup，又要求一个 global raw cgroup；在同一 cgroup-v2
hierarchy 中同一进程不能同时属于两者。`no raw launch receipt remains` 也不是可执行的
释放条件：launch receipt 是后续审计输入，不应消失。文档缺少
`RESERVED/RUNNING/DRAINED/RELEASED` 的原子线性点及 OD crash recovery。

### 4. CUDA DeviceView 无法由 P1 独立验真

DeviceView 的字段描述较充分，但 P1 没有 expected view 的可信输入，只能读取 P2 的
自报。原始 worker 的 CLI 仍接受任意 `--device`，没有将 `cuda:0`、UUID/MIG、可见
设备、ABI、节点 rdev 与 cgroup policy 绑定到 P1 的 dispatch 输入。

## 已确认的非阻断改进

- `python -I -S -B` 的 P1 启动形式已经明确。
- `MS_PRIVATE → pivot_root → MNT_DETACH` 的旧根分离顺序足以表达其设计意图。
- `/m6p2/...` 可兼容历史 raw worker 对输入路径的 `Path.resolve()` 以及 output directory
  必须初始不存在的约束。

## 处置

本审查不建议继续为 v27 增加 FD、cgroup 或 GPU 特权机制。后续
`m6_5_mainline_scope_review_v1.md` 已基于冻结 CR 与威胁模型重新判定：v27 保留为
`DESIGN_ONLY / NOT_SELECTED_FOR_M6.5_MAINLINE` 的生产化候选，不是 M6.5 的实现前提。

