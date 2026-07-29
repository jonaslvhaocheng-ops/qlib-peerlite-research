# M6.5 R3 修复设计 v18 — Closed authority-context implementation

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一架构输入是
`architecture_confirmation_v21.md`（SHA-256
`7e14a5b8a5cbdb1d1bc3e44fa7bb623ce9c5c8bba20cd1efe8ca418618b66881`）；
本设计替代 `m6_5_repair_change_design_v17.md`。它只定义 M6.5 的新治理代码和
合成测试边界，不创建真实 Bootstrap/E/C/P/F/A/B/Q/R/V，不运行 archival replay、
M7、PIT 或最终 OOS，也不改任何 immutable M6/M5/M3 证据或 trial ledger。

## 1. 问题、目标与范围

### 当前行为

现有 `src/qlib_peerlite/governance/m6_archive.py` 能以只读方式验证冻结 M6
evidence/ledger prefix；`trial_ledger.py` 能原子、幂等地 reconcile journal starts。
它们不拥有 M6 archival replay 的 runtime authority、FD identity、control root、
reservation 或 crash lifecycle。v20/v17 因而只把六项 evidence role 传过下游，
未能机械证明 family/runtime/startup/scope 与物理 registry root 同时相等。

### 目标

实现一个小而独立的 M6 replay control-plane：

1. 解析和重算 v21 的完整 `M6ReplayAuthorityContext v1`；
2. 从 quality-PASS-bound Bootstrap 验证并发行 `M6ReplayAuthorityBinding v3`；
3. 通过 no-follow FD identity 将 E、A、registry、lock 与固定 slots 绑定到同一
   root；
4. 用完整 `DirectoryIdentity v2`（含 opaque handle）计算 K v4，并实现
   Q → R → V 的不可重建 reservation / pre-S0 recovery；
5. 为之后的只读 archival replay 提供 fail-closed validation seam，但本改动绝不
   启动 replay 或模型 fit。

### 非目标

- 不增加 M7/CCC/Gate、市场状态、数据产品、模型或组合逻辑；
- 不重解释或迁移 M6 历史 receipt、冻结 Git revision、M6 `6/44` close 或 legacy
  `4/29` ledger；
- 不让 macOS/local tests 冒充 Linux `name_to_handle_at` production proof；
- 不新增数据库、daemon、网络服务、权限提升或外部依赖。

### 约束与假设

- 运行时为冻结的 Python 3.11；真实 control-plane 只能在受支持的 Linux server
  上运行，缺少 `statx`/`name_to_handle_at(AT_EMPTY_PATH)`/no-replace publish
  primitives 就拒绝；
- 正常路径、配置、并发、crash/recovery 和 runtime misbinding 在防御范围；host、
  ACL、内核或任意 native-code compromise 不在冻结威胁模型内；
- 所有真实 authority inputs 必须来自未来 M6.5 PASS 的 Bootstrap 与 QualityPass；
  单元测试仅用明确标记的 synthetic observer/temporary topology。

## 2. Repository evidence and bounded approach

| Surface | Existing responsibility | v18 decision |
| --- | --- | --- |
| `governance/artifacts.py` | canonical JSON and SHA helpers | Reuse; do not introduce a second serializer. |
| `governance/m6_archive.py` | read-only historical M6 proof | Preserve behaviour and public API; it must not become a writer or root resolver. |
| `governance/trial_ledger.py` | append-only trial counts and its own lock | Preserve; replay control registry never substitutes it for the family ledger. |
| `scripts/server/verify_m6_peerlite_archival_replay.py` | 14-fold read-only replay worker | Do not invoke or broaden in this change; a later accepted authority may call it only after validation. |
| `tests/test_m6_archive.py`, `tests/test_trial_ledger.py` | retained historical/ledger regression evidence | Preserve and run unchanged. |

考虑过的方案：

1. **在 `m6_archive.py` 追加 authority/FS code**：拒绝。它会把 historical verifier、
   production-like writer 和 platform-specific FD code 混在一起，增加对冻结 M6 proof
   的回归面。
2. **新建一个 governance control-plane 模块组（选择）**：identity、authority graph
   和 registry lifecycle 各自单责，复用既有 canonical serializer，且所有新接口只在
   新测试和将来的 server entry 使用。
3. **引入数据库或常驻服务管理 claim**：拒绝。单 host 上固定、可 fsync 的 slots 已能
   满足当前 failure model，额外服务会增加部署和恢复状态而不增加本阶段信息价值。

## 3. Proposed components and public contracts

### 3.1 `src/qlib_peerlite/governance/m6_replay_identity.py`

该模块是唯一允许读取 FD identity 或把 component list 解析为 FD 的边界。它不接受
任意 string path 作为 authority root，也不从 cwd/environment 推断位置。

公开/稳定的内部接口：

```python
class M6ReplayIdentityError(RuntimeError): ...

@dataclass(frozen=True)
class DirectoryIdentityV2: ...

@dataclass(frozen=True)
class FileIdentityV1: ...

class FdIdentityProvider(Protocol):
    def observe_directory_v2(self, fd: int) -> DirectoryIdentityV2: ...
    def observe_file_v1(self, fd: int) -> FileIdentityV1: ...
    def resolve_dir_components(
        self, parent_fd: int, components: tuple[str, ...]
    ) -> tuple[int, tuple[DirectoryIdentityV2, ...]]: ...

def canonical_directory_identity_v2(value: DirectoryIdentityV2) -> bytes: ...
def canonical_file_identity_v1(value: FileIdentityV1) -> bytes: ...
```

`NativeLinuxFdIdentityProvider` 是 production implementation：只接受已打开的
no-follow descriptors；使用 frozen fd helper 获取 `statx` mount/btime 和
`name_to_handle_at(fd, "", …, AT_EMPTY_PATH)` 的 exact handle。它只能为一次初始
`EOVERFLOW` 进行精确 sizing retry，随后任何 unsupported/permission/low-fidelity/
noncanonical handle 错误都抛出 `M6ReplayIdentityError`。它不降级为 inode tuple。
对 directory 和 file 的 canonical object 固定包含 v21 中的所有稳定字段，特别是
`opaque_file_handle_sha256`；未知/缺失/额外字段、非小写 64 hex handle 或对 file 的
非 canonical default-ACL absence 均拒绝。

`SyntheticFdIdentityProvider` 仅置于 tests fixture 中，不属于 production API；
它的存在只用于验证拒绝语义，不能产出可用于真实 authority 的 receipt。

### 3.2 `src/qlib_peerlite/governance/m6_replay_authority.py`

该模块是纯 canonical schema/graph validator。它不创建目录、不做模型调用、不打开
archive runner。它定义：

```python
class M6ReplayAuthorityError(RuntimeError): ...

@dataclass(frozen=True)
class TypedArtifactRef: ...
@dataclass(frozen=True)
class ReplayControlRootBindingV1: ...
@dataclass(frozen=True)
class M6ReplayAuthorityContextV1: ...
@dataclass(frozen=True)
class M6ReplayAuthorityBootstrapV1: ...
@dataclass(frozen=True)
class M6ReplayAuthorityBindingV3: ...

def derive_authority_context_key(context: M6ReplayAuthorityContextV1) -> str: ...
def derive_coordinate_k_v4(
    *, anchor_sha256: str, namespace_sha256: str,
    final_parent_identity: DirectoryIdentityV2, leaf_component: str,
) -> str: ...
def validate_context_snapshot(
    candidate: Mapping[str, Any], authority: M6ReplayAuthorityBindingV3
) -> None: ...
def validate_bootstrap_quality_pass(
    bootstrap: M6ReplayAuthorityBootstrapV1, quality_pass: TypedArtifactRef
) -> None: ...
```

`TypedArtifactRef` 必须严格解析 schema/role/version/repository-relative path/
canonical-bytes hash；path 不得绝对、含 `.`/`..`、separator injection 或非 allow-list
template。`M6ReplayAuthorityContextV1` 的字段集合、role labels、family ID、scope、
14/0/OOS profile、六项 M6 evidence、七项 runtime roles、Bootstrap ref、actor matrix、
allow-list、topology 和 slot layout 都完全按照 v21。`derive_authority_context_key()`
只接受完整 typed Context，使用唯一 v21 domain；legacy `m6_evidence_key`、partial
role map 或 caller-supplied key 均拒绝。

`M6ReplayAuthorityBindingV3.from_verified_inputs()` 只在以下相等关系全部成立后构造
E：QualityPass→Bootstrap、Bootstrap→Context、Bootstrap→issuer/actor/root/runtime/
slots、research contract→family ID。它没有“选择最佳 matching ref”或 path fallback。
`validate_context_snapshot()` 由 C/P/F/A/B/Q/R/V 与所有 receipt/state 的 parser 统一
调用，要求 authority ref、context key、canonical snapshot 完全相等；Q/V/receipt 的
实际 runtime inventory、family、scope/profile 和六项 historical evidence 还要逐项
等于 Context。这样 C/P/F/A 不能保留第二个 selector，Q/V 也不能将 RT1 authority
与 RT2 execution 混接。

### 3.3 `src/qlib_peerlite/governance/m6_replay_registry.py`

该模块拥有唯一的 control-root resolution、transaction lock、durable no-replace
publisher、Q/R/V lifecycle 和 pre-S0 recovery。它依赖 3.1/3.2，但不依赖模型、Qlib、
数据或 `trial_ledger.py`。

```python
class M6ReplayRegistryError(RuntimeError): ...

@dataclass(frozen=True)
class VerifiedControlTopology: ...
@dataclass(frozen=True)
class ReplayInputPrecommitV1: ...
@dataclass(frozen=True)
class FreshOutputReservationV6: ...
@dataclass(frozen=True)
class M6ReplayInputBindingV12: ...

def reopen_and_validate_control_topology(
    *, authority: M6ReplayAuthorityBindingV3,
    anchor_fd: int,
    provider: FdIdentityProvider,
) -> VerifiedControlTopology: ...
def build_precommit_before_claim(...) -> ReplayInputPrecommitV1: ...
def reserve_then_bind(
    *, topology: VerifiedControlTopology, precommit: ReplayInputPrecommitV1,
) -> tuple[FreshOutputReservationV6, M6ReplayInputBindingV12]: ...
def recover_pre_s0(..., topology: VerifiedControlTopology) -> RecoveryDecision: ...
```

`reopen_and_validate_control_topology()` 按 v21 固定五步顺序重新验证 sealed anchor、
root component chain、registry chain、lock FileIdentity 和 fixed slots；它返回的
descriptor 只能由 registry API 使用。没有 `Path`/root string overload，也没有从
A、P、环境或 caller 获取“另一个 registry”。每次 freeze、claim、prelaunch、recovery、
scan、state transition 和 archive entry 都必须先调用它。

`build_precommit_before_claim()` 必须完成 Context snapshot、complete V payload、
full D v2、K v4 和固定 slots 的所有 validation；其 schema 明确禁止 R/V/output/
state/receipt/current-head/time/random。它重开 final-parent FD、比较 D、重算 K；失败时
没有可写副作用。

`reserve_then_bind()` 在已验证 transaction lock 内以 fixed claim slot `O_EXCL` 发布
R，然后仅从 `(Q, Ref(R))` materialize V；V 的 raw canonical bytes 必须等于
`CanonicalComplete(Q, reservation_ref=Ref(R))`，并在固定 binding slot no-replace
发布。publisher 使用 same-directory temporary file → file fsync → supported atomic
no-replace link/rename → parent directory fsync；不具备 primitive 立即失败，不以
`replace` 或 non-atomic existence check 降级。R 不含 V bytes/ref，Q 不含 R/V，V 不
引入任何 future ref，故没有 R↔V cycle。

对于 R 后 failure，`recover_pre_s0()` 只在 topology 已重新完整验证时写入固定、
一次性 terminal：R 无有效 V、R+V 无 S0、invalid V/pre-S0 output，以及 final-parent
identity mismatch，分别映射至 v21 的 burn/quarantine reason。无法验证 topology 时
不得在第二 root 写 terminal；已有 claim 变为 unavailable。任何 terminal 禁止后续
V/S0/output/archive，且不删除、不重建、不重领 R。

### 3.4 Server entry and integration boundary

新增 `scripts/server/validate_m6_replay_authority.py` 作为单一 server-side
**validate-only** entry：它接收已由 release/quality pipeline 提供的 Bootstrap、
QualityPass 和 sealed anchor descriptor contract，执行 authority/topology validation，
输出不含数据内容的 diagnostic manifest。它没有 `--run-replay`、fit、M7 或 OOS
option，也不写 E/R/V，除非今后由已批准的独立 archival replay handoff 明确调用 new
registry API。既有 `verify_m6_peerlite_archival_replay.py` 不修改、不运行。

真实 E/R/V writer 只能由 `replay_supervisor` identity 经新 registry API 调用；
archive acceptor/child verifier 的 writer matrix 在 authority parser 和 publisher
两层验证。测试可通过 dependency-injected provider/publisher 观察行为，但不得借此
生成 production-style authority artifacts。

## 4. Data ownership, state and failure behaviour

| Data / state | 唯一 owner | 可变性 / failure rule |
| --- | --- | --- |
| Bootstrap / QualityPass / E Context | quality pipeline / archive acceptor | immutable；缺 ref、hash、issuer、runtime、root 或 actor mismatch 时 E 不构造。 |
| C/P/F/A/B/Q | replay supervisor，按 Context 固定 slot/template | immutable no-replace；任何 snapshot/key/topology mismatch 在 R 前停止。 |
| D / K | FD identity provider + authority derivation | 不信任 caller digest；每阶段重观测，opaque handle unavailable 即停止。 |
| R/V/PreS0Terminal | registry API under validated lock | R 一次性；V 只能 Q+R；crash residue 永不删除或重建。 |
| S0…S6 / receipts | v21 writer matrix | 仅在 context/topology/precedessor 都相等时前进；没有 mutable head。 |
| M6 historical proof / trial ledger | existing modules | read-only historical verification / append-only budget；本模块不改写。 |

正确流程为：验证 Bootstrap/QualityPass → 构造 E → C → P/F → A → B → 重开 topology
与 D/K → Q → R → V → S0。实际实现阶段只会在 synthetic control root 跑到相应
mechanics；没有 M6 quality PASS 或任何真实 M6 replay。

异常与恢复规则：所有 schema、hash、identity、ACL、runtime、fixed slot、writer 或
predecessor mismatch 抛出稳定 reason code、没有 fallback。R 前错误不产生 claim；R
后/S0 前只可在原已验证 topology 写 terminal；S0 后错误只停止后续阶段/acceptance，
不得制造新 terminal、parallel root 或 S6。锁竞争返回 deterministic `ALREADY_CLAIMED`
或 re-read existing immutable object 后的 validation failure，绝不“重试到另一个 K”。

## 5. Compatibility, deployment, observability and rollback

新 schema 仅存在于新的 M6.5 control namespace：`M6ReplayAuthorityBinding v3`、
Context v1、DirectoryIdentity v2 complete encoding 与 K domain v4。不接受 v20/v17
draft `m6_evidence_key`、reduced-D encoding 或 v3 coordinate，也不迁移任何历史 M6
artifact。现有 M6 proof/tests 是回归约束，不是新 API 的输入格式。

部署前，server release pipeline 必须能提供 Bootstrap 和 native helper 的冻结 identity；
否则 validate-only entry 返回 nonzero 并不会创建 output。发布顺序为：纯 parser/
identity code → synthetic tests → independent review → Linux acceptance fixture →
M6.5 gate decision。回滚只是不调用新 entry/不发行新的 E；不可删除任何已发布 claim
或 terminal。

每次拒绝输出最小 structured manifest：schema version、reason code、stage、对象
role、authority-context key prefix 与 control-topology component label；不输出原始
handle bytes、数据、checkpoint、环境 secret 或可选 path。成功的 validate-only manifest
包含 input typed-ref hashes、validated topology identities/hashes、code version 与
explicit `replay_started=false` / `model_fit_calls=0` / `final_oos_opened=false`。

## 6. Verification obligations for the later test-design stage

详细用例、fixtures、oracle 和 coverage 由下一关 `eng-design-tests` 决定；它至少必须
能够证明以下行为义务：

- Context key 对完整、唯一前像重算，且 family、scope、任一 evidence/runtime/startup/
  argv-cwd-import/Bootstrap/root/actor/allow-list drift 在 R 前拒绝；
- E→A→registry/lock 的 FD-derived identity chain 没有 same-ACL alternate root、
  registry、claims parent、lock 或 resolver fallback；
- DirectoryIdentity v2 的每一字段（特别 opaque handle）参与 canonical equality/K v4，
  缺 handle/unsupported helper 不会降级；
- Q/R/V 的 bytes、slots、claim exclusivity、crash terminal 和 S0…S6 predecessor/
  writer rules没有 cycle、fork、重建或越过 terminal；
- 既有 M6 historical verifier、trial ledger、PIT/state tests 不回归；全部行为在
  synthetic input 下完成且没有 training/replay/budget/OOS side effect。

## 7. Ordered implementation plan

1. 在 `m6_replay_identity.py` 实现 closed identity models、canonical serializers 和
   production Linux provider contract；先拒绝 unsupported platform/helper，绝不写
   permissive fallback。
2. 在 `m6_replay_authority.py` 实现 typed refs、Bootstrap/Context/E schema parsers、
   Context key/K v4 derivation及统一 snapshot validation；只复用 `artifacts.py` 的
   canonical serializer。
3. 在 `m6_replay_registry.py` 实现 root/registry/lock reopen validation、fixed slot
   derivation、atomic no-replace publisher、Q-before-R lifecycle和 terminal recovery；
   不改 `m6_archive.py` 或 ledger ownership。
4. 增加 validate-only server entry，将它限制为 no replay/no fit/no M7/no OOS 的
   diagnostic operation；将 actor identity 和 explicit input manifest 传给新 API，
   不读取 ambient config。
5. 由 test-design 定义并经 red-test 阶段证明上述义务；随后实现满足 tests，再跑
   full local regression、Linux acceptance fixture和独立 code review。
6. 仅当 M6.5 的 design/test/code/E2E 证据全部 fresh PASS 时，才允许 gate receipt
   发行 Bootstrap/QualityPass 或考虑 archival replay；M7 仍须独立冻结和审查。

## 8. Open decisions

无产品、数据、模型或研究语义 open decision。Linux native helper 的具体 frozen
build/hash、server control-root 的实际 FD identities 和未来 QualityPass/Bootstrap
实例是运行时输入，不由本设计或本机合成测试自行生成；缺任一输入时为 fail-closed
`NOT_AUTHORIZED`，不是需要用户临时选择的分支。

结论：v18 已将 v21 的 authority/root/D/K 约束映射到受限模块、明确 API、失败语义、
兼容和实施次序。它需要新的独立 R3 design-review PASS；在此之前不进入 test design、
tests、implementation、code review、server replay、M7、CCC/Gate 或 final OOS。
