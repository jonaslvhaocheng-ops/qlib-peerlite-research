# M6.5 架构确认 v26 — 完整 writer graph、一次性 launch 与可恢复的受控 worker

状态：`DESIGN_ONLY / ARCHITECTURE_REPAIR`。本文件在
`architecture_confirmation_v25.md` 之上修复 v21 change-design preflight 的
actor、runtime、helper、P2 isolation、recovery、ledger 和 state-topology 缺口。v25
和此前审查文件均保留为历史证据；本文件是当前 architecture proposition。

不创建真实 Pin/Policy/Bootstrap/QualityPass/E/C/state/official result，不运行 archival
replay、训练、M7、PIT 或 final-OOS，不改 immutable M6 evidence、`trial_ledger.py`、
`m6_archive.py` 或历史 raw worker。所有后续开发先使用 fake provider/fake worker；真实
Linux release 仍必须缺原语即 fail closed。

## 1. 完整的 physical writer graph

OD（OuterDispatcher）仍是既有 server-governance supervisor 的 one-shot control process；
它只重新观察 sealed release、原子消费 permit、创建 session cgroup、启动/reap actor，不做
研究、归一化或 official slot publication。

```text
trusted scheduler
  └─ OD (trusted outer layer; no durable research-result writer)
       ├─ QualityGateIssuer[ISSUE]  quality-gate-issuer
       │      Bootstrap → QualityPass, then exit/reap
       ├─ ArchiveAcceptor[ADMIT]    result-publisher
       │      E → C, then exit/reap
       ├─ P0 ReplaySupervisor       research-runner
       │    └─ P1 Verifier           child-verifier
       │         └─ P2 RawMechanics  raw-mechanics
       └─ ArchiveAcceptor[FINALIZE] result-publisher, fresh invocation
              ArchiveReceipt → S6 → FinalIndex / post-S5 rejection
```

`quality-gate-issuer`、`result-publisher`、`research-runner`、`child-verifier` 与
`raw-mechanics` 是 Policy 固定的五个不同 Unix uid/gid/group profiles。P2 不再与 P1
共享 uid；这比在 shared uid 上引入 pid-namespace proxy/liveness ambiguity 更小、更可审计。
P2 没有 capabilities，且不属于 P1/P0 的 control supplementary groups。若有专用 staging
read/write group，它必须在 Policy 中逐项列出，且不能赋予 control-root 或 `/proc/<pid>/fd`
access。

| Object / transition | Sole durable publisher | Required precondition |
| --- | --- | --- |
| Bootstrap, QualityPass | QualityGateIssuer[ISSUE] | its runtime observation + observed policy/evidence + its own quality-root lease |
| E, C | ArchiveAcceptor[ADMIT] | verified B/P inputs + its own fresh topology lease |
| S0--S3, H, O, Invocation, Normalized, Envelope, S4, Manifest, S5, pre-S5 terminal | P0 | P0 runtime observation + P1 READY + P0 topology lease |
| P1/P2 mechanics attestation | P1, authenticated IPC only | P2 exit/reap + P1 verification; never a durable control writer |
| ArchiveReceipt, S6, FinalIndex, post-S5 rejection | ArchiveAcceptor[FINALIZE] | P0 reaped + fresh lease + durable S5 chain |

The mandatory sequence is therefore:

```text
OD observation
→ QualityGateIssuer self-observation → Bootstrap → QualityPass → issuer exit/reap
→ ArchiveAcceptor[ADMIT] self-observation → E → C → acceptor exit/reap
→ P0/P1/P2 session → S0…S5 → P0 exit/reap
→ ArchiveAcceptor[FINALIZE] self-observation → receipt/S6/index or rejection
```

No role may substitute another writer because a string role matches. Every durable object carries the
publisher’s observed identity, runtime receipt, launch receipt and descriptor core hash.

## 2. Deployable, one-shot actor launch primitive

### 2.1 Fixed external deployment prerequisite

The trusted supervisor supplies exactly one reviewed native launch helper,
`m6_actor_exec`. It is an OS/deployment primitive, not a Python fallback and not a general process
runner. Before a release can be admitted, `M6ActorExecInstallationV1` must be observed from the final
host and pinned in Policy:

```text
absolute helper FileIdentity and SHA-256; owner_uid=0; owner_gid=m6-governance;
mode=04750; Linux ABI/version; allowed SELinux/AppArmor label if configured;
compiled protocol version; fixed capability set; helper entrypoint identity;
server-governance root and allowed invocation group.
```

The helper rejects any mode/owner/hash/profile mismatch. It accepts **no caller-selected** uid, gid,
argv, entrypoint, cwd, environment, root path or FD number. Its only fixed descriptor labels are:

| FD | Meaning | Available to |
| --- | --- | --- |
| 3 | sealed core descriptor or role view | helper and designated actor only |
| 4 | sealed one-shot `M6ActorPermitV2` | helper only |
| 5 | one-use OD permit-redeem `SOCK_SEQPACKET` endpoint | helper only |
| 6 | sealed anchor / role-fixed input FD | profile-defined P0, issuer or acceptor only |
| 7 | worker-job `O_PATH` FD | only P2 launch helper before private view setup |
| 0--2 | fixed `/dev/null` or role-fixed diagnostic streams | as profile defines |

All other descriptors are closed with `close_range`; no child retains an FD merely because a parent
forgot `CLOEXEC`. The helper checks `F_GET_SEALS` on every required memfd and rejects mutable, missing,
extra or wrong-labelled descriptors.

### 2.2 Atomic permit redemption

OD creates a one-use `M6ActorPermitV2` sealed memfd and a dedicated redeem socket endpoint for every
edge. The permit is copyable as an FD, so its value is not enough. Before any uid transition, helper
must send canonical `REDEEM` over FD 5; OD atomically verifies and transitions a nonce from
`ISSUED → REDEEMED` in its in-memory session table, then returns exactly one `REDEEM_ACK`. The check
binds helper peer credentials, expected parent pid/start-ticks, current session cgroup, permit hash,
core/role-view hash, actor edge and monotonic deadline. A second request, copied FD, wrong parent,
expired permit or absent ACK makes the helper exit before exec.

The helper records an `M6ActorLaunchReceiptV1` in its signed/credentialed response to the launched
actor. It includes the permit hash/nonce, helper installation identity, observed parent identity,
target role identity, cgroup/session id, actual child pid/start-ticks and runtime/entrypoint refs.
The actor binds that receipt into its first durable object or P1 IPC message. OD never writes it into
the research control root.

For `raw-mechanics`, the same helper uses a fixed `P2_VIEW` profile; there is no separate generic
`m6_p2_view_exec`. P0 requests a P2 permit from OD only **after** durable S3. That permit binds the
exact S3 digest, P1 launch receipt/pid/start-ticks, session nonce, one worker-job D-v2 and the single
allowed P2 profile. Thus exactly one P2 can be redeemed for one S3.

### 2.3 Fixed exec behavior

For normal profiles, helper verifies the policy-pinned interpreter and entrypoint files by no-follow FD
and identity/hash, transitions identity, clears ambient capabilities, applies `no_new_privs`, installs
the fixed environment/umask/cwd and uses `execveat`/equivalent fixed exec form. For the sole P2_VIEW
profile it performs the Policy-fixed mount/pivot/proc setup **while still privileged**, validates the
resulting mount identities, then transitions to `raw-mechanics`, clears all capabilities and execs.
It never calls a Python `preexec_fn` or accepts a shell/caller argv. Missing helper installation is
`M6_REPLAY_ACTOR_EXEC_UNAVAILABLE`: fake provider tests may exercise the protocol, but no official
Linux dispatch is permitted.

## 3. Non-cyclic descriptor and runtime-provenance contract

### 3.1 Canonical construction

`M6CoreDescriptorV1` is canonical bytes with **no self digest field**. Its SHA-256 is
`core_descriptor_sha256`. It contains release/context/ledger bindings, root D-v2 chains, actor graph,
slot topology, runtime closure refs, fixed deadline profile and worker-view template.

`M6RoleViewV1` is separately canonical bytes:

```text
{schema, core_descriptor_sha256, role, allowed_parent_edge, fixed_fd_labels,
 runtime_profile_ref, entrypoint_ref, allowed_slot_capabilities,
 session_binding_requirements, worker_view_profile_ref if P2}
```

Its SHA-256 is `role_view_sha256`; neither document includes its own digest. Permit V2 binds both
hashes. OD seals the core and each role view independently; helpers validate seals and equality before
launch. This eliminates descriptor self-reference and gives every actor one unambiguous input.

### 3.2 Exact runtime closure

`RuntimeClosureManifestV1` is generated offline from the frozen runtime. It has an ordered inventory
of interpreter, entrypoint, Python stdlib, pure-Python package roots, extension modules, native
dependencies/`DT_NEEDED` resolution, source trees and canonical file identities/hashes. It also fixes
the initial/allowed `sys.path`, allowed builtin/frozen modules and import policy. It is distinct from
the historical M6 code-binding list: the new verifier/bootstrap assets are M6.5 assets and are never
misrepresented as historical M6 source.

At earliest possible code in each actor, `observe_runtime_candidate_from_self()` records and compares:

```text
interpreter executable and Python ABI; fixed entrypoint and argv profile;
sys.prefix, initial sys.path and environment; uid/gid/groups/capabilities;
loaded module -> origin/hash/native dependency map; descriptor and role-view hashes;
launch receipt and expected parent/session cgroup.
```

It installs a closure import guard before any control action, then takes a second module/native-map
observation before every first durable write and after dynamic import boundaries. Any module, extension,
namespace package, RPATH-resolved library, site-package or entrypoint outside the manifest fails closed.
P0, QualityGateIssuer and ArchiveAcceptor cannot publish until both observations match their profile.

P1 and P2 are standalone pinned bootstrap assets, launched by direct fixed entrypoint—not via
`python -m qlib_peerlite...`. This is required because the current project root eagerly imports model
modules. P1 uses only stdlib parsing/hash/socket/FD code and never imports `qlib_peerlite`. P2 begins
with `-I -S -B`; its stdlib-only bootstrap reconstructs only the manifest sys.path, verifies initial
`sys.modules` lacks `qlib_peerlite`, and permits every `qlib_peerlite.*` import only through the exact
StageInventory module-name/path/hash map. NumPy/pandas/torch/lightgbm/qlib and their native dependency
closures are checked against RuntimeClosureManifestV1, not silently trusted because they are not
`qlib_peerlite`.

## 4. P2 host isolation with a distinct raw identity

P1 forks the launch stub; after successful helper redemption it remains P2’s direct parent across the
uid transition. Because a credential change clears a prior parent-death setting, the native helper
transitions to `raw-mechanics`, immediately sets `PR_SET_PDEATHSIG=SIGKILL`, rechecks P1
pid/start-ticks, and only then execs the P2 bootstrap. P1 owns P2’s pidfd/reap. P0 has a pidfd only for
P1; it receives P2 exit proof in P1’s authenticated attestation rather than pretending it owns P2’s
pidfd.

The helper creates a private mount namespace with propagation made `MS_PRIVATE`, then pivot-roots to a
minimal root whose literal `/m6p2` child contains the fixed raw-worker paths. It must **not** simply
chroot to `/m6p2`, because the legacy worker resolves `/m6p2/...` absolute paths. The P2 root exposes
only:

```text
/m6p2/runtime/                 read-only sealed runtime closure
/m6p2/program/{p2_bootstrap.py,verify_m6_peerlite_archival_replay.py,p2-launch.cjson}
/m6p2/in/{frozen-source-root,frozen-source-archive,product,run,historical-verification.json,trial-ledger.jsonl}
/m6p2/scratch/{tmp,raw-output(absent at start)}
/lib, /lib64, /usr/lib, /usr/lib64    sealed loader/native-library aliases from RuntimeClosureManifestV1
/proc                           fresh private proc mounted hidepid=2
```

The loader alias trees are verified read-only mounts, not a visible host filesystem fallback; every
file in them is part of the runtime closure/native dependency map. The host root, control root, sibling
jobs and P0↔P1 sockets are not mounted. P2 gets no descriptor, permit, job, socket, control, slot, O
or lock FD after helper setup; its post-exec table contains only fixed stdio. The separate raw uid,
`hidepid=2` private proc, `PR_SET_DUMPABLE=0`, no capabilities and `no_new_privs` prevent
`/proc/<P1>/fd`, signal or ptrace access to P1 under the normal-failure model.

Host worker-job permissions are frozen as a single group/ACL template: supervisor-owned parent is not
enumerable; P1/P2 may access only their passed job view; staged inputs are immutable after H; raw output
is writable only until P1’s freeze protocol; P1 may read scratch for verification; P0 can re-open it
through its authoritative job FD. The isolated mount root, not an ACL guess, is what prevents P2 from
traversing known sibling/control paths.

## 5. OD-owned session liveness and crash recovery

OD creates a per-`{K,session_nonce}` cgroup before issuing the first actor permit and places every
launched QI/AA/P0/P1/P2 process in it. Its session table retains launch receipts, pidfds, start-ticks,
role and deadline state. Roles own only their direct child relation:

| Actor | Direct child/handle | Failure action |
| --- | --- | --- |
| OD | QI, AA, P0 and session cgroup | deadline → TERM/KILL/reap/drain; issue sealed drain evidence |
| P0 | P1 pidfd | sends authenticated CANCEL; waits/reaps P1; asks OD cgroup manager on deadline; never claims P2 pidfd ownership |
| P1 | P2 pidfd | normally waits/reaps P2; on cancellation closes job capability and exits, so P2 receives non-ignorable PDEATHSIG=SIGKILL |
| P2 | none | dies on parent death; no control writer |

`SessionDrainEvidenceV1` is generated by OD only after every recorded descendant pidfd has exited and
the session cgroup is empty; it binds core descriptor hash, K, session nonce, full launch receipt set,
drain method/timestamps and no-live-descendant predicate. A fresh P0 recovery actor can terminalize
S0--S4 only after it observes this sealed evidence; it does not reuse pid values or infer safety from
start-ticks alone. OD launches ArchiveAcceptor[FINALIZE] only after P0 has exited/reaped and, where
needed, session drain is complete. If drain cannot be proven, outcome is `HARD_HOLD`.

Because uid transition removes P1's ordinary signal permission over P2, P1 never relies on
`pidfd_send_signal` to cancel it. A normal P2 completion is `waitpid`/pidfd-reaped by its direct P1
parent. An explicit cancellation is P1 closing write capability and exiting; its already-installed
PDEATHSIG=SIGKILL kills P2. If P1/P0 is itself hung, OD—as cgroup owner under the trusted supervisor
root—performs TERM/KILL and produces the drain evidence. The fixed LivenessProfileV1 values from v25
remain: P0/P1/lease/P2 READY 60s, raw 21600s, P1 verify 600s, freeze/reap 120s, archive finalize 600s,
TERM 30s and KILL/reap 30s. Every timeout writes no official state until the responsible child/drain
condition is proved.

## 6. Exact ledger-snapshot and state/output order

### 6.1 Snapshot protocol

After P0 has acquired its OFD lease and created O/S1 but before any P1 dispatch, it performs this exact
sequence:

```text
S0 claim
→ create OUTPUT_O O_EXCL + fsync
→ S1 commits OUTPUT_O D-v2 and fixed child-slot topology
→ create private worker job
→ acquire legacy shared dot-lock BEFORE opening ledger leaf
→ open no-follow fixed leaf; fstat-before; read full L from same FD; fstat-after equal
→ validate close 14328-byte 6/44 prefix, line boundary, M6 journal relation,
   whole newline-terminated JSONL tail/event schema and caps 27/60
→ stream same FD into staged S; fsync; immutable modes; byte length/SHA equality
→ release shared dot-lock
→ publish H
→ publish Invocation including StageInventory and L/S equality
→ S2 commits O/H/Invocation identities
→ S3 commits P1 session/launch receipt/nonce
```

The whole tail validator rejects duplicate JSON keys, truncated/non-newline JSONL, invalid event schema,
altered close prefix, count overflow or source/staged divergence. It uses new read-only control-plane
semantics; it does not turn the legacy pathname writer or its `os.replace` lock into the official OFD
lease. P0 retains no staged write capability after immutable modes are set; no live-ledger FD/path is
ever passed to P1/P2.

### 6.2 State commits and orphan outcomes

The fixed state payloads are:

| State | Required immutable references |
| --- | --- |
| S0 | Context, P0 launch/runtime receipt, K/session claim |
| S1 | S0, exact OUTPUT_O D-v2 and fixed child-slot views |
| H | logical ledger authority, observed L, staged S equality, worker-job D-v2 |
| Invocation | H, StageInventory, exact raw call map, runtime/device refs |
| S2 | S1, H, Invocation, O D-v2 |
| S3 | S2, P1 launch/runtime receipt, nonce, P2 permit request binding |
| S4 | S3, Envelope, Normalized |
| S5 | S4, Manifest, O leaf inventory and all durable evidence refs |

Recovery treats O with no S1, S1 without H, H without Invocation, Invocation without S2, and S2
without S3 as pre-S5 incomplete chains: after OD drain evidence it publishes the prescribed pre-S5
terminal and quarantines the job/O, never reuses K or scratch. A valid S5 with missing/malformed O
leaf, wrong O D-v2 or broken reference is a deterministic post-S5 rejection when the rejection leaf is
absent; an occupied malformed rejection leaf is `REJECTED_HARD_HOLD` and is never overwritten.

## 7. Target code boundaries and verification consequences

The bounded implementation remains a new Linux-only governance sub-system:

```text
identity → fs
identity → authority
authority + fs → ledger / quality / process
ledger + quality + process + fs → worker_adapter
worker_adapter + control state → lifecycle/resolver
```

`m6_replay_fs.py` may not import authority/control/lifecycle. `m6_replay_ledger.py` owns logical
snapshot semantics and does not mutate the legacy ledger. `m6_replay_process.py` owns packet FSM,
pidfds, helper bridge and OD session evidence. P1/P2 bootstraps live as standalone sealed program
assets, not normal `qlib_peerlite` module entrypoints. Historical raw worker, archive verifier, generic
artifact writer and budget ledger remain regression-only inputs.

Later test design must include fake-provider unit proofs and Linux privileged integration proofs for:
QualityIssuer B/P ordering; helper owner/mode/hash/FD labels; copied permit and duplicate redeem;
non-cyclic descriptor bindings; wrong closure/native import; P2 different uid/private proc/no inherited
FD/path escape; OD drain/P0 crash/late attestation; lock-before-open snapshot races and legal append
replacement; S0/O/S1/H orphan recovery; and post-S5 missing/malformed durable leaves. No such test is
claimed executed here.

## 8. Architecture verdict

`PASS FOR ROUTING TO CHANGE-DESIGN` — all physical writer roles, deployable privilege boundary,
one-shot permit semantics, non-cyclic descriptor, complete runtime closure, P2 process identity/
filesystem isolation, OD-owned crash drain, 6/44 snapshot order and durable state recovery are now
defined. This is not an M6.5 PASS and does not authorize M7, real replay, data access, training,
budget consumption or final-OOS work.
