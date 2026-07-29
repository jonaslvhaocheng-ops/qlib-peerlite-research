# RunAuthorityGenerationV5

- 状态：`DESIGN_ONLY`
- 取代：`run_authority_generation_v4.md`
- 当前唯一可激活 purpose：`M6_5_SYNTHETIC_TEST_ONLY`；M7 upstream PASS objects 不存在。

## 1. Canonical refs, safe IDs and registry policy

所有 JSON strict/canonical 规则与 `ArtifactRefV1` 采用 Capacity V6 §1。自由 ID 必须匹配
`[A-Za-z0-9_.-]{1,128}`，禁止 `/`、`\`、`:`、`sha256`、64hex及 reserved words
`registration,commit,receipt,authority-generations`。

`AuthorityRegistryPolicyV1` exact：

```json
{
  "schema_version": "qlib_peerlite_authority_registry_policy_v1",
  "synthetic_registry_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "trial_registry_root": {"path":"<absolute>","device":"<decimal>","inode":"<decimal>"},
  "global_control_lock": "<absolute fixed path>",
  "m6_close_snapshot": "<ArtifactRefV1>",
  "m6_candidate_count": "6",
  "m6_fit_count": "44",
  "m7_max_candidate_count": "8",
  "m7_max_fit_count": "60",
  "canonical_sha256": "sha256:<64hex>"
}
```

两 roots 与 lock realpath/no-symlink 且 path/ancestor/inode 分离。M6 close snapshot 必须 strict
证明 retained exact `6/44`，且其 ledger head/hash 与每个 trial registration 的 `ledger_h0`
相等；不接受服务器 legacy `4/29`。

每个 namespace 的 generation 从1连续。generation decimal 以20位零填充为 `<g20>`。固定 paths：

```text
<registry_root>/.authority-generations.lock
<registry_root>/plans/<plan_id>.json
<registry_root>/authorities/<authority_id>.json
<registry_root>/registrations/<g20>.<run_id>.json
<registry_root>/commits/<g20>.json
<registry_root>/receipts/<g20>.json
```

plan/authority ID须等于其canonical preimage SHA派生安全ID；run_id在全namespace唯一。每个 final
JSON的唯一temp为`<path>.tmp.<canonical_sha256 without prefix>`。unknown temp/entry HOLD。

## 2. Linear event plan and purpose matrix

`LinearEventPlanV5` exact fields：

```text
schema_version,plan_id,purpose,ordered_events,canonical_sha256
```

每个 event exact fields：

```text
seq,source_event_id,type,evaluation_id,model_id,fold_id,seed
```

无extra/free maps；seq从1连续。purpose matrix：

| purpose | namespace | exact plan | caps | qualification | real_fit |
| --- | --- | --- | --- | --- | --- |
| M6_5_SYNTHETIC_TEST_ONLY | synthetic | 1+ SYNTHETIC_OBSERVER only；fold NONE | 0 candidate / 0 fit | null | false |
| M7_CCC_ISOLATED | trial | CANDIDATE；wf_2018..wf_2024七个FIT；wf_2018一个DETERMINISTIC_REFIT | 1 / 8 | nonnull PASS | true |
| M7_GATE_ISOLATED | trial | 同上 | 1 / 8 | nonnull PASS | true |

所有 purpose 的 final_oos=false。两个 M7 purpose 都要求 derived contract、screening prerequisite、
qualification 三个 strict ArtifactRefs nonnull且已独立 PASS；任何 candidate/fit/claim first event
前重复验证，不存在 CCC 例外。当前三类 M7 upstream fixed slots 尚不存在，所以 M7 purpose 必须
拒绝。

M7 upstream refs只接受 schema IDs：

```text
qlib_peerlite_m7_derived_contract_v1
qlib_peerlite_m7_screening_prerequisite_v1
qlib_peerlite_market_state_qualification_envelope_v6
```

这些 upstream objects 禁止 run/generation/registration/commit/receipt及下游 path/SHA。

## 3. Closed authority, registration, commit and receipt

`RunAuthorityV5` exact fields：

```text
schema_version,authority_id,purpose,namespace,run_id,generation_number,
linear_event_plan{ArtifactRef},registry_policy{ArtifactRef},
roots{journal,snapshot,output},
caps{candidate_evaluations,model_fits},
m6_prefix{candidate_evaluations="6",model_fits="44",binding{ArtifactRef}},
derived_contract{ArtifactRef|null},screening_prerequisite{ArtifactRef|null},
qualification{ArtifactRef|null},
real_fit_authorized,final_oos_access_authorized=false,
issued_at,issuer_policy{ArtifactRef},canonical_sha256
```

`RegistrationV5` exact fields：

```text
schema_version,namespace,generation_number,
previous_generation_commit{ArtifactRef|null},
authority{ArtifactRef},purpose,run_id,linear_event_plan{ArtifactRef},
registry_policy{ArtifactRef},roots{journal,snapshot,output},
caps{candidate_evaluations,model_fits},
ledger_h0,m6_prefix{candidate_evaluations="6",model_fits="44",binding{ArtifactRef}},
derived_contract{ArtifactRef|null},screening_prerequisite{ArtifactRef|null},
qualification{ArtifactRef|null},issuer_policy{ArtifactRef},canonical_sha256
```

Registration 与 authority 的 namespace/generation/purpose/run/plan/policy/roots/caps/M6 prefix/
三个upstreams/issuer policy/real-fit含义逐项 canonical equality；不得自报不同 identity。

`AuthorityGenerationCommitV5` exact fields：

```text
schema_version,namespace,generation_number,
previous_generation_commit{ArtifactRef|null},
registration{ArtifactRef},authority{ArtifactRef},purpose,run_id,
linear_event_plan{ArtifactRef},registry_policy{ArtifactRef},
prior_terminal{path,file_sha256,canonical_sha256,status}|null,
ledger_h0,m6_prefix{candidate_evaluations="6",model_fits="44",binding{ArtifactRef}},
retained_before{candidate_evaluations,model_fits,purpose_sequence_digest,event_status_digest},
authorized_increment{candidate_evaluations,model_fits},
retained_after_ceiling{candidate_evaluations,model_fits,purpose_sequence_digest},
issuer_policy{ArtifactRef},canonical_sha256
```

commit 的重复字段必须与 registration/authority exact equality。generation1 的 previous/prior
terminal 均null；后续两者nonnull并指向 exact predecessor commit与其 terminal ledger receipt。

`ActivationReceiptV4` exact fields：

```text
schema_version,namespace,generation_number,generation_commit{ArtifactRef},
registration{ArtifactRef},authority{ArtifactRef},observed_registry_head{ArtifactRef},
global_control_lock_path,verified_at,canonical_sha256
```

receipt 是可选审计回执，不是 authority source；commit 是唯一 activation point。

## 4. Global budget, order and no replacement

持 global control lock 后，validator 从 registry root FD no-follow 扫描全部 commits，要求：

- generation恰为`1..next-1`，无gap/duplicate/unknown files；
- 每个previous ref、registration、authority、plan、terminal和ledger chain全量重算；
- 每个run_id全历史唯一；
- trial namespace 的 retained purpose sequence 只能是 `[]`、`[CCC]`、`[CCC,GATE]`；
- CCC与Gate各最多一次；Gate predecessor必须是CCC terminal；
- CANDIDATE/FIT/DETERMINISTIC_REFIT 一旦 CLAIMED、RUNNING、PASS、FAILED、
  CLAIMED_INTERRUPTED或MANUAL_ABORT 均计入 retained counts；
- FAILED、CLAIMED_INTERRUPTED、MANUAL_ABORT 均不得 replacement，也不能签发相同purpose新
  generation；
- retained_before 必须等于从 M6 `6/44` close snapshot 加所有 prior plans/events 重算结果；
- proposed increment 必须等于当前 plan exact 1/8；retained_after ceiling 不超过`8/60`。

synthetic namespace永远0/0，不影响 trial sequence或budget。任一 history/terminal 缺失或
不一致时 HOLD，禁止新 commit。

## 5. Durable activation state machine

在 global control lock 内按以下顺序：

1. strict重验 registry policy/root/device/inode、M6 close snapshot、连续 predecessor、ledger H0、
   purpose order、retained counts、upstream PASS和role DAG；
2. plan 和 authority 必须已在固定 paths durable；用 final parent fsync evidence验证；
3. 以 fixed temp write/fsync/chmod0440，hardlink no-replace发布 registration，fsync registrations
   dir；existing identical resume，different bytes HOLD；
4. 再次全量重算 registry head与budgets；
5. 以同样协议发布 generation commit 到唯一 `<g20>.json`，fsync commits dir与registry root；
   此成功 fsync 是唯一 activation point；
6. commit durable 后才可发布 activation receipt并fsync receipts dir；receipt失败不撤销commit，
   重试只能发布 identical receipt。

crash/retry：

- 无registration：从步骤1重试；
- registration有、commit无：registration exact valid才继续，否则HOLD；
- commit有：若exact valid则已激活，只允许补receipt；different registration/commit/receipt HOLD；
- gap、两个run争同generation、重复run ID、unknown temp/entry、role reversal一律HOLD；
- 永不overwrite、删除或重编号 generation。

## 6. Role DAG and execution check

```text
M6 close + upstream contracts/prerequisite/qualification + registry/issuer policy
 -> plan
 -> RunAuthority
 -> Registration
 -> GenerationCommit (activation)
 -> optional ActivationReceipt
 -> event claims/artifacts/terminal
```

validator 遍历所有 strict strings/refs，拒绝 self、ancestor/container、下游回边或角色倒置。
executor 在每个 event 前重验 active commit、plan当前位置、全部upstream PASS和当前ledger retained
counts；无active commit或first-event prerequisite不完整即拒绝。当前 M6.5 只能激活 synthetic
observer authority、zero trial caps和fake observer plan。
