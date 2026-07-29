# M6.5 v23 独立对抗性 R3 设计审查

- Reviewer context：`/root/m65_v23_adversarial_review`
- Author context：`/root`
- Subject：`m6_5_repair_change_design_v23.md`
- Subject SHA256：`b5ba1f3cd84923911ed5c2a3b3c522da9fed8b85069bd1f63eb24b9c1bd92e8d`
- 行为：只读；未编辑仓库，未调用 quality ledger，未运行 replay/训练/真实数据，
  未访问 final-OOS。

## Findings

### [P1] 非分区输入没有冻结可执行的 pre-OOS 成功路径

当前五个辅助源均为单一 Parquet；`mkt_adjf` 很可能只有一个横跨 2025 cutoff 的 row group。
v23 对它的严格结果可能只能是 `HOLD`，而其余非分区源又可能物理解码 2025+ 值。

修复方向：为所有非分区源冻结可验证的 pre-OOS 物理切片流程；若原 snapshot 不可按完整
row group隔离，则先产生独立 sealed pre-OOS-only derived snapshot，并由单独 gate/manifest
绑定，builder 只能消费该派生快照。

### [P1] Per-source as-of/future-poison 规则仍不唯一

进入/退出公告、缺失退出公告、status publication、forbidden/解除、日历和 poison oracle
未全部冻结；builder 也不能自签 future-poison PASS。

修复方向：将 exact source clocks、null/transition/status/calendar/mutation oracle写入 policy，
future-poison receipt 由独立 behavior verifier 产生。

### [P1] RunAuthorityV1 仍可由 caller 自声明，run_id 也没有全局唯一索引

caller 可选择任意 authority root 并写一个内部自洽、非 test purpose 的 authority；
两个不同 registration path 也可对同一 run_id 分别 `O_EXCL`。

修复方向：M6.5 live acceptance 完全 fail-closed，只实现 synthetic-only API；未来 live
authority必须绑定 M6.5 PASS、derived contract、固定 server slot/issuer。共享锁下维护
canonical `run_id -> registration hash` no-replace index。

### [P1] O_EXCL 直接写最终 JSON 不能保证 crash-atomic no-replace

ledger replacement 后若 receipt 最终文件只写了一部分即崩溃，retry 只能看到损坏的已存在
文件，无法恢复。产品目录 existence check + 普通 rename 也可能覆盖并发发布者。

修复方向：私有临时文件写满+fsync，再使用真正 no-replace 的原子 publish/claim；定义 partial
prepared artifact 的 quarantine/recovery，目录发布同样先取得不可覆盖 claim。

### [P1] 合法 current tail 后的 run continuation 没有终态

Run A 在 S1 replacement 后崩溃，Run B 合法追加 H2，A 恢复 receipt 后的 S2 仍绑定 H1。
v23 只规定 stale-head fail，未说明剩余 plan 是 abandoned、继续还是重新注册。

修复方向：增加 post-first-append `ABANDONED/CLOSED` 终态；一旦 current tail 越过该 run 的
receipt head，旧 run 只能关闭，剩余 attempts 必须新 run/new counted event，不允许隐式 rebase。

### [P1] Replay 未证明 measured bytes 就是 consumed bytes

issuer/launcher验证 path 后 child 再打开，正常复制/部署任务可在中间替换 source、worker、
product、run或checkpoint；receipt可能描述的不是实际消费 bytes。

修复方向：将 source、worker、product、run/checkpoints materialize 到 attempt-owned staging，
写满后复算 inventory、去写权限并从该 staging 执行；冻结 interpreter/runtime/import-origin
和 score byte规则。无需恢复 v27 的特权 actor或 hostile-host承诺。

## Verdict

`NEEDS_CHANGES`

- P0：0
- P1：6
- P2：0
- P3：0
- 最早修复阶段：`change-design`
- Reason：`M65_V23_PREOOS_AUTHORITY_CRASH_AND_REPLAY_BINDINGS_UNCLOSED`

## 应保留

- v28 的单仓库 data/governance/composition-root 边界。
- M6 historical prefix 与 current whole-ledger head 分离。
- 五入口 Gate fail-closed、M6 false-gate checkpoint compatibility。
- archive links/devices rejection、fresh tree inventory 与 M7 `NOT_RUN`。

## Residual risks

未打开真实 snapshot、archive 或 checkpoint，未声称 row-group/runtime acceptance PASS；
final-OOS 继续 sealed。
