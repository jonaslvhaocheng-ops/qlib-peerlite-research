# M6.5 v22 / v19 独立对抗式 R3 设计审查

## Findings

### [P1] pre-E release policy 与“已完成 M6.5 gate”的证据集合仍是调用方可提供的抽象对象，QualityPass 不能机械证明它由冻结质量闭包授权

**Section：** `architecture_confirmation_v22.md` §1 第 12–62 行；`m6_5_repair_change_design_v19.md` §3.2 第 85–114 行、§3.3 第 116–151 行；现有 `evidence/gates/M6_5_pre_m7_quality_gate.json` 与 `contracts/changes/m6_5_pre_m7_quality_gate_v1.json`。

**Scenario：** v22 宣称唯一 pre-E trust root 是“fixed in the reviewed M6.5 release closure”的 `M6QualityGateReleasePolicy v1`，但没有给该 policy 一个固定 immutable ArtifactRef、canonical hash、已验证 slot/issuer，或从 sealed anchor 取得它的 `VerifiedReleasePolicy` capability。v19 的两个 public routes 却直接接收可构造的 `M6QualityGateReleasePolicyV1`：

```python
QualityGatePublisher.publish_bootstrap(policy, actor, raw)
observe_verified_quality_inputs(sealed_anchor_fd, policy, provider, actor)
```

`TypedArtifactRef` 的 `release_policy_ref` 只能证明 PASS 声称了哪份 policy；没有 API 要求将该 ref 对应到 observed frozen policy bytes。更重要的是，v22 只写“validates all M6.5 engineering evidence”，而 v19 的 PASS parser 只说“all required M6.5 evidence/closure fields”，没有 closed role map、hash/ref equality、或与正式 M6.5 gate/ledger route 的具体绑定。当前 gate 仍是 `NEEDS_CHANGES`，且其 change request 明确要求 fresh independent review、test/code evidence receipts 后才可 PASS；新的 `M6EngineeringQualityGatePassV1` 没有规定如何逐项承接这些 future evidence。

因此一个普通 release wiring 错误可以将另一个格式正确的 policy mapping 传给 quality publisher/reader，并发行一个有正确 Bootstrap ref、正确 status 和结构字段的 PASS，但它未必来自本次冻结 release closure，也未必证明完整的 M6.5 design/test/code/E2E gate 已通过。后续 `VerifiedQualityInputs` 会把它当成 E/C 的唯一授权输入。

**Impact：** 这不是 hostile-host 模型。它是正常 release manifest/path/configuration 选择错误，恰好发生在 E 之前唯一的授权边界。Context、slot、writer 和 lock 即便全部正确，也无法阻止一个未由规定质量路线证明的 QualityPass 开启 authority；因此为 P1。

**Evidence：**

- v22 §1 将 policy 描述为“reviewed release closure 的一部分”，但字段列表没有 policy 的 immutable observed identity、publisher、slot或 closure evidence inventory。
- v19 §3.3 的 public APIs以 raw parsed `policy` 参数工作；`VerifiedQualityInputs` 保存该对象却没有 `ObservedReleasePolicy`/policy-bytes/ref/parent-chain 成员。
- v19 §3.2 将 PASS 的必填 evidence 简写为“all required”，而没有将 M6.5 change request 的独立设计审查、test design/red-green/code review/E2E、gate-route result等列为 closed typed refs；现有 gate file也尚未是该 schema的 PASS。

**Direction：** 在 release policy 之上增加一个不可由调用方 mapping 替代的 observed trust object：从 sealed anchor 的固定 policy slot/compiled release manifest 读取 canonical bytes，验证其 fixed ref/hash/issuer/root chain，然后只传递 `VerifiedReleasePolicy` capability。将 `M6EngineeringQualityGatePassV1` 的 evidence inventory 写为 exact closed role map（至少包含本次 M6.5 route 的 required architecture/design/test/code/E2E/final gate evidence及其版本/bytes refs），让 quality issuer 在 PASS publish 前逐项观察、hash/role/schema 校验并记录它们。任何 policy-ref/bytes/slot、gate-id、evidence role或 quality-route revision drift 都应在 Bootstrap/PASS publication 前拒绝。

### [P1] `ChildReceipt` 的唯一 writer、held-lock 规则与“child 无 control-root writer capability”相互冲突，现有 raw worker 也不能产生该 canonical receipt

**Section：** `architecture_confirmation_v22.md` §2 第 71–94 行、§4 第 141–176 行、§5 第 178–217 行；`m6_5_repair_change_design_v19.md` §4 第 153–207 行、§5 第 211–243 行；`scripts/server/verify_m6_peerlite_archival_replay.py` 第 195–380 行。

**Scenario：** v22 的 exhaustive matrix 规定 `child_verifier` 是 `ChildReceipt` 的 sole writer；同一份 architecture 又规定**每个** mutable operation 需要 `LockedVerifiedControlTopology`，而 handoff 明说 child 不接收 control-root writer capability。v19 没有 `ChildReceiptIssuer`、受限 child slot capability、IPC authorisation protocol 或 child-side lock/publish API；`M6ReplayLifecycle.record_child(locked, child_receipt)` 只接收一个已经存在的 receipt。

实际保留的 worker也不能补足这个缺口：它接受多条 caller paths，使用 `output_dir.mkdir` 和 `os.replace` 仅写 `archival_replay_receipt.json`，其 schema 是 `qlib_peerlite_m6_archival_checkpoint_replay_v1`。v22/v19 明确要求该 raw receipt 只是 ChildReceipt 的 input，且不得当作 ChildReceipt/official evidence。于是实现只有三条未授权选择：让 child 取得 topology/lock 并写 canonical receipt（违背“无 control-root writer capability”）；让 replay supervisor 将 raw receipt 包装成 ChildReceipt（违背 child-only physical writer matrix）；或把 raw receipt 当 ChildReceipt（被 schema rules 明确禁止）。

**Impact：** 这会让 S3→ChildReceipt→S4 没有可实现、可验证的正常路径，或迫使实现时偷偷改变 writer model。若采用 supervisor wrapper，wrong-actor test会失效；若给 child 任意 root/lock capability，则 child 能写超出唯一 receipt slot 的控制状态。该错误在正常子进程/IPC/权限配置下即可出现，故为 P1。

**Evidence：**

- v22 §2 的 matrix 将 ChildReceipt 独占给 child，§4 又将 held topology 设为所有 mutation 的不可绕过前提，§5 第 198–199 行禁止 child 获得 control-root writer capability。
- v19 §5.1 的 launcher只“captures raw receipt”，并未定义 child receipt publication；`record_child` 的输入是现成对象，缺乏其 provenance/writer construction route。
- 保留 worker的 `run()` 在第 195–380 行只生成 raw receipt，并在第 386–416 行要求 path CLI inputs；它没有 Context、slot、actor、lock或 ChildReceipt schema。

**Direction：** 选择并冻结唯一 receipt handoff model，不能靠 implementation judgment：例如 child 仅通过 kernel-authenticated one-shot IPC 把 canonical child-author statement传给 supervisor，schema中区分 `author=child_verifier` 与 `publisher=replay_supervisor`；或为 child 提供仅能发布一个 pre-authorized ChildReceipt slot 的 narrow capability，并明确其不等同于 control-root/lock capability。无论选择哪种，需定义 writer matrix中的 author vs physical publisher、slot lifecycle、lock interaction、raw receipt binding、crash outcome和 peer credential validation。加入 wrong child UID、supervisor forged child receipt、raw receipt substitution、child attempting other slot及 IPC crash的拒绝 tests。

### [P1] `ArchiveAcceptanceReceipt → S6 → FinalIndex` 的两个 durable crash windows 没有恢复状态机，已接受结果可能既不能 promote 也不能 quarantine

**Section：** `architecture_confirmation_v22.md` §5 第 184–206 行、§6 第 229–244 行；`m6_5_repair_change_design_v19.md` §5 第 213–243 行、§6 第 263–276 行。

**Scenario：** `accept_archive(S5)` 依次 durable-publishes `ArchiveAcceptanceReceipt → S6 → FinalIndex`。但是 `recover_post_s0()` 只定义“完整 S5 且 no later artifact 可交给 archive_acceptor”与“ambiguous S0…S4 写 POST_S0_TERMINAL”。它没有定义下列普通 crash residues：

```text
valid ArchiveAcceptanceReceipt, no S6
valid ArchiveAcceptanceReceipt + S6, no FinalIndex
invalid/partial ArchiveAcceptanceReceipt, no S6
```

第一种已经有一个 archive-acceptance object，不再满足“no later artifact”；第二种已经有 S6，architecture 又禁止 S6/FinalIndex 与 terminal 共存；但两种都没有一个可 idempotent continuation 的 API。v19 的 `ArchiveAcceptor.accept_archive()`同样只描述一次性顺序 publish，`recover_post_s0()` 只到 S5，`OfficialArchiveResolver` 只认 FinalIndex。

**Impact：** 服务器在正常断电、fsync后进程崩溃或 network-less process crash 时会留下一份已验证 output 和部分 acceptance chain。实现者只能在恢复时自行决定重发 S6/FinalIndex、把已接受链 terminalize（与 v22 的 coexistence rule 冲突），或永久遗失 official result。这破坏了 linear receipt claim和可审计恢复，属于冻结威胁模型明确覆盖的 crash/partial-write failure，故为 P1。

**Evidence：**

- v22 §5 把 ArchiveAcceptanceReceipt、S6、FinalIndex列为三个不同 immutable objects和 slots，而 §201–206 的 recovery rules没有覆盖这三者之间的窗口。
- v19 §239–243同样只给出 publication order；§225–230的 recovery table对S0…S4残留做了规定，却不处理 S5 后的 partial acceptance。
- `OfficialArchiveResolver`依赖 FinalIndex，故S6 missing index cannot be read as official；yet v22 expressly bars terminal coexistence with S6/FinalIndex.

**Direction：** 增加一个完整、lock-held、post-S5 recovery table与专用 archive-acceptor API：明确每个 observed combination的唯一 terminal/continuation action、何时可从 a valid receipt deterministically publish S6、何时可从 a valid S6 deterministically publish FinalIndex、何时必须 quarantine，以及每次 continuation重新校验的 complete chain/output inventory/actor/slot conditions。确保任何 recovery object只指向 existing predecessors且不产生 receipt/state cycle；对三个 crash windows、duplicate/wrong receipt、S6-with-wrong-index和 archive actor loss 写 synthetic fault-injection cases。

### [P1] “FD-only controlled launcher”无法直接调用保持不变的 path-argument mechanics worker；缺少 staging/FD-to-worker adapter 会把实际运行输入重新降级为自由路径

**Section：** `architecture_confirmation_v22.md` §5 第 208–217 行；`m6_5_repair_change_design_v19.md` §1 第 10–28 行、§2 第 49–52 行、§5 第 232–261 行；`scripts/server/verify_m6_peerlite_archival_replay.py` 第 195–253、386–416 行。

**Scenario：** v22/v19 宣称 `AuthorizedArchivalReplayLauncher` 以 fixed `env -i`/argv/cwd/import 给 child “only sealed read FDs plus a staging/output FD”，server entry也只接受 sealed manifest FD。但保留 worker的 public `run()`和 CLI 要求九个独立 `Path` values（source root/archive、product、run、historical verification、ledger、output等），随后对它们调用 `.resolve()`、按 pathname 读取，并以 pathname `mkdir`/`os.replace` 创建输出。v19 同时规定旧 worker保持不变，并只留下未定义签名的 `MechanicsWorker` protocol。

没有指定 adapter 如何将 sealed FDs转成 worker所需路径、如何保证这些路径属于同一 immutable staging tree、如何避免 raw worker在 validation之后重新按路径打开另一个对象、如何把 raw output与 accepted `O`/H/output FDs重新对齐，或如何在 child crash后清理/封存 staging。实现者只好传回原始 caller paths（违背 no-free-path claim）、修改 frozen worker（违背保留不变）、或自行发明隔离/mount/staging协议。

**Impact：** 这是正常 launcher/deployment/TOCTOU失配，而非 hostile native-code injection。错误 wrapper可让 worker使用未被 Context/V绑定的 product/run/output path，再把一个形式正确的 raw receipt交给 ChildReceipt route；即使 final resolver拒绝 direct CLI output，受控 route仍无法证明“measured bytes = executed bytes”。因此为 P1。

**Evidence：**

- v22 §208–217明确将 old worker作为唯一 route的 mechanics child，同时承诺 sealed FD inputs；v19 §255–261又明确它不修改、authorized entry不传 individual paths。
- actual worker的 `run()`签名（195–208）和 CLI（386–399）只接受 `Path`，并在211–252调用 `.resolve()`/path filesystem operations；其 output publication第52–70行使用 `os.replace`，不接受 pre-opened output FD。
- v19 只称 injected `MechanicsWorker` protocol，未定义 staged invocation/FD inheritance/immutable tree inventory/receipt verification contract。

**Direction：** 定义一个具体、可测的 `StagedMechanicsInvocation`/adapter boundary：supervisor用 verified FDs materialize一个 private immutable staging tree，绑定 tree inventory/ref and the exact nine worker paths, runs the unchanged worker only with fixed stage-relative paths (or a deliberate `/proc/self/fd` mapping with revalidation), uses a unique supervisor-owned output namespace, and post-run reopens/hashes actual FDs before raw receipt can enter ChildReceipt. Freeze `pass_fds`/CLOEXEC/environment/argv/cwd semantics, stage cleanup/quarantine and crash recovery. The raw worker must remain mechanics-only, but its adapter—not a future wrapper convention—must become the sole permissible invocation implementation and be tested against source/product/run/output path swaps.

## Verdict

`NEEDS_CHANGES` — **0 P0、4 P1、0 P2、0 P3**。v22/v19 正确解决了 v18 的 complete slot topology、writer matrix、observed PASS bytes与 held OFD lock 的主要缺口；但 pre-E policy/gate-evidence provenance、ChildReceipt author/publication model、archive acceptance finalization recovery和实际 path-worker adapter仍是必须在实现前冻结的 material decisions。最早修复阶段为 `architecture`。在此之前不得进入 test design、red/green tests、implementation、code review、archival replay、M7、CCC/Gate、PIT 新认证或 final OOS。

## Retained strengths

- 完整 Context key、runtime/startup ref equality、DirectoryIdentity v2 opaque handle、K v4 与 Q-before-R precommit仍保持无环且比 v21 更清晰。
- v22 现在以 root-relative `SlotSpec` 覆盖 quality、authority、registry、states、receipts、outputs和 final-index，修复了此前 registry-only topology和 component-base ambiguity。
- `quality_gate_issuer → Bootstrap → QualityPass → VerifiedQualityInputs`、archive-acceptor-only E/C、supervisor-owned pre-S0以及 `F_OFD_SETLK` revalidation模型正确回应了上一轮大部分 issuer/lock findings。
- direct raw worker PASS、`M6ArchiveSummary`、generic status和 mutable heads被 official resolver明确拒绝；M6/M7/OOS/fit/trial-budget boundaries仍被保留。

## Review limits and status

- 本审查为 distinct-subagent、独立、只读 R3 review，只覆盖冻结威胁模型内的普通 policy/configuration、identity、path/TOCTOU、concurrency和 crash/recovery faults；没有把 hostile runner、host/control-root/kernel/ACL compromise或恶意 native injection当作 finding。
- 未修改产品代码、tests、contracts、gates、ledger、状态文件或历史 evidence；未执行项目代码、训练、archival replay、budget consumption、PIT `CERTIFY` 或 final OOS。
- 审查时只读观察 ledger revision=`127`；subject 为 v19，architecture evidence 为 v22。路由记录前必须重新读取 ledger。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 127,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "RELEASE_PROVENANCE_CHILD_RECEIPT_ACCEPTANCE_RECOVERY_AND_WORKER_ADAPTER_NOT_CLOSED",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 4, "P2": 0, "P3": 0},
  "subject_digest": "sha256:c6788d62318141b3a5f16e09f69e185303247910946582cb6501fad6b7b963a0",
  "next_route": "architecture"
}
```
