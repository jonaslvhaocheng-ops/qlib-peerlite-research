# M7 独立设计审查

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/m7_design_review`  
审查对象：初始 `m7_change_design.md`、`architecture_confirmation.md`、`m7_test_plan.md`。

被审初始设计 hash：

- change design: `b50d204cf8412acfbc53a720ab6da2630d0f922e74aedebf8fda885c8eade5a3`
- architecture confirmation: `b92cd889fe327b35349d32ee83aa767bc16bbd86eb1c6ae10f16a7cdd02530dc`
- test plan: `d0124cac7033c26d6d4ad1687508c0c4b35250718c0c870e9c2ab15009f9ba45`

## Findings

### [P1] Gate market state 被未来信息条件化

- 场景：直接从 M3 supervised matrix 的完整 `U(T)` 聚合 state。
- 影响：M3 matrix 在生成时已经按 `finite_label`、T+1 价格限制/停牌、label corporate-action
  cross 和 purge/embargo 排除行；这些条件依赖 T+1 至 T+5，故同日 state 组成不再是 T 时
  可得的横截面。
- 方向：建立 hash 绑定的 `market_state_population`，只含 T 时已知的 PIT membership、上市/
  状态与因果 feature 资格；保留每日 key set、count、state digest；做增量 PIT 与“改变同日
  未来 label/execution/action 条件，state 不变”的负对照。

### [P1] 唯一日期 standardization 没有强制接口

- 场景：只加 Dataset adapter，仍复用当前 `PeerLiteModel`。
- 影响：广播后 state 的每股票重复行会参与 `market_standardizer.fit_transform`，使日期按股票数
  加权，违反“训练日期各一次”的冻结语义。
- 方向：将 M7 专用 wrapper 设为必需。它必须抽取唯一日期 state、仅以训练日期拟合、再
  精确 join/broadcast；checkpoint 保存 schema、日级统计量和 hash，拒绝任何不精确广播或
  日期不匹配。

### [P1] 组合激活与预算缺少可执行、契约一致判据

- 场景：两个 isolated branch “通过”后决定 CCC+Gate 是否执行。
- 影响：初始设计禁止成本后选择，但冻结研究契约要求相对 MSE 的成本后 IR；无预设判据会迫使
  实现时临时选择，或以工程成功替代科学晋级。
- 方向：派生契约必须区分工程 PASS、科学晋级 PASS、组合触发、候选/seed/fold/refit 的
  不可挪用预算和 candidate-event 计数。若组合触发用成本后指标，必须预先冻结开发期组合/
  成本评估规范；否则组合保持 HOLD。

### [P2] CCC checkpoint 选择语义未冻结

当前训练 CCC 而验证/early-stop 固定 MSE。M7 execution spec 必须冻结 CCC 公式、epsilon、
按日 reduction、singleton fallback、validation metric、early-stop 与 tie-break。

### [P2] 账本恢复和 state 负对照不足

需定义 lock/CAS、`FIT_STARTED → terminal` 耐久状态机、崩溃恢复、不重用 run ID 的测试；
同时加入同日 future-dependent exclusion mutation 与 direct non-finite state fail-closed。

## 审查结论

`NEEDS_CHANGES`：无 P0；三个 P1 必须先关闭，才可建立 M7 派生契约、写 M7 代码或启动
真实标签训练。最终 OOS 继续封印。

## 已保留的正确方向

- M6 runner/历史证据隔离正确；不应覆盖其路径。
- 已识别旧 `market` 列的 label 泄漏。
- 独立 runner/verifier、hash、OOS seal、append-only ledger 的方向正确。

## 审查执行证据

独立只读回归：

```text
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider \
  tests/test_m6_spec.py tests/test_m6_evidence.py tests/test_peerlite.py
```

结果：`14 passed`。它只证明现有 M6/PeerLite 回归未漂移，不构成 M7 行为验证。

