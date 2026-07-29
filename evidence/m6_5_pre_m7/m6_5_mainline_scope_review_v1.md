# M6.5 主线范围复核 v1

状态：`PASS — scope correction within the approved M6.5 change request`  
复核者：独立子任务 `/root/m6_5_mainline_scope`；主负责人复核引用的冻结证据  
性质：设计/范围证据；未编辑产品或测试代码，未运行 replay、训练或 M7。

## True Status Card

| 字段 | 当前事实 |
| --- | --- |
| 当前阶段与轨道 | `M6.5-PRE-M7-ENGINEERING-QUALITY` |
| 最近实际动作 | v27 的两份独立架构审查完成，均为 `NEEDS_CHANGES`；没有执行 replay/训练。 |
| Executed / completed / passed | M6：`yes / yes / PASS`；M6.5：质量路线已启动但未通过；M7：`NOT_RUN`。 |
| 最强当前证据 | `contracts/changes/m6_5_pre_m7_quality_gate_v1.json`、`evidence/gates/M6_5_pre_m7_quality_gate.json`、M6 immutable spec/gate。 |
| 历史性证据 | M6 的 6 candidate / 44 fit close-time ledger prefix 和历史 M6 receipt；不得改写。 |
| 当前阻断 | 需要一份与冻结 M6.5 scope 相称、可测试、可实现的 architecture confirmation。 |
| 下一高信息动作 | 对新的 bounded architecture 进行 change-design 与独立 design review。 |
| 禁止动作 | M7 real fit、CCC+Gate、final-OOS、预算增加、将 M6.5 声称为生产安全认证。 |

## 证据与解释

批准的 CR 明确要求：独立 M6 code review、M6 test revalidation 和 archival verification
design、独立 M7 design review、M7 behavior-to-test matrix 与 M6.5 receipt。其允许的
修复包仅为 archival M6 verifier、crash-safe ledger reconciler 和 T-known state-population
mechanics（见 `contracts/changes/m6_5_pre_m7_quality_gate_v1.json` 与
`evidence/gates/M6_5_pre_m7_quality_gate.json`）。

其中的 “P0/P1/P2 findings” 是未解决发现的**严重度**，而非要求建设名为 P0/P1/P2 的
多进程特权控制面。现有威胁模型也明确将 hostile host、恶意 runner、内核和 native
injection 排除在本研究系统的证明范围外。v27 所引入的 setuid helper、FD capability
graph、cgroup drain、namespace/pivot-root、GPU ACL 和跨 uid handoff 因此属于生产化
hardening，而不是已批准的 M6.5 研究质量门。

## 决定

1. 保留 v27 及其两份失败审查，不删除、不改写、也不将其当作通过证据。
2. 将 v27 标注为 `DESIGN_ONLY / NOT_SELECTED_FOR_M6.5_MAINLINE`；它可在未来的生产化
   阶段重新评估。
3. M6.5 的最小、完整且不豁免任何发现的范围固定为四条：

   - 独立的 T-known `market_state_population` 与 future-poison/PIT 验证；
   - 保留 M6 `6/44` 历史前缀的 append-only journal→global-ledger reconciliation；
   - 从 frozen archive 实际加载 14 个 checkpoint、逐折比对 key/score 的 M6 archival
     verifier，并生成新的只读 receipt；
   - M7 的 CCC checkpoint 语义、组合晋级/预算规则和行为—测试矩阵，随后接受独立审查。

4. M6.5 不声称 hostile-host resistance。research server operator、项目工作树、冻结
   archive、OS/CUDA runtime 和文件权限是受信任的执行环境；损坏或不匹配输入必须拒绝
   receipt，但不为敌对本地 root/user 构建安全边界。

## 为什么不需要新的用户授权或 CR

本决定没有改变市场、标签、数据、M6 历史结论、M7 门槛、final-OOS 封印或任何接受条件；
也没有删除任何 unresolved finding。它仅选择了批准 CR 已列出的、能产生可证伪证据的
最小实现路线，并停止一个不产生 M6.5 必需工件的 production-scope 偏航。因此不是研究
语义、scope 或 gate 的修改。

## 结论

下一份架构确认必须用上述四项约束，不能再要求或实现特权 actor/control-plane。它通过后
才可进入 change-design；随后仍须经过独立 design review、test design、red tests、实现、
green tests、独立 code review 与 E2E，才能重新评估 M6.5。

