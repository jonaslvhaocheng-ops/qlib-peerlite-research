# M6.5 R3 修复设计 v8 — 研究治理控制面与封闭 archive replay

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
Owner：M6.5 pre-M7 quality track  
Requirement：解决 independent design review v7 的四个 P1（fork/继承下重复 fit、未外部锚定的 authority activation、未绑定 admission 的 terminal publish、未闭合的 Python/native runtime replay）。  
Risk：`R3`。本设计不授权真实 M7 QRC freeze/fit、CCC/Gate、server replay、final OOS 或 M6 immutable/history 改写。

## Canonical incorporation

本文件是此 change 的**唯一 canonical change-design artifact**。它按以下精确组合形成完整合同：

1. 原样纳入 `m6_5_repair_change_design_v6.md` SHA-256
   `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78` 的 §1、§2、§3、§4、§7；
2. 本文件 §5 完整替代 v6 §5（job snapshot / authorized fit / official results）；
3. 本文件 §6 完整替代 v6 §6（archive replay）；
4. `m6_5_repair_change_design_v7.md` 是历史补充，已由本文件 §6 取代，不是并行实现依据；
5. 架构依据是 `architecture_confirmation_v11.md` 与冻结的
   `research_governance_threat_model_v1.md`。

因此 v6 的 M6-only public Gate denial、M6 `6/44` genesis、PIT / behavior / state chain、synthetic-only boundary、coverage/full-suite/code-review sequence 均未被删除。任何实现或审查必须把上述 hash-bound base 和两个 replacement 当作一个合同；不得只执行本文件局部段落。

## Problem and scope

### Current observable behavior

现有 `trial_ledger.py` 的 `flock`、event claim 和 archive receipt 只能提供部分协调/证据，不能定义跨 fork 的一次性 `model.fit()` call boundary。现有设计也没有一个从 frozen QRC/plan 到唯一 deployment slot 的闭合 external anchor；`result-publisher` 的“matching terminal receipt”没有完整地绑定 admission/dispatch；现有 archival verifier 在 module top level 已导入 `numpy` 和 `pandas`，之后再加载 frozen source / `torch` / parquet stack，故仅检查 `qlib_peerlite` import origin 无法证明实际执行的 Python/native runtime 是绑定的 bytes。

### Desired observable behavior

- 每个 frozen retained event 在受信 runner 的正常 fork/restart/crash 场景中，最多越过一次 `model.fit()` call boundary；任何不确定 crash 保守计费，并只可使用另一个 planned contingency event。
- future M7 的 authority 只能由 frozen plan → frozen QRC → control-root profile 激活；内部自洽但未被 profile 外部锚定的 authority 不能写 journal、claim、fit、staging 或 official index。
- official result 只能由 descriptor-bound publisher transaction 产生；staging/checkpoint/prepared/final-without-terminal-index 永远不是 official。
- M6 archive replay 只在 fixed Linux/CUDA staged runtime closure 中执行；全部 historical data inputs、interpreter/package/native closure、environment、GPU deterministic profile、bootstrap、execution and child receipts 必须一致。

### Non-goals and constraints

- 不建立生产交易、实时服务、网络 RPC、数据库、host attestation 或 hostile-runner sandbox。
- 不声称防止已经取得 arbitrary native-code execution 的 runner，或 control root/host/kernel/ACL/driver 被攻破；发生时有关证据无效。
- M6 history / immutable contracts / close evidence 只读；legacy server `4/29` 绝不能成为 authority。
- 所有实现和 E2E 在 `SYNTHETIC_NOT_EMPIRICAL` root 完成，production loader/runner 拒绝该 root；真实 M7、archival replay、final OOS 一律继续封印。
- 权威 M6 replay 平台是 Linux x86_64 CUDA；macOS 仅可执行 synthetic test adapter，不能输出 authority receipt。

## Repository evidence and affected boundary

| Existing surface | Current responsibility | v8 change boundary |
|---|---|---|
| `src/qlib_peerlite/governance/trial_ledger.py` | M6 prefix/reconciliation mechanics | 保留 M6 history semantics；为 authority logical-head and retained event check 提供受控 input，不把 `flock` 当一次性 fit permission |
| `src/qlib_peerlite/governance/m6_archive.py` | M6 historical evidence verifier | 增加 v4 replay-binding / v3 receipt agreement validation，不改变 frozen M6 source/history |
| `scripts/reconcile_trial_ledger.py` | constrained reconciliation CLI | 只被 future supervisor control path 调用；不开放 authority/root selection |
| `scripts/server/verify_m6_peerlite_archival_replay.py` | current archival verifier evidence | 保留为历史输入；新增 v3 verifier / bootstrap path，不在 bootstrap 后补丁修复 top-level imports |
| `src/qlib_peerlite/models/peerlite.py`, `config.py`, `cli.py` | M6 public model API | 依 v6 §2 封掉 Gate/raw market-state public surface；v8 不把 M7 mechanic 暴露回 public API |
| `tests/test_m6_*`, `tests/test_trial_ledger.py` | existing synthetic governance checks | 扩展为 v8 contract tests；真实 data/replay 不参与 |

新增代码只进入 `src/qlib_peerlite/governance/` 和受控 server scripts，不引入第三方 framework。建议的责任边界为：

```text
governance/schema.py            strict canonical JSON, ArtifactRef, safe control-root reads
governance/authority.py         plan/QRC/registry/grant/activation/profile graph
governance/admission.py         descriptor and immutable job snapshot materialization
governance/dispatch.py          fresh-exec claim, process identity, one-use permit guard
governance/publication.py       prepared receipt, publisher transaction, resolver
governance/replay_binding.py    M6ReplayInputBinding v4 + exact inventory verifier
governance/replay_runtime.py    closure manifest, bootstrap observation, receipt validation
scripts/server/replay_bootstrap.py
                                stdlib-only entry before verifier imports
scripts/server/replay_exec_helper
                                approved Linux FD-exec helper; no macOS authority fallback
scripts/server/verify_m6_peerlite_archival_replay_v3.py
                                sealed-root-only archive verifier
```

`governance/*` may depend on standard-library filesystem/JSON/hash primitives and the existing M6 evidence helpers, but model/data/Qlib modules may not write control indexes. `result-publisher` and `OfficialResultResolver` use governance schemas only; public model APIs cannot import or expose their M7 mechanics.

## Options considered

| Option | Correctness / operability | Decision |
|---|---|---|
| Keep `flock` + an `O_EXCL` file and add a few guards | Small diff, but fork inherits open-file descriptions/FDs and no external plan/publisher transaction exists | Rejected: cannot establish at-most-once fit or official-result identity |
| Chosen: single-host, file-backed control plane with strict immutable objects, fresh exec, one-use permit and publisher index | More schemas/files, but matches current server topology, is auditable, reversible before M7 and needs no service/database | Chosen |
| Require an OCI container image for every replay | Strong deployment boundary but adds an unverified container runtime/operator dependency to the current research host | Deferred to productionization; use sealed interpreter/runtime root + explicit host ABI/GPU profile now |

## Proposed design

### Common control-root contract

Every cross-object reference uses the closed `ArtifactRef v1` shape:

```json
{
  "role": "descriptive_role",
  "relative_path": "control-root-relative/path",
  "schema_version": "object_schema_vN",
  "sha256": "<64 lowercase hex>",
  "bytes": 0
}
```

All JSON is canonical and closed-schema. Paths are relative to a supervisor-compiled control root, reject `..`, absolute paths, symlinks, devices, FIFOs and sockets. Controlled reads use root FD + `openat`, `O_NOFOLLOW`, `fstat` type/owner/mode/`nlink == 1` checks plus SHA-256. Writer operations use temp file → file fsync → atomic no-overwrite publication where required → parent-dir fsync. A mutable file inode is never a permanent authority identity: permanent links use content digests and logical ledger heads; FD device/inode is only a short-lived revalidation fact.

The identities are fixed:

```text
governance-supervisor  creates authority/admission/dispatch/profile indexes
research-runner        reads sealed snapshot; writes exactly one descriptor staging root
result-publisher       sole final-root and terminal-index writer
official resolver      read-only (activation_id, event_id) lookup; no Path API
replay-supervisor      sole replay staging/runtime/execution-receipt writer
```

### §5 replacement — authority, admission, single fit and official result

#### 5.1 Authority graph and external activation anchor

The graph is acyclic and has these exact roles:

```text
M7AuthorizationPlan v1 (does NOT reference QRC)
  -> frozen QRC (binds plan + control policy)
  -> RunAuthorityRegistry v1
  -> RunAuthority v1
  -> RunAuthorityGrant v1
  -> AuthorityActivationReceipt v1
  -> M7RunControlProfile v1 (O_EXCL sealed external anchor)
```

`M7AuthorizationPlan v1` holds run/family ID, exact ordered event plan, budget/spec references, M6 `6/44` genesis reference, logical namespace/journal/output policy and explicit contingency events. The QRC binds its exact plan digest and control-policy digest. Registry/authority/grant/activation repeat equal QRC/plan/policy/genesis/budget/spec/event-plan/namespace references; this is full equality, never count/overlap comparison.

`AuthorityActivationReceipt v1` additionally binds activation nonce, issuer identity, activation-time logical ledger head, all control-root-relative roots and actor identities. Under a control-root exclusive lock, supervisor validates the entire DAG, verifies M6 `6/44` close proof/genesis, then fsyncs receipt and creates exactly one `M7RunControlProfile v1` in a fixed deployment slot by `O_EXCL`. The profile repeats the expected QRC/plan/policy/activation hashes, actor identities and root identity. Only after profile seal is the activation `ACTIVE`.

No runner CLI accepts authority, registry, QRC, plan, budget, root or profile selection. Supervisor resolves its one fixed profile slot, rechecks the graph under authority/ledger lock for every admission, and passes verified FDs/canonical bytes to the child. An interrupted install without profile seal cannot start a runner. An active profile is immutable: replacement requires a distinct run/plan/QRC/namespace and an explicit prior `CLOSED` record; stale valid activation/profile is rejected.

#### 5.2 Admission and fork-safe one-use fit

For each plan event, supervisor does this sequence under authority + ledger lock:

1. verify current sealed profile, plan membership and exact logical ledger head;
2. append the event as `START_RETAINED` to the authoritative ledger before launching anything; a crash at any later boundary is therefore conservatively counted;
3. materialize/re-hash/fsync the exact job-private immutable snapshot from the certified state/candidate/PIT/behavior/join chain;
4. derive and `O_EXCL` publish `FitAdmissionDescriptor v3` in `AdmissionIndex`.

The descriptor binds activation/QRC/plan/authority/grant, exact event-plan entry, event/evaluation/fit semantic IDs, retained ledger record and before/after logical head, fixed/behavior/state/join/candidate/snapshot identities, fold/segment/date/schema, frozen runner launch binding, descriptor nonce, and unique claim/staging/final/publisher-index identities. A duplicate/altered semantic ID, wrong head, wrong activation, non-planned event, existing root or snapshot mismatch fails before runner spawn.

Supervisor launches a fresh direct-exec runner (`close_fds=True`; no pool, daemon or pre-fork mode). `RunnerLaunchBinding v1` contains descriptor digest, frozen executable/config digest, sealed descriptor/snapshot FD identities and `ProcessIdentity v1 = boot_id + pid + /proc/<pid>/stat start_ticks + runner_instance_nonce`. The child creates an immutable `DispatchClaim v1` in the governance-owned claim directory using `O_CREAT|O_EXCL`; it binds admission/activation/event/generation one/ProcessIdentity/sealed FDs and is never removed or reused.

Immediately before `model.fit()`, `FitDispatchGuard` reopens the claim from control root, validates descriptor/ProcessIdentity/snapshot FDs, then asks the supervisor's Unix-domain control socket to consume a `FitDispatchPermit v1`. The supervisor uses peer credentials plus PID/start identity, atomically writes/fsyncs `DispatchReceipt v1(state=DISPATCHED)` and permit consumption, and only then answers success. The local guard permits one successful consume only. `os.register_at_fork` poisons admission/claim/ledger/snapshot state in children; relevant FDs use `CLOEXEC`. A child, stale/PID-reused process, inherited FD, pre-fork pool, duplicate API call or second direct runner cannot consume the permit.

If claim or dispatch exists and anything crashes, state becomes `ABANDONED_UNKNOWN`; that event is permanently spent. Recovery never deletes/renames/reclaims the claim or starts the same event. The only legal retry is a separately frozen contingency event with distinct descriptor and roots. This establishes the normal trusted-runner guarantee “at most one fit boundary per retained event”, not a promise against malicious raw syscalls.

#### 5.3 Prepared result, publisher transaction and resolver

Runner writes only regular data files inside its descriptor staging root and emits `OutputInventory v1` plus `PreparedResultReceipt v1`. The inventory holds exact relative file set/type/bytes/hash and excludes receipts/indexes to avoid hash cycles. Prepared receipt binds activation/admission/event/claim/dispatch, worker ProcessIdentity, state/snapshot/model input identity, expected staging root, inventory/tree digest and `outcome=FIT_SUCCEEDED`.

Publisher accepts only `(activation_id, event_id)`. It resolves through the sealed control profile and indexes to the unique expected admission, claim, dispatch, staging and final roots; it never accepts a caller path or self-reported root. It re-opens all objects by FD and requires full equality of activation/event/descriptor/claim/dispatch/state/snapshot identities. It rejects stale/foreign receipt, un-dispatched job, incomplete/extra file, symlink/hardlink, owner/mode/nlink mismatch, hash mismatch, pre-existing final root or any non-success prepared outcome.

After verification, publisher seals a copy into a publisher-owned prepared root, fsyncs the inventory, then atomically performs a no-replace move to the descriptor-derived final root. If the platform cannot prove no-replace semantics, it fails closed rather than use a replace-capable rename. After rehashing final content, publisher writes deterministic `TerminalPublishedReceipt v1` to `TerminalPublishIndex` under event lock with `O_EXCL` + fsync. The receipt binds publisher identity/transaction ID/index sequence plus activation/admission/event/claim/dispatch/prepared/state/snapshot/inventory/final-root equality and `terminal_status=TERMINAL_PUBLISHED`.

`OfficialResultResolver` takes only `(activation_id,event_id)`, reads terminal index, verifies receipt and final inventory each time, and returns a result descriptor. It has no directory scan or direct-path API. State machine:

```text
PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> CLAIMED -> DISPATCHED
    -> PREPARED -> PUBLISHING -> TERMINAL_PUBLISHED
                    \-> QUARANTINED_REJECTED

any crash after START_RETAINED but before terminal index
    -> ABANDONED_UNKNOWN / QUARANTINED_* (forensic-only; never auto-promote or reuse)
```

#### 5.4 Failure, compatibility, observability

All controls are new versioned objects; existing M6 ledger/archive evidence remains read-only. Every transition yields a canonical receipt carrying activation/event/descriptor correlation IDs, logical ledger head, actor identity, input/output tree digests and quarantine reason where relevant. No legacy result is silently migrated to official. The initial implementation is synthetic-only; rollback means stop new activation before sealing any M7 profile and retain forensic/quarantine objects, never overwrite history.

### §6 replacement — M6 archive replay with executable closure

#### 6.1 Binding and runtime schemas

`M6ReplayInputBinding v4` is frozen before any replay and enumerates every external transfer manifest; archive/single root/internal manifest/tree; M6 immutable spec/gate/close proof/historical verification; approved v3 verifier; M3 bound product manifest plus each consumed partition; M6 run manifest/candidate list/14 fold receipts/every checkpoint metadata+state/every prediction partition/K16 deterministic-refit receipt; legacy read-only ledger; new output policy; fixed argv/cwd/environment policy; `ReplayBootstrap v1`; native exec helper; and `ReplayRuntimeClosure v1`. Each entry uses `ArtifactRef` with exact role/path/hash/bytes/schema. The v3 verifier receives one sealed staged descriptor/root only—never caller source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter flags.

`ReplayRuntimeClosure v1` is a supervisor-owned, content-addressed Linux x86_64 CUDA runtime root with:

- exact interpreter binary (SHA/bytes/ELF build-id/version/ABI/SOABI), real `bin/python3.11` layout, prefix metadata, stdlib and lib-dynload inventory;
- complete no-symlink regular-file runtime tree digest for trace-observed pure/extension packages; required observed minimum is `numpy`, `pandas`, `torch`, `pyarrow`; any other module (including `qlib`) appears only if the closure-construction trace requires it;
- frozen `sys.path` order; allowed built-in/frozen module set; exact module-name → staged/runtime origin/hash map; namespace root rules; required-minimum import set;
- extension and native shared-library inventory (SHA/build-id/SONAME/ABI) plus approved host loader/libc/driver baseline and exact CUDA/GPU profile;
- deterministic runtime configuration including `device=cuda`, `CUBLAS_WORKSPACE_CONFIG=:4096:8` and historical deterministic flags;
- closure-construction receipt: platform/ABI/GPU probe, import trace, expected module/native-map digests and runtime tree digest.

Wheel/lock provenance is supplementary only; it never substitutes for observed runtime bytes. Different host ABI/GPU/driver/CUDA/determinism profile fails closed. Host compromise remains outside this threat model.

#### 6.2 Staging, bootstrap and observed closure

Replay supervisor FD-verifies every binding object, materializes data/source/verifier/manifests plus the full runtime layout into a fresh supervisor-owned stage, then fsyncs/tree-hashes it and makes it read-only. It invokes the opened staged interpreter FD through the approved native exec helper (`execveat(AT_EMPTY_PATH)` / `fexecve`), while setting canonical staged `argv[0]`. Bootstrap confirms `sys.executable`, `sys.prefix`, stdlib and lib-dynload resolve within the stage. If FD-execution/layout invariants are unavailable, it fails; it never falls back to mutable pathname/PATH/current-venv execution.

The only launch form is fixed `env -i`, fixed cwd/argv, `python -I -S` and an **external stdlib-only `replay_bootstrap.py`**. Bootstrap is hash-bound and runs before any verifier import. It rejects `PYTHON*`, `VIRTUAL_ENV`, `CONDA*`, `LD_PRELOAD`, `LD_AUDIT`, `LD_DEBUG`, `DYLD_*`, unapproved loader search paths, site/usercustomize and cwd/deployment path entries. It validates its initial flags/modules, installs only closure `sys.path`, clears importer caches, sets no bytecode writes, validates verifier/frozen-source origins and installs an import guard. Only then it runs v3 verifier against the sealed descriptor/root.

The import guard requires each later module to be an allowed built-in/frozen module or exact staged/runtime origin/hash. On import preflight, after CUDA preflight and at child exit it records `sys.modules` origin digest and Linux `/proc/<pid>/maps` native map; final map catches lazy Torch/CUDA loads. Any unexpected import, extension, native library, module shadow, tree swap, ABI/GPU/determinism mismatch, bootstrap-after-verifier import, ledger mutation, extra/missing input or pre-existing output rejects the replay before acceptance.

`ReplayExecutionReceipt v3` is supervisor-owned and binds input binding, runtime/bootstrap/exec-helper digests, staged runtime/data tree digests, interpreter FD dev/inode/mode/hash/build-id and observed executable, fixed cwd/argv/environment digest, PID/start/exit, initial flags/sys.path digest, observed module/native-map digests, host ABI/GPU/determinism profile, output and ledger before/after. Child receipt repeats binding/runtime/bootstrap/stage identities, exact 14 checkpoints/predictions, 14 replay/0 fit/OOS=false and observed closure digest. `m6_archive` accepts replay only if v4 binding + supervisor receipt + child receipt agree exactly and output is a new root.

#### 6.3 Replay failure and compatibility

Current archive verifier and historical Git verifier remain evidence inputs; new v3 verifier/bootstrap are new separately approved code. No replay process can write the authoritative ledger; any write attempt terminates/rejects. Existing output is rejected, never overwritten. macOS synthetic adapter may validate schemas/import guard logic but emits an explicitly non-authoritative result; only the Linux/CUDA path can later be proposed for an archival server receipt.

## Verification obligations

The router-selected test-design stage must create a matrix proving the following behavior, using call-boundary spies, controlled control-root fixtures and a synthetic Linux-runtime adapter where necessary:

- M6 `6/44` authority genesis still passes and legacy `4/29` / wrong proof / wrong logical head cannot activate an authority.
- QRC/plan/registry/authority/grant/activation/profile equality, no-cycle and stale/replacement rules reject before journal/claim/fit/output side effects.
- fork-before/after claim/dispatch, inherited FD, pre-fork pool, PID/start/boot mismatch, duplicate direct runner, restart and crash boundaries record at most one fit for one event and no second official result.
- wrong descriptor/claim/snapshot/receipt/staging/final root, concurrent publishers, no-replace conflict, every post-fit crash boundary, final swap and path-based resolver all cannot yield an official result.
- runtime inventory/path traversal/symlink/extra/missing input, interpreter/stdlib/package/extension/native/host ABI/GPU/CUDA/determinism mismatch, `sitecustomize`/`.pth`/cwd/path/loader injection, bootstrap order violation and late lazy native load reject with no accepted receipt.
- full binding/execution/child/archive agreement still proves only `14 replay / 0 fit / OOS=false`, not M7 eligibility, Alpha or production readiness.

Contract tests must enforce strict schemas, source exports, ownership/mode checks and no free CLI roots. Later red/green stages also retain v6 §7's frozen include-list 100% line+branch coverage, full suite/lint/type and public synthetic E2E requirements.

## Implementation plan

1. Add strict schema, safe control-root IO and test fixture primitives in `governance/`; reject unknown fields/paths before adding any writer.
2. Complete v6 §2 public M6-only Gate denial and prove raw market state / `col_set="market"` cannot cross a production model boundary.
3. Implement read-only M6 close proof/genesis installation and retained-ledger logical-head checks; do not change immutable M6 rows/contracts/gates.
4. Implement plan/QRC/registry/authority/grant/activation/profile graph and a supervisor-only activation installer; expose no selection CLI to runner.
5. Implement snapshot/admission/claim/permit/dispatch with fresh exec, ProcessIdentity, at-fork poison, conservative crash accounting and synthetic fit-boundary seam.
6. Implement prepared inventory, publisher seal/no-replace terminal transaction and resolver-only logical lookup/quarantine behavior.
7. Implement v4 replay binding, runtime closure builder/verifier, Linux native exec helper, pre-import bootstrap, v3 sealed-root verifier and three-receipt archive validation.
8. Update constrained server CLIs/configurations, manifests/model cards and synthetic E2E harness; retain historical verifier inputs separately.
9. Execute the approved red/green/code-review/E2E quality route. Only after every M6.5 gate passes may a separately approved, read-only server replay be proposed; M7/CCC/Gate/final OOS remain separate later gates.

## Open decisions

None for M6.5 implementation. If a target server cannot satisfy the fixed Linux x86_64 CUDA runtime profile or no-replace / FD-exec invariants, the correct outcome is `BLOCKED` for archival replay acceptance, not a weaker fallback. The project can still complete synthetic code-quality work without asserting a server replay result.
