# M6.5 有界修复变更设计 v49 — 已落地切片绑定确认

## Header

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- 所有者：研究治理层
- 需求：在不改变 v48 主线的前提下，使未来 M7 initial-screen 的 `RunIntent` 显式绑定冻结预算和 T-known 市场状态权威。
- 风险：`R3`
- Architecture：`architecture_confirmation_v29.md`
- 基准设计：`m6_5_repair_change_design_v48.md`
- 当前生产代码对象：`src/qlib_peerlite/governance/trial_ledger.py`
- 当前对象 SHA256：`127ecbfb9cf2f7a89302e6d917bef5ac99b8ffe4f6cd21b90bc50a4822d489a4`

## Problem and scope

### Current observable behavior

历史 `RunIntent` 只绑定 `run_id`、`family_id` 和 execution-spec 内容哈希。若未来 M7
initial-screen 继续使用该形状，trial identity 无法证明本次运行同时使用了冻结预算权威和
T-close 市场状态权威。

### Desired observable behavior

- family 为 `QLIB_PEERLITE_M7_INITIAL_SCREEN_V1` 时，两项权威绑定必须同时存在。
- 任意 family 只提供其中一项时立即拒绝。
- 提供的绑定必须是字典，并通过 canonical JSON 进入不可变 identity。
- 带绑定的 intent 使用 V2 identity；无绑定的历史非 M7 intent 保持 V1 identity。

### Non-goals

- 不实现预算扣减、市场状态计算、ledger recovery、M6 replay、CCC、Gate 或模型训练。
- 不改变 M6 的冻结字节、6/44 计数、模型、数据、screen 规则或最终样本外边界。
- 不引入服务、数据库、后台进程、特权控制面或跨进程安全承诺。

### Constraints and assumptions

- 运行架构仍是可信单进程/单操作员研究环境。
- 两项 binding 的具体完整 schema 仍由 v48 normative bundle 定义；本切片只保证 presence、
  类型和 identity binding，不冒充完整的递归 schema 校验。
- `canonical_json_bytes` 是仓库现有的稳定序列化边界。

## Repository evidence

- `governance/trial_ledger.py` 已拥有 `RunIntent`、canonical identity 与 ledger/journal 边界，
  因此此处是唯一合理所有者。
- `tests/test_trial_ledger.py` 与 `tests/test_reconcile_trial_ledger_cli.py` 覆盖历史 V1 消费路径。
- `tests/test_m65_expected_red.py` 定义本切片最小缺口：M7 initial-screen 不得接受无权威绑定的
  intent。
- `m6_5_normative_closure_manifest_v6.json` 继续冻结 v48 的完整四条 workstream；本文件不替代
  其中任何 component/replay/M7 规范。

当前控制流为：composition root 构造 intent → `RunIntent.__post_init__` 验证 →
`content_sha256` 生成 immutable identity → journal/ledger 消费 identity。没有新增反向依赖。

## Options

### A. 在 `RunIntent` 内做有界的条件验证和版本化哈希（采用）

- 正确性：在 identity 形成前 fail closed。
- 复杂度：两个可选字段、一个 family 条件、V1/V2 两条 canonical hash 路径。
- 兼容性：历史非 M7 无绑定对象保持原 V1 字节语义。
- 可运维性与测试性：无外部依赖，可由纯单元/契约测试验证。
- 性能与安全：仅增加常数级序列化；不扩大权限边界。
- 可逆性：删除 M7 未使用的 V2 路径即可回滚，不迁移历史证据。

### B. 在每个 CLI/composition caller 外围校验

- 优点：`RunIntent` 数据类表面更简单。
- 缺点：任一新 caller 可绕过检查；identity 自身不携带权威，审计证据分散。
- 结论：不采用，因为不能在唯一所有权边界上保证 fail closed。

### C. 立即建立完整 typed binding hierarchy

- 优点：可递归验证每个字段。
- 缺点：超出当前最小红测，复制 v48 schema 责任并制造新抽象；会把本轮变成治理平台重构。
- 结论：不采用；完整 schema 校验留在 v48 后续有界切片。

## Proposed design

### Responsibilities by component

- `RunIntent.__post_init__`：验证核心 identity 字段、M7 family 的双 binding presence、成对性和
  顶层字典类型。
- `RunIntent.content_sha256`：无绑定走 V1；双绑定走 V2，并把两项权威完整纳入 canonical
  JSON。
- journal/ledger/reconciliation：保持不变，只消费 intent identity。

### Interfaces and schemas

新增内部可选字段：

```text
budget_limit_binding: dict[str, Any] | None
market_state_authority_binding: dict[str, Any] | None
```

V2 identity payload 固定包含：

```text
schema_version
run_id
family_id
execution_spec_content_sha256
budget_limit_binding
market_state_authority_binding
```

### Data ownership and state transitions

binding 由上游 composition root 从已冻结规范读取；`RunIntent` 不修改它们，只验证并哈希。
对象冻结后无状态迁移。合法路径只有 `unbound non-M7 → V1 identity` 或
`fully-bound intent → V2 identity`；M7 unbound、partial 或非字典输入均在构造时终止。

### Success sequence

上游加载冻结权威 → 构造 fully-bound M7 intent → 本地验证 → 计算 V2 内容哈希 →
后续 journal/ledger 以该哈希绑定运行。

### Failure/recovery sequence

构造期验证失败立即抛出 `TypeError`，尚未创建 journal event、未写 ledger、未触发 fit，
因此无重试、补偿或 partial success。调用方修正输入后以新对象重试。

### Concurrency and idempotency

本切片没有 I/O 或共享状态。相同 canonical inputs 生成相同哈希；不同 binding 内容生成不同
哈希。现有 ledger lock 语义不变。

### Security and privacy

binding 只允许治理元数据，不应含凭据或个人信息。该类型检查不是不可信输入安全边界；整体仍是
可信单操作员架构。

### Performance and resource bounds

每个 intent 增加一次常数规模 canonical JSON 序列化；不改变 O(NK) 模型复杂度，也不增加
训练、磁盘扫描或网络调用。

### Observability

成功身份由 `content_sha256` 可追溯；失败以明确字段名的 `TypeError` 暴露。此切片不新增日志、
指标或告警系统。

## Evolution

### Compatibility and migration

- 历史非 M7、无 binding 的 intent 继续产生 V1 hash，无数据迁移。
- 未来 M7 initial-screen 必须采用 V2。
- 其他 family 可在显式同时提供两项 binding 时采用 V2；仅提供一项禁止。

### Rollout and rollback

先通过合成测试、回归套件、Ruff、独立设计审查和独立代码审查。未通过任一门则不进入 M7。
回滚只移除未投入 M7 的 V2 切片；不得改写 M6 archive 或 ledger prefix。

### Feature flags and version skew

无需 feature flag。schema 字符串本身区分 V1/V2；同一进程内构造与消费，当前不存在分布式版本
偏差。

## Verification obligations

- M7 initial-screen 无绑定、partial binding、错误顶层类型必须在任何副作用前失败。
- fully-bound M7 intent 必须稳定产生 V2 identity，且任一 binding 变化都会改变 identity。
- 历史非 M7 无绑定 intent 的 V1 identity 和现有 journal/ledger 路径不得回归。
- 全量测试与静态检查必须保持通过。
- 后续完整 v48 实现仍须分别验证预算权威内容、T-known 状态内容、恢复协议、静态 archive 和
  no-fit replay；本切片不得被误报为这些能力已完成。

测试 seam 是纯 `RunIntent` 构造和 `content_sha256`，以及现有 journal/ledger 集成入口。关键
E2E 仍是合成的“冻结权威 → intent → start event”旅程，不接真实数据或 fit。

## Implementation plan

1. 在 `RunIntent` 增加两项可选 binding，并保持历史调用签名可用。
2. 在 `__post_init__` 实现 M7 必填、成对和顶层类型的 fail-closed 验证。
3. 在 `content_sha256` 增加完整双 binding 的 V2 canonical payload，并保留无绑定 V1。
4. 运行最小行为测试、既有 ledger/CLI 回归、全量 pytest 和 Ruff。
5. 由独立 reviewer 检查本设计与源码差异；通过后才继续质量路由。

以上 1–4 已作为最小切片落地；本 v49 只把实际源码对象与 v48 约束重新绑定，不授权更多实现。

## Open decisions

无阻塞决策。完整 binding 递归 schema 与其消费路径已由 v48 后续 workstream 持有，不在本切片
内临时决定。

## Verdict

`PASS`：实际切片符合最小设计、兼容边界和 v48 主线；应进入独立 R3 design review。M7 仍为
`NOT_RUN`，execution、replay、fit、PIT、real data、budget mutation 和 final OOS 仍未授权。
