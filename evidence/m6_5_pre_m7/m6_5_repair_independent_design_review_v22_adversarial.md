# M6.5 v22 对抗式独立设计审查

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/m65_v22_adversarial_review`  
审查对象：`m6_5_repair_change_design_v22.md`，SHA-256
`92ee9aab598c38d3f9d00d8d6ab4a2bfa444b08c7da5da99c7b70e6d616d28a6`  
方式：只读；未编辑设计/代码，未运行 replay、训练或访问 OOS。

## Findings

### [P1] MarketStatePolicyV1 尚未冻结可复现语义

四个 state source 是 20-day window，但现有 `features.py` action mask 是 60-session；v22
没有固定使用哪一个、warm-up、日期域、raw-field mapping、allowed partitions 或空日规则。两个
实现可生成 schema/hash 都正确却得到不同 `U_state(T)`。必须写入最小
`MarketStatePolicyV1`，并与 PIT receipt 绑定。

### [P1] Registration/exact-head/crash recovery 没有完整生命周期

首次 `RUN_REGISTERED` 将 head 从 H0 改为 H1，随后 journal/replacement/receipt crash 的合法
recovery head与 no-op 条件未定义；registration 的 no-replace issuance、authority root 与
immutable binding也未定义。需要小型单机 lifecycle contract，而不是 daemon 或 v27 actor。

### [P2] Transfer manifest 与 raw worker inner manifest 的交接未裁决

外部 transfer manifest 和 raw worker 期望的 inner `frozen_source_manifest.json` 有不同 schema。
v22 只说“必要 adaptation”，未冻结内层是否必需、canonical inventory 算法/字段、child argv
与 outer receipt authoritative identifier。`M6ReplayInputBindingV1` 必须给出唯一 handoff。

### [P2] M7 v2 review 与当前主线的状态指针陈旧

M7 v2 review 绑定旧 v2 architecture，当前 `docs/STATUS.md` 又仍指向已拒绝的特权控制面。
需要一个短的 M7-v28 compatibility addendum/独立复核和当前控制指针更新；它不能创建 M7
derived contract、模型或训练器。

## Verdict

`NEEDS_CHANGES`，最早修复阶段为 `change-design`。应保留 v28/v22 的最小路线；上述均是
声明式契约/指针补全，不增加服务、特权、cgroup、namespace 或交易系统。

