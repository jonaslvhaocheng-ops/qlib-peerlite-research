# M6.5 canonical v13 / architecture v16 独立对抗式设计审查

## Findings

### [P1] v8 没有验证 B / R / policy / leaf name 的完整等值关系，错误 composite 仍可取得自洽的 archive acceptance

**Section：** v16 §1 第 23–31 行、§2 第 66–90 行、§3 第 95–101 行；v13 §1 第 20–32 行、§2 第 36–51 行。

**Scenario：** `NamespaceParentBinding v1`（B）独立记录 policy ref、parent path 和 `(reservation_id, nonce, basename)`；`FreshOutputReservation v2`（R）也独立记录 policy digest 和同名 tuple；v8 只并列引用两份 content-hash-valid 的对象。设计没有把下列关系列为 freeze、prelaunch、lock、handoff 与 archive 都必须拒绝的 invariant：

```text
B.policy_ref == v8.policy_ref == R.policy_ref
B.parent_relpath == policy.parent_relpath
B.(reservation_id, nonce, basename) == R.(reservation_id, nonce, basename)
basename == CanonicalDerive(reservation_id, nonce, policy_ref)
```

因此普通 constructor/configuration/recovery 错误可以写出 hash-valid 的混合 v8：B 为 `P0/N0` 做了 parent/absence witness，R 却声明 `P1/N1`。每份 JSON、FD identity、receipt 与 hash 都可局部成立，但正文没有规定 `fstatat`、`mkdirat`、root reopen、archive 应以哪份对象为 name/policy authority，也没有要求它们相等。

`derived basename` 也没有被定义为 canonical 的单一 pathname component。`mkdirat(parent_fd, derived_basename, 0700)` 不自动继承此前 control-root → parent 的 `openat2` resolver：absolute path 会忽略 `dirfd`，relative path 可含 `..`。这使一个没有被 schema 拒绝的 leaf 值能够逃出已冻结 parent chain；之后同一 leaf 被 archive reopen 时，receipt 仍可能自洽。Linux [`mkdirat(2)`](https://man7.org/linux/man-pages/man2/mkdir.2.html) 明确规定 absolute `path` 忽略 `dirfd`。

**Impact：** 这是 frozen threat model 内的普通 schema/path/configuration failure，不依赖 hostile runner 或 host compromise。当前 acceptance contract 自身不能拒绝错误 policy/name/parent composite，因而可能接受一个没有由正确 reservation witness 约束的 output root；它直接破坏 future output 不得拥有自由 root authority 的 P1 边界。

**Evidence：**

- v16 第 23–31 行和第 70–78 行分别列 B/R fields；第 95–101 行只要求 fresh-B equality 和 B digest presence，未列 B↔R↔policy tuple equations。
- v13 第 28–32、41–51 行同样未定义 relational validation 或 single-component name grammar。
- v16 第 100 行直接调用 `mkdirat`，但 resolver flags 只在第 27–29 行定义给 parent resolution。

**Direction：** 在 v8 前定义唯一 `ReservationNameBinding v1`（或把它纳入 B），以 typed policy ref、parent relpath、reservation ID、nonce、derivation version 与一个 strict leaf component 为唯一 source of truth。R 应只引用该 object 的 exact digest，或所有重复 fields 都在每一阶段进行 exact equality check。leaf 必须拒绝 empty、`.`、`..`、slash、NUL、absolute/normalization ambiguity 和非单组件值；lookup/reopen 也必须使用 no-follow/no-xdev semantics。测试要分别覆盖 B/R policy mismatch、B/R nonce/basename mismatch、`../`、absolute/slash leaf 及 legacy/unknown receipt substitution。

### [P2] post-`mkdirat` reservation transaction 缺少明确的 FD、lock lifetime 与 durable-state 协议，无法从设计证明 crash/no-reuse 语义

**Section：** v16 §1 第 27–46 行、§3 第 95–110、129–139 行；v13 §2 第 36–56 行。

**Scenario：** v16 唯一明确的 resolver FD contract 是 `O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`，但随即要求在 `mkdirat` 后 `fsync` parent/root。`O_PATH` FD 不能用于 `fsync`；Linux [`open(2)`](https://man7.org/linux/man-pages/man2/open.2.html) 只允许它进行有限操作或充当 `*at()` dirfd。设计没有说明如何用同一 witness 安全重开可同步的 directory FD、再比较 full identity，亦没有规定 namespace lock 必须持有到 created-root FD capture、receipt/state durability 和 descriptor handoff 之后。

v13 把 lock 内的 recheck/`mkdirat`（step 3）和 afterward 的 root identity/receipt（step 4）分开。若实现者在两步间释放 lock，普通 restart/cleanup race 可在第一次 root identity 读取前替换 `R0`；若实现者保留 lock，仍没有 frozen durable `ISSUED/RESERVED/CONSUMED` state 的写入顺序来区分 “从未 mkdir” 与 “mkdir 过但 crash 前未持久化”。这不证明当前会在受信 supervisor 下被错误接受，但让 core crash/never-reuse guarantee 依赖未写出的实现选择，故为 R3 P2，而非把受信 supervisor 的正确实现偏好误列 P1。

**Impact：** authoritative replay 的 crash/quarantine/retry evidence 不能仅凭现有文本被重建或测试；按字面只使用 `O_PATH` 时 `fsync` 会失败，采用额外 FD 或锁范围则留下未冻结的 material design decision。

**Evidence：**

- v16 第 98–101 行明确锁住 re-resolve / absence / `mkdirat`，第 103–107 行才首次记录 root identity、fsync、写 reservation receipt。
- v13 第 41–45 行重现同一切分，且没有 specified sync FD、lock release point 或 state-record ordering。
- v16 第 137–139 行要求 post-reservation crash 永不 delete/recreate/reuse，但没有对应 immutable reservation-state authority。

**Direction：** 写死一个同锁、可恢复的 protocol：`O_PATH` 仅做 identity witness；用 verified resolver 取得 `O_RDONLY|O_DIRECTORY` sync/operation FD 并立即重比 identity/ACL；锁必须覆盖 `mkdirat`、no-follow created-root FD capture、root identity/ACL check、supervisor-only `RESERVED` state 的 `O_EXCL` durable write、receipt write/fsync 及 handoff anchor。state 应唯一绑定 `(v8,B,R,root identity)`，任何 retry/acceptance 先检查它。测试增加 mkdir-return→first-root-open、identity-recorded→receipt-fsync、receipt→handoff、archive 前的 crash/swap hooks。若这些步骤在 implementation design 中被证明由受信 supervisor 单独保证，可在后续 review 降为实现 evidence，而不能继续保持隐含。

### [P2] `control-root binding digest` 是无 typed producer 的 digest edge，当前 no-cycle claim 不能被唯一实现

**Section：** v16 §1 第 16–31 行；v13 §1 第 20–26 行；base v14 §2 第 15–26 行。

**Scenario：** B 在 v8 前创建以避免 binding cycle，却把未定义的 `control-root binding digest` 放进 closed fields。base v14 只定义 policy 内的 control-root identity，没有一个 `ControlRootBinding` artifact；当前项目搜索也只发现 v16 这一处该术语。若实现者把它解释为包含 newly written B/R/v8 的 control-root inventory，则变成 `B → root-digest → B`；若解释为 mutable tree snapshot 或任意 policy hash，则不同实现可生成不可比较的 B。

**Impact：** 这不会单独证明受信 supervisor 会接受错误 output，因而列为 P2；但它使 control-root rotation/recovery 的 evidence edge 与 v16 的 hash-cycle 说明缺少唯一 schema/creation order，阻断 implementation-ready design。

**Evidence：** v16 第 23–25 行及 v13 第 20–26 行都没有定义 artifact type、role/path/schema/hash input universe、writer 或 “must precede B and exclude B/R/v8” 规则；base v14 第 15–26 行的 policy only contains root identity.

**Direction：** 定义 pre-existing immutable `ReplayControlRootBinding v1 ArtifactRef`（role/path/schema/hash/bytes、writer、identity/ACL、content universe 明确排除 future B/R/v8），或删除模糊字段并明确它只能是 canonical `RootIdentityV1` digest。唯一 DAG 应为 `control-root binding → B → R → v8`；所有 JSON 需 canonical、duplicate-key-rejecting serialization，legacy/unknown root-binding and receipt schemas fail closed。

## Controls verified as retained

- v16 对上一轮 D0→same-owner/mode/ACL-D1 parent replacement 的直接修复是正确方向：root、full chain 与 final parent identity 被冻结并在 launch/post-create/archive 比较；这项控制和测试必须保留。
- existing `ArtifactRef` 与 future output 已概念分离；v8 仍保留 M6 archive/spec/gate/close proof、M3 consumed partitions、run/folds/checkpoints/predictions/K16 refit、legacy ledger、runtime/startup/umask 和 `14 replay / 0 fit / OOS=false` inventory，未重开 caller roots。
- v13 的 v7/v1 reservation/binding 与 v6 receipt fail-closed migration 应保留，并在修复中扩展为所有 legacy/unknown `OutputReservationReceipt` 与 child-receipt forms 的明确拒绝。
- v11/v14 的 M7 descriptor v5 / closure-receipt v2、PIT、6/44 genesis、four-actor ACL、effective startup/umask、publisher transaction 和 final-OOS seal 未被本 amendment 授权或放宽。
- `docs/STATUS.md` 仍为 `M6.5=DESIGN_REVIEW_PENDING`；M7、CCC/Gate、server replay、PIT 新认证与最终 OOS 均封存。

## Verdict

`NEEDS_CHANGES` — **0 P0、1 P1、2 P2、0 P3**。最早修复阶段为 `architecture`。完成 canonical architecture/change-design 修订并重新独立审查前，不得进入 test design、red/green tests、implementation、code review、server replay、M7 derived-contract freeze/fit、CCC/Gate 或 final OOS。

## Review limits and status

- Current phase/track: `M6.5-PRE-M7-ENGINEERING-QUALITY` / `design-review`; this review executed and completed, but M6.5 did not pass.
- 本审查是 distinct-subagent、read-only、R3；只讨论 frozen threat model 中的 ordinary schema/path/TOCTOU/concurrency/crash/ACL/runtime errors，不把 hostile runner arbitrary native code、host/control-root/kernel/ACL compromise 或 malicious loader injection 作为 finding。
- 未修改产品代码、tests、research contract、gate、historical evidence 或 quality ledger；未运行项目代码、training、M6 replay、budget consumption、PIT `CERTIFY` 或 final OOS。
- Router 在审查时选择 `design-review`；observed ledger revision=`92`，source digest=`sha256:60240c73fbb786c03434fd97e80b6935be0bb9729e811f3cbcf94356581eedd0`。后续记录必须重新 route，不能盲用本报告的 revision。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 92,
  "source_digest_observed": "sha256:60240c73fbb786c03434fd97e80b6935be0bb9729e811f3cbcf94356581eedd0",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "REPLAY_RESERVATION_ASSOCIATION_AND_DURABILITY_NOT_CLOSED",
  "summary": "v16 correctly adds parent identity binding, but the acceptance contract does not require B/R/policy/name equality or a safe one-component leaf. The post-mkdir FD/lock/durability transaction and typed control-root digest edge remain implementation-ambiguous.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 1, "P2": 2, "P3": 0},
  "subject_digest": "sha256:fdba160c3e22680b3ba20844966fef0e673cbcb66b9ad1a3b51b0f283dba9e8a",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v13.md",
    "sha256": "sha256:fdba160c3e22680b3ba20844966fef0e673cbcb66b9ad1a3b51b0f283dba9e8a"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v16.md",
    "sha256": "sha256:4a245590e8cc2a30610376167c67cbf3054d039a70fa2c7d410711f4d05992a4"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "status_evidence": {
    "path": "docs/STATUS.md",
    "sha256": "sha256:0c625bb4dd01ab585bf825f3e52296520141dabdf34260dc9af6888ed476d7c5"
  },
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v13_adversarial.md"
  ],
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next --ledger .engineering-quality/changes/m6-5-pre-m7-repair/ledger.json --repo . (route inspection only)",
    "read-only inspection of v11/v12/v14/v15 retained contracts and current replay/governance source interfaces",
    "read-only consultation of Linux open(2), openat2(2), and mkdirat(2) semantics"
  ],
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_adversary",
    "limitations": [
      "No product/test/contract/gate/ledger/historical-evidence implementation changes.",
      "No training, M6 replay, budget consumption, real PIT certification, or final-OOS access."
    ]
  },
  "blockers": [
    "Define and validate one canonical reservation-name/policy/parent-binding relation, including a non-escaping one-component leaf.",
    "Specify a lock-held, sync-capable, durable post-mkdir reservation-state protocol before implementation.",
    "Define a typed, pre-existing, acyclic control-root binding edge, then obtain a fresh independent design review."
  ],
  "next_route": "architecture"
}
```
