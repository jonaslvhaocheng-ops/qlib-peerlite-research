# M6.5 canonical v17 / architecture v20 独立对抗式设计审查

## Findings

### [P1] `m6_evidence_key` 的声明 preimage 与后代 validator 的实际比较集合不同，冻结 verifier/runtime/family context 仍可在六个 M6 evidence role 不变时被 cross-splice

**Section：** architecture v20 §1 第 13–37、50–55 行，§4 第 156–160 行；change design v17 §1 第 13–19 行；retained M6 replay inventory 为 architecture v14 第 76–81、87–97 行；frozen threat model 第 15–19、33–39 行。

**Scenario：** v20 的 E 很好地把六个核心 M6 role 和独立 M6.5 PASS 放入 authority bundle。但第 33–37 行给 `E.m6_evidence_key` 的 canonical preimage 还包含 `family ID`、`frozen verifier/runtime-contract refs` 和 scope；紧接着却要求 C/P/F/A/Q/V “only as an index”携带 key，并让 validator **从各对象的六个 role refs**重新计算。第 50–55 行同样只要求六个 role-by-role equality，V 的 historical inventory 也只要求其中六个对应 role 等于 E。

因此没有一个写出的 exact equation 要求 V（以及 Q/C/P/F/A 必要的 runtime contract fields）中的 sealed verifier、FD-exec helper、bootstrap、`ReplayRuntimeClosure`、`PythonStartupPolicy`、`ProcessStartupState`、fixed argv/cwd/import policy、family ID 和 scope，与 E 为 key 声称承诺的那些值相等。若 implementation 真按第 36 行“从六个 refs”重算，得到的 preimage 与第 33–35 行定义的 key 不同，合法对象无法被无歧义地验证；若为了运行而忽略 non-six components，便出现下列正常配置/恢复错误：

```text
E/C/P/F/A/Q: M6 evidence set + approved runtime RT1
V:           same six M6 evidence refs, but RT2 / launcher / startup policy
```

它们可以拥有相同六-role comparison 和 same key index，却在实际 replay 中运行不同的 verifier/runtime。这里不需要 hostile runner 或被攻破的 host：RT2 可以是同一受信 store 中另一个格式正确、甚至独立测量过的 closure。威胁模型明确要求防止 archive/verifier/launcher/runtime/environment 绑错；retained M6 contract 也要求这些对象和 observed execution receipt 精确相等。

**Impact：** 当前 architecture 在两种实现之间留下一个 material decision：要么以不匹配的 preimage 错误拒绝本应合法的 authority，或隐式从 E/ambient configuration 取回缺失字段并接受 V 的 non-six runtime drift。后一种会让 M6 archival replay 的 code/runtime/environment 不再由 immutable authority 逐 role 证明，并可能让其 output 进入 archive acceptance；所以是 P1，而不是 hostile-host 假设。

**Evidence：**

- v20 第 17–24 行列出的恰好六个 typed evidence roles 不包含 frozen verifier/runtime contracts；第 33–37 行却将它们与 family/scope 放入 key preimage，而只承诺从六 refs recompute。
- v20 第 50–55 行的 downstream equality 仍只覆盖 six roles；第 101–111 行的 Q/V precommit 固化的是 V bytes，但没有修复 E 与 V runtime-contract equality 的缺失。
- retained v14 第 76–81、87–97 行明确把 verifier, FD helper, bootstrap, runtime closure, startup/process state and fixed argv/cwd/import 视为 exact replay inputs，并要求 replay receipt binding；threat model 第 18、39 行把 wrong runtime/environment 作为本阶段必须防止的风险。
- v17 第 13–19、44–47 行重复 “six-role” validation/test wording，未增加一个只改变 family/runtime-contract、保持六 role 不变的 adversarial fixture。

**Direction：** 将 E 的 complete authority context 定义为一个 closed typed preimage，而不是让 `m6_evidence_key`承担未写出的关系。最小修复可以是：

1. 为 `family_id`、scope 和每个 frozen verifier/runtime/startup contract 增加 exact complete typed role/ref（或一个 closed `M6ReplayRuntimeContract v1` typed ref）到 E；
2. 令 C/P/F/A/Q/V 和 V historical inventory either carry the full same context role-by-role, or carry an exact `authority_context_ref=Ref(E)` **并**让 validator resolve E then compare every V runtime/startup field to it. Key must be recomputed from exactly the same declared preimage in every phase, never only from a subset;
3. Add fixtures that hold all six M6 evidence roles and quality PASS constant while changing only family ID, sealed verifier, FD helper, runtime closure, Python startup/process state, argv/cwd/import or scope. All must fail before Q/R/V/any output claim.

This preserves E→C→{P,F}→A→B→Q→R→V acyclicity: the context is entirely pre-existing before E, and V merely repeats/resolves it; it must not point back to Q/R/V/receipts.

### [P2] v20 对同名 `DirectoryIdentity v2` 的 inline closed encoding 未明确保留 opaque file handle，D/K 的 anti-alias boundary 因而变成 version ambiguity

**Section：** architecture v20 §2 第 80–99、156–160 行；retained `DirectoryIdentity v2` definition in architecture v17 第 61–73 行；change design v17 §2 第 23–28、44–47 行。

**Scenario：** v20 将 D 写成 inline closed canonical data，并列出 type/dev/inode/mount/btime/UID/GID/mode/ACL，但没有列出 v17 `DirectoryIdentity v2` 中的 mandatory `opaque_file_handle_sha256 from name_to_handle_at(AT_EMPTY_PATH)`。v20 同时宣称保持 v19 的 FD boundary，又继续使用同一个 `DirectoryIdentity v2` schema name。

如果该列表是新 closed schema 的完整字段，则它会静默弱化原有 inode-reuse / path-replacement witness，或在同名下产生 schema drift；如果 opaque handle 仍是 required field，则 v20/v17 没有明确它必须 serialize、compare 和在 unsupported helper 上 fail closed。两种解释都会把 K 的 actual parent identity 留给 implementation 选择。

**Impact：** 这不是要求抵御 hostile filesystem/kernel。正常 crash/recovery 后的 directory replacement 或低保真 identity API 是当前 FD/ACL design 原本要 fail closed 的情况。未澄清时，某个 implementation 可能用缩减 tuple 重新算 K，而另一个仍使用 full v2，导致 claim/recovery/archive 对同一 physical parent 的 identity conclusion 不一致。因尚未证明这一缩减一定可安全等价，列为 P2。

**Direction：** 明确 `D` 逐字段等于 retained `DirectoryIdentity v2`（包括 opaque handle），并在 freeze/claim/prelaunch/recovery/archive 每次 compare；缺 `name_to_handle_at` 或 canonical handle 时 fail closed。若确实要删该字段，必须用新的 schema version 和单独的 equivalence/risk decision，不能复用 v2 名称。增加 “其他 v2 fields 相同、opaque handle 不同” 以及 unsupported-handle fixtures，确认它们不能生成/接受 K claim。

## Controls verified as retained

- E 现在把 M6.5 quality PASS 放在 future replay 之外，并固定单一 `archive_acceptor` issuer、actor/ACL map、control-store/slot和 recursive nested-ref allow-list；这正确关闭了上一轮 policy/profile/P issuer ambiguity 与直接 M7 reference path。
- C 的 PTemplate、fixed P/profile slots、P/F independent materialization 和 A subsequent binding 以正确方向避免 C/P/F hash cycle；P 不再自由选择 policy/template/slot。
- K 已直接使用 observed canonical D 而非 caller-supplied `parent_identity_digest`，R 的 flat once-only K slot、Q-before-R complete V preimage、V exact completion和 pre-S0 burn/quarantine table均有效关闭了上一轮 duplicate-coordinate 与 R→V crash-window主问题（仅保留上文的 v2 encoding clarity）。
- S0…S6 fixed predecessor/receipt chain、archive-before-S6 ordering、writer matrix、anchored registry lock、separate O_PATH/sync FDs、root ACL/empty checks、fsync ordering、seed/umask/PIT/legacy-ledger/final-OOS controls均未见倒退。
- STATUS 仍准确限制在 `M6.5-PRE-M7-ENGINEERING-QUALITY / DESIGN_REVIEW_PENDING`；本 review 没有授权 M6 replay、M7 derived contract/fit、CCC/Gate、PIT 新认证或 final OOS。

## Verdict

`NEEDS_CHANGES` — **0 P0、1 P1、1 P2、0 P3**。最早修复阶段为 `architecture`。在 authority context/key 统一为完整 typed preimage、并澄清 D 的 exact v2 encoding 后，需同步更新 canonical change design 并重新进行独立 R3 review；此前不得进入 test design、red/green、implementation、code review、server replay、M7、CCC/Gate 或 final OOS。

## Review limits and status

- Current phase/track: `M6.5-PRE-M7-ENGINEERING-QUALITY` / `design-review`; historical M6 engineering gate is `PASS`, but M6.5 remains unpassed.
- 本审查只覆盖 frozen threat model 中的 ordinary schema/path/TOCTOU/concurrency/crash/ACL/runtime/configuration failure；hostile runner arbitrary native code、host/control-root/kernel/ACL compromise 和 malicious loader injection 都未作为 finding。
- 未修改 code、tests、contracts、gates、historical evidence 或 quality ledger；未运行 project code、training、M6 replay、budget consumption、PIT `CERTIFY` 或 final OOS。
- Router review-time observation: ledger revision=`106`，source digest=`sha256:bd5c5b78acb95375bd519da5c61cf3e2f28f79427756297ad23417f84e1645b7`。此 result 只读；写入 ledger 前必须重新 route/refresh。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 106,
  "source_digest_observed": "sha256:bd5c5b78acb95375bd519da5c61cf3e2f28f79427756297ad23417f84e1645b7",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-r3-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "AUTHORITY_CONTEXT_KEY_AND_DIRECTORY_IDENTITY_ENCODING_NOT_FULLY_CLOSED",
  "summary": "v20 materially improves authority issuance, P/F materialization, coordinate claims and pre-S0 recovery. But its key preimage includes family/runtime/scope while its downstream validator compares only six evidence roles, leaving verifier/runtime context unbound or validation mathematically ambiguous; its inline DirectoryIdentity v2 field list also omits the retained opaque-handle field.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {
    "P0": 0,
    "P1": 1,
    "P2": 1,
    "P3": 0
  },
  "subject_digest": "sha256:e83b5f20971c4813307a561e3beb4b62737e9d6c46e000fa534eefd8096ce9fc",
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v17.md",
    "sha256": "sha256:e83b5f20971c4813307a561e3beb4b62737e9d6c46e000fa534eefd8096ce9fc"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v20.md",
    "sha256": "sha256:d944ab700454dbc22515a779366a60e09337efb9b69b2365c0608f08441528e0"
  },
  "threat_model_evidence": {
    "path": "evidence/m6_5_pre_m7/research_governance_threat_model_v1.md",
    "sha256": "sha256:d2fb7afe7525bc53c528645794093a43b396a39d8daabb908da6484277dcca14"
  },
  "status_evidence": {
    "path": "docs/STATUS.md",
    "sha256": "sha256:16e558a7c2bc8e175207f9eea7383bc1305762d4cd2511574941e6b183b96667"
  },
  "artifact_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_independent_design_review_v17_adversarial.md"
  ],
  "commands": [
    "read-only rg --files/rg/nl/sed/shasum/git status",
    "quality_ledger.py next --ledger .engineering-quality/changes/m6-5-pre-m7-repair/ledger.json --repo . (route inspection only)",
    "read-only inspection of v14/v17/v19 retained runtime and DirectoryIdentity contracts"
  ],
  "independence": {
    "mode": "distinct-subagent-review",
    "author_context_id": "/root",
    "reviewer_context_id": "/root/design_review_v7_adversary",
    "limitations": [
      "No product/test/contract/gate/ledger/historical-evidence implementation changes.",
      "No training, M6 replay, budget consumption, real PIT certification, or final-OOS access."
    ]
  },
  "blockers": [
    "Bind family/runtime/startup/scope into the same complete authority context/key that every C/P/F/A/Q/V/V-inventory validator compares.",
    "Specify whether D is byte-for-byte retained DirectoryIdentity v2 including opaque handle, or version it explicitly and prove its replacement-safe equivalence.",
    "Re-run independent design review before test design or implementation."
  ],
  "next_route": "architecture"
}
```
