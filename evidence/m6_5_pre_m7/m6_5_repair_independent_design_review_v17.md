# M6.5 canonical v17 / architecture v20 独立 R3 设计审查

## Findings

### [P1] `m6_evidence_key` 的声明 preimage 与所有后代实际验证集合不一致，runtime / verifier / family context 仍可脱离六项证据 role 漂移

**Section：** `architecture_confirmation_v20.md` §1（13–37、50–55、156–160 行）；`m6_5_repair_change_design_v17.md` §1（13–19、44–47 行）；冻结威胁模型（15–19、33–39 行）。

**Scenario：** E 的六个 typed evidence role、独立 quality-PASS receipt、唯一 issuer 和递归 allow-list 已正确建立。不过 v20 33–35 行把 `family ID`、frozen verifier/runtime-contract refs 和 `M6_ARCHIVAL_REPLAY_ONLY` scope 一并放入 `m6_evidence_key` 的 canonical preimage；36–37 行却规定 C/P/F/A/Q/V 只携带该 key 作为 index，并由 validator **从六项 role refs**重算。50–55 行也只规定六项 role 的逐项 equality，V 的完整历史清单只需令其中六项等于 E。

因此 written contract 没有一个 exact equation 要求 V/Q 中的 sealed verifier、FD helper、runtime closure、startup/process/argv/cwd/import policy、family ID 和 scope 必须等于 E 用来派生 key 的那些值。实现若严格按“六项 role”重算，得到的 preimage 与 E 的定义不同；若为使流程可运行而忽略非六项字段，就可能出现 `E` 使用 RT1、而 Q/V 冻结同一六项 M6 evidence 却使用 RT2 的配置。Q 在 R 前冻结 V bytes 解决了 post-claim choice，却不能证明 RT2 等于 E 的 RT1。

**Impact：** 这是冻结威胁模型内的普通 runtime / launcher / environment 误选，并不依赖 hostile runner、host 或 ACL 被攻破。它会使 archive-verifier 对一个与 authority bundle 不同的 runtime 执行，而六项证据和 key index 仍看似一致；这正是威胁模型要求拒绝的错误 archive/verifier/launcher/runtime/environment 绑定，故为 P1。

**Evidence：**

- v20 17–24 行的六项 role 本身不含 runtime、verifier、family 或 scope；33–37 行却把这些额外值放入 key preimage，同时只描述从六项 ref 重算。
- v20 50–55 行在 C/P/F/A/Q/V 和 V inventory 上规定的是六项 role equality；101–112 行固定 Q/V 的 bytes，但没有规定 `V.runtime_context == E.runtime_context`。
- v17 13–19、44–47 行仅继承 “six-role / derived key” 和对应 splice tests，未增加“六项不变、仅 runtime/family/scope 改变”的拒绝用例。
- 威胁模型 17–19、33–39 行明确把 runtime/environment 绑错列为本阶段必须防止的正常故障。

**Direction：** 在 E 中定义一个 closed、typed `M6ReplayAuthorityContext`（或等价的 role 集合），精确包含 family、scope 与所有 verifier/runtime/startup refs。令 E 的 key 只哈希该同一 canonical preimage；C/P/F/A/Q/V 要么逐项携带并比对完整 context，要么携带 `authority_context_ref=Ref(E)`，且 validator resolve E 后逐项比对 V/Q 的 runtime/startup fields。加入保持六项 evidence 和 quality PASS 不变、只改变 family、scope、verifier、FD helper、runtime closure、Python startup/process state 或 argv/cwd/import 的拒绝 fixtures；必须在 Q/R/V 和任何输出前失败。

### [P1] E 的 immutable control-store identity 未被机械等式绑定到 A、registry、lock 和所有 claim / terminal slot 的实际解析根

**Section：** `architecture_confirmation_v20.md` §1（26–31、57–66、68–76 行）、§2（101–112 行）、§3（116–132 行）、§4（150–154 行）；`m6_5_repair_change_design_v17.md` §1–3（13–40 行）。

**Scenario：** v20 说 E 包含 immutable control-store identity，C 的 PTemplate 固定 parent components、resolver 和 root ACL spec，且 A bind exact C/P/F。但是没有写出 `A.control_store_identity == E.control_store_identity`、A-rooted registry/transaction-lock components 的 closed identity，或每个 Q/R/V/terminal phase 必须从 E/A 所锚定的 FD 重开并做 exact equality 的规则。随后 `registry/claims/<K>`、`registry/bindings/<K>` 和 `registry/pre-s0-terminals/<K>` 都以“A-rooted”或相对 `registry/` 被描述，却没有定义该 registry 相对哪个已验证 identity。

在同一受信主机上，replay supervisor 可以因普通部署/路径配置错误解析到另一个 ACL 相同、schema 也相同的 control store / registry。对象 bytes、E six-role refs、PTemplate 和 writer identity 都可正确，而 R、V 和永久 terminal 被发布、恢复或扫描在错误 registry 下。当前文字没有一条可机械执行的 root-equation 拒绝这个 twin-root 情形。

**Impact：** 这会把唯一 K claim 与 pre-S0 burn/quarantine 的物理存放位置从 E 所承诺的 authority 根分离，造成错误 namespace 中的状态被当作 canonical，或 canonical crash residue 被错误忽略。它属于威胁模型已覆盖的路径/配置/重启恢复错误，而不是 hostile control-root compromise，故为 P1。

**Evidence：**

- v20 28–31 行只称 E “contains … immutable control-store identity”；57–66 行对 C/P/F/A 的 closed materialization 未列出 control-store/root/registry identity equality；68–76 行仅比较 writer identity。
- v20 101–112、116–132 行使用 A-rooted 或 `registry/...` fixed slots，但未规定 A 的 resolved root/registry/lock identity 与 E 的 exact relation；150–154 行也只概述 “under A's resolved registry/transaction lock”。
- v17 13–19、23–40 行将其概括成 “fixed slots/control store” 和 “anchored lock”，没有补上 object fields、FD comparison 或 alternate-root rejection tests。
- frozen threat model 15–19 行把路径/配置误选、重启和半写控制状态列入必须防御的范围。

**Direction：** 明确 E、C/PTemplate、A 和 B 之间的 control-root contract：若使用同一 root，写出 `A.control_store_identity == E.control_store_identity`；若 evidence store 与 registry root 有意不同，则把两者作为 E 中独立、typed、immutable identities，并定义不可替换的 mapping。A 必须闭合 registry/lock component list、resolver 和完整 FD-derived identity chain；freeze、claim、prelaunch、recovery、archive 每次都以 no-follow FD 重开并比较。Q/R/V/terminal 的 fixed paths 必须只能从该 A/E-bound registry 派生。添加“相同 ACL / 相同 relative path / 不同 control-store or registry inode”的 fixtures，并在 R 前拒绝。

### [P2] 继续使用 `DirectoryIdentity v2`，但 v20 的 inline canonical field list 未说明保留 opaque file-handle 字段，导致 D/K 版本语义不唯一

**Section：** `architecture_confirmation_v20.md` §2（80–99、150–160 行）；retained `architecture_confirmation_v17.md` §1（61–74 行）；`m6_5_repair_change_design_v17.md` §2（23–28、44–47 行）。

**Scenario：** v20 将 D 定义为 `DirectoryIdentity v2` 的 inline closed canonical data，并列出 type、device、inode、mount、btime、uid/gid/mode 和 ACL，却没有列出 v17 对相同 `DirectoryIdentity v2` 明确要求的 `opaque_file_handle_sha256 from name_to_handle_at(AT_EMPTY_PATH)`。若 v20 的列表是新的完整 schema，就静默弱化了既有 FD identity witness；若 opaque handle 仍是必填字段，则 v20/v17 没有明说它必须进入 D 的 serialization、K recomputation 和每次 phase comparison。

**Impact：** 普通 filesystem API capability 差异或 crash 后目录替换时，不同实现可能对同一 parent 得出不同 D/K，导致 claim、recovery 与 archive 的 identity 判断不一致。尚未证明缩减 tuple 与既有 v2 等价，故为 P2。

**Evidence：**

- v20 80–84 行将 D 的列举称为 `DirectoryIdentity v2`，但少于 v17 63–73 行给出的 v2 fields，后者明确要求 opaque file handle 且 helper 不支持时 fail closed。
- v20 96–99、150–160 行要求每 phase compare D/K 和测试 D/K tamper，却未指定 opaque-handle comparison 或 unsupported-handle fixture；v17 change design 仅复述 “canonical inline data”。

**Direction：** 明确 D byte-for-byte 复用 retained `DirectoryIdentity v2`（含 opaque file handle），并在所有 phases 比较；无法取得 canonical handle 时 fail closed。若有意删除该字段，必须使用新的 schema version、重做 equivalence/risk decision，且增加“其余字段相同、opaque handle 不同”及 unsupported-helper fixtures。

## 已验证且应保留的控制

| 核查项 | 结论 | 依据 |
| --- | --- | --- |
| 六项 M6 evidence role 与 quality PASS | role-level closure 已建立；完整 authority context 仍受第一项 P1 阻断 | v20 13–31、50–55、156–160；v17 13–19、44–47 |
| C PTemplate → 独立 P/F materialization → A | 静态依赖方向正确，无 C/P/F/A hash cycle | v20 57–66；v17 13–19 |
| Writer matrix | issuer、replay supervisor、child verifier 与 archive writer 已显式分配，并有 actual peer/FD ACL check | v20 68–76；v17 36–40 |
| Q 在 R 前冻结完整 V preimage | 已正确限制 Q 内容，V 只可为 `CanonicalComplete(Q, R)` | v20 101–112；v17 23–28 |
| R→V 固定槽与 pre-S0 crash terminal | 表格覆盖 R-only、V-only、invalid/partial V、pre-S0 output 和 terminal permanence | v20 116–132；v17 32–34 |
| S0…S6 left-only lineage、M6/M7 isolation | fixed predecessor / O_EXCL scan / archive-before-S6 / M7 schema rejection 方向正确 | v20 29–31、134–146；v17 36–40 |

## Verdict

`NEEDS_CHANGES` — **0 P0、2 P1、1 P2、0 P3**。最早修复阶段为 `architecture`。在完整 authority context/key 和 E→A→registry control-root binding 被写成可机械验证的 closed equations、且 D 的 v2 encoding 被澄清前，不得进入 test design、red/green tests、implementation、code review、server replay、M7、CCC/Gate、PIT 新认证或 final OOS。

## Strengths to preserve

- E 的 six-role bundle、future-replay-independent quality PASS、唯一 `archive_acceptor` issuer、exact artifact refs 和 recursive allow-list。
- C 的 closed PTemplate，P/F 的独立 materialization，以及 A 后置统一，避免了旧版 policy/materialization cycle。
- Q-before-R 完整 V preimage、flat `O_EXCL` claims、不可重建 pre-S0 terminal 和 S0…S6 receipt chain。
- `O_PATH` witness 与独立 sync FD、no-replace/fsync publication，以及 M6/PIT/M7/final-OOS 的既有边界。

## Review limits and status

- 本审查是 distinct-subagent、独立、只读 R3 review；严格限于 frozen threat model 中的普通 schema、路径、runtime、并发和 crash/recovery failure。没有将 hostile runner、host/control-root/kernel/ACL compromise 或恶意 native injection 当作 finding。
- 未修改产品代码、tests、research contract、gate、历史证据或 quality ledger；未运行项目代码、训练、M6 replay、PIT `CERTIFY`、预算消费或 final-OOS。
- 只读观测 quality ledger revision=`107`，repository source digest=`sha256:dfd743d7abc1a1cb32088a5420387a8a9608a218eb840b06d3f91b20ef6a9886`；后续路由必须重新读取。

## Normalized result for `eng-route-quality-work`

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision": 107,
  "source_digest_observed": "sha256:dfd743d7abc1a1cb32088a5420387a8a9608a218eb840b06d3f91b20ef6a9886",
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "AUTHORITY_CONTEXT_AND_CONTROL_ROOT_BINDING_NOT_CLOSED",
  "summary": "v20/v17 correctly close the PTemplate materialization, preclaim V freeze and pre-S0 lifecycle, but do not make the declared evidence-key preimage or the E-to-A-to-registry root binding mechanically verifiable; DirectoryIdentity v2 also has an unresolved field-set ambiguity.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 2, "P2": 1, "P3": 0},
  "subject_digest": "sha256:e83b5f20971c4813307a561e3beb4b62737e9d6c46e000fa534eefd8096ce9fc",
  "next_route": "architecture"
}
```
