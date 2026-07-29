# M6.5 架构确认 v21 — Closed authority context and single-root archival replay

状态：`ARCHITECTURE_READY / 待变更设计`。本文件以
`architecture_confirmation_v20.md`（SHA-256
`d944ab700454dbc22515a779366a60e09337efb9b69b2365c0608f08441528e0`）为
直接基线，针对两份 v17 独立 R3 设计审查的全部 P1/P2 发现作出架构修订。
v20 中已经正确的 `C → {P,F} → A` 无环物化、Q 在 R 之前冻结完整 V
前像、固定 pre-S0 terminal 和 S0…S6 左向收据链均保留。本文件是
`DESIGN_ONLY`：不创建 E/C/P/F/A/B/Q/R/V 或收据实例；不运行 replay、训练、
PIT、M7 或最终 OOS。

## 1. 适用范围、预先存在的权威与无环发行

本修订只允许 `qlib-peerlite-a-share-daily-v0` 的 M6 archival replay。其
唯一允许的 mode/profile 是：

```text
scope = M6_ARCHIVAL_REPLAY_ONLY
required_profile = { replay_count: 14, model_fit_count: 0, final_oos_opened: false }
```

`M6ReplayAuthorityBootstrap v1`（**Bootstrap**）是 M6.5 工程质量 gate 的
一个强制、immutable、future-free 成员：`M6_5_ENGINEERING_QUALITY_GATE v1 PASS`
必须以 complete typed ref 精确引用它。Bootstrap 不得引用 E/C/P/F/A/B/Q/R/V、
任何 state/receipt、输出、PID、时间或随机数；它只绑定下列预先存在的输入：

- 唯一 `archive_acceptor` 发行身份及完整 actor/ACL/writer matrix；
- E 的单一 O_EXCL 槽、固定 control-root topology、resolver 与 slot layout；
- 七项冻结 runtime role；
- 允许的 family、scope、14/0/OOS profile、schema/nested-ref allow-list。

Bootstrap 是防止 E 自行选择 root、issuer 或 runtime 的唯一发行起点。其内容和
quality gate PASS 都先于 E；因此不存在 E 自我授权或回指未来对象的边。

`M6ReplayAuthorityBinding v3`（**E**）只能由 Bootstrap 指定的
`archive_acceptor` effective identity，在 Bootstrap 指定的 E 槽以
same-directory durable `O_EXCL` 发布。E 必须同时满足：

```text
E.replay_issuer_bootstrap_ref == QualityPass.replay_issuer_bootstrap_ref
E.replay_issuer_bootstrap_ref == Ref(Bootstrap)
E.issuer_identity             == Bootstrap.archive_acceptor_identity
E.actor_acl_writer_matrix     == Bootstrap.actor_acl_writer_matrix
E.replay_control_root_binding == Bootstrap.replay_control_root_binding
E.runtime_roles               == Bootstrap.runtime_roles
E.slot_layout                 == Bootstrap.slot_layout
```

任何一个不等、未知字段、默认值、别名、环境变量、当前工作目录或调用方 selector
都在 E 发布前 fail closed。E 和 Bootstrap 的 allow-list 拒绝 M7/QRC/Plan、任何
future replay object，以及不在列的 schema/role/path template。

## 2. 一个完整、可重算的 authority context

E 内嵌 `M6ReplayAuthorityContext v1`（**Context**）。Context 是闭合
`CanonicalObject-v1`，字段恰好如下；complete typed ref 固定包含
`schema、role、version、repository-relative path、canonical-bytes SHA-256`，并按
以下 role label 的字典序序列化。没有 optional、null、未知成员或隐式推断。

```text
Context = {
  schema: "M6ReplayAuthorityContext/v1",
  family: {
    research_contract_ref,
    family_id: "qlib-peerlite-a-share-daily-v0"
  },
  scope: "M6_ARCHIVAL_REPLAY_ONLY",
  required_profile: { replay_count: 14, model_fit_count: 0,
                      final_oos_opened: false },
  m6_evidence_roles: {
    m6_execution_spec,
    m6_public_gate,
    m6_close_proof,
    m6_historical_verification,
    m6_verified_close_6_44,
    m6_5_quality_gate_pass
  },
  runtime_roles: {
    sealed_verifier,
    fd_exec_helper,
    bootstrap (typed M6ReplayProcessBootstrap; distinct from
               replay_issuer_bootstrap_ref),
    replay_runtime_closure,
    python_startup_policy,
    process_startup_state,
    fixed_argv_cwd_import_policy
  },
  replay_issuer_bootstrap_ref,
  replay_control_root_binding,
  actor_acl_writer_matrix,
  recursive_schema_and_nested_ref_allowlist,
  fixed_control_slot_layout
}
```

`research_contract_ref` 的 `family_id` 必须与 Context family ID byte-for-byte
相同。第六项 M6 evidence role（quality PASS）必须精确引用同一个 Bootstrap；
Context 的 `replay_issuer_bootstrap_ref` 也必须为该 Bootstrap。这样 quality
gate、Bootstrap、E 三者的 issuer/runtime/root/actor matrix 不能被分别替换。
`Context.fixed_control_slot_layout ==
Context.replay_control_root_binding.fixed_slot_layout == Bootstrap.slot_layout`；
下文的 `E.root` 是 `E.Context.replay_control_root_binding` 的唯一简称，不是
另一个可选择的 root 字段。

唯一合法的 key 为：

```text
authority_context_key = SHA256(CanonicalObject-v1({
  domain: "qlib-peerlite/m6-replay-authority-context/v1",
  context: Context
}))
```

旧的 `m6_evidence_key` 名称和“只对六项 M6 evidence role 重算”的算法全部拒绝。
key 的前像不能含 E 自身 SHA、C/P/F/A/B/Q/R/V、state、receipt、输出、current
head、wall-clock、PID 或随机数，故对象图保持无环。

每个 `X ∈ {C,P,F,A,B,Q,R,V}`，以及每个 S0…S6、ChildReceipt、
ReplayExecutionReceipt 与 ArchiveAcceptanceReceipt，必须带有：

```text
X.authority_binding_ref      == Ref(E)
X.authority_context_key      == E.authority_context_key
Canonical(X.authority_context_snapshot) == Canonical(E.Context)
RecomputeKey(X.authority_context_snapshot) == E.authority_context_key
```

所有这些 schema 拒绝任何另行选择的 family、scope、runtime、resolver、root、
registry、lock、slot 或 writer 字段。若某字段为功能所必需，它只能从
`authority_context_snapshot` 解析，并逐项相等。特别是：

```text
Q.complete_v_preimage.runtime_roles          == E.Context.runtime_roles
V.historical_inventory.runtime_roles         == E.Context.runtime_roles
V.historical_inventory.m6_evidence_roles     == E.Context.m6_evidence_roles
V.family/scope/profile                        == E.Context.family/scope/profile
ReplayExecutionReceipt observed runtime roles == V.runtime_roles == E.Context.runtime_roles
ChildReceipt and ArchiveReceipt runtime roles == V.runtime_roles == E.Context.runtime_roles
```

因此“六项静态 M6 evidence 均相同、但 family/scope/verifier/helper/runtime/
startup/argv/cwd/import 改变”的对象，在 Q、R、V 和任何输出之前均不可通过。

## 3. 单一 replay control root、registry 与 transaction lock

Context 的 `replay_control_root_binding` 是 `ReplayControlRootBinding v1`。
它不是逻辑名称或 ACL 描述，而是从 Bootstrap 中 no-follow FD 观察得到的闭合物理
拓扑。E、C、P、F、A 与 registry 只使用这一 root；不允许 evidence-store/root
的可选映射或第二条解析路径。

```text
ReplayControlRootBinding v1 = {
  resolver_profile_ref,
  control_store_anchor_ref,
  control_store_anchor_identity: DirectoryIdentity v2,
  replay_control_root_components: ["m6-replay-control"],
  replay_control_root_component_identity_chain: [DirectoryIdentity v2],
  replay_control_root_identity: DirectoryIdentity v2,
  registry_components: ["registry"],
  registry_component_identity_chain: [DirectoryIdentity v2],
  registry_identity: DirectoryIdentity v2,
  transaction_lock_components: ["registry", "locks", "m6-replay-transaction.lock"],
  transaction_lock_identity: FileIdentity v1,
  claims_parent_components: ["registry", "claims"],
  claims_parent_identity_chain: [DirectoryIdentity v2, DirectoryIdentity v2],
  bindings_parent_components: ["registry", "bindings"],
  bindings_parent_identity_chain: [DirectoryIdentity v2, DirectoryIdentity v2],
  pre_s0_parent_components: ["registry", "pre-s0-terminals"],
  pre_s0_parent_identity_chain: [DirectoryIdentity v2, DirectoryIdentity v2],
  fixed_slot_layout: {
    authority: ["authority", "m6-replay-authority-v3.cjson"],
    control_policy: ["policies", "m6-replay-control-policy-v5.cjson"],
    namespace: ["namespaces", "m6-replay-output-namespace-v5.cjson"],
    profile: ["profiles", "m6-replay-control-profile-v5.cjson"],
    anchor: ["anchors", "m6-replay-control-anchor-v5.cjson"],
    claim: ["registry", "claims", "<K>.reservation-v6.cjson"],
    binding: ["registry", "bindings", "<K>.binding-v12.cjson"],
    pre_s0_terminal: ["registry", "pre-s0-terminals", "<K>.cjson"]
  }
}
```

`<K>` 只能是已验证的小写 64 位 SHA-256 单一路径 component；绝对路径、`..`、
separator、symlink、替代 resolver、替代 registry 或由配置提供的 slot 一律拒绝。
`FileIdentity v1` 是 closed FD-derived regular-file identity，字段为
`type、dev_major、dev_minor、ino、statx_mnt_id、btime_ns、opaque_file_handle_sha256、
uid、gid、mode_octal、access_acl_sha256、default_acl_sha256`；default ACL absence
也必须使用 canonical absence value。不能完整观察 lock 即 fail closed。

A 不得“描述一个相似 root”，而必须复制 E 的整个 binding：

```text
A.replay_control_root_binding == E.Context.replay_control_root_binding
A.control_root_identity        == E.root.replay_control_root_identity
A.resolver_profile_ref         == E.root.resolver_profile_ref
A.registry_components/chain/id == E.root.registry_components/chain/id
A.lock_components/id           == E.root.transaction_lock_components/identity
A.fixed_slot_layout            == E.root.fixed_slot_layout
```

C 的 PTemplate、P、F、B、Q、R、V 和所有 state/receipt 只能引用/继承这一个
binding；它们不得拥有可选 root、registry、lock、resolver 或 slot。每个
freeze、claim、prelaunch、recovery、state transition、archive 或 registry scan 都
按固定顺序执行：

```text
1. 从 Bootstrap 指定的 sealed anchor 取得 no-follow control-root FD。
2. ObserveDirectoryIdentityV2(anchor_fd) == E.root.control_store_anchor_identity；
   用 E/A resolver 从该 FD 解析 `replay_control_root_components`，每级 identity
   等于 `replay_control_root_component_identity_chain`，最终
   `ObserveDirectoryIdentityV2(root_fd) == E.root.replay_control_root_identity
   == A.control_root_identity`。
3. 用 E/A 的 resolver 与 components 从已验证 root FD 解析 registry；每级 identity
   均等于 E/A 的 registry component chain，最终等于 registry_identity。
4. 从已验证 registry 解析 transaction lock；ObserveFileIdentityV1(lock_fd)
   == E/A 的 transaction_lock_identity。
5. 仅在步骤 1–4 全部通过后，获取 lock、解析 E/A 固定的 claim/binding/terminal
   slots、执行 O_EXCL 或继续既有状态。
```

同 ACL、同相对路径、同 schema 但不同 root/registry/claims parent/lock inode 或
opaque handle 的 twin topology 必须在 R 之前失败。步骤 1–4 失败时，绝不在备用
root 写 claim、terminal、receipt 或 archive；若 R 已存在且控制拓扑无法重新验证，
claim 永久不可用，且不能以另一个 root 写替代 terminal。

## 4. 完整的 DirectoryIdentity v2 与 canonical coordinate

`DirectoryIdentity v2` 在本修订中保留既有完整语义，绝不是缩减版。所有
`ObserveDirectoryIdentityV2(fd)` 的 canonical payload 恰有：

```text
type = "directory"
dev_major; dev_minor; ino; statx_mnt_id; btime_ns
opaque_file_handle_sha256
uid; gid; mode_octal
access_acl_sha256; default_acl_sha256
```

`opaque_file_handle_sha256` 为 approved `fd_exec_helper` 对同一 no-follow
`O_PATH|O_DIRECTORY` FD 运行 `name_to_handle_at(fd, "", …, AT_EMPTY_PATH)` 所得
`{handle_type, mount_id, exact_handle_bytes}` 的 `CanonicalObject-v1` SHA-256。
helper 返回的 mount ID 必须等于 `statx_mnt_id`。初始 `EOVERFLOW` 只允许一次
精确 buffer-sizing retry；任何第二次 `EOVERFLOW`、unsupported API/filesystem、
permission error、空/截断/非 canonical handle 或任何其他错误均 fail closed，绝不
退回 stat/inode tuple。没有 optional/null/default/unknown member；
`parent_identity_digest` 和任何装饰性 digest 都拒绝解析。

该完整 v2 identity 同时用于 control root、registry chain、claims/bindings/
terminal parents 和 B 的 final parent。令 `D = B.final_parent_identity`，唯一
coordinate 公式为：

```text
K = SHA256(CanonicalObject-v1({
  domain: "qlib-peerlite/m6-replay-coordinate/v4",
  anchor_sha256: A.sha256,
  namespace_sha256: P.sha256,
  final_parent_identity_v2: D,
  leaf_component: B.basename
}))
```

D 不单独 hash/ref；K 不含 R/Q/V hash、slot contents、state/head、time 或 random。
在 freeze、claim、prelaunch、每次 recovery、每个 registry scan 和 archive，强制：

```text
D_obs = ObserveDirectoryIdentityV2(final_parent_fd)
Canonical(D_obs) == Canonical(B.final_parent_identity)
K_obs = DeriveK_v4(A, P, D_obs, B.basename)
K_obs == Q.K == R.K == V.K
```

R 前失败不写 R/V/S0/输出。R 后、S0 前若 E/A root topology 仍完整可验证，则只在
固定 E/A-bound terminal 槽写入 `FINAL_PARENT_IDENTITY_MISMATCH` terminal 并永久
burn/quarantine；不得替换 D、重算 K 或重新领 claim。S0 后发生不等时拒绝继续、
accept 或 archive，绝不写 S6 或平行 terminal。

## 5. Retained Q → R → V precommit and lifecycle

Q 是 `M6ReplayInputPrecommit v1`：在 claim 之前冻结 complete V payload、完整
Context snapshot、K、固定 V/terminal slots、全部 historical/runtime input；它不含
R/V/output/state/receipt/current-head/time/random。R 是唯一 `O_EXCL` coordinate
claim，且只能写入 `Resolve(E/A-bound registry, claim slot, K)`；R 不含 V bytes 或
V ref。V 只能在固定 binding slot 以 no-replace 发布，且 raw canonical bytes 必须是：

```text
V == CanonicalComplete(Q, reservation_ref = Ref(R))
```

因此 reservation graph 保持单向：

```text
B[D] → Q[K, complete V preimage] → R[K, fixed slots]
     → V = CanonicalComplete(Q,R) → S0 → S1 → O → S2 → H → S3
     → ChildReceipt → S4 → ReplayExecutionReceipt → S5
     → ArchiveAcceptanceReceipt → S6
```

Q alone inert；R without valid V 为 `ABANDONED_BURNED_PRE_V`；R + valid V without
S0 为 `ABANDONED_BURNED_POST_V_PRE_S0`；invalid/duplicate/partial V 或 pre-S0 output
为 `QUARANTINED_PRE_S0`；现存 terminal 永远拒绝 V/S0/root/archive。所有 R/V/
terminal slots 均为上述 binding 的纯路径函数。D/handle 不创建 ArtifactRef 或收据，
不增加 hash cycle。

## 6. 架构边界、执行责任与可验证义务

- `archive_acceptor` 只写 Bootstrap/E/C、ArchiveAcceptanceReceipt/S6；
  `replay_supervisor` 只写 P/F/A/B/Q/R/V、pre-S0 terminal、S0/S1/O/S2/H/S3/S4、
  ReplayExecutionReceipt/S5；child verifier 只写 ChildReceipt。实际 peer/FD ACL
  与 Context actor map 必须相等。
- C 继续只保存 closed PTemplate（不保存 P hash）；P/F 独立从 C materialize；A
  再统一两者。P/F/A 无法选择 Context、root 或 runtime，故不引入 C/P/F/A cycle。
- 所有 durable publish 保持 temp → file fsync → atomic no-replace → directory fsync，
  以及既有 no-follow/no-xdev/umask/ACL/PIT controls。此修订不改变 M6 既有证据、
  trial budget、M7 contract、数据产品或最终 OOS seal。

后续 test design 必须至少证明：完整 Context 的任一 family/scope/runtime/argv-cwd-
import/Bootstrap/root/actor/allow-list splice 在 R 前拒绝；同 ACL twin root/registry/
lock 拒绝；DirectoryIdentity v2 缺失或仅改变 opaque handle 时拒绝；unsupported
handle helper fail closed；D/K 每 phase 重算；Q/R/V byte completion、pre-S0 recovery、
writer matrix 和 retained FD/ACL/umask/PIT fixtures 均成立。设计独立 PASS 前不得写
测试或实现；M7、CCC/Gate、archival replay 与 final OOS 继续封锁。

## 7. 架构决定

选择“一个完整 Context snapshot + 一个单根 topology binding”，而非只传递六项
evidence digest 或允许相同 ACL 的多根映射。前者多出有限的 canonical bytes 与
比较，但将普通部署/runtime/path/recovery 错误变成确定的 R 前拒绝；后者会留下
运行时或物理控制根拼接空间，不符合冻结威胁模型。该选择不增加服务、数据库、
网络依赖或研究模型复杂度。

结论：在 v18 变更设计逐项落实本架构、随后通过新的独立 R3 设计审查前，M6.5
仍未通过，且所有下游工程与 M7 工作保持禁止。
