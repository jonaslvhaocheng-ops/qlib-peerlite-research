# M6.5 有界修复变更设计 v50 — RunIntent V2 不可变规范快照

## Header

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- 所有者：研究治理层
- 风险：`R3`
- 修复对象：v49 独立审查的 2 个 P1 和 1 个 P2
- Architecture：`architecture_confirmation_v29.md`
- 上位主线：v48 + normative closure v6
- 取代：v49

## Problem and scope

### Current observable behavior

当前 `RunIntent` 对 M7 initial-screen 已要求预算与市场状态 binding 同时存在，也把两者加入 V2
哈希；但它保留调用方传入的可变字典，并在每次访问属性时重新计算哈希。调用方在构造后修改原
字典或嵌套容器，可使同一对象产生不同 identity。非 JSON 值、非 NFC 字符和 NFC key collision
也没有在构造边界统一拒绝。

### Desired observable behavior

- 构造时完成 V2-only 的递归 JSON 验证、NFC 规范化、canonical bytes 生成和 identity 缓存。
- `RunIntent` 持有自己拥有的深度不可变快照；调用方后续修改输入不能改变对象或哈希。
- 非字符串 key、NFC key collision、非 JSON 类型、循环容器、NaN/Infinity 在构造时失败。
- V1 payload、serializer 和最终哈希保持逐字节兼容。
- 当前完成声明仅限 `RunIntent` class seam，不宣称 caller、journal V3、replay 或 fit 已接通。

### Non-goals

- 不实现完整 binding 业务 schema、authority roster、journal/retained event V3 或 CLI loader。
- 不实现预算扣减、state builder、recovery、M6 replay、CCC、Gate、真实训练或最终样本外。
- 不修改全局 `canonical_json_bytes`，避免影响历史 V1 和其他已冻结哈希。

### Constraints and assumptions

- 可信单进程/单操作员边界不变。
- 顶层 binding 必须是 `dict`；嵌套只接受 JSON primitives、`list` 和 `dict`。
- 本切片建立稳定快照能力；完整 v48 workstream 后续必须使用该快照生成 byte-identical event
  bindings，而不能重新读取调用方对象。

## Repository evidence

- `trial_ledger.py` 是 `RunIntent` 和 identity 的现有所有者。
- `artifacts.canonical_json_bytes` 已提供 sort-keys/compact/no-NaN，但不递归 NFC；全局修改会扩大
  兼容风险。
- v49 独立审查通过实际源码证明 `frozen=True` 不会冻结嵌套字典。
- 当前 `scripts/reconcile_trial_ledger.py` 只构造 V1-shaped intent；因此本设计明确不声称 M7
  caller 已落地。
- closure v6 要求未来 V2/event V3 使用 UTF-8/NFC/sort-keys/compact/no-NaN/no-duplicate。

当前流保持：调用方输入 → `RunIntent` 构造验证/快照 → 稳定 identity。journal/ledger 集成仍是
后续独立切片。

## Options

### A. 构造时规范化、深度冻结并缓存 identity（采用）

- 正确性：所有错误在副作用前出现；对象 identity 不再依赖外部可变状态。
- 复杂度：一个局部 recursive normalizer/freezer 和三个私有缓存字段。
- 兼容性：V1 继续用原 payload 和原 serializer；V2 规则局部化。
- 可测试性：纯构造、属性和输入变异即可验证。
- 可逆性：M7 尚未运行，可删除 V2 局部路径，不迁移 M6。

### B. 只 `deepcopy` 输入并在访问时重算哈希

- 优点：改动较小。
- 缺点：对象公开字典本身仍可被修改；无法兑现 immutable identity。
- 结论：不采用。

### C. 修改全局 canonical JSON serializer

- 优点：统一所有路径。
- 缺点：可能改变已冻结的 M6/V1 哈希，影响面远超本切片。
- 结论：不采用。

## Proposed design

### Responsibilities by component

仅修改 `governance.trial_ledger`：

- `_normalize_json_value`：递归验证 JSON 类型、检测循环、NFC-normalize key/value string，并拒绝
  normalized-key collision。
- `_freeze_json_value`：将 normalized dict 递归转换为 read-only mapping、list 转 tuple。
- `RunIntent.__post_init__`：先验证基础字段和 binding 成对规则，再生成本地 normalized plain
  payload、canonical bytes 和 cached hash，最后把公开 binding 字段替换为 owned immutable
  snapshot。
- `RunIntent.content_sha256`：只返回构造时缓存值。

### Interfaces and schemas

构造接口保留名称：

```text
budget_limit_binding: dict[str, Any] | None
market_state_authority_binding: dict[str, Any] | None
```

构造完成后，这两个属性表现为递归 read-only `Mapping`/tuple/scalar 视图。新增私有、不参与
repr/equality 的缓存：

```text
_content_sha256: str
_budget_limit_binding_bytes: bytes | None
_market_state_authority_binding_bytes: bytes | None
```

V2 full payload 仍固定为 v49 的六个字段；使用 normalized plain JSON values 一次性序列化。
V1 full payload 字段、schema string 和 `canonical_json_bytes` 调用保持原样。

### Canonicalization rules

- key：必须是 string，递归 NFC；两个原 key 规范化成同一 key 时拒绝。
- string value：递归 NFC。
- scalar：仅 `null/bool/int/finite float/string`。
- array/object：仅 `list/dict`；检测当前递归栈中的循环引用并拒绝。
- 不接受 tuple、set、bytes、自定义 mapping、自定义 JSON encoder、NaN 或 ±Infinity。
- 规范化后以 UTF-8、sort_keys、compact separators、`allow_nan=False` 序列化。

### Data ownership and state transitions

调用方拥有原始输入；`RunIntent` 在构造期生成独立 normalized snapshot 后不再引用它。合法对象只有
一次 `constructing → immutable` 状态迁移。任何验证失败都不产生对象。

### Success sequence

传入双 binding → 递归验证/NFC → 生成两份 binding bytes 与 V2 full-payload bytes →
缓存 SHA256 → 深度冻结 owned snapshot → 返回对象。

### Failure/recovery sequence

任一非法值在构造中抛出 `TypeError`，发生在 journal/ledger/fit 之前，无 partial success。
修正输入后新建对象即可；失败对象没有恢复语义。

### Concurrency and idempotency

对象没有 I/O 和共享状态。相同规范值产生相同 identity；调用方并发或后续修改原容器不能改变
已构造对象。该保证不升级为跨进程控制面承诺。

### Security and privacy

拒绝循环和自定义对象，避免隐式 encoder 行为。binding 不得含凭据/PII。可信单操作员威胁边界
保持不变。

### Performance and resource bounds

每个小型治理 binding 做一次 O(payload size) 遍历、序列化和冻结。没有网络、训练或数据扫描。
不为可信本地冻结文件引入额外大小限制；完整 file/schema loader 后续拥有文件大小策略。

### Observability

异常信息包含 binding 路径和违规类型；成功以稳定 `content_sha256` 和私有 canonical bytes 可供
后续 event V3 seam 使用。本轮不增加日志系统。

## Evolution

### Compatibility and migration

- 无绑定非 M7：原 V1 schema/payload/serializer/hash，零迁移。
- fully-bound intent：V2 normalized snapshot/hash。
- M7 unbound、partial 或非法输入：构造期拒绝。
- M6 archive、ledger prefix 和 6/44 计数不读写。

### Rollout and rollback

只在合成测试、全量回归、Ruff、独立设计审查和独立代码审查全部通过后保留。M7 未运行，回滚无需
迁移；不得改写历史证据。

### Feature flags and version skew

无需 feature flag；V1/V2 schema string 是本地版本边界。没有分布式部署或版本偏差。

## Verification obligations

- 修改原始顶层及嵌套输入后，intent snapshot 和 hash 保持不变。
- 尝试修改 intent 暴露的 nested mapping/sequence 必须失败。
- NFC 等价 string 生成相同 V2 identity；NFC key collision 必须拒绝。
- 非字符串 key、非 JSON object、tuple/set/bytes、cycle、NaN/Infinity 必须在构造时拒绝。
- M7 absence/partial/type rejection 保持 fail closed。
- 既有非 M7 V1 的已知 hash 和 journal/CLI 回归保持不变。
- 本切片仍不得被当作 caller、journal V3、replay、fit 或完整 authority-schema 已完成。

测试 seam 仅为 `RunIntent` 构造、公开只读 snapshot 和 `content_sha256`；不新增真实 E2E。

## Implementation plan

1. 在 `trial_ledger.py` 增加局部递归 normalizer/freezer 和私有缓存字段。
2. 将 V2 验证、规范化、序列化和 hash 固定在 `__post_init__`，保留 V1 原 payload 路径。
3. 扩展 RunIntent 单元/契约测试，覆盖变异、NFC、非法 JSON、V1 regression 和原始缺口。
4. 运行聚焦测试、全量 pytest、Ruff；不运行 replay/fit/PIT/真实数据。
5. 独立 code review 验证源码未越过 class-only 边界。

当前代码只完成了双 presence 和初步 V2 payload；上述 immutable/canonical 修复尚未实现。

## Open decisions

无阻塞决策。完整 binding schema、caller/event V3 接线仍由 v48 后续独立切片持有，不在此处提前
实现。

## Verdict

`PASS`：v50 在同一 RunIntent class-only 切片内关闭 v49 的 identity 可变性、V2 canonicalization
和落地状态夸大问题；应进入独立 R3 复审。M7 仍为 `NOT_RUN`，所有执行边界保持禁止。
