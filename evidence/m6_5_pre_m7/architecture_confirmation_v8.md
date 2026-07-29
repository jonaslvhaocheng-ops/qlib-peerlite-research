# M6.5 架构确认 v8 — 完整行为覆盖、密封 Fit 输入与事务性结果发布

状态：`PASS — revised bounded architecture confirmation`  
替代：本文件替代 `architecture_confirmation_v7.md` 作为当前 M6.5 架构依据；旧版本与审查保留历史可追溯性。  
不变：不运行 M7、replay 或 OOS；不修改 M6 immutable history；M6.5 仅实现 synthetic proof path。

## 1. 追加的五个不可分离边界

v7 的方向保留，但 production artifact 还必须满足：

1. 每个派生 state source、selection predicate 与 aggregation 的 future behavior 证据覆盖完整 candidate state
   输出，不能以无关/`PREFIX_REPLAY` receipt 代替。
2. 每个 fit admission 将 exact certified state、candidate、fold、FD/bytes 与 event 永久绑定；guard 不从
   caller 接受任何另一 state object。
3. Dispatch 用独立的 durable single-winner claim，不依赖可 fork 继承的 flock 或内存 receipt。
4. 任何非 terminal fit 的 checkpoint/score/recorder 永远不是可发现的 official result；崩溃后仅能 forensic
   quarantine，不能“顺手继续使用”。
5. 实际 replay launcher 的 bundle/entrypoint identity 与 grant、activation、deployment、acceptance signature
   全链绑定。

## 2. State behavior 由冻结 coverage plan 约束

在 CandidateTrainingInputManifest 与 M7 QRC 之间新增 immutable `StateBehaviorCoveragePlan v1`。该计划没有
运行结果，只冻结：

- state builder/feature/predicate/aggregation code or query digests，四个 derived sources、所有 seven
  selection flags/outcomes 与 daily aggregate 的完整 feature axis；
- candidate state-output projection 的 exact protected key-set/count/digest，以及全部 candidate prediction-date
  上界；
- 每个 coverage entry 的 required probe suite：对适用路径必须有 future-value、revision 和 universe/selection
  counterfactual；`PREFIX_REPLAY` 只能补充，永远不可替代未来 probe；
- 若某个 probe 按 frozen source semantics 确实不适用，明确 QRC-bound rationale、target path 和拒绝条件，而非
  loader 的默认豁免。

每个 behavior manifest must have the same exact production fixed-audit parent, matching code/query and candidate
projection. Its protected output keys/values must equal the coverage plan's candidate state projection, not merely a
non-empty subset. Loader requires a complete entry set and rechecks B001–B004, raw/params/env/output lineages and
future mutation scope. The behavior result remains `NOVEL_CANDIDATE`: coverage is a necessary negative-evidence
bundle, never a replacement for fixed `CERTIFY`.

## 3. State-to-fit sealed input contract

`FitAdmissionDescriptor v2` is the only object the authoritative executor can use. It binds:

```text
QRC + authorization plan + activation/event identity
StateArtifactBinding hash
fixed / behavior coverage bundle / join evidence hashes
CandidateTrainingInputManifest hash
exact state artifact and consumed-cell/key/date/value digests
four-column schema/order and fold/segment/date coverage
sealed input/state FD device/inode/content identity
```

Supervisor opens and validates the exact state/candidate objects, then exposes them to the runner only as sealed
read-only FDs (or equivalently content-addressed copied bytes) named in descriptor. `ModelFitExecutionGuard` reopens/
fstats/hashes these FDs and reconstructs the only permitted input itself; it does not accept caller DataFrame, tensor,
alternate descriptor or free fold. Official checkpoint, prediction, result and terminal receipt repeat the same identity
set. A valid admission paired with another valid state/fold, post-admission FD swap, synthetic descriptor or direct
library call fails before `model.fit`.

## 4. Fork-safe one-winner dispatch and output transaction

### 4.1 Dispatch claim

After `ADMISSION_ISSUED`, the runner creates an event-specific durable dispatch claim with a single-winner primitive
(`O_CREAT|O_EXCL`/equivalent CAS) in a fixed, governance-owned state root. The claim is keyed by activation nonce +
event ID + admission content hash and stores PID, process start/boot identity and sealed-input identities. Guard opens
the claim afresh; inherited lock/FD or in-memory receipt is never sufficient.

The supervisor forbids fork after admission; workers are clean `spawn` children before admission. An `at_fork` child
handler closes and invalidates lease/admission/state/ledger FDs. Even if a child inherits a token, only one process can
win the durable claim; loser/child/stale/retry transitions to `ABANDONED_UNKNOWN` without model call. The winner fsyncs
claim and durable `DISPATCHED` before `model.fit`; a crash after either means the event is irrevocably spent.

### 4.2 Result publication

Plan/admission reserves unique, non-reusable `staging_root` and `final_root` per event; contingency event roots are
different. `ModelFitExecutionGuard` is the only writer and can write **only** to staging. It validates a complete
output inventory/digests and writes a `PreparedResultReceipt`; then it atomically renames staging to event final root.
That directory remains quarantine until the stable official-result index receives an fsynced
`TERMINAL_PUBLISHED` record binding event/admission/state identities, inventory, terminal-result hash and final root.

All model selection, recorder readback, score loading and report code use `OfficialResultResolver`, which accepts only
a published-index record plus matching terminal receipt/inventory. A crash before index publication leaves final/staging
files forensic-only and undiscoverable; recovery marks them `ABANDONED_OUTPUT_READY`/quarantined, never promotes or
reuses them. A crash after fsynced `TERMINAL_PUBLISHED` is valid only if final inventory matches; mismatch is fail-closed.
No cleanup deletes forensic output automatically. This intentionally may waste a plan slot but prevents unknown result
consumption.

## 5. Replay launcher identity is an approved measured input

`ReplayLauncherBundle v1` is a content-addressed, governance-owned tree: canonical tree digest, entrypoint relative
path/bytes, bootstrap runtime identity, argv grammar and source inventory. `M6ReplayLaunchGrant`,
`ReplayActivationReceipt`, deployment inventory, launcher observation, child process record and signed acceptance
payload all bind exactly the same launcher bundle digest/entrypoint/argv policy.

Supervisor executes launcher only from activation-selected sealed FD/immutable bundle. Acceptance service independently
checks the deployment launcher measurement, expected launcher process identity/exit/argv, grant/activation nonce,
runtime/staged verifier/archive/tree/output/ledger and child linkage before it signs. A wrong/replaced launcher, argv
swap or receipt with mismatched launcher digest cannot be accepted even if its verifier and output look self-consistent.

## 6. Mandatory proof obligations

- Behavior coverage: omitted entry, subset key digest, wrong source code, `PREFIX_REPLAY` substitute, irrelevant future
  poison, unapproved NOT_APPLICABLE path and mismatched fixed parent must fail.
- Fit input: valid admission + wrong state/fold, FD replacement, synthetic descriptor, post-admission state mutation and
  direct tensor must fail with no call/output.
- Dispatch: exact fork after admission/before claim, parent-child race, inherited FD reopen, crash during claim publish
  and stale claim retry must yield at most one observed fit call.
- Output: crashes before fit/during fit/after fit/before receipt/after rename/before index/after index must never expose
  non-terminal output through OfficialResultResolver; different contingency root is enforced.
- Replay: wrong launcher bundle/entrypoint/argv/replacement and signature with a mismatched launcher measurement must
  fail acceptance.

Only after a design proving these interfaces passes independent review may red tests and implementation begin.
