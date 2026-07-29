# M6.5 架构确认 v9 — 研究治理边界下的完整权威链

状态：`PASS — bounded research-governance architecture`

替代：本文件替代 `architecture_confirmation_v8.md`；适用威胁模型为
`research_governance_threat_model_v1.md`。旧架构/审查保留为历史证据。

本文件不授权真实 M7、CCC/Gate、server replay、final OOS 或生产交易。

## 1. M6 `6/44` 是不可省略的 authority genesis

```text
M6 immutable gate + M6CloseArchiveProof
  + byte-exact close snapshot (51 lines, 14,328 bytes, SHA 31a90…; 6 candidate / 44 fit)
    -> LedgerAuthorityGenesis
      -> new M7 authority ledger namespace
```

`M6CloseArchiveProof v1` 绑定 M6 gate/static evidence、historical verifier git blob、pre-run `4/29` prefix、
close snapshot SHA/bytes/counts、journal-start 与 retained-ID equality 及 terminal chain。installer 在治理 lock
下验证它们，并 atomically 创建唯一 policy-derived authority namespace。它拒绝 legacy server
`contracts/trial_ledger.jsonl` (`8d08…`, `4/29`)、错误 proof/path/schema/link/target，且永不改写 M6 history。

## 2. Data/PIT/behavior chain

```text
sealed raw snapshot -> construction state
-> audit-only CandidateTrainingInputManifest + StateBehaviorCoveragePlan
-> future frozen QRC/authorization plan
-> PIT CERTIFY + complete behavior bundle + join evidence
-> StateArtifactBinding -> immutable job input snapshot
-> authorized runner
```

State behavior coverage fixes all four sources、selection flags/outcomes、aggregates、candidate projection keys/values、
code/query/parameters/environment 及 required future/revision/universe probes。`PREFIX_REPLAY` 不可替代 future
probe。production loader parses exact fixed/behavior executor manifests/reports and all QRC/candidate/join links; it
rejects `VERIFY`、test adapters 与 synthetic roots。

Supervisor 将 exact certified state/candidate materialize 到新的 job-private snapshot，fsync/hash verify，并以
ownership/mode make it immutable to `research-runner`。runner 使用再核验的 read-only FDs。这是研究治理范围内的
normal TOCTOU defense，不声称防御恶意 holder of runner privileges。

## 3. Plan, one authorized fit and terminal result

`M7AuthorizationPlan` precedes QRC；QRC binds plan/candidate/coverage/policy；governance 后续 materializes immutable
registry/grant/authority and one activation receipt。accepted job binds event、budget、ledger head、state binding、
fixed/behavior/join/candidate hashes、input snapshot digest、fold/segment/date/schema and unique output roots。

对于正常 concurrent runners，stable run lock + event-specific `O_EXCL` dispatch claim only permits one planned
worker dispatch。crash after start/claim spends event；retry needs a separately planned contingency event。direct library
calls cannot create official output。

Runner writes only unique staging output。independent `result-publisher` (separate Unix identity) rehashes the staged
inventory and matching terminal job receipt，atomically publishes final immutable result object and appends controlled
`TERMINAL_PUBLISHED` receipt。`OfficialResultResolver` validates receipt/root/file hashes；checkpoint/score/staging/
final-without-terminal-record are never official。normal crash recovery quarantines incomplete output，不 promote/reuse。

## 4. Frozen M6 replay input and execution evidence

`M6ReplayInputBinding v2` is frozen before execution. It binds external transfer manifest、archive bytes/single root、
internal manifest/tree inventory、M6 spec/gate/historical proof、verifier source、approved `ReplayLauncherBundle`、
runtime bundle、profile `14 replay / 0 fit / OOS=false`、logical read-only ledger and output policy。

Governance supervisor launches the approved launcher from measured deployment using fixed interpreter/runtime、fixed argv
and clean `env -i` allowlist (rejecting loader/Python injection). It emits `ReplayExecutionReceipt` containing binding/
grant, launcher/verifier/runtime FD hashes, argv/environment digest, PID/start identity, nonce, child exit and read-only
ledger before/after. The receipt is generated outside verifier/launcher reporting and is locally verifiable from pinned
control-root policy. `m6_archive` accepts replay only when input binding、execution receipt and child receipt agree。

This is research reproducibility evidence under trusted governance supervisor, not hostile-host security attestation。

## 5. Test gates

M6.5 tests: 6/44 genesis and 4/29 rejection; legacy Gate denial; construction/PIT/coverage/join refusal; input snapshot
hash/ACL/FD mutation detection; normal concurrent/restart dispatch; staged/quarantined output rejection; terminal
publisher/resolver integrity; binding/runtime/env/launcher mismatch; archive safety and no-ledger-write replay。Changed core
code requires 100% line+branch coverage and public synthetic E2E. Only then can code/test review and a new read-only
server replay be considered。
