# RunAuthorityGenerationV4

- 状态：`DESIGN_ONLY`
- 当前可接受purpose：仅`M6_5_SYNTHETIC_TEST_ONLY`；M7 objects尚不存在。

## 1. ArtifactRef and safe IDs

所有upstream refs exact `{path,file_sha256,canonical_sha256}`。自由ID regex
`[A-Za-z0-9_.-]{1,128}`，禁止`/`,`\\`,`:`,`sha256`、64hex及reserved words
`registration,commit,receipt,authority-generations`。

`LinearEventPlanV4` exact绑定plan ID和ordered events；plan本身使用ArtifactRef定位。events exact
fields seq/source_event_id/type/evaluation_id/model_id/fold_id/seed。无extra/free maps。

## 2. Purpose matrix

| purpose | allowed exact plan | caps | real_fit | upstream |
| --- | --- | --- | --- | --- |
| M6_5_SYNTHETIC_TEST_ONLY | 1+ `SYNTHETIC_OBSERVER` only；fold_id=`NONE` | candidate=0, fits=0 | false | derived/prerequisite=null |
| M7_CCC_ISOLATED | `CANDIDATE`, seven ordered `FIT` wf_2018..wf_2024, one `DETERMINISTIC_REFIT` wf_2018 | candidate=1, fits=8 | true | derived+prerequisite nonnull |
| M7_GATE_ISOLATED | same exact event shape | candidate=1, fits=8 | true | derived+prerequisite+qualification nonnull |

all final_oos=false。当前validator因M7 upstream fixed slots不存在而拒绝两个M7 purposes。

M7 upstream refs只接受strict schema IDs
`qlib_peerlite_m7_derived_contract_v1`,
`qlib_peerlite_m7_screening_prerequisite_v1`,
`qlib_peerlite_market_state_qualification_envelope_v6`；这些schemas禁止run_id/generation/
registration/commit/receipt字段和下游paths/SHAs。validator递归role-graph检查。

## 3. RunAuthorityV4

strict fields：

```text
schema_version,authority_id,purpose,run_id,generation_number,
linear_event_plan{ArtifactRef},roots{journal,snapshot,output},
caps{candidate_evaluations,model_fits},m6_prefix{6,44,binding ArtifactRef},
derived_contract{ArtifactRef|null},screening_prerequisite{ArtifactRef|null},
qualification{ArtifactRef|null},real_fit_authorized,final_oos_access_authorized=false,
issued_at,issuer_policy{ArtifactRef},canonical_sha256
```

unknown/free maps拒绝。plan/authority/upstream在registration前发布，均不得引用downstream roles。

## 4. Authority→Registration equality

RegistrationV4 strict fields：

```text
schema_version,generation_number,previous_generation_commit{ArtifactRef|null},
authority{ArtifactRef},run_id,linear_event_plan{ArtifactRef},
roots{journal,snapshot,output},ledger_h0,m6_prefix{6,44,binding ArtifactRef},
issuer_policy{ArtifactRef},canonical_sha256
```

Registration绑定authority后，下列必须逐项byte/canonical相等：

```text
generation_number
run_id
linear_event_plan ArtifactRef
roots journal/snapshot/output
m6_prefix candidate/model/binding
issuer_policy ArtifactRef
```

Registration不得自报不同plan/root/identity。previous commit/H0属于registration专有字段。

`AuthorityGenerationCommitV4` strict：

```text
schema_version,generation_number,previous_generation_commit{ArtifactRef|null},
registration{ArtifactRef},authority{ArtifactRef},run_id,linear_event_plan{ArtifactRef},
prior_terminal{path,file_sha256,canonical_sha256,status CLOSED|ABANDONED|null},
ledger_h0,m6_prefix{6,44,binding ArtifactRef},issuer_policy{ArtifactRef},canonical_sha256
```

generation1两个previous/prior terminal均null；之后nonnull且exact predecessor。commit与registration/
authority所有重复字段相等。

`ActivationReceiptV3` strict：

```text
schema_version,generation_commit{ArtifactRef},registration{ArtifactRef},
observed_registry_head{ArtifactRef},verified_at,canonical_sha256
```

receipt仅下游；commit/registration/authority不反向绑定。任一mismatch在activation前FAIL。

## 5. Role DAG

```text
upstream contracts/prerequisites/qualification
 -> plan + issuer policy
 -> RunAuthority
 -> Registration
 -> GenerationCommit
 -> optional ActivationReceipt
 -> event artifacts
```

validator遍历所有strict string/ref字段，拒绝self、ancestor/container、role reversal及任何下游
path/SHA。当前M6.5只能生成synthetic authority、zero trial caps和fake observer plan。
