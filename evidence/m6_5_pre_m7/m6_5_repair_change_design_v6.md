# M6.5 R3 修复设计 v6 — 比例化研究治理的完整实施合同

状态：`IMPLEMENTATION_READY / 待独立设计审查`。质量变更：`m6-5-pre-m7-repair`；风险：`R3`。架构依据：`architecture_confirmation_v9.md` 与 `research_governance_threat_model_v1.md`。本文件替代 v5，完整保留 PIT、行为覆盖、6/44、结果发布和 replay 的必须要求，是唯一实现依据。禁止真实 M7 QRC freeze/fit、CCC/Gate、server replay、final OOS 与 M6 immutable/history 改写。

## 1. Scope and common rules

M6.5 仅在显式 `SYNTHETIC_NOT_EMPIRICAL` fixture root 下实现和测试 production parsers/state machines；production loaders/runners 一律拒绝该 root。受信边界仅为治理 supervisor/control root/ACL/frozen runner；防御错误配置、正常并发、崩溃、半写文件和路径/环境误选；不防御 runner 任意 native code execution 或 host/control-root compromise。所有 JSON strict canonical/closed-schema；controlled reads 用 relative path、`openat`、`O_NOFOLLOW`、type/owner/mode/`nlink==1` 和 content hash 校验。

## 2. Legacy Gate and public surface

Public `PeerLiteModel`、`PeerLiteNetwork` 是 M6-only：删除 `market_gate`、`market_dim`、raw `market_state` 参数；gated metadata/config/factory/CLI/model registry 在 Dataset/journal/fit 前拒绝。Gate mechanics 移至 non-exported module，synthetic mechanics 不能写 ledger/checkpoint/score/Recorder/result。package exports 无 Gate-capable type；archived frozen source 处理 M6 historical replay。测试证明 public path 从不请求 Qlib `col_set="market"`，不可能把 label-derived daily state 变成 official input。

## 3. Verified M6 6/44 genesis

`M6CloseArchiveProof v1` closed schema 绑定 M6 gate/static evidence、approved historical verifier git blob、pre-run `8d08…`/4 candidate/29 fit、close `31a90…`/14,328 bytes/51 lines/6 candidate/44 fit、journal-start=retained-ID set 和 terminal chain。old server v2 replay receipt 不能替代。`LedgerAuthorityGenesis v2` 绑定 proof+byte-exact close snapshot。installer 仅接受 genesis ID+supervisor root，锁内验证并 atomically 创建新的 policy-derived authority namespace；拒绝 legacy `contracts/trial_ledger.jsonl`、4/29 head、wrong proof/path/schema/link/target 和历史覆盖。Synthetic `RunAuthority` 冻结 genesis/ledger/head/parent/budget/spec/journal/output/full events。server reconcile 在 stable lock 内验证 head/semantic IDs/budget，再用 temp/fsync/replace 写 old bytes+canonical batch；changed duplicate、unknown tail、count swap、bad journal、overbudget 和失败零修改 ledger。

## 4. State, PIT and full behavior coverage

`StateBuildBinding v2` allowlists sealed raw files/columns/clocks/code/predicates，atomic publishes state audit/population/daily state/manifest/marker，status=`BUILT_NOT_EMPIRICALLY_CERTIFIED`，且 builder 不 import labels/execution/purge/M3/model/ledger。Audit-only `CandidateTrainingInputManifest v1` joins construction state with frozen supervised development product but never creates Dataset/model input；it fixes consumed cells/fold/segment/schema/key/date/value/count/source lineage。`StateBehaviorCoveragePlan v1` frozen with future QRC binds candidate/construction, builder/query/parameter/environment, complete `StateOutputProjectionManifest`（four sources、flags/outcomes/reason、membership、aggregates）and one coverage entry for every derived source/predicate/aggregate。Each applicable entry requires `FUTURE_POISON`、`REVISION_REPLAY`、`UNIVERSE_CANARY`; `PREFIX_REPLAY` only adds coverage；`NOT_APPLICABLE` needs QRC rationale+replacement probe。Each behavior receipt has exact fixed parent, B001–B004 PASS, plan-matching lineage/probe and equality—not overlap—of protected candidate projection keys/values。

Production binding order is candidate → frozen QRC/coverage/authorization plan → PIT `CERTIFY` → complete behavior bundle → audit-only join。Loader parses exact fixed manifest/report requiring PASS/QUALIFIED/evidence ceiling PASS/FULL_TRAINING_INPUT/`quant_contract_v2`/PRODUCTION_CLI/non-test adapter/all 17 checks/matched anchors；it parses behavior manifests/reports and join evidence。`VERIFY`、partial/fake behavior、test adapter and synthetic root fail。

## 5. Job snapshot, authorized fit and official results

After binding checks supervisor copies exact state/candidate payload to a fresh job-private snapshot, rehashes/fsyncs/atomically publishes it and uses ACL/ownership to make it read-only to runner。`FitAdmissionDescriptor` binds event/budget/head, state binding/fixed/behavior/join/candidate hashes, snapshot digests, fold/segment/date/schema and unique staging/final roots。Trusted frozen runner rebuilds input only from rechecked snapshot FDs；caller frames/tensors/paths cannot create official output。For normal concurrency stable lease+event-specific `O_EXCL` claim allows one planned worker; claim+`DISPATCHED` fsync before fit; crash spends event; retry requires planned contingency event。This is authorized-runner behavior under frozen threat model, not hostile raw syscall defense。

Runner writes only unique staging。Separate `result-publisher` is sole final/index writer：it opens/re-hashes staging regular files and matching terminal job receipt, atomically publishes final output and writes controlled `TERMINAL_PUBLISHED`。`OfficialResultResolver` accepts only that record plus final inventory/hash；direct/staging/final-without-terminal stays quarantined。Crashes retain forensic output and never auto-promote/reuse。

## 6. Frozen M6 replay input and execution receipt

`M6ReplayInputBinding v2` frozen before execution binds transfer manifest、archive/single root、internal manifest/tree、M6 revision/spec/gate/close proof、verifier source、`ReplayLauncherBundle` tree/entrypoint/argv、runtime bundle、profile `14 replay/0 fit/OOS=false`、legacy read-only ledger and output policy。Supervisor validates deployment and runs approved launcher with fixed interpreter/runtime/argv and clean `env -i` allowlist rejecting Python/dynamic-loader injection。It emits supervisor-owned `ReplayExecutionReceipt` outside verifier/launcher self-report with binding/grant、launcher/verifier/runtime FD hashes、argv/environment digest、PID/start、nonce、child exit、ledger before/after。Launcher safe-extracts/imports temp-tree modules and writes child receipt。`m6_archive` requires binding+execution receipt+child receipt agreement；archive/tree/verifier/launcher/runtime/environment/output reuse/ledger-write mutation fails。

## 7. Tests and order

Red tests cover 6/44 success/4/29 rejection, proof/path/link mutation, old Gate/config/checkpoint/raw tensor, construction/PIT/coverage/join omissions, normal snapshot hash/ACL/FD mutation, ledger race/crash, staging/final/terminal resolver rejection, replay binding/runtime/env/launcher/archive mutation。Implementation order：legacy denial; proof/genesis/reconcile; state artifacts/parsers/snapshot materializer; publisher/resolver; replay binding/launcher/execution receipt; all synthetic only。Public synthetic E2E covers genesis→authority→reconcile、candidate→coverage→loader、job→staging→terminal/quarantine、replay binding→clean launcher→14/0/OOS=false fake receipt。Changed core modules/public CLIs require frozen include-list 100% line and branch coverage with raw report/argv/source digest, full suite/lint/type, independent code/test reviews。Only then may read-only server v3 replay be proposed; M7/final OOS remain sealed。
