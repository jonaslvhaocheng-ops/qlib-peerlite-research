# M6.5 R3 修复设计 v19 — Issuance, locked lifecycle and official resolver

状态：`IMPLEMENTATION_READY / 待独立设计审查`。唯一架构输入是
`architecture_confirmation_v22.md`（SHA-256
`389ccd530c7705244e9025ef72efd891527a55a97286f14293e4912f12af49e9`）；本设计
替代 v18。它只定义合成可测的 M6.5 control-plane 代码，不创建真实 QualityPass/
Bootstrap/E/C/P/F/A/B/Q/R/V/state/receipt，不运行 archival replay、训练、M7、PIT
或 final OOS，不改 immutable M6 evidence、历史 runner 或 trial ledger。

## 1. Scope and current repository fit

现有 `m6_archive.py` 是冻结 M6 历史 proof 的只读 verifier，
`verify_m6_peerlite_archival_replay.py` 是接受 caller paths 并产生 raw mechanics
receipt 的 replay worker，`trial_ledger.py` 是独立的 append-only budget ledger。三者
均不适合兼任 authority issuer、control-root resolver 或 official result resolver。
v19 新增独立 governance modules；不修改它们的历史语义或把 raw worker receipt
升级为 official evidence。

目标是以最低必要模块交付 v22 的五个强制边界：

1. `quality_gate_issuer → Bootstrap → QualityPass` 的 observed-byte trust chain；
2. `archive_acceptor` 独占 E/C durable issuance；
3. root-relative SlotSpec、FD identity 和 held OFD lock；
4. Q/R/V、pre-S0 和完整 S0…S6 / receipt / output lifecycle；
5. 只能读取 FinalIndex→S6 的 official resolver，明确拒绝 raw mechanics output。

非目标仍为 M7/CCC/Gate、任何真实 fit/replay、最终 OOS、数据库/daemon、外部服务、
权限提升或对 hostile host 的防御。

## 2. Component layout and dependency direction

```text
m6_replay_identity.py      canonical FD identities, no-follow resolution and
                            opaque effective-actor capabilities
          ↓
m6_replay_authority.py     pure schemas / canonical Context / typed refs
          ↓
m6_replay_quality.py       fixed quality-policy reader and Bootstrap/PASS issuer
          ↓
m6_replay_control.py       SlotSpec topology, actor capability, held OFD lock,
                            archive-acceptor E/C issuance, Q/R/V/pre-S0
          ↓
m6_replay_lifecycle.py     S0…S6, controlled worker launcher, archive acceptance,
                            FinalIndex resolver
          ↓
scripts/server/*           validate-only and future authorized entrypoints
```

Only downward imports are allowed. `m6_archive.py`, `trial_ledger.py`, data,
models and the old worker do not import the new control-plane. The new lifecycle
may spawn the frozen raw worker only through an injected `MechanicsWorker`
protocol; it never treats the raw output as a state/receipt by itself.

This is preferable to extending `m6_archive.py` because it keeps frozen historical
proof separate from mutable control-plane publication. A database/service is
rejected because one local FD/lock/slot graph already matches the threat model.

## 3. Schemas and trusted observed inputs

### 3.1 `m6_replay_identity.py`

Retain `DirectoryIdentityV2` and `FileIdentityV1` exactly as v21/v22: all stable
device/inode/mount/btime/opaque-handle/owner/mode/ACL fields, no partial or
fallback form. `NativeLinuxFdIdentityProvider` uses `statx`,
`name_to_handle_at(AT_EMPTY_PATH)`, one initial sizing retry only and F_OFD lock
support; unsupported/permission/noncanonical result fails closed. It provides:

```python
class FdIdentityProvider(Protocol):
    def observe_directory_v2(self, fd: int) -> DirectoryIdentityV2: ...
    def observe_file_v1(self, fd: int) -> FileIdentityV1: ...
    def open_dir_chain_from_root(
        self, root_fd: int, components: tuple[str, ...]
    ) -> VerifiedDirectoryChain: ...
    def open_regular_file_from_root(
        self, root_fd: int, components: tuple[str, ...]
    ) -> int: ...
```

Both component methods enforce root-relative, no-follow/no-xdev component grammar;
they never accept `Path`, cwd or a registry-relative overload. `VerifiedDirectoryChain`
owns its FDs and exposes canonical identities; callers cannot silently drop a
prefix. Test-only synthetic providers live under `tests/`, not production source.

### 3.2 `m6_replay_authority.py`

This remains a pure parser/canonicaliser. It defines closed dataclasses for:

```text
TypedArtifactRef
M6QualityGateReleasePolicyV1
M6EngineeringQualityGatePassV1
M6ReplayAuthorityBootstrapV1
ReplayControlRootBindingV2 / SlotSpecV1
M6ReplayAuthorityContextV1
M6ReplayAuthorityBindingV3
M6ReplayControlPolicyV5
```

It exposes only deterministic functions:

```python
def parse_canonical_artifact(raw: bytes, *, expected_schema: str) -> Mapping[str, Any]: ...
def typed_ref_for_observed_bytes(raw: bytes, *, schema: str, role: str, path: str) -> TypedArtifactRef: ...
def derive_authority_context_key(context: M6ReplayAuthorityContextV1) -> str: ...
def derive_coordinate_k_v4(...) -> str: ...
def validate_context_snapshot(candidate: Mapping[str, Any], authority: M6ReplayAuthorityBindingV3) -> None: ...
```

`TypedArtifactRef` represents observed bytes only; parsing a caller-supplied
mapping does not establish a ref. `M6EngineeringQualityGatePassV1` has mandatory
`status=PASS`, exact gate ID, `release_policy_ref`, `replay_issuer_bootstrap_ref`,
quality issuer identity and all required M6.5 evidence/closure fields. Its parser
rejects generic `status=PASS`, raw worker receipt schemas and `M6ArchiveSummary`.

### 3.3 `m6_replay_quality.py`

This module owns pre-E quality slots and cannot issue E/C/R/V. Its public surface
uses FD capabilities, not paths:

```python
@dataclass(frozen=True)
class ObservedArtifact:  # ref + canonical bytes + verified parent chain
    ...

@dataclass(frozen=True)
class VerifiedQualityInputs:  # non-public constructor
    release_policy: M6QualityGateReleasePolicyV1
    bootstrap: ObservedArtifact
    quality_pass: ObservedArtifact
    root_chain: VerifiedDirectoryChain

class QualityGatePublisher:
    def publish_bootstrap(self, *, policy, actor: ActorCapability, raw: bytes) -> ObservedArtifact: ...
    def publish_quality_pass(self, *, policy, actor: ActorCapability,
                             bootstrap: ObservedArtifact, raw: bytes) -> ObservedArtifact: ...

def observe_verified_quality_inputs(
    *, sealed_anchor_fd: int, policy: M6QualityGateReleasePolicyV1,
    provider: FdIdentityProvider, actor: ActorCapability,
) -> VerifiedQualityInputs: ...
```

`QualityGatePublisher` accepts only a `quality_gate_issuer` capability and the
two policy-fixed quality slots. It O_EXCL-publishes Bootstrap then PASS; before
PASS publication it parses the candidate bytes and demands its observed
Bootstrap ref, release-policy ref, issuer/ACL/root/runtime/family/profile values
equal the observed Bootstrap/policy. `observe_verified_quality_inputs()` repeats
the same check from no-follow observed bytes and builds the non-public capability.
It never reads an arbitrary repository path. Real values arrive only after the
future M6.5 gate; tests use synthetic canonical bytes and FDs.

## 4. Control topology, publisher roles and lock capability

### 4.1 `m6_replay_control.py`

`SlotResolver` receives an observed Bootstrap or E Context and resolves every
`SlotSpecV1` from the replay-control root FD. It compares the **complete** parent
identity chain for each role before returning an `OpenedSlotParent`; it has no
generic path/open API. All slots in v22's table, including quality, E/C, P/F/A,
B/Q/R/V, every state/receipt, outputs and final index, are represented once.

`m6_replay_identity.authenticate_actor()` compares effective uid/gid/groups/
capabilities/process identity plus the relevant parent FD ACL to the supplied
writer-matrix entry and returns an opaque `ActorCapability`. It has no public
constructor and is revalidated per write. Correct content from a wrong role is
rejected before a temp file or state write. Placing this capability in the
lowest-level identity module lets quality and control code depend on it without
an import cycle.

```python
class LockedVerifiedControlTopology(AbstractContextManager):
    # private constructor; owns exact F_OFD_SETLK fd and verified slot parents
    ...

def acquire_locked_verified_topology(
    *, sealed_anchor_fd: int, bootstrap_or_authority: BootstrapOrAuthority,
    actor: ActorCapability, provider: FdIdentityProvider,
) -> LockedVerifiedControlTopology: ...
```

The acquisition protocol is exact: resolve root/required parents → open the
single root-relative lock → `F_OFD_SETLK` exclusive + CLOEXEC → re-resolve and
compare root, lock and all required parent chains after lock acquisition. Loss,
close/fork/exec, failed revalidation or unsupported OFD lock discards the
capability without a write. All mutations receive this capability and make a
last predecessor/terminal/slot check while it is held.

`ArchiveAuthorityIssuer.issue_authority_and_control()` is separate from registry
operations. It accepts exactly `VerifiedQualityInputs`, an archive-acceptor
capability and `LockedVerifiedControlTopology`; builds E from observed PASS/
Bootstrap values, validates Context key, then writes E and C in their exact slots
via durable O_EXCL publication. It cannot be called by replay supervisor. No
registry/lifecycle class exposes an E/C publication method.

`ReplayReservationRegistry` starts at P/F/A/B/Q and exposes:

```python
def build_precommit_before_claim(...) -> ReplayInputPrecommitV1: ...
def claim_and_bind(locked: LockedVerifiedControlTopology, q: ReplayInputPrecommitV1) -> tuple[R, V]: ...
def recover_pre_s0(locked: LockedVerifiedControlTopology, k: str) -> RecoveryDecision: ...
```

`claim_and_bind` holds one capability from R through V and publishes only R→V or
R→PreS0Terminal. It rechecks terminal/V absence before each step. `recover_pre_s0`
uses the same lock and cannot publish terminal while another holder can publish V.
No raw `VerifiedControlTopology` mutation method exists.

## 5. Full lifecycle, controlled worker and official resolver

### 5.1 `m6_replay_lifecycle.py`

`M6ReplayLifecycle` is the only post-V mutator. It exposes the exact v22 state
operations and no generic `publish_state`:

```python
enter_s0(locked, v) -> S0
prepare_output(locked, s0, b) -> S1, O, S2
seal_handoff(locked, s2, output_fds, launch_contract) -> H, S3
record_child(locked, child_receipt) -> S4
finalize_execution(locked, s4, child_receipt) -> ReplayExecutionReceipt, S5
recover_post_s0(locked, k) -> RecoveryDecision
```

Each method checks Context snapshot, actor role, exact previous state, fixed
SlotSpec parent, no future/terminal object and output root D v2; it durable
O_EXCL-publishes the listed objects in order. `recover_post_s0` accepts a fully
validated S5 only for archive acceptance; every incomplete/forked/gapped/wrong-
writer/ambiguous S0…S4 residue produces the one fixed `POST_S0_TERMINAL` under
the same held lock, after which no lifecycle method can continue.

`AuthorizedArchivalReplayLauncher` is injected with a `MechanicsWorker` protocol.
In a real server it constructs a fixed `env -i` argv/cwd/import invocation from
Context, grants the child only sealed read FDs plus a staging/output FD and
captures its raw receipt. Tests use a fake worker and never invoke the historic
script or perform a replay. A raw mechanics receipt is an input to
`ChildReceipt`, never a substitute for it.

`ArchiveAcceptor.accept_archive()` requires archive-acceptor capability plus
locked topology, rehashes S0…S5 and output inventory, rejects any terminal or
unexpected object, then publishes `ArchiveAcceptanceReceipt → S6 → FinalIndex`
in the v22 slots. The final index references only S6/Archive receipt/context/K;
it never scans a directory or chooses a current head.

### 5.2 Official admission and server scripts

`OfficialArchiveResolver.resolve(k)` accepts only an archive-acceptor-authenticated
FinalIndex at its fixed slot, then validates its S6/ArchiveAcceptance/S5 chain
through the same topology/context. It explicitly rejects:

- `qlib_peerlite_m6_archival_checkpoint_replay_v1` raw receipts;
- `M6ArchiveSummary`, generic PASS/status documents and staging/output paths;
- caller-selected roots, output dirs, mutable heads and legacy direct CLI output.

Existing `scripts/server/verify_m6_peerlite_archival_replay.py` stays unchanged
and is labelled mechanics/forensic-only by new parsers. Add
`scripts/server/validate_m6_replay_authority.py` (no write/replay) and
`scripts/server/run_authorized_m6_archival_replay.py`, which accepts one sealed
input-manifest FD/descriptor rather than individual paths. The latter rejects
unless `VerifiedQualityInputs`, E/C, locked topology and the complete V→S5 chain
are available; it is never executed in M6.5 tests or this design stage.

## 6. Publication, errors, compatibility and observability

All durable writes use same-directory temp → file fsync → Linux atomic no-replace
link/rename → parent fsync. Unsupported primitive, parent identity change,
writer mismatch, lock loss, duplicate leaf or unexpected existing object returns a
stable error code and leaves no accepted new state. Raw worker `os.replace` is
outside official topology and cannot be accepted by resolver.

No historical artifact is migrated. Legacy evidence, worker receipts and the
trial ledger are schema-rejected as authority/official inputs. The only allowed
rollback is to stop issuing new Bootstrap/E or new K; published claims/terminals/
states remain immutable. Diagnostic manifests record role, stage, hashed refs,
identity hashes and `replay_started=false` for validate-only paths; they never
expose raw handle bytes, input data, checkpoints or secrets.

## 7. Verification obligations for later test design

The next skill owns detailed cases and coverage, but it must prove that: observed
PASS bytes—not just a ref—bind Bootstrap; wrong actor/ACL cannot write any role;
every slot parent/root/lock replacement fails; OFD lock competition leaves no
V+terminal coexistence; every state/receipt transition and post-S0 recovery is
deterministic; raw direct worker PASS is never an official result; and all work
uses synthetic input with zero model fits/replay/budget/OOS side effects. Existing
M6 historical and ledger tests remain regression gates.

## 8. Ordered implementation slices

1. Implement identity models/resolvers and canonical schema parsers with no
   permissive fallback.
2. Implement quality policy, observed-byte Bootstrap/PASS publisher and reader.
3. Implement SlotSpec resolver, actor capabilities, F_OFD lock capability and
   archive-acceptor E/C issuance.
4. Implement locked Q/R/V/pre-S0 registry and then the complete lifecycle/
   acceptance/resolver modules.
5. Add server entrypoints as capability-only wrappers; preserve the raw worker.
6. Proceed through test design, red tests, implementation, green tests, independent
   code review and E2E acceptance. Bootstrap/QualityPass may only be published
   by the fixed quality issuer while finalizing that future gate; only a fresh
   M6.5 PASS can authorize E/C issuance or replay consideration.

结论：v19 不留下 writer、PASS reader、path base、lock ownership、post-S0 recovery 或
official admission 的隐含实现决策。它需要独立 R3 design-review PASS；在此之前不得
进入 test design、tests、implementation、code review、archival replay、M7、CCC/Gate
或 final OOS。
