# M6.5 v21 变更设计预检 — 返回架构修复

状态：`NEEDS_CHANGES / architecture`。本预检没有形成 implementation-ready change design，
也没有改 product/test code、历史 evidence、contract、gate 或运行项目代码。它只检查
`architecture_confirmation_v25.md` 能否无新增架构猜测地进入 v21 设计。

## 阻断项

### [P1] Quality issuer 未出现在 v25 的可执行 actor graph

v25 禁止 P0 写 Bootstrap/QualityPass，同时把 ArchiveAcceptor[ADMIT] 限定为 E/C，OD
又仅启动/reap。因此没有 physical publisher 能在 E/C 前产生 Bootstrap/QualityPass。
需要加入独立、runtime-self-observed 的 `quality_gate_issuer` 角色及其 B/P→E/C 顺序。

### [P1] cross-identity/namespace helper 没有固定为可部署的一次性 capability

`m6_actor_exec` 需要受控 privilege elevation，P2 worker view 需要 mount privilege；sealed
permit FD 可被复制，OD nonce table 本身不是原子消费协议。需要冻结 root-owned helper 的
安装/identity/mode、固定 FD map、OD `REDEEM` handshake、one-shot launch receipt 与
P2-per-S3 binding；不得依赖 generic Popen/preexec fallback。

### [P1] descriptor/runtime/P2 boundary仍有 material ambiguity

descriptor hash 自引用、runtime closure/source/native-import provenance、以及 P2 与 P1
共享 uid 时的 `/proc/<P1>/fd` visibility 都没有完整闭合。应使用 non-cyclic core descriptor
and role-view hashes；每个 authority actor 观察完整 runtime closure；并令 P2 使用独立
`raw-mechanics` uid、private mount root 和 private `hidepid=2` proc，而不是同 uid。

### [P1] crash/timeout recovery缺少 OD-owned descendant-drain evidence

P0/P1/P2 pidfd ownership相互冲突。需要由 OD 建立 per-session cgroup/pid binding、记录
launch receipt、在 P0 death 后 drain children，并只向 fresh recovery actor 交付 sealed
drain evidence；recovery 不得按可重用 PID 猜测安全。

### [P2] snapshot 与 O/state order需要在架构层固定

需固定为 `S0 → O create → S1(O D-v2) → job stage + shared-lock snapshot → H → Invocation
→ S2 → S3`；定义 full-tail JSONL validation、staged ownership、orphan O/S1/H/Invocation
和 S5 缺 O leaf 的 deterministic terminal/rejection outcome。

## 结论

这些问题改变 actor/writer matrix、identity/deployment trust boundary、runtime authority、
recovery owner 与 durable state topology，不能留给 change-design 或 implementation 决定。
路由必须返回 `architecture`。在新的 architecture confirmation、change design 和独立 R3
review PASS 前，不进入 test design、tests-red、implementation、code review、E2E、replay、
M7、PIT 或 final-OOS。
