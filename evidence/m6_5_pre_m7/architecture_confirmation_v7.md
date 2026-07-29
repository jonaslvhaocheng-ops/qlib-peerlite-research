# M6.5 架构确认 v7 — 单向授权、一次性 Fit 与可验证运行时

状态：`PASS — revised bounded architecture confirmation`  
替代：本文件替代 `architecture_confirmation_v5.md` 与 `architecture_confirmation_v6.md` 作为 M6.5 当前架构
依据；旧文件和全部否决审查保留为历史证据。  
范围：只修复 pre-M7 trust boundaries；不冻结 M7 contract、不训练、不重放、不访问最终 OOS。

## 1. 审查后的四条不可妥协原则

1. **权威研究执行只有一个 server control-plane runner。** Python library API、raw tensor network、DataFrame
   和手工 capability 可以用于非权威 mechanics test，但永远不能生成 budget/admission/model-result receipt。
2. **任何可能已进入 `model.fit` 的事件都不可重复。** 不确定性宁可浪费一个已计数的计划槽位，也绝不复用。
3. **真实 state 的正向放行由 exact PIT executor outputs 决定。** `VERIFY`、construction artifact 和自述 JSON
   永远不能被转换为 capability。
4. **来自 server 的 replay 证据由独立 signer 和 runtime bundle 证明。** verifier、launcher、receipt 任一方
   都不能单独证明自己。

这些原则防御普通调用、路径/版本替换、并发及崩溃；不声称治理 control-plane root、独立 signer 或内核
被攻破后仍可信。此类事件将该 scope 的所有 receipt 置为无效。

## 2. 网络与模型：将 Gate 从 legacy public API 移除

```text
M6 public package
  PeerLiteModel + PeerLiteNetwork (strict no-gate signature only)
      └─> no `market_gate`, no `market_dim`, no `market_state`, no MarketStateGate

M7 control-plane runner only
  private _M7GateNetwork + private _M7FitExecutor
      └─> receives sealed state only after admission
```

- `PeerLiteModel` and public `PeerLiteNetwork` are permanently M6/no-gate. Their constructors/forward signatures
  remove `market_gate`/`market_dim`/raw `market_state`; root and `models` exports contain no Gate-capable class.
  `MarketStateGate` and any gate-capable network move to a non-exported M7 implementation module.
- Any historical gated config/checkpoint/factory/CLI request rejects before Dataset read, journal write or fit. M6
  no-gate checkpoint/replay stays supported; M6 frozen-source archive supplies its old implementation for historical
  verification, so new source need not retain a gated compatibility shim.
- The M7 network/executor is not a supported research-public API. It has no `fit` command, entry-point or exported
  class that can create official output. Only a root-supervised M7 runner can instantiate it after receiving a sealed
  `FitAdmission` descriptor. Direct import/forward may at most be a test-only mechanics path and is rejected from all
  governance/artifact writers.

## 3. State issuance is a single forward pipeline

The following order eliminates the `FULL_TRAINING_INPUT` / join / capability cycle:

```text
sealed raw snapshot
  -> StateBuildBinding -> construction-only state artifact
  -> audit-only CandidateTrainingInputManifest
  -> freeze M7 derived QRC (binds candidate-manifest + authorization plan)
  -> PIT CERTIFY exact candidate values
  -> derived-feature behavior audit + audit-only join verification
  -> StateArtifactBinding
  -> sealed state descriptor inside one FitAdmission
  -> control-plane runner only
```

### 3.1 Audit-only candidate input

`CandidateTrainingInputManifest v1` is constructed from the construction state artifact plus the frozen supervised
development fold with a pure audit-only join. It contains the exact final consumed state and supervised keys/values,
schema, fold/segment/date/key/cell digests, raw/state/supervised inventories and expected counts. It is **not** a
Dataset, capability, model input object or runner API; its builder cannot import model/runner/ledger code and cannot
call fit. It is permissible for PIT auditors to read this manifest before a capability exists.

The future M7 QRC freezes its exact manifest SHA and a pre-authored `M7AuthorizationPlan` SHA. Only then can the
production PIT `CERTIFY` job run on `FULL_TRAINING_INPUT`; any failure leaves the candidate construction-only.

### 3.2 Closed production evidence parser

`StateArtifactBinding` does not accept semantic aliases such as “certificate”. Its loader parses/re-hashes exact
executor artifacts:

- `pit_audit_manifest_v1` and exact report, requiring `status=PASS`, `pit_qualification=QUALIFIED`,
  `evidence_ceiling=PASS`, `coverage_matrix.scope=FULL_TRAINING_INPUT`, production `quant_contract_v2`,
  `execution_boundary=PRODUCTION_CLI`, `test_only_adapter=false`, declared claim, all I001–L002 (17) checks PASS,
  exact candidate manifest/input lineage, and matched request-external review/semantic/interval anchors.
- `pit_behavior_manifest_v1` and report, with exact fixed-manifest parent audit ID/content hash, B001–B004 PASS,
  `NOVEL_CANDIDATE` preserved, protected key/value/count digests, and both baseline/probe raw snapshots, code/query,
  parameters, environment, outputs and perturbation ledger hashes.
- `StateJoinEvidence v1`, produced by the audit-only join verifier, binding candidate manifest, exact supervised
  product/fold/segment/key/date digest, state manifest, four-column schema/order, date-constant broadcast and every
  missing/duplicate/non-finite rejection result.

All three documents have explicit parent hashes; parser versions are closed and recompute both manifest/report hashes.
No synthetic/test adapter may cross into this production parser. Synthetic M6.5 fixtures use an explicit
`SYNTHETIC_NOT_EMPIRICAL` root and must be rejected by production loader.

## 4. Acyclic authority activation

The plan is frozen before the QRC; registry is generated after it. That removes QRC↔registry hash cycles:

```text
immutable M7AuthorizationPlan (no QRC reference)
        └─> future frozen M7 QRC binds plan SHA
                └─> governance installer validates QRC + plan
                        └─> Registry / Grant / Authority (bind QRC SHA + plan SHA)
                                └─> signed AuthorityActivationReceipt
                                        └─> root-supervised runner
```

`M7AuthorizationPlan v1` predefines run ID, allowed candidate/fit slots, models/folds/seeds/purposes, budget/spec
identity, namespace and logical journal/output policy; it cannot contain a registry SHA. It becomes immutable and is
referenced by the frozen QRC. After QRC freeze only governance control plane can create content-addressed
`RunAuthorityRegistry`, `RunAuthorityGrant`, `RunAuthority` and `AuthorityActivationReceipt`; all bind both QRC and
plan exact hashes.

The control plane owns a fixed root, signer key and root-supervised process. Research runner has no write access and
no user CLI for selecting a registry/authority/contract. A supervisor opens the one deterministic activation descriptor
for a predeclared run ID, validates its signature and identity, and passes sealed FDs/bytes to runner. The descriptor
binds control-root device/inode, registry/grant/authority/budget/spec hashes, activation nonce, signer key ID,
namespace and expected head. Runner holds all validated object FDs, copies canonical bytes into memory, and under
ledger lock rechecks the same activation identity. Thus a valid old snapshot, ancestor rename, post-verify replacement
or cross-file mixture cannot become active.

`openat`/`O_NOFOLLOW`/`fstat`/owner/mode/`nlink==1`, content-addressed filenames and atomic activation are mandatory.
They complement, rather than replace, the signed activation descriptor. M6.5 implements only synthetic policy/plan/
activation fixtures; it cannot activate a real M7 run.

## 5. FitAdmission is an at-most-once state machine

Ledger accounting and actual fit dispatch are separate but transactionally linked under stable locks that are never
renamed with the ledger file:

```text
PLANNED
  -> START_RETAINED              (journal + authoritative ledger; budget consumed)
  -> ADMISSION_ISSUED            (deterministically recoverable receipt)
  -> DISPATCHED                  (durable before calling model.fit)
  -> TERMINAL | ABANDONED_UNKNOWN
```

`RunLease` is granted under the authority/run lock then ledger exclusive lock and binds activation nonce, event-plan
entry, worker identity, journal inode/digest and exact before/after head. `FitAdmission` is a one-use, signed/opaque
descriptor under that lease. The runner writes and fsyncs `DISPATCHED` **before** invoking `model.fit`; only the holder
of this undispatched descriptor may cross the call boundary once.

If a process crashes after `DISPATCHED` for any reason—including immediately before fit—the event is terminally
`ABANDONED_UNKNOWN` on recovery and can never be retried. Ledger commit with a missing admission receipt is reconstructed
from deterministic ledger/event bytes but does not dispatch. Receipt failure after dispatch also cannot dispatch again.
Any desired retry needs a separate preplanned/counted contingency event, not reuse of source ID/nonce. Two workers,
lease expiry, duplicate runner invocation and journal/reconcile idempotency cannot produce a second dispatch.

The FitAdmission verifier records call-boundary attempt counts and is the only component allowed to write official
model artifacts. Synthetic crash-at-each-boundary and multiprocess tests must prove no event ID sees more than one
observed model-call attempt; uncertainty is intentionally counted as spent.

## 6. Replay has independent activation, signer and runtime closure

```text
immutable ReplayAcceptanceTrustRoot + ReplayRuntimeBundle
  -> signed M6ReplayLaunchGrant
  -> governance deployment + signed ReplayActivationReceipt
  -> FD-pinned staged launcher/verifier/archive
  -> independent acceptance-signing service
  -> signed M6ReplayAcceptanceReceipt
```

`ReplayAcceptanceTrustRoot v1` is pinned by M6.5 immutable acceptance policy and contains actual versioned Ed25519
public keys, key IDs, algorithm, validity/rotation rules and signer-role separation. `ReplayRuntimeBundle v1` is
content-addressed and root-owned: interpreter binary hash, stdlib/site-package/native-extension inventory, allowed
import-origin set, dynamic-loader environment policy and runtime bundle digest (or an equivalently signed OCI digest).

The launch grant is issued/signed by a control-plane issuer distinct in Unix permissions and key custody from launcher
and acceptance signer. It binds input binding, deployment nonce, runtime bundle, fixed output, profile and trust-root
key ID. Launcher uses same-FD hash-and-copy for verifier/archive **and** verifies runtime executable/bundle from
sealed descriptors before `fexecve`/equivalent immutable execution; it starts with `-I -S`, a fixed import path, and
cleared Python/loader injection variables. Post-run it emits an unsigned observation payload only.

An independent acceptance service reopens/validates deployment, grant, runtime, staged inputs, child receipt/output
inventory and ledger before/after itself; it will not sign caller-provided JSON. It signs a domain-separated canonical
payload containing schema/version/key ID, activation/deployment nonce, grant/binding/runtime/staged-input/output/ledger/
child identities and anti-replay sequence. `m6_archive` verifies signature from the pinned trust root, not from the
receipt, and verifies complete child linkage. A remote copied receipt without this signature is non-evidence.

`M6CloseArchiveProof` is likewise produced only by a pre-authorized verifier deployment and independently signed;
proof path/hash alone never establishes issuance authority.

## 7. Acceptance boundary

The next design must make all six areas implementable and testable: exported raw-tensor Gate removal; audit-only
candidate issuance and exact PIT parser; acyclic activation; single-use FitAdmission; signed replay trust root/runtime;
and signed close proof. Until its independent review passes, no test-design, product implementation, server replay,
real M7 contract or model fit is allowed.
