# M6.5 架构确认 v24 — Deployable release DAG, Linux control primitives and attested worker session

状态：`ARCHITECTURE_READY / 待变更设计`。本文件以
`architecture_confirmation_v23.md`（SHA-256
`8e7eb49da6f4600bcf393b342997afeffb08fdac9256ddd95cdefd17f0b38a7a`）为基线，且只修复
v20 变更设计预检发现的 Linux/部署级架构问题。v23 的 Pin/PolicyV2/evidence closure、
writer matrix、E/C→Q deterministic materialization、post-S5 continuation 和 raw-worker
mechanics-only原则均保留；本文件覆盖其中的 release build、filesystem/process、child IPC、
output promotion 和 rejection canonicalization 细节。

仍为 `DESIGN_ONLY`：不创建正式 release bundle/pin/quality PASS 或 replay control object；
不运行 raw replay、训练、M7、PIT 或 final OOS；所有后续验证先以 fake provider/fake worker
进行。生产 dispatch 仅支持 Linux + CPython 3.11，缺少任一列明原语即 fail closed。

## 1. 无环的 release-build / Pin 安装 DAG

`M6QualityReleasePinV1` 不能同时被它所 hash 的 entrypoint 自身编译进去。v24 固定两个
不同 trust layers：受信 server supervisor/outer dispatcher 与被 quality route 审查的 immutable
runtime entrypoint。Pin 是 outer dispatcher 在最终安装后通过 sealed descriptor 交给 inner
entrypoint 的 trusted deployment input；inner entrypoint 的 source/hash 不含 Pin bytes。

唯一允许的顺序为：

```text
1. Freeze RuntimeCandidate
   = authorized inner entrypoint + Python runtime/dependency closure + source manifest.
   Produce RuntimeClosureRef and AuthorizedEntrypointRef; neither contains Pin/Policy bytes.

2. Complete M6.5 quality route against RuntimeCandidate.
   M6_5_ROUTE_CLOSURE contains an append-only ledger PREFIX
   {ledger_identity, prefix_byte_length, prefix_sha256}, exact stage-result refs,
   PASS predicates and independent-review receipts; it does not reference a future Pin/PASS.

3. Offline release builder copies the exact closed evidence set into a read-only EvidenceBundle,
   then creates PolicyV2 from RuntimeClosureRef, AuthorizedEntrypointRef, evidence refs and
   topology template. PolicyV2 never references Pin.

4. Installer creates the final sealed anchor filesystem, writes PolicyV2/EvidenceBundle,
   fsyncs, installs final ACLs and mounts/places it at its final location. No later copy,
   bind-mount replacement or relocation is permitted.

5. Installer observes final anchor D-v2, policy-parent chain, policy FileIdentity and PolicyV2
   bytes/ref, then constructs PinV1. The outer dispatcher seals PinV1 together with the
   sealed-anchor contract and passes it only by descriptor to the inner entrypoint.

6. Runtime re-observes PinV1 → PolicyV2 → EvidenceBundle from that installed anchor before
   it can publish Bootstrap/PASS or E/C.
```

Pin construction after final placement intentionally makes any later copy/mount/ACL/root identity drift
invalid. The outer dispatcher and sealed anchor are part of the existing trusted supervisor boundary;
they are not a second application service. Current M6.5 gate is still `NEEDS_CHANGES`, so steps 2–6
cannot occur now; synthetic test fixtures model them without claiming a real release.

## 2. Linux filesystem primitive boundary

New `m6_replay_fs.py` is the sole production implementation of control-root filesystem operations.
It imports only pure identity types and exposes no generic `Path` publisher. Its Linux capability probe
must require, before any official dispatch:

```text
CPython 3.11 on Linux
openat-style O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC descriptor traversal
statx/name_to_handle_at identity support required by DirectoryIdentityV2
fcntl(F_OFD_SETLK) using a reviewed native ABI wrapper
renameat2(RENAME_NOREPLACE) and directory fsync for durable immutable publication
AF_UNIX SOCK_SEQPACKET, SO_PASSCRED/SCM_CREDENTIALS, and pidfd support
```

Missing primitive, unsupported filesystem, `EINVAL`, `ENOSYS`, `ENOTSUP`, identity ambiguity or
permission mismatch returns a stable `M6_REPLAY_LINUX_PRIMITIVE_UNAVAILABLE` / specific fail-closed
error; there is no `flock`, `os.replace`, generic tempfile or portable fallback. macOS and other
platforms may instantiate only synthetic fake providers in unit tests and are never production evidence.

Control publication is exact: verified parent FD → create same-parent temporary leaf with `O_EXCL` →
write canonical bytes and file fsync → `renameat2(RENAME_NOREPLACE)` into fixed leaf → parent fsync.
Every reopen is component-by-component no-follow with full D-v2/file identity comparison. Existing
`artifacts.atomic_write_json`, `trial_ledger` locks and raw worker `os.replace` remain outside this
boundary and cannot publish or lock official control state.

`m6_replay_fs.py` also exposes an OFD lease object only to control code. It uses an `O_RDWR`
no-follow lock FD, explicit `ctypes`/reviewed native `struct flock` ABI and nonblocking `F_OFD_SETLK`;
`EAGAIN`/`EACCES` means `BUSY`. `O_PATH` FDs are rejected for lock/fsync use.

## 3. Exact process graph and message-authenticated child attestation

There are exactly two runtime processes in an authorized mechanics run:

```text
replay_supervisor (P0, topology-lock owner, supervisor identity)
    └── verifier session (P1, child_verifier identity, runs frozen raw worker as a function)
```

P1 is not a direct `exec` of the raw worker. It is a tiny frozen Python session module launched before
P0 acquires the topology lock. P1 receives only an IPC endpoint and minimal `env -i`; it has no
control-root, policy, lock, slot or official-output FD. After S3, P0 transfers only the private
`WORKER_JOB` FD and dispatch payload. P1 `fchdir`s to that job, dynamically loads the staged frozen
raw-worker file and calls its unchanged `run()` with the frozen stage-relative parameter set. It can
therefore wait for return, re-open scratch and produce an attestation without a third raw-worker process
or unsafe `preexec_fn`.

P1 is bound to P0 with a Linux `PR_SET_PDEATHSIG` call made by P1 after exec, followed immediately by
an expected-parent-PID recheck. It runs under the policy-fixed `child_verifier` Unix identity, distinct
from P0; P0 opens a pidfd and records P1's PID, `/proc` start ticks, uid and gid in S3. P1 owns no
official durable writer capability. If this identity/ACL/pidfd/PDEATHSIG predicate cannot be established,
official dispatch refuses before starting the raw function.

The transport is a pre-created `AF_UNIX/SOCK_SEQPACKET` pair, but **not** authenticated with
`SO_PEERCRED`: socketpair peer credentials can describe the pre-fork parent. P0 sets `SO_PASSCRED` on
its receive side and requires exactly one P1→P0 attestation message carrying kernel-attached
`SCM_CREDENTIALS`. It rejects missing/duplicate messages, `MSG_CTRUNC`, extra/missing FDs, credential
PID/uid/gid mismatch, start-tick mismatch, wrong nonce/H/context binding or a message after session exit.
`SCM_RIGHTS` used for P0→P1 job transfer proves no identity by itself; received FDs are made
non-inheritable and re-observed before use. P0's spawn uses `close_fds=True` plus an explicit allow-list;
P1 never receives topology/root/slot/lock/O descriptors.

The original at-fork poison/PID-generation guard remains mandatory for P0's `LockedVerifiedControlTopology`.
P1 begins before the lock exists and cannot inherit it; defense-in-depth child-at-fork closes any
accidental control FD. P0 holds the same topology lock from durable S3 through P1 completion, credential
validation, envelope/S4 and S5. Live lock contention returns `BUSY`; after P0 death P1 dies and cannot
promote scratch, while a successor may terminalize the incomplete pre-S5 chain.

## 4. Worker-job compatibility and canonical official output

`WORKER_JOB` is one O_EXCL private directory role, created under a supervisor-only parent and FD-passed
to P1. It contains exactly:

```text
stage/inputs/frozen-source-root
stage/inputs/frozen-source-archive
stage/inputs/product
stage/inputs/run
stage/inputs/historical-verification.json
stage/inputs/trial-ledger.jsonl
stage/program/verify_m6_peerlite_archival_replay.py
scratch/raw-output                 # absent before raw run
scratch/tmp
```

`StagedMechanicsInvocationV1` freezes the exact legacy-call field names, staged absolute paths derived
from the received job FD, expected source archive hash, expected revision, expected historical hash,
fixed device, interpreter/runtime/script hashes, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`,
`TMPDIR=scratch/tmp`, recursive stage inventory and read-only stage modes. It is the only adapter
contract allowed to invoke the unchanged raw `run()`. There are no caller paths, symlink/hardlink stage
entries, writable source/import directories, raw-worker CLI semantic changes or direct access to O.

The staged ledger is an immutable copy. Its unchanged hash proves only that the raw function could not
mutate the copy; H separately binds the observed live-ledger identity and immutable prefix and records
that no live ledger FD/path was passed to P1. It makes no false claim that a copied-ledger check proves
global live-ledger immutability.

P0 alone converts observed scratch facts into an official `ReplayOutputManifestV1` in O. The manifest
is a canonical, deterministic object containing Context/H/envelope refs, staged invocation ref,
normalized verified mechanics claims, raw-receipt digest/schema and scratch inventory digest—never a
scratch path, directory traversal or a raw receipt treated as authority. `ChildMechanicsAttestationV1`
and `ChildReceiptEnvelopeV2` bind the same raw digest/inventory/normalized claims. S5 references the
manifest and envelope; ArchiveAcceptor independently re-opens O and recomputes these canonical bindings
without reading worker scratch. Thus scratch cannot become an implicit long-term official dependency.

## 5. Deterministic archive rejection and resolver priority

`ArchiveAcceptanceRejectionV1` has one canonical schema:

```text
schema, K, Context ref, reachable S5 ref (or explicit absence),
reason_code enum, sorted offending role→observed digest/ref relation,
expected predecessor relation
```

It excludes exception strings, timestamps, PIDs, cwd, random values and mutable paths. Under the held
lock, `accept_or_resume_post_s5` first opens the rejection slot, then ArchiveReceipt, S6 and FinalIndex,
and applies the fixed priority:

```text
valid existing rejection                → reject idempotently
valid complete receipt/S6/index, no rejection → accept idempotently
valid receipt only                       → continue S6 then index
valid receipt+S6 only                    → continue index
valid S5 with no later slot              → publish receipt then S6 then index
any malformed/gap/wrong binding/final-index conflict → publish canonical rejection once; never promote
```

`OfficialArchiveResolver` checks rejection before FinalIndex. Any rejection with a FinalIndex, or an
inconsistent late artifact combination, rejects rather than selecting a winner. `POST_S0_TERMINAL`
remains forbidden after reachable valid S5; rejection is the sole post-S5 failed branch.

## 6. Refined module boundaries and scope

The dependency graph is now:

```text
m6_replay_identity.py      pure D-v2/F-v1/actor/ref value types
          ↓
m6_replay_fs.py            Linux FD traversal, identity observation, OFD/no-replace primitives
          ↓                 ↘
m6_replay_process.py       fork generation, P1 launcher, pidfd and credential transport
          ↓                  \
m6_replay_authority.py     canonical Pin/Policy/schema parsing and deterministic derivations
          ↓                  /
m6_replay_quality.py       observed release/evidence and Bootstrap/PASS issuance
          ↓
m6_replay_control.py       slots, held topology, E/C and P-through-Q recovery
          ↓                 ↘
m6_replay_worker_adapter.py private staging, legacy-call mapping, normalized mechanics verification
          ↓                 ↙
m6_replay_lifecycle.py     S0–S6, output/envelope, archive recovery and official resolver
```

`m6_archive.py`, `trial_ledger.py`, generic artifacts and the raw worker remain unchanged/read-only or
mechanics-only. No database/service, research change, M7 operation or production run is introduced.
The next change design must freeze the listed public/internal DTO fields, error codes, staged-call
mapping, Linux capability probe, release installer manifest and synthetic-vs-server test separation;
none may be chosen ad hoc in implementation.
