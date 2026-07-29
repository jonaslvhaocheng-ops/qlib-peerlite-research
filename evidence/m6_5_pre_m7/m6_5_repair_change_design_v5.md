# M6.5 R3 修复设计 v5 — 完整 state 覆盖、sealed fit 与 terminal-only 结果

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
质量变更：`m6-5-pre-m7-repair`；风险：`R3`。  
架构依据：`architecture_confirmation_v8.md`。  
替代：本文件替代 `m6_5_repair_change_design_v4.md` 作为唯一实现依据；M6  immutable history 与所有旧审查不变。  
禁止：真实 M7 QRC freeze/fit、CCC/Gate、server replay、final OOS、M6 gate/spec/historical ledger rewrite。

## 1. 共同规则、范围与 legacy Gate 拒绝

M6.5 只在显式 `SYNTHETIC_NOT_EMPIRICAL` fixture 根下实现/测试 production parsers and state machines；所有
production issuer/loader/runner 拒绝该根。JSON strict-canonical，control-root reads use `openat`/`O_NOFOLLOW`/
`fstat`/owner/mode/`nlink==1` and content-addressed paths; caller paths/unknown keys/noncanonical bytes/link or rename
substitution fail closed.

`PeerLiteModel`/public `PeerLiteNetwork` are M6 no-gate APIs: no `market_gate`, `market_dim` or raw `market_state`
constructor/forward parameter; `MarketStateGate`/gate network move to non-exported `_m7_gate_impl`. legacy config/factory/
CLI/model registry/gated checkpoint fail before Dataset read/journal/fit. Root/models exports expose no Gate-capable type.
M6 frozen source archive maintains historical replay; new source need not load gated checkpoint. M7 private mechanics may
run only under test-only synthetic root and are forbidden from all official writers.

## 2. Complete, QRC-frozen StateBehaviorCoveragePlan

### 2.1 Single-forward issuance order

```text
sealed raw snapshot -> construction-only state artifact
-> audit-only CandidateTrainingInputManifest
-> StateBehaviorCoveragePlan
-> frozen M7 QRC binds candidate + coverage plan + authorization plan/policy
-> production PIT CERTIFY exact candidate
-> complete behavior bundle + audit-only join evidence
-> StateArtifactBinding -> sealed FitAdmissionDescriptor -> authoritative runner
```

Construction artifact has `BUILT_NOT_EMPIRICALLY_CERTIFIED`; its builder cannot import labels/execution/purge/M3/model/
runner/ledger. Audit-only candidate builder emits exact joined consumed values plus state/supervised/fold/segment/schema/
key/date/cell/value inventories; it is not a Dataset/capability and cannot invoke model code.

### 2.2 Closed coverage-plan schema

`StateBehaviorCoveragePlan v1` is authored after the candidate manifest and frozen in the QRC. It binds:

- candidate manifest SHA, construction state manifest/audit SHA, full builder/causal-feature/predicate/aggregation
  code-or-query/parameter/environment digests;
- an immutable `StateOutputProjectionManifest v1`: every candidate-relevant state output key and value axis
  (`four sources`, seven flags/outcome/reason, selected population membership and four daily aggregates), exact sorted
  protected key-set/count/value digest, date upper bound and canonical behavior-output mapping;
- one unique coverage entry for each derived source, each selection predicate and each aggregate. An entry fixes the
  target code path/digest, candidate projection subset, required probe IDs/types and any explicitly QRC-approved
  non-applicability rationale.

The required default suite is `FUTURE_POISON`, `REVISION_REPLAY` and `UNIVERSE_CANARY` for every applicable entry.
`PREFIX_REPLAY` may be additional but cannot satisfy a required future counterfactual. If source semantics make one type
impossible, QRC must list it as `NOT_APPLICABLE` with raw-field rationale and replacement probe; loader never infers an
exception. No plan with empty/partial projection or absent derived path is valid.

Each probe has its own `pit_behavior_manifest_v1`/report because the behavior executor permits one probe per request.
For each required plan entry, loader verifies all of:

1. exact production fixed `pit_audit_manifest_v1` parent/audit ID/content SHA, `PASS`, `QUALIFIED`,
   `evidence_ceiling=PASS`, `FULL_TRAINING_INPUT`, `quant_contract_v2`, `PRODUCTION_CLI`, non-test adapter and all 17
   fixed checks PASS;
2. behavior B001–B004 PASS, `NOVEL_CANDIDATE` retained, probe type/mutation boundary matching the plan, builder/query/
   parameters/environment hashes matching plan, and complete baseline/probe snapshot/output/ledger lineage;
3. behavior protected keys/count/digest and output feature projection equal—not merely overlap—the plan projection for
   that entry; baseline/probe protected values remain identical; no future mutation falls outside declared source scope;
4. each candidate state output has the complete required probe set, with no duplicate entry, omitted entry, unrelated
   raw mutation, substituted `PREFIX_REPLAY`, altered code digest or smaller protected set.

`StateJoinEvidence v1` remains audit-only and binds candidate/supervised product/fold/segment/key/date digest, state
manifest, schema/order, date-constant broadcast and zero unresolved missing/duplicate/nonfinite rows. `StateArtifactBinding
v4` references exact fixed manifest/report, coverage plan, all behavior manifests/reports, join evidence and every
inventory. Production loader rehashes and parses each; `VERIFY`, synthetic evidence, fake JSON or partial behavior
bundle cannot produce a descriptor.

## 3. Acyclic authority chain and sealed state-to-fit admission

`M7AuthorizationPlan v1` (no QRC reference) fixes run IDs, candidate/fit slots, models/folds/seeds/purposes, budget/spec,
namespace/journal/output policy. Future QRC binds plan, candidate manifest, coverage plan and `M7ControlPlanePolicy v1`.
Post-freeze governance installs content-addressed Registry/Grant/Authority, all binding QRC + plan, then emits a signed
`AuthorityActivationReceipt` at deterministic `(qrc, plan, run_id)`. Supervisor, not caller CLI, verifies policy public
key and passes sealed activation FDs/bytes to runner; no mutable selector/current.json exists.

`FitAdmissionDescriptor v2` is signed/opaque, one-use and must include:

```text
QRC/plan/policy/activation nonce/event payload/worker nonce/ledger heads
StateArtifactBinding + fixed/coverage/behavior/join/candidate hashes
state artifact and exact consumed cell/key/date/value digests
four-column schema/order; fold/segment/date coverage
sealed state + candidate FD device/inode/content SHA identities
unique staging_root/final_root and output policy hash
```

Supervisor opens the exact certified state/candidate files from activation-selected control root, validates all evidence,
and passes read-only sealed FDs listed in descriptor. `ModelFitExecutionGuard` accepts *only* descriptor + inherited sealed
FDs; it independently re-fstats/re-hashes them, reconstructs the input itself and rechecks fold/date/schema before the
call. It never receives caller DataFrame/tensor/state descriptor/fold. Official checkpoint/prediction/result/terminal
receipts repeat exactly the descriptor identity set. Valid admission plus wrong valid state/fold, FD swap, raw tensor,
synthetic descriptor or direct private import fail before model call and cannot produce an official artifact.

## 4. Fork-safe atomic dispatch claim

State transitions are `PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> DISPATCHED -> TERMINAL_PUBLISHED`, with
`ABANDONED_UNKNOWN` or `ABANDONED_OUTPUT_READY` terminal failure states. Ledger START is retained under stable locks;
missing admission receipt can be deterministically recreated from that retained event but cannot dispatch by itself.

Before fit, guard creates `<state_root>/<activation_nonce>/<event_id>.dispatch-claim` using `O_CREAT|O_EXCL|O_NOFOLLOW`.
The winner writes/fsyncs canonical claim fields (admission SHA, PID, process-start/boot identity, claim generation,
sealed FD identities), fsyncs parent, reopens/fstats/hashes the claim, then fsyncs durable `DISPATCHED` and alone may call
fit. A preexisting, malformed, stale or different claim means `ABANDONED_UNKNOWN`; it is never removed/retried.

Supervisor prohibits fork after admission; all worker processes are clean `spawn` before it. `os.register_at_fork` child
handler closes/invalidates lease/admission/state/ledger FDs. The O_EXCL claim—not inherited flock or in-memory receipt—
is the final single-winner primitive, so parent/child/restarted worker cannot both cross the call boundary. Any crash after
claim or dispatch spends the event. A retry requires a distinct frozen contingency event/source ID/output roots.

## 5. Crash-safe output transaction and terminal-only discovery

Plan/admission derives unique non-reusable same-parent `staging_root` and `final_root` for every event. Only
`M7ResultSink` inside `ModelFitExecutionGuard` can write model artifacts, and it can write only staging. The guard:

1. after successful fit, validates a complete expected artifact inventory/hashes and writes/fsyncs `PreparedResultReceipt`
   binding descriptor/state/event/claim/inventory;
2. atomically renames staging to final root and fsyncs its parent;
3. only then atomically appends/fsyncs a stable official-result index `TERMINAL_PUBLISHED` record containing final root,
   terminal-result hash, inventory, descriptor identity and event/claim.

`OfficialResultResolver`, recorder reader, score loader, selection and reporting code must resolve results solely via
the published index plus matching terminal receipt/inventory; direct paths, staging paths and final roots without a
published index are rejected. Crash before index publication leaves output forensic-only; recovery adds
`ABANDONED_OUTPUT_READY` quarantine and cannot promote/reuse it. Crash after index fsync requires exact final inventory;
mismatch fails closed. Contingency events have different roots. No automatic deletion/cleanup of potentially useful
forensic material is permitted.

## 6. Measured replay launcher chain

`ReplayLauncherBundle v1` fixes canonical tree digest, entrypoint path/bytes, bootstrap-runtime identity, argv grammar
and source inventory. Its exact digest/entrypoint/argv policy must appear in `M6ReplayLaunchGrant`,
`ReplayActivationReceipt`, deployment inventory, launcher unsigned observation, child process record and final signed
acceptance payload. Supervisor runs launcher only from activation-selected sealed bundle FD.

`ReplayAcceptanceTrustRoot` supplies actual Ed25519 keyring/role/rotation policy; runtime bundle fixes interpreter,
stdlib/site-package/native inventory/import origins. Grant issuer, launcher and acceptance signer use separate Unix
identities/key custody. Acceptance service reopens deployment and verifies measured launcher process identity/exit/argv,
activation/grant nonce, runtime, staged verifier/archive/tree, child/output/ledger before it signs domain-separated
payload. `m6_archive` verifies against pinned key bytes, not receipt-supplied data. Wrong/replaced launcher, argv swap,
signature with launcher mismatch or unsigned copied JSON cannot pass. M6 close proof uses the same preauthorized
deployment/signer rule.

## 7. Red-test and implementation order

1. Write red tests for public Gate surface, every behavior coverage omission/subset/probe substitution, fake fixed/join,
   state-to-fit swaps, fork/cas claim races, crash points, output discoverability and launcher identity substitutions.
2. Implement schemas/parsers/legacy deny and synthetic builders, then authority/admission/claim/output transaction,
   then replay control plane. Test mechanics only; no real data/QRC/M7 fit.
3. Public synthetic E2E: candidate→coverage completeness rejection; plan→activation→sealed state→single dispatch→terminal
   publication; crash/quarantine resolver behavior; grant→measured launcher→signed acceptance.
4. All changed core modules/public CLIs require frozen include-list 100% line **and** branch coverage with raw report;
   then full suite/lint/type and independent code/test reviews.
5. Only after those pass can a separate read-only server v3 replay be proposed; M7/final OOS remain sealed.

M6.5 never creates real M7 authority. A later phase must perform genuine QRC freeze, PIT CERTIFY, behavior/join, control
plane installation and a separate gate before any production-style fit.
