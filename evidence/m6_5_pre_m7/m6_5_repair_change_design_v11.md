# M6.5 R3 修复设计 v11 — 自包含的实现合同

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
Owner：M6.5 pre-M7 engineering-quality track  
Risk：`R3`

本文件是 `m6-5-pre-m7-repair` 的唯一、**自包含** implementation contract；v6–v10 仅保留为历史审查证据。它不授权真实 M7 QRC freeze/fit、CCC/Gate、server replay、final OOS、生产交易或 M6 immutable/history mutation。所有实现/测试先在 `SYNTHETIC_NOT_EMPIRICAL` root；production loader/runner 拒绝该 root。

## 1. Scope, trust boundary and common rules

M6.5 要在 M7 前修复四类研究治理边界：

1. legacy Gate/raw state/label 不得进入 official model input；
2. verified M6 `6/44` close 必须是唯一 trial authority genesis；
3. future M7 official fit/result 必须从 PIT-certified input、one-way plan/QRC authority、一次性 permit、measured execution closure 和 terminal publisher 产生；
4. M6 archival replay 必须绑定所有历史 input 和实际 Python/native startup/runtime bytes。

受信前提仅是 governance supervisor/control root/host ACL/frozen approved code。正常 configuration、concurrency、fork/restart/crash、partial file、path/env/runtime/ACL 误选必须 fail closed。runner arbitrary native-code execution、control root/host/kernel compromise、恶意 external loader 注入不在 M6.5 对手模型；发生即 evidence invalid，而非由 Python API 弥补。

All controlled JSON is strict canonical closed-schema. `ArtifactRef v1` always has `role,relative_path,schema_version,sha256,bytes`; paths are root-relative/no `..`/no symlink. Reads use root FD + `openat/O_NOFOLLOW` + type/owner/mode/ACL/nlink/hash; writes use temp/file fsync/atomic no-overwrite/parent fsync. Permanent identity is content digest + logical ledger head, never an atomic-replaceable inode.

## 2. Public M6-only surface

`PeerLiteModel`, `PeerLiteNetwork`, config/factory/CLI/registry are M6-only. Remove/reject `market_gate`, `market_dim`, raw `market_state` and any Gate metadata before Dataset/journal/fit. Public production path must never request Qlib `col_set="market"`; it cannot turn label-derived market values into official input. Gate mechanics, if later researched, live in a non-exported synthetic-only module with no ledger/checkpoint/score/Recorder/result capability. Archived frozen source remains available only to M6 replay.

Affected surfaces: `src/qlib_peerlite/models/peerlite.py`, `config.py`, `cli.py`, package exports, model registry/config validation and public API tests. This is a breaking M7-prevention change, not a compatibility bridge.

## 3. Verified M6 `6/44` genesis and ledger authority

`M6CloseArchiveProof v1` binds M6 gate/static evidence, approved historical verifier git blob, pre-run prefix `8d08f39a569d62cf5078368075dce39e94014a4ad3a6095f0b03863baa93f133` / 4 candidate / 29 fit, close prefix SHA `31a90d1ff506d9dfae48ab8bd191bf8ee9bbcbdc261c8f1acde9c3741992de93` / 14,328 bytes / 51 lines / 6 candidate / 44 fit, journal-start=retained-ID equality and terminal chain. `LedgerAuthorityGenesis v2` binds proof and byte-exact close snapshot.

Installer accepts only supervisor-selected genesis/control root, validates all links under lock, then atomically creates a new policy-derived authority namespace. It rejects legacy `contracts/trial_ledger.jsonl`, 4/29 head, wrong proof/path/schema/link/target and historical overwrite. M6 historical archive verification remains read-only. Future reconciliation validates prefix/head/semantic IDs/budget under stable lock then writes old bytes plus canonical batch through temp/fsync/replace; duplicate divergence, unknown tail, bad journal, count swap, overbudget or failure leave ledger bytes unchanged.

Any started event is retained before fit. The ledger’s `flock` is only short transaction coordination; it is never the one-use fit authorization boundary.

## 4. State, PIT and behavior handoff

`StateBuildBinding v2` allowlists sealed raw files/columns/clocks/code/predicates and atomically publishes construction audit/population/daily state/manifest/marker with `BUILT_NOT_EMPIRICALLY_CERTIFIED`; builder may not import labels, execution, purge, M3/model/ledger. `CandidateTrainingInputManifest v1` is audit-only and fixes consumed cells/folds/segments/schema/keys/dates/values/counts/lineage without creating Dataset/model input.

`StateBehaviorCoveragePlan v1` binds frozen candidate/construction, builder/query/parameters/environment and full output projection (four sources, flags/outcomes/reasons, membership, aggregates). Each applicable source/predicate/aggregate has FUTURE_POISON, REVISION_REPLAY and UNIVERSE_CANARY; PREFIX_REPLAY is supplemental only. Behavior receipts must have fixed parent, B001–B004 PASS, matching lineage/probe and equality—not overlap—of protected keys/values.

Production order is candidate → frozen QRC/coverage/authorization plan → PIT `CERTIFY` → complete behavior bundle → audit-only join → `StateArtifactBinding` → job snapshot. Loader requires fixed audit PASS/QUALIFIED/evidence ceiling PASS/FULL_TRAINING_INPUT/`quant_contract_v2`/production CLI/non-test adapter/all 17 checks and complete behavior/join evidence. `VERIFY`, fake/partial behavior, test adapter and synthetic root fail.

## 5. M7 file-backed control plane

### 5.1 Actor policy and one-way authority graph

`M7ControlPlanePolicy v1`, QRC-bound and immutable, contains numeric UID/GID, allowed groups/capabilities, control-root identity, socket peer allowlists and ACL matrix for four non-root pairwise nonalias writers:

```text
governance-supervisor -> policy/registry/activation/profile/admission/dispatch
research-runner       -> own claim + own staging only
result-publisher      -> publisher-prepared/final/terminal index only
replay-supervisor     -> replay stage/runtime/receipt only
```

Resolver is a read-only supervisor capability accepting `(activation_id,event_id)` only. No shared writable group; runner cannot access final/index; publisher cannot write authority/admission/dispatch; replay actor cannot write M7 authority/final/index. Activation and every permit/publish/resolve recheck numeric IDs, groups/capabilities, owner/mode/POSIX ACL and `SO_PEERCRED`; aliases/ACL drift/wrong peer fail closed.

The exact no-cycle graph is:

```text
M7AuthorizationPlan v1 (no QRC/registry/grant/activation ref)
  --creation order only-->
Frozen QRC (Plan SHA + ControlPlanePolicy SHA)
  -> Registry (QRC/Plan/policy/M6-genesis SHA)
  -> Authority -> Grant -> ActivationReceipt -> O_EXCL RunControlProfile
```

Plan contains family/run/event/budget/spec/M6 genesis/namespace/journal/output/contingency semantics but no QRC selector. Registry validates exact QRC.plan SHA and same family. Cycle/placeholder/mutable selector/mixed references/legacy 4/29 reject. Lifecycle under one activation lock is INSTALLING→ACTIVE→CLOSING→CLOSED; CLOSING marks all nondispatched admissions abandoned and rejects later permits while already dispatched work terminal/quarantines. No stale profile reactivates; a new activation uses new run/plan/QRC/namespace.

### 5.2 Admission and single `model.fit()` boundary

For active event supervisor locks authority+ledger, rechecks profile/head, writes `START_RETAINED`, materializes/re-hashes/fsyncs certified private snapshot, then `O_EXCL` writes **`FitAdmissionDescriptor v5`**. Required fields include:

```text
graph/policy/genesis/event-entry/retained-record/logical-head identities
PIT/behavior/state/join/candidate/snapshot/fold/date/schema identities
unique claim/staging/final/terminal-index roots
expected RunnerExecutionClosure v2 ArtifactRef
expected PythonStartupPolicy v1 + ProcessStartupState v1 digests
expected RunnerExecutionReceipt v2/effective-startup contract
```

There is no compatibility path: descriptor v4, closure/receipt v1, environment-only seed record and implicit version alias/upgrade are rejected before claim/permit. `DispatchClaim v2`, `FitDispatchPermit v2`, `DispatchReceipt v3`, `PreparedResultReceipt v3`, `TerminalPublishedReceipt v3` and resolver descriptor repeat v5/v2 closure/startup/process/receipt equality.

State/order is exactly:

```text
PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> RUNNER_STARTED
        -> CLAIMED -> DISPATCHED -> PREPARED -> PUBLISHING -> TERMINAL_PUBLISHED
                                      \-> QUARANTINED_*
```

Supervisor stages verified closure/descriptor/snapshot then runs one fresh direct-exec worker (`close_fds=True`, minimal audited `pass_fds`, no pool/daemon/pre-fork/existing Python worker). Bootstrap must finish before source import/snapshot read/claim. The post-exec worker creates `ProcessIdentity(boot_id,pid,start_ticks,runner_nonce)` and `O_CREAT|O_EXCL` `DispatchClaim v2`. On permit request, supervisor uses same activation/event lock to reread ACTIVE profile, peer identity, claim, snapshot FD, head and observed v2 execution receipt; it fsyncs DISPATCHED/FIT_STARTED and consumes one permit before reply. `FitDispatchGuard` permits one call boundary, destroys permit state; `os.register_at_fork` poisons controls in child and non-passed FDs are CLOEXEC. Claim/dispatch/crash is conservatively spent; retry requires distinct frozen contingency event.

### 5.3 Measured execution and effective startup state

`SealedPythonExecutionClosure v2` provides `RunnerExecutionClosure v2` and `ReplayRuntimeClosure v3`: exact interpreter/entrypoint/config/source/runtime tree, CPython 3.11 ABI/stdlib/lib-dynload/site-package/extension inventory, allowed sys.path/module origins, native/host ABI/GPU profile, fixed argv/cwd and two required startup contracts.

`PythonStartupPolicy v1` specifies exact CPython 3.11, flags `-s -S -P`, forbidden `-I/-E`, complete exact envp (only `PYTHONHASHSEED=0` among Python variables), expected flags `isolated=0,ignore_environment=0,no_user_site=1,no_site=1,safe_path=1,hash_randomization=0`, and ABI-bound `hash("qlib-peerlite")` probe. `ProcessStartupState v1` separately specifies cwd, `umask_octal=0077`, deterministic thread/CUDA/GPU/cache/temp values and resource bounds—umask is not an environment variable.

FD-exec helper builds envp from scratch, sets `umask(0077)` before exec, immediately re-reads it, sends `LaunchStateReceipt v1` through supervisor-controlled channel, then `execveat/fexecve`s measured staged interpreter with canonical argv0. Bootstrap first verifies stage/executable/prefix/argv/envp/policy flags/probe, does `previous=os.umask(0o077); assert previous==0o077; os.umask(0o077)`, verifies launch state/no site/usercustomize and module origins, then installs import guard. It emits `EffectiveHashPolicyReceipt v1` and `BootstrapStartupReceipt v1` before runner claim or replay root resolution. `RunnerExecutionReceipt v2` binds expected/observed closure/policy/process/launch/bootstrap, argv/env/cwd/umask/probe/import/native-map/ABI/GPU facts. Any mismatch fails before permit; publisher refuses mismatch.

### 5.4 Publisher and resolver

Runner writes only descriptor staging regular files plus exact `OutputInventory` and `PreparedResultReceipt v3`. Publisher only accepts `(activation_id,event_id)`, resolves expected profile→descriptor→claim→dispatch roots itself, exact-compares all v5/v2 identities/inventory, rejects extra/missing/symlink/hardlink/owner/mode/hash/stale/preexisting objects, seals publisher-owned copy, atomic no-replace moves final root and O_EXCL writes terminal receipt. Resolver only follows terminal index/rehashes final. Any incomplete/wrong/crash residue remains quarantine/forensic; never auto-promote/reuse/Path-discover.

## 6. Full M6 archive replay contract

`M6ReplayInputBinding v6` is frozen before any replay. Every entry is a closed `ArtifactRef` (relative path/SHA/bytes/schema/role), and it enumerates all of:

1. external transfer manifest; source archive; internal manifest; single root; full archive tree inventory;
2. M6 immutable spec, gate, close proof, historical verification receipt and approved frozen verifier source;
3. M3 bound product manifest and every consumed product partition;
4. M6 run manifest, candidate list, all 14 fold receipts, every checkpoint `metadata.json` + `state_dict.pt`, every candidate prediction partition and K16 deterministic-refit receipt/reference score;
5. legacy read-only ledger identity and required before/after hash;
6. sealed-root verifier v3, FD-exec helper, bootstrap, `ReplayRuntimeClosure v3`, `PythonStartupPolicy v1`, `ProcessStartupState v1`, fixed argv/cwd/import policy;
7. fresh nonexistent output root and exact `14 replay / 0 fit / OOS=false` profile.

There are no caller source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter path flags or free roots. Replay supervisor verifies every entry by FD, stages immutable data/source/runtime/verifier, applies the same pre-exec envp/umask/startup policy, and creates `ReplayExecutionReceipt v5`. Child receipt repeats binding/runtime/startup/process/stage identities, exact 14 checkpoint/prediction identities and 14/0/OOS values. `m6_archive` accepts only exact binding + supervisor + child agreement, new output and unchanged legacy ledger. Missing/extra/substituted role, caller path, old v1/v2 runtime/receipt, seed/umask receipt substitution, native map drift, existing output or ledger write fails. Linux x86_64 CUDA only is authoritative; macOS yields synthetic non-authoritative evidence.

## 7. Failure, observability, verification and ordered work

All failures before fit deny execution; after `START_RETAINED` they preserve conservative budget accounting; output failures quarantine. Receipts carry activation/event/descriptor/claim/ProcessIdentity, graph/head, actor-policy/ACL, expected+observed closure/startup/process facts, inventory/tree hashes and reason. There is no auto migration of M6 history, old schemas or partial output.

Test-design must cover: M6 6/44 vs 4/29; public Gate denial; PIT/state chain; no-cycle graph/stale profile; UID/group/ACL/socket failures; v4/v1↔v5/v2 substitutions; fork/restart/PID/close-permit races; exact seed/flags/probe/umask pre-exec and bootstrap errors; executable/runtime/native/GPU drift; publisher crash/root/receipt/inventory failures; every M6 v6 inventory role/no-free-path rule and 14/0/OOS ceiling. Later red/green stages retain frozen include-list 100% line+branch coverage, full suite/lint/type and public synthetic E2E.

Implementation order: (1) strict schemas/root IO; (2) public Gate denial; (3) genesis/PIT parsers; (4) actor policy/authority/profile; (5) shared closure/startup helper/bootstrap; (6) descriptor v5/dispatch; (7) publisher/resolver; (8) M6 v6 binding/archive; (9) constrained CLI/E2E. Only after quality red/green/code-review/E2E passes may a separate read-only server replay be proposed. M7, CCC/Gate and final OOS remain later sealed gates.
