# M6.5 R3 修复设计 v4 — 权威 runner、单向 PIT issuance 与一次性执行

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
质量变更：`m6-5-pre-m7-repair`；风险：`R3`。  
架构依据：`architecture_confirmation_v7.md`。  
替代：本文件替代 `m6_5_repair_change_design_v3.md` 作为唯一实现依据；历史版本和所有审查报告保持不改。  
禁止：真实 M7 QRC freeze、真实 M7 fit、CCC/Gate、server replay、最终 OOS、M6 immutable gate/spec/ledger 历史修改。

## 1. 交付范围和硬边界

本修复交付**合成 fixture 下**的 schemas、parsers、state machines、拒绝路径与 public CLI E2E。它不能创建
真实 M7 authorization plan/QRC/grant、不能产生 PIT `CERTIFY`，不能签发真实 server receipt。生产对象的解析
和拒绝逻辑可以实现、可以用明确 `SYNTHETIC_NOT_EMPIRICAL` 根测试，但生产 runner 一律拒绝该根。

不可改对象：

```text
contracts/immutable/m6_trial_budget_start.json
contracts/immutable/m6_peerlite_execution_spec_v1.json
evidence/gates/M6_peerlite_gate.json
历史 M5/M6 ledger 行、M6 score/checkpoint、2025+ 分区
```

所有 schema 均严格 closed；canonical JSON 为 UTF-8/sorted keys/finite values/no duplicate keys，`content_sha256`
不包括自身。生产路径只接受 governance-owned control roots 中 `openat` + `O_NOFOLLOW` 逐段读取的 regular files，
且检查 root/parents/file `st_dev/st_ino`、owner/mode、`nlink==1`。任何 caller path、unknown key、noncanonical
bytes、link/rename/substitution、test-only root 或 hash mismatch 均 fail-closed。

## 2. P0/P2：彻底迁移 legacy raw-Gate surface

### 2.1 明确 API 破坏与兼容

`src/qlib_peerlite/models/peerlite.py` 内的 public `PeerLiteModel` 与 `PeerLiteNetwork` 被定义为 M6-only。
实现将：

1. 从 `PeerLiteNetwork.__init__` 删除 `market_gate`、`market_dim`，从 `forward` 删除 `market_state`；其结构只保留
   M6 no-gate 路径。`MarketStateGate`/gate-capable network 移入未导出的
   `src/qlib_peerlite/models/_m7_gate_impl.py`。
2. `PeerLiteModel.__init__` 遇到任何 non-false `market_gate` 立即抛 `LegacyMarketGateForbidden`；
   `_market_frame` 不能再请求 `col_set="market"`。`fit/predict`/checkpoint load 同样拒绝 gated metadata。
3. 删除根包和 `models.__init__` 对任何 Gate-capable type 的 export；公共 `PeerLiteNetwork` 的 no-gate signature
   只为 M6 mechanics compatibility 保留。`config.py`、generic CLI、factory 与 `model_registry.yaml` 拒绝
   `market_gate:true`，并在读取 Dataset/journal 前失败。
4. M6 archived replay 不受影响：它使用独立冻结历史 source tree。新工作树不承诺加载历史 gated checkpoint；
   M6 no-gate checkpoint 继续可 load/replay。

### 2.2 Authority-only M7 execution

Gate-capable `_M7GateNetwork`/`_M7FitExecutor` 不属于 research-public API：不在 package exports、不提供 CLI
entry point、不写 official artifacts。只有 root-supervised `m7_authoritative_runner` 取得 sealed
`AuthorityActivationDescriptor` 与 one-use `FitAdmissionDescriptor` 后才能构造它。

直接 import/raw tensor/`M7BoundFold`/capability 的 mechanics-only test path 必须显式带
`test_only=True`，强制在 `tests/fixtures/synthetic` root 内运行，且 artifact writer 拒绝其所有输出。它不能写
ledger、model checkpoint、prediction parquet、recorder 或 promotion receipt。故 Python 私有对象不被当作
安全边界；**official artifact issuance** 才是边界。

### 2.3 最低红测试

- `PeerLiteNetwork(...market_gate/market_dim...)`、`forward(...market_state...)`、top-level/models imports、
  direct factory/reflection、old gated checkpoint/config/CLI 都在任何 Dataset prepare/fit/journal 前失败。
- 将 `label_open/label_close` 聚成日内常量 market、伪造 Qlib Dataset、PanelDataset/market_state frame、raw tensor
  均不得生成 official M7 artifact；spy 证明 legacy public route 从不请求 `col_set="market"`。
- M6 no-gate checkpoint、existing M6 frozen archival replay/mechanics tests不退化。

## 3. P1：state 的无循环、可执行 PIT issuance 协议

### 3.1 Construction-only phase

`StateBuildBinding v2` 和 builder 只从 sealed raw snapshot allowlist 生成 `state_input_audit`、population、
daily state、manifest/marker，status 固定为 `BUILT_NOT_EMPIRICALLY_CERTIFIED`。它不得 import labels/execution/
purge/M3 readers/model/runner/ledger。所有 output 同父 temp + fsync + atomic rename；已有非一致 output 不覆盖。

新 `CandidateTrainingInputManifest v1` 由独立的 **audit-only** join builder 生成：

```text
construction state artifact + frozen supervised development product
  -> audit-only exact candidate training input values
  -> CandidateTrainingInputManifest
```

它必须绑定 construction state manifest/audit inventory、supervised product/fold/segment manifest、exact joined
`(datetime,instrument,feature)`/state cell/key/date/value digests、schema/dictionary/time semantics、expected counts、
raw snapshot/availability lineage与所有 join rejection counts。它既不是 `DatasetH`、不是 model input object，也不能
导入/调用 model runner；PIT auditor 可以读取它，但它无法 mint capability。

### 3.2 Future production phase (defined now, not executed now)

未来先冻结 `M7AuthorizationPlan v1`，它没有 QRC reference，只包含 run IDs、candidate/fit slots、model/fold/
seed/purpose、budget/spec identities、namespace 和 journal/output policy。M7 derived QRC 再以 exact
`CandidateTrainingInputManifest` SHA 与 plan SHA 冻结。顺序固定：

```text
CandidateTrainingInputManifest
-> frozen M7 QRC (bind candidate + authorization plan)
-> PIT CERTIFY over exact candidate values
-> behavior audit against exact fixed parent
-> audit-only join verifier
-> StateArtifactBinding
-> authoritative FitAdmission only
```

`StateArtifactBinding v3` contains closed references, not user-written status fields:

1. `PITFixedCertificateRef v1` references exact `pit_audit_manifest_v1` + report bytes/hashes. Loader parses both and
   requires: `status=PASS`; `pit_qualification=QUALIFIED`; `evidence_ceiling=PASS`;
   `coverage_matrix.scope=FULL_TRAINING_INPUT`; `contract_binding.adapter=quant_contract_v2`;
   `execution_boundary=PRODUCTION_CLI`; `test_only_adapter=false`; declared claim; all I001,I002,S001,T001,T002,T003,
   U001,U002,C001,M001,A001,H001,Q001,Q002,Q003,L001,L002 PASS; exact frozen QRC/candidate input lineage; and all
   matched request-external review-authority, semantic-review, and applicable interval-authority runtime anchors.
2. `StateBehaviorEvidenceRef v1` references exact `pit_behavior_manifest_v1` + report. Loader requires parent fixed
   `audit_id/content_sha256`, B001–B004 PASS, `NOVEL_CANDIDATE` designation (never promoted), protected through/key
   count/key hash/value-output consistency, and baseline/probe raw snapshots, code/query, parameters, environment,
   paired outputs and perturbation-ledger hashes.
3. `StateJoinEvidence v1` is an audit-only verifier output that binds the exact candidate manifest and supervised
   product/fold/segment/key/date digest, state manifest/schema/order/date-constant broadcast, and zero unresolved
   missing/duplicate/nonfinite results.

Production loader recomputes every artifact/report hash and cross-parent identity before creating a **sealed descriptor
only for a current FitAdmission**. `VERIFY`, sample-only, test adapter, fake JSON, incomplete manifest/report, changing
trust anchors or mismatch in any parent cannot pass. M6.5 synthetic tests prove the parser rejects them; no real data is
certified or loaded.

## 4. P1：acyclic registry bootstrap and activation

### 4.1 Objects and issuance order

```text
immutable M7AuthorizationPlan (no QRC hash)
  -> future frozen M7 QRC binds plan SHA and control-plane policy SHA
  -> governance installer validates QRC + plan
  -> content-addressed RunAuthorityRegistry + RunAuthorityGrant + RunAuthority
  -> signed AuthorityActivationReceipt
  -> supervisor passes sealed descriptor bytes/FDs to runner
```

`M7ControlPlanePolicy v1` is referenced by QRC and fixes governance root identity, installer role, signer public key/key
ID/algorithm/validity, root ownership/mode policy and deterministic path grammar. It is not chosen by runner.

Registry only maps approved grant IDs. Each `RunAuthorityGrant v1` fixes the authority's bytes/SHA, ledger/genesis,
parent head/receipt, execution spec/budget identity/max counts, journal/output paths and complete event-plan SHA. The
authority repeats the ordered event payloads. Every registry/grant/authority binds QRC SHA + plan SHA, but QRC binds
only plan/policy—not a registry SHA—so no hash cycle exists.

Governance installer atomically writes content-addressed registry/grant/authority and a signed
`AuthorityActivationReceipt` at a deterministic `(QRC hash, plan hash, run ID)` location. Receipt binds registry/grant/
authority/budget/spec hashes, control-root `st_dev/st_ino`, activation nonce, signer key ID, expected ledger head and
deployment/installer identity. It is the sole selector; there is no mutable `current.json`, caller `authority_id`,
registry path, contract path or fallback selection.

### 4.2 Execution rule

Production runner has no user-facing selection CLI. The governance supervisor validates receipt signature using the
policy's **actual pinned public key**, opens every object by FD under the fixed root, copies canonical bytes to memory,
and passes sealed descriptor + read-only FDs to runner. At ledger lock the runner rechecks descriptor/FD inodes/hashes
and current raw head. Old-valid snapshot rollback, parent directory rename, cross-file substitution, test-root upgrade
or activation nonce reuse fails before journal/model activity. M6.5 supplies only synthetic policy/key/installer fixtures
under a clearly test-only root.

## 5. P1：FitAdmission makes a planned fit at-most-once

`RunLease` and `FitAdmission` use fixed lock filenames (never the replaceable ledger pathname) and a durable per-run
execution-state log. Event transitions are:

```text
PLANNED -> START_RETAINED -> ADMISSION_ISSUED -> DISPATCHED -> TERMINAL
                                                  \-> ABANDONED_UNKNOWN
```

1. Supervisor holds authority/run lease. It fsyncs planned `START`; under ledger exclusive lock validates activation,
   plan, semantic uniqueness and budget; then atomically appends canonical retained start. This consumes budget.
2. From the exact retained record it deterministically reconstructs/atomically writes `FitAdmissionReceipt` bound to
   activation nonce, event ID/payload, worker nonce, journal inode/digest and ledger before/after heads. A crash here may
   recreate the same admission receipt, but cannot call fit yet.
3. Under persistent run-state lock the runner writes/fsyncs `DISPATCHED` before crossing the `model.fit` call boundary.
   `ModelFitExecutionGuard` accepts only an undispatched matching receipt and invokes fit exactly once.
4. Any recovery finding `DISPATCHED` without terminal result writes/derives `ABANDONED_UNKNOWN`; it can never invoke
   that event again. A desired retry consumes a separately preplanned and counted contingency event. Receipt write failure
   after ledger or dispatch is recoverable only as the same record, never as another dispatch.

The official model artifact writer and model-call instrumentation live inside `ModelFitExecutionGuard`; all direct model
library paths are non-authoritative. Tests use multiprocessing and injected crashes before/after every fsync/replace/
dispatch/call/terminal boundary, asserting each event sees no more than one observed fit call and every uncertain call
remains spent.

## 6. P1：replay signer and runtime are independently verifiable

### 6.1 Trust objects

- `ReplayAcceptanceTrustRoot v1`: M6.5 immutable acceptance policy reference; actual Ed25519 public-key/keyring bytes,
  key IDs, algorithm, validity/rotation rules, role separation and canonical hash.
- `ReplayRuntimeBundle v1`: governance-owned content-addressed interpreter binary, stdlib/site-package/native-extension
  inventory, allowed import origins, dynamic-loader policy and runtime digest (or an equivalently signed OCI digest).
- `M6ReplayLaunchGrant v1`: signed by a grant issuer distinct in Unix identity/key custody from launcher and acceptance
  signer; binds replay input binding, deployment/activation nonce, runtime bundle, fixed new output, profile, trust-root
  key ID and source identities.
- `ReplayActivationReceipt`: signed deployment selection; binds grant/deployment/control root/runtime/staged-input policy.

### 6.2 Execution and acceptance

Installer validates grant signature/key role, root metadata and all inputs before atomic content-addressed deployment.
Launcher opens verifier/archive/runtime from sealed FDs; it same-FD hash-and-copies verifier/archive to private staging,
verifies runtime executable and import inventory, starts immutable runtime via `fexecve`/equivalent, `-I -S`, fixed
`sys.path`, fixed cwd and environment allowlist clearing `PYTHON*`, `LD_*`, `DYLD_*` injection. It holds legacy ledger
shared lock through child and records an unsigned observation only.

An independently permissioned acceptance service reopens deployment/grant/runtime/staged inputs, child receipt/output
inventory/profile/ledger before/after; it will not sign arbitrary launcher JSON. It signs a domain-separated canonical
payload with schema/version/key ID, grant/binding/activation/deployment nonce, runtime/staged verifier/archive/tree,
child/output/ledger identities and anti-replay sequence. `m6_archive` loads the actual public key from pinned trust root,
verifies signature/payload/key validity and all child links. Copying unsigned JSON off server is non-evidence.

`M6CloseArchiveProof` follows the same pre-authorized deployment + independent signer pattern. A historical verifier
hash within a self-reported proof never authorizes issuance.

## 7. Required verification matrix and sequence

1. Write red tests for legacy raw Gate imports/signatures/forward, construction-vs-production state parser, fake PIT/
   behavior/join evidence, candidate issuance order, cyclic/alternate activation, mixed-FD/rename/path attacks,
   multiprocess FitAdmission/crash/duplicate-call, wrong key/payload/runtime/signature/import-origin and close-proof
   signer attacks.
2. Implement the above interfaces against synthetic fixtures; public CLI E2E covers candidate→synthetic audit rejection,
   plan→activation→lease→one dispatch, and grant→deployment→acceptance signature.
3. Set frozen `coverage.py` include to every changed core module/public CLI; require 100% line **and** branch and retain
   raw coverage JSON/report/argv/source digest without omit/exclude relaxation.
4. Full suite/lint/type checks, independent code review and independent test/coverage review must pass.
5. Only then may a separate server-read-only v3 replay be proposed. It still cannot train M7 or access final OOS.

M6.5 does not grant any real M7 authority. After M6.5 gate PASS, a separate phase must freeze real QRC/plan, run actual
PIT `CERTIFY` plus behavior/join audits, install real control plane, and obtain a new phase gate before any fit.
