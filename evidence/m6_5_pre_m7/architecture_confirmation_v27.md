# M6.5 架构确认 v27 — 可执行 FD 图、受控 CUDA worker 与 P2 handoff

状态：`DESIGN_ONLY / ARCHITECTURE_REPAIR`。本文件保留 v26 的完整 writer graph、logical
6/44 authority、durable O/H/Invocation/Normalized/Envelope/Manifest chain 和 resolver
semantics，并替代 v26 中任何与下列 FD、P2、GPU、process-tree 或 OD-recovery 规定冲突
的文字。它只修复独立 v26 architecture/runtime review 的 P1 finding；没有运行或改变任何
历史 M6、训练、M7、PIT、final-OOS、预算或 immutable evidence。

## 1. Actor graph and OD lifetime

```text
OD
├─ QualityGateIssuer[ISSUE] : Bootstrap → QualityPass
├─ ArchiveAcceptor[ADMIT]   : E → C
├─ P0 ReplaySupervisor
│   └─ P1 Verifier
│       └─ P2 RawMechanics (one global serialized raw worker)
└─ ArchiveAcceptor[FINALIZE] : ArchiveReceipt → S6 → FinalIndex / rejection
```

Every launched actor has an expected-parent relation. After its final uid/gid/capability transition,
the native helper installs `PR_SET_PDEATHSIG=SIGKILL`, verifies expected parent pid/start-ticks, and
only then executes the pinned entrypoint. P0/QI/AA bind to OD; P1 binds P0; P2 binds P1. The first
instructions of standalone P1/P2 bootstrap reassert `PDEATHSIG`, set dumpability to zero where
applicable, compare `getppid()` with the sealed launch plan, and exit before parsing untrusted data on
a mismatch. This second check covers an exec/runtime-specific reset while the helper-side check closes
the pre-exec race.

OD is non-resumable. If OD exits, its actor death chain drains QI/AA/P0→P1→P2; the trusted
scheduler/root supervisor also kills and drains the session cgroup if any process survives a failed
parent-death transition. A new OD never reuses an old nonce table, permit or session; it starts recovery
only after sealed `ODRecoveryDrainEvidenceV1` proves the old cgroup empty. Otherwise outcome is
`HARD_HOLD`.

## 2. Two-phase fixed FD map

The native helper has a short pre-exec map and a disjoint actor post-exec map. `close_range` closes
everything not listed. No packet may add an arbitrary FD; a receiver rejects unexpected SCM_RIGHTS.

### 2.1 Helper pre-exec map

| FD | Object | Lifetime |
| --- | --- | --- |
| 3 | sealed `M6CoreDescriptorV1` | helper verifies; retained only by non-P2 profile |
| 4 | sealed `M6RoleViewV1` | helper verifies; retained only by non-P2 profile |
| 5 | sealed one-shot `M6ActorPermitV2` | helper only; closed before target exec |
| 6 | dedicated OD `REDEEM` seqpacket endpoint | helper only; closed before target exec |
| 7 | Policy-defined sealed anchor or worker-job `O_PATH` | helper validates/remaps/closes per profile |

Both descriptor memfds must have required `F_GET_SEALS` values. Permit V2 binds core SHA, role-view
SHA, exact edge, parent pid/start-ticks, session cgroup, expiry and post-exec FD profile. OD atomically
changes `ISSUED → REDEEMED` only after credentialed `REDEEM`; copied permit FDs, duplicate redemption
or absent ACK fail before uid transition.

### 2.2 Actor post-exec map

| FD | Fixed name | Held by | Rules |
| --- | --- | --- | --- |
| 3 | `CORE_DESCRIPTOR` | P0, P1, QI, AA | sealed core bytes; P2 receives only derived launch file |
| 4 | `ROLE_VIEW` | P0, P1, QI, AA | sealed role bytes matching FD 3 core SHA |
| 5 | `SEALED_ANCHOR_OR_ROOT` | P0/QI/AA only | role-fixed input, never P1/P2 |
| 8 | `OD_SESSION_CONTROL` | P0/QI/AA | credentialed seqpacket; P0 READY, P2-permit and drain requests |
| 9 | `P0_P1_CONTROL` | P0 and P1 | credentialed seqpacket; READY/ACK/DISPATCH/ATTEST/FREEZE/CANCEL only |
| 10 | `SCRATCH_READ_O_PATH` | P1 only | O_PATH to exact scratch root; no write capability |
| 11 | `P1_P2_EVENT` | P1 and P2 | credentialed seqpacket; READY/ACK/DONE/ABORT only; no SCM_RIGHTS |
| 12 | `WORKER_JOB_O_PATH` | P1 until helper starts P2 | may only be passed to helper, then P1 closes it |
| 13--16 | `ROLE_ROOT_n` | P0/QI/AA as RoleView enumerates | exact O_PATH roots; never generic paths |

P0 receives a P2 permit from OD over FD 8 and sends exactly three rights over FD 9 to P1:
`P2_PERMIT`, `WORKER_JOB_O_PATH`, `SCRATCH_READ_O_PATH`. P1 maps permit/job to helper FDs 5/7,
maps its own verified scratch/event endpoints to fixed 10/11 with `dup3`, retains only 9/10/11
afterwards, and rejects any other right. P2 post-exec has only FDs 0--2 and 11; it never receives Core,
RoleView, permit, OD/P0 socket, job, scratch O_PATH, control root, output root or lock FD.

All IPC channels use AF_UNIX/SOCK_SEQPACKET with `SO_PASSCRED`, fixed peer uid/gid/pid/start-ticks,
descriptor core SHA, session nonce, monotonic sequence and bounded canonical bytes. They reject
truncation, wrong sender/state/deadline, duplicate message and extra FD. P2 events are informational
until P1 reopens verified files and obtains OD drain evidence; they carry no authority.

## 3. Sterile P1/P2 runtime and non-cyclic binding

`M6CoreDescriptorV1` is canonical bytes without a self digest; its external identity is
`core_descriptor_sha256`. `M6RoleViewV1` is separate canonical bytes binding that SHA and its own
`role_view_sha256`. P1 receives both FD 3 and FD 4 and verifies their equality relation before it
accepts P0 READY/DISPATCH.

P1 is a standalone sealed stdlib bootstrap, not a `qlib_peerlite` module. Its pinned exec form is
`python -I -S -B <sealed-p1-bootstrap>` with `env -i`; it reconstructs only its
`RuntimeClosureManifestV1` sys.path and rejects `site`, `.pth`, customizations, `PYTHON*`,
`VIRTUAL_ENV`, `CONDA*`, `LD_PRELOAD`, `LD_AUDIT` and caller cwd/path input. P1 takes its first
runtime/module/FD/identity observation before parsing any P0 packet.

P2’s read-only `p2-launch.cjson` is generated by helper from sealed core/role/permit and contains core/
role SHA, P1/P2 launch receipt hashes, expected P1 pid, StageInventory SHA, RuntimeClosure SHA,
DeviceView SHA, fixed environment and exact raw call map. Before raw code, P2 writes
`P2ObservedRuntimeReceiptV1` at its fixed scratch leaf with mode `0640` and fsync; it binds launch-file
SHA, identity/capability/PDEATHSIG/dumpable/FD state, mountinfo and DeviceView, environment/sys.path,
initial module/native map, StageInventory and raw-script identity. P1 opens it through FD 10, checks it
against FD 3/4 and Invocation, then sends the only `P2_ACK`. P2 can run raw only after ACK; P1 checks
pre-run and final receipts again after P2 drain.

## 4. P2 process, namespace and CUDA DeviceView

### 4.1 One raw worker and no surviving descendants

`raw-mechanics` is a fixed service uid, so OD owns `RAW_MECHANICS_LEASE` in addition to the session
lease. It issues a P2 permit only if the global raw cgroup is empty and no raw launch receipt remains.
A second P2 request is `BUSY`; archival replay is deliberately serialized. The raw account has nologin
and can only be entered through the helper.

Each P2 joins a dedicated nested cgroup:

```text
/m6-replay/<K>/<session_nonce>/p2
```

`P2ProcessPolicyV1` is pinned in RoleView. It denies `fork`, `vfork`, `unshare`, `setns` and
process-form `clone`; it allows only thread-form `clone` flags required by the sealed Python/Torch
runtime. `clone3` returns `ENOSYS` so the reviewed runtime takes its tested thread fallback.
`pids.max` is a fixed tested thread budget.

On P2 DONE and leader exit, P1 requests `P2_DRAIN` through P0/OD. OD freezes only this P2 child cgroup,
verifies leader pidfd exit, checks `cgroup.events.populated=0` and the process-policy status, then
returns sealed `P2DrainReceiptV1`. If any process remains, OD kills that child cgroup, waits empty and
returns a failure receipt; P1 must not attest. P1 never direct-signals cross-uid P2: cancellation is
P1 exit (PDEATHSIG kills leader), while OD owns deadline/cgroup cleanup.

### 4.2 Private root with no old-root escape

While privileged, helper executes:

```text
unshare(CLONE_NEWNS) → recursively make / MS_PRIVATE
→ create verified newroot mountpoint and Policy-fixed bind/tmpfs mounts
→ pivot_root(newroot, newroot/.oldroot) → chdir("/")
→ umount2("/.oldroot", MNT_DETACH) → rmdir("/.oldroot")
→ close pre-pivot path FDs/cwd references
→ verify mountinfo contains no old host-root or unexpected mount
→ transition raw uid/capabilities → parent-death/dumpable guards → exec P2.
```

Visible root has only verified read-only runtime/library aliases (including the sealed `/lib`, `/lib64`,
`/usr/lib` and `/usr/lib64` loader trees), `/m6p2` input/program trees, scratch, private `hidepid=2`
proc, fixed `/dev/null`, and the DeviceView below. It never mounts host control, output or worker
parents, sibling roots, sockets or general `/dev`. Literal `/m6p2/...` survives pivot-root, so the
unchanged worker’s `Path.resolve()` remains valid.

### 4.3 CUDA is an immutable DeviceView

Official raw replay is CUDA-only; CPU fallback is forbidden. `GpuDeviceViewV1` is pinned in Policy,
Invocation and p2-launch. It includes selected GPU UUID/MIG identity, `CUDA_VISIBLE_DEVICES`,
driver/CUDA ABI, libcuda/runtime hashes, node destination/rdev/mode/ACL inventory and cgroup
device-allow rules. Helper mounts only required selected `/dev/nvidiaN`, `/dev/nvidiactl`,
`/dev/nvidia-uvm`, necessary caps/uvm nodes, plus fixed-size/mode `/dev/shm`; there is no catch-all
host `/dev`. P2 receipt re-observes nodes, ABI, environment and cgroup rule. Missing or mismatched
view is `M6_REPLAY_DEVICE_VIEW_UNAVAILABLE`, never a CPU retry.

## 5. Cross-UID scratch handoff without changing raw worker

Helper creates host scratch as `raw-mechanics:m6-verifier-read`, mode `02750`: P2 owner has rwx,
P1’s dedicated group has rx only, and P0 retains its authoritative job FD. P2 has
`m6-verifier-read` only as a tightly scoped result-read supplementary group. FD 10 is P1’s O_PATH to
this exact scratch root. P1 may only use:

```text
openat2(FD10, fixed_relative_leaf,
  RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS,
  O_RDONLY | O_NOFOLLOW)
```

`raw-output` is absent at raw start and P2 umask is `0027`. The unchanged raw writer may atomically
create its final receipt with mode `0600`. After raw `run()` succeeds, **only P2 bootstrap** performs
`RawOutputHandoffV1`:

1. It no-follow opens the sole `scratch/raw-output/archival_replay_receipt.json` and rejects a
   symlink, nonregular file, extra raw-output leaves, wrong setgid verifier-read group, wrong
   schema/status/content hash, or changed staged-ledger claims.
2. It changes no receipt bytes; it fchmods the receipt to `0640`, then fsyncs receipt and both
   raw-output/scratch directories.
3. It writes fixed `P2CompletionReceiptV1`, mode `0640`, binding pre-run receipt SHA, raw receipt SHA,
   stage/scratch inventory, final module/native map and exit intent, then fsyncs it.
4. It sends digest-only P2_DONE and exits.

If raw throws, P2 writes no completion receipt. P1 needs a passing P2DrainReceipt before opening any
leaf, then requires pre-run/raw/completion hashes and inventory to match Invocation and event claims.
Mode handoff makes raw bytes readable; raw receipt remains mechanics-only.

## 6. Fully specified control sequence

```text
P0 (FD8) READY → OD ACK
P1 (FD9) READY → P0 ACK
P0 lease → S0 → OUTPUT_O → S1 → stage/ledger snapshot → H → Invocation → S2 → S3
P0 (FD8) P2_PERMIT_REQUEST → OD reserves global/P2 cgroup → permit
P0 (FD9 + exact three rights) DISPATCH → P1
P1 starts helper/P2 → P2 (FD11) READY(pre-run hash) → P1 validates FD10 → ACK
P2 raw → RawOutputHandoff → DONE → exits
P1 leader exit → P0/OD P2_DRAIN → P2DrainReceipt
P1 verified scratch → ATTEST(FD9) → P0 verifies → FREEZE_REQUEST
P1 closes 9/10/11 and exits → P0 reaps P1
P0 final equality → Normalized → Envelope → S4 → Manifest → S5 → exits
OD reaps P0 → fresh ArchiveAcceptor[FINALIZE] lease → receipt/S6/index or rejection
```

Missing ACK, extra FD, wrong credential/sequence, invalid P2 receipt/handoff, nonempty P2 cgroup,
lost IPC or deadline creates no S4/S5. P1 exits, OD drain evidence is required, then P0 may write only
the canonical pre-S5 terminal. v26 ledger snapshot order and post-S5 resolver semantics are unchanged.

## 7. Architecture verification obligations

The next change design must specify unit, fake-provider and Linux privileged integration coverage for:
core/role FD equality; all post-exec FD allow-lists and SCM_RIGHTS rejection; sterile P1 startup;
credentialed packet FSM; permit replay; global raw lease `BUSY`; P2 process-form clone denial/thread
allowance; P2 cgroup nonempty drain failure; pivot old-root detachment; no host/sibling/control path;
post-exec dumpability; RawOutputHandoff mode/bytes/fsync behavior; P2 pre/final runtime receipt
substitution; CUDA DeviceView missing/rdev/ABI/cgroup/shm failure; P0/OD crashes; and no S4/S5 until
P2DrainReceipt passes.

## 8. Architecture verdict

`PASS FOR ROUTING TO CHANGE-DESIGN` — normal success, cancellation, CUDA and crash paths now have an
explicit actor, FD, namespace, process-tree, scratch and device contract. This is architecture only:
it is not M6.5 PASS and does not authorize replay, M7, data access, training, budget consumption or
final-OOS work.
