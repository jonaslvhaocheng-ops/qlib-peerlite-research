# M6.5 架构确认 v14 — 自包含的研究治理控制面

状态：`ARCHITECTURE_READY / 待独立设计审查`。风险：`R3`。

本文件是 M6.5 唯一、**自包含**的架构依据，替代 v9–v13 的组合规则；旧版本及其审查仅是历史证据。它不改写 M6 immutable/history，不授权 M7 实证、CCC/Gate、archive replay、final OOS 或生产交易。威胁边界固定为 `research_governance_threat_model_v1.md`：防御受信 host/control-root 下的普通配置、并发、fork、崩溃、路径、运行时和 ACL 错误；不声称防御 hostile runner arbitrary native code 或 host/control-root/kernel compromise。

## 1. Non-negotiable evidence and data boundaries

新的 authority 必须从 `M6CloseArchiveProof v1` 和 byte-exact M6 close snapshot 创建：51 lines、14,328 bytes、SHA `31a90d1ff506d9dfae48ab8bd191bf8ee9bbcbdc261c8f1acde9c3741992de93`、6 candidate / 44 fit。installer 验证 gate/static evidence、historical verifier blob、pre-run SHA `8d08f39a569d62cf5078368075dce39e94014a4ad3a6095f0b03863baa93f133` / `4/29` prefix、journal-start=retained-ID equality 和 terminal chain；它在治理 lock 中创建新 namespace，拒绝 legacy server `contracts/trial_ledger.jsonl` 的 `4/29` head，永不改写 M6 history。

生产输入链保持：sealed raw snapshot → construction-only state (`BUILT_NOT_EMPIRICALLY_CERTIFIED`) → audit-only candidate manifest / full behavior coverage → frozen QRC → PIT `CERTIFY` + complete behavior bundle + join evidence → `StateArtifactBinding` → immutable job snapshot。`VERIFY`、synthetic/test root、partial behavior、label/execution/purge import 或 caller frame/tensor/path 都不得成为 official M7 input。四个 derived sources、flags/outcomes/aggregates/projection 必须保留 future/revision/universe coverage and equality checks。public PeerLite API remains M6-only: no Gate/raw market-state parameter/export/config/CLI/registry path can create official input/output.

## 2. Actors, ACL policy and control root

`M7ControlPlanePolicy v1` is frozen in the QRC and defines four non-root, pairwise distinct Unix writer UIDs/GIDs, allowed supplementary groups/capabilities (empty unless explicitly listed), control-root identity, socket peer allowlists and exact ACL matrix:

```text
governance-supervisor: policy/registry/activation/profile/admission/dispatch writer
research-runner:       own event claim + own staging writer only
result-publisher:      publisher-prepared/final/terminal-index writer only
replay-supervisor:     archive stage/runtime/replay-receipt writer only
```

`OfficialResultResolver` is a read-only governance-supervisor capability taking only `(activation_id,event_id)`; it has read/search but no write ACL to final/index. No shared writable group is allowed. runner has no final/index path access; publisher cannot write authority/admission/dispatch; replay supervisor cannot write M7 authority/final/index. Policy preflight and every permit/publish/resolve revalidate UID/GID nonalias, groups/capabilities, owner/mode/POSIX ACL and Unix socket `SO_PEERCRED`. Any alias, shared write, wrong peer, ACL change or unsafe path fails closed.

All controlled objects use canonical closed JSON and `ArtifactRef v1` (`role, relative_path, schema_version, sha256, bytes`). Reads are root-FD `openat`/`O_NOFOLLOW` + type/owner/mode/ACL/nlink/hash checks; writes are temp+fsync+atomic no-overwrite+parent fsync. Permanent authority links are content digests and logical ledger heads, never mutable file inodes.

## 3. One-way authority graph and lifecycle

The only allowed digest graph is:

```text
M7AuthorizationPlan v1 (contains no QRC/registry/grant/activation ref)
  --creation order only-->
Frozen QRC (exact Plan SHA + ControlPlanePolicy SHA)
  -> RunAuthorityRegistry v1 (exact QRC/Plan/policy/M6-genesis SHA)
  -> RunAuthority v1 -> RunAuthorityGrant v1
  -> AuthorityActivationReceipt v1 -> M7RunControlProfile v1
```

Plan contains family/run semantics, exact ordered event/budget/spec plan, M6 genesis, namespace/journal/output policy and distinct contingency events. Registry proves the selected QRC/Plan pair by equality (`QRC.plan_sha == sha256(plan)`, same family); plan never gains a reverse QRC field. Cycle/placeholder/mutable selector/same-ID-different-bytes/mixed plan/QRC/legacy `4/29` are rejected.

Supervisor validates full graph/genesis/policy under control-root/authority lock, writes activation receipt and `O_EXCL` seals fixed-slot control profile. Only profile-selected activation is authoritative; no runner/publisher takes authority/root/plan/profile selection input. Lifecycle under one activation lock:

```text
INSTALLING -> ACTIVE -> CLOSING -> CLOSED
```

`CLOSING` atomically fences new permits and marks every not-yet-dispatched admission `ABANDONED_BEFORE_DISPATCH`; existing dispatched work may terminal/quarantine, then `CLOSED` is written. New activation requires new run/plan/QRC/namespace; stale profile never reactivates.

## 4. M7 admission, schema evolution and one-use fit

For an active plan event, supervisor rechecks profile/head, writes `START_RETAINED`, materializes exact certified snapshot, then `O_EXCL` writes **`FitAdmissionDescriptor v5`**. It binds all graph/policy/genesis refs, exact event entry, retained record and logical heads, state/PIT/behavior/join/candidate/snapshot refs, fold/date/schema, unique claim/staging/final/index roots, and these exact execution contracts:

```text
expected RunnerExecutionClosure v2 ArtifactRef
expected PythonStartupPolicy v1 digest
expected ProcessStartupState v1 digest
expected RunnerExecutionReceipt v2 schema/equality contract
```

`FitAdmissionDescriptor v4`, `RunnerExecutionClosure v1`, `RunnerExecutionReceipt v1`, environment-only seed records and any implicit upgrade/alias are rejected before claim/permit. All new M7 control objects carry v5/v2 identities: `DispatchClaim v2`, `FitDispatchPermit v2`, `DispatchReceipt v3`, `PreparedResultReceipt v3`, `TerminalPublishedReceipt v3` and resolver descriptor repeat descriptor/closure/startup/process-state/observed-receipt digests exactly.

The only event order is:

```text
PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> RUNNER_STARTED
        -> CLAIMED -> DISPATCHED -> PREPARED -> PUBLISHING -> TERMINAL_PUBLISHED
                                      \-> QUARANTINED_*
```

Supervisor stages measured closure/descriptor/snapshot then starts one fresh direct-exec worker with `close_fds=True` and minimal audited `pass_fds`; no pool, daemon, pre-fork helper or existing Python worker. Post-exec bootstrap validates execution/startup state before snapshot read or claim. The actual worker derives `ProcessIdentity(boot_id,pid,start_ticks,runner_nonce)` and alone creates `DispatchClaim v2` with `O_CREAT|O_EXCL`. At permit request supervisor holds the same activation/event lock, rechecks ACTIVE profile/generation/head, peer credentials, identity, claim, snapshot FD and observed v2 receipt, then fsyncs `DISPATCHED/FIT_STARTED` and consumes one permit before reply. `os.register_at_fork` poisons controls in children; all non-passed FDs are `CLOEXEC`. Crash/claim/dispatch is conservatively spent; retry requires distinct frozen contingency event.

## 5. Effective Python execution and process startup state

`RunnerExecutionClosure v2` and `ReplayRuntimeClosure v3` share `SealedPythonExecutionClosure v2`. Each includes measured interpreter/entrypoint/config/source/runtime tree, CPython 3.11 ABI/stdlib/lib-dynload/site-package/extension inventory, ordered allowed module origins, native/host ABI/GPU profile, fixed argv/cwd and two separate startup contracts:

1. **`PythonStartupPolicy v1`**: approved FD-exec helper builds exact `envp` from scratch; only Python startup variable is `PYTHONHASHSEED=0`; all other `PYTHON*`, virtualenv/conda and loader injection variables are absent. It invokes measured CPython 3.11 with `-s -S -P`, never `-I`/`-E`. Expected flags are `isolated=0, ignore_environment=0, no_user_site=1, no_site=1, safe_path=1, hash_randomization=0`, plus an ABI-bound fixed `hash("qlib-peerlite")` probe. `-P` unavailable is reject.
2. **`ProcessStartupState v1`**: independent of envp; exact `cwd`, `umask_octal=0077`, deterministic thread/CUDA/GPU/cache/temp state and supported resource bounds. Before exec helper calls `umask(0077)`, immediately re-reads it (`umask(0077)` return), emits `LaunchStateReceipt v1` over supervisor-controlled channel, then execs. Bootstrap's first standard-library action is `previous=os.umask(0o077); assert previous==0o077; os.umask(0o077)` and binds its observed value. A missing/helper mismatch/bootstrap mismatch rejects.

Bootstrap is first staged code before runner/verifier/source import or snapshot read. It validates executable/prefix/argv/FD stage, exact envp, policy flags/probe, process-state receipt/umask, no site/usercustomize and allowed module origins; then installs only closure sys.path/import guard. It emits `EffectiveHashPolicyReceipt v1` and `BootstrapStartupReceipt v1`. `RunnerExecutionReceipt v2` / `ReplayExecutionReceipt v5` bind expected+observed closure, policy, process state, launch state, bootstrap, argv/env/cwd/umask/probe/import/native maps/ABI/GPU. Any wrong interpreter/path/venv/config/seed/flags/env/umask/ABI/CUDA/map fails before M7 claim/permit or replay acceptance.

## 6. Publisher and full M6 archival replay binding

Publisher accepts only `(activation_id,event_id)`, resolves profile→descriptor→claim→dispatch itself, requires v5/v2 execution equality and exact regular-file `OutputInventory`, seals publisher-owned copy, atomically no-replace moves to unique final root, then `O_EXCL` emits terminal receipt. Resolver only reads terminal index/rehashes final; every incomplete/wrong/crash residue stays quarantine/forensic, never auto-promoted/reused.

**`M6ReplayInputBinding v6`** is frozen before replay and has a complete closed inventory (every item is exact relative path/SHA/bytes/schema/role):

1. external transfer manifest; source archive; internal manifest; single root; full archive tree inventory;
2. M6 immutable execution spec, gate, close proof, historical verification receipt and approved frozen verifier source;
3. M3 bound product manifest and **every** consumed product partition;
4. M6 run manifest, candidate list, all 14 fold receipts, every checkpoint `metadata.json` plus `state_dict.pt`, every candidate prediction partition and K16 deterministic-refit receipt/reference score;
5. legacy read-only ledger identity and required before/after hash;
6. approved v3 sealed-root verifier, bootstrap, FD-exec helper, `ReplayRuntimeClosure v3`, `PythonStartupPolicy v1`, `ProcessStartupState v1`, fixed argv/cwd/import policy;
7. previously nonexistent output root and fixed profile `14 replay / 0 fit / OOS=false`.

No verifier CLI/API accepts source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter roots. Replay supervisor FD-verifies every entry, stages immutable data/source/runtime/verifier, runs the shared startup policy, and emits `ReplayExecutionReceipt v5`. Child receipt repeats v6 binding/runtime/startup/process-state/stage identities, exact 14 checkpoints/predictions and 14/0/OOS values. `m6_archive` accepts only three-way v6 binding/supervisor/child agreement, new output and unchanged legacy ledger. Missing/extra/substituted input, caller path, old closure version, seed/umask receipt substitution, native map drift or ledger write rejects. Authority replay is Linux x86_64 CUDA only; macOS synthetic adapter is non-authoritative.

## 7. Migration and proof boundary

All v1/v4 M7 execution/admission schemas are fail-closed; no auto-upgrade. M6 historical verifier/immutable evidence stay read-only; v6 binding is a new synthetic-only contract, not historical mutation. Tests later must cover canonical graph, state/PIT chain, UID/ACL/socket failures, v4/v1 versus v5/v2 substitutions, post-exec fork/close/permit races, effective seed/umask/process-state errors, full replay inventory/no-path rule, publisher crash boundaries and 14/0/OOS ceiling. Only after red/green/code-review/E2E gates can read-only server replay be proposed; M7, CCC/Gate and final OOS remain sealed.
