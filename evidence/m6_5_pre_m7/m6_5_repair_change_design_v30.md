# M6.5 有界修复变更设计 v30

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v29；历史版本与失败审查保留。

## 1. 精确 composition

base是v29 exact SHA：

```text
be21d2301fd8911f1dcc620ade824d4e6e2fc6b0dcc9ddb85965024836fc4d1e
```

保留v29 §1与未被下表替换的v28/v27 normative ancestry。精确替换：

| v29 | v30 |
| --- | --- |
| §2全部 | 本文件§2 |
| §3全部 | 本文件§3 |
| §4全部 | 本文件§4 |
| §5全部 | 本文件§5 |
| §6全部 | 本文件§6 |
| §7全部 | 本文件§7 |

没有隐式段落选择。若ancestry文字与本文件冲突，以本文件精确replacement为准。v30不授权产品
实现、server replay、M7、fit、budget变更或final-OOS。

## 2. Behavior qualification 的可执行证明面

### 2.1 Official single-horizon rule

future derived contract冻结exact unique horizons。每个official request/manifest只允许一个scalar
`protected_through=T`且`probe_type=FUTURE_POISON`；一T一manifest。mutation只改
`vendor_available_time>T`的row/field。official manifest保持上游closed schema和exact
`B001,B002,B003,B004`，不得添加项目私有字段。

official B004只代表其实际输出的projected rows。项目资格判定必须额外绑定同T的：

1. `BehaviorAvailabilitySupplementV1`；
2. `AuxPrefixBehaviorVerificationV1`；
3. `BehaviorIndependentReviewReceiptV1`。

三者的closed schemas、canonical JSON/hash、exact check IDs、authority时序与parent binding以本文件
§6绑定的M7 v8 §2.3–§2.5为唯一规范。official state使用v8 §2.2 canonical flatten adapter；
population count及aux/population/state完整prefix由AP001–AP004独立复核。缺任一、T不一致、
unknown key、hash或parent substitution均在qualification creation前FAIL/HOLD。

### 2.2 Security lifecycle availability

`md_security.LIST_DATE/DELIST_DATE`当前证书只说明availability“不定时”。任何validator不得从
event date、row date或数据库抽取时间推断vendor availability。future derived contract必须绑定：

```text
contracts/immutable/security_lifecycle_availability_authority_v1.json
```

其资格规则完全采用M7 v8 §2.6。当前slot不存在是预期状态：M6.5只实现并测试fail-closed路径，
不得创建真实qualification或把当前状态写成PASS。

## 3. Durable Nested Directory CommitV4 与 staging lifecycle

### 3.1 Payload publication

沿用v28 §3.1的typed directory/file inventory、relative path限制、no-symlink/no-device规则。
每次input/output transaction固定：

1. private staging directories为0700；regular files写满、fsync、chmod 0440；
2. prepared claim绑定target、schema、content UUID、directory/file payload inventory、staging
   inventory、policy/code SHA和capacity reservation；
3. parent publish lock内no-replace发布prepared；
4. final root/descendant dirs按depth top-down以0700创建；
5. regular files从staging root FD执行no-follow hardlink；existing必须type/size/hash相同；
6. fsync files，再bottom-up fsync dirs；
7. files确认0440；descendant dirs bottom-up chmod/fsync 0550；root暂留0700；
8. internal `PUBLISH_COMPLETE.json`在private temp写满、fsync、chmod 0440，再no-replace link至
   final root；它绑定prepared SHA与payload inventory SHA，且不属于payload inventory；
9. fsync root，root chmod/fsync 0550，再fsync parent；
10. sibling `.<target>.COMMITTED.json`在private temp写满、fsync、chmod **0440**，atomic
    no-replace publish后再次fsync parent。

sibling COMMITTED是唯一durability commit point，内容绑定target、prepared SHA、completion SHA、
payload inventory SHA、final mode和自身schema。loader取得同一publish lock后验证PREPARED、
internal completion、sibling COMMITTED、所有hash/inventory以及：

- payload files/internal marker/sibling COMMITTED均0440；
- final root/descendant dirs均0550；
- COMMITTED前绝不读取。

existing identical返回existing；不同bytes/type/mode/hash为conflict HOLD。COMMITTED后不允许更改
payload inode。

### 3.2 Crash recovery

- internal marker前：same prepared claim可补齐payload；
- marker后/COMMITTED前：只允许完成root mode、parent fsync和COMMITTED；
- COMMITTED后：只验证；
- missing staging且无法从同一sealed inputs精确重建：HOLD；
- 任一conflict：HOLD，不覆盖、删除或quarantine final。

### 3.3 Capacity reservation 与安全清理

runtime policy固定正整数：

```text
per_attempt_staging_byte_cap
aggregate_staging_byte_threshold
minimum_free_filesystem_bytes
```

logical byte count定义为staging inventory内regular file `st_size`之和；hardlink只计staging目录项
指向的logical bytes一次。开始copy/extract前在独立GC lock内：

1. no-follow扫描同一staging root下全部attempt；
2. 对每个attempt重算logical bytes并验证inventory（无inventory的partial attempt按实际文件计）；
3. 要求expected bytes不超过per-attempt cap；
4. 要求current aggregate + expected bytes不超过aggregate threshold；
5. `statvfs` available bytes减expected bytes后不得低于minimum free bytes；
6. 写no-replace reservation并fsync；reservation包含attempt ID、expected bytes、policy SHA。

任一条件失败则在创建新staging目录、registration/journal/output/fit前拒绝。copy/extract过程中每写一
file后更新实际计数；超cap立即失败并进入清理。

只有sibling COMMITTED已通过完整验证后才清理该transaction的private staging。清理在GC lock内：
只把private staging **directories** chmod 0700，然后从root directory FD no-follow、bottom-up
unlink directory entries/rmdir；不得chmod、truncate或写任何regular file，因为它可能与final
payload hardlink共享inode。清理失败只写durable warning并保留容量计数；aggregate threshold会
阻止后续attempt，不能静默忽略。定向GC只能处理已COMMITTED且验证通过的staging，绝不处理final
tree、未commit transaction或其他root。

## 4. Generation activation、run artifacts 与 terminal

### 4.1 无环 AuthorityGenerationCommitV2

global registry仍只有连续：

```text
authority-generations/0000000000000001.json
authority-generations/0000000000000002.json
...
```

publication DAG严格单向：

```text
authority + inert root
  -> registration
  -> generation commit  [唯一activation]
  -> optional activation receipt [只读下游证明]
```

`registration.json`只绑定：

- generation number和previous generation commit SHA（首代为canonical null）；
- immutable authority root/path/hash；
- run_id、linear event-plan hash；
- journal/snapshot/output roots；
- ledger H0、M6 prefix、issuer/policy SHA。

registration **不得**包含current generation commit path/hash或activation receipt hash。

generation commit随后绑定generation number、previous commit SHA、registration path/hash、
authority path/hash、run_id、plan hash、prior terminal path/hash、H0/M6 prefix与issuer/policy
SHA。它在global control lock内atomic no-replace最后发布，是唯一activation point。

可选`activation-receipt.json`只能在commit后创建，绑定commit path/hash、registration SHA、
observed contiguous registry head和验证时间；它不是activation条件，commit/registration都不得
反向绑定它。这样canonical bytes和SHA可按拓扑顺序计算，不存在自引用或hash环。

在global control lock内扫描所有连续commits，验证run_id从未出现、previous commit/terminal、
current ledger head和generation number。commit前inert root无权威；same bytes可resume，不同bytes
conflict。commit后retry只返回existing。generation gap或parent不一致FAIL。

### 4.2 Canonical event artifacts

M6.5只接受authority `purpose=M6_5_SYNTHETIC_TEST_ONLY`。任何LIVE/M7 purpose或live fixed slot
不存在时，在registration/journal/output/claim前抛`LiveRunAuthorityNotFrozen`。

每generation root固定：

```text
authority.json
registration.json
activation-receipt.json
snapshots/<zero-padded-seq>.json
receipts/<event_key>.json
claims/<event_key>.json
outcomes/<event_key>.json
run-terminal.json
```

```text
event_key = sha256(
  registration_sha256 UTF-8 + 0x1f + source_event_id UTF-8
)
```

所有object使用atomic file no-replace。snapshot绑定完整journal prefix、previous snapshot、
ordered source events和expected head；receipt绑定snapshot、H_before/H_after、appended event
IDs/counts；claim绑定receipt/source event/attempt identity；outcome绑定claim及
COMPLETED/FAILED/CLAIMED_INTERRUPTED。相同bytes idempotent，不同bytes conflict。

### 4.3 Worker与 Idempotent TerminalReconcilerV1

实际副作用worker直接持server-wide execution lease：

1. lease；
2. global control→ledger locks；
3. 验generation commit/registration/head/plan/caps及全部前序COMPLETED；
4. append/recover batch+receipt；
5. fresh claim；
6. 释放global/ledger但保留lease；
7. worker执行fake observer并写/fsync outcome；
8. 重新取得global→ledger locks并进入terminal decision；
9. 最后释放lease。

parent无claim/outcome权限。worker死亡后lease由OS释放；recovery若见claim无outcome，写
CLAIMED_INTERRUPTED，不重放。

reconciler验证generation commit、registration、current ledger head、全部receipt/claim/outcome和
linear plan：

- all events COMPLETED：no-replace发布`CLOSED`；
- first FAILED或CLAIMED_INTERRUPTED：no-replace发布`ABANDONED`，其后events列UNUSED；
- completed但尚有next event：不发布terminal；
- outcome/partition/head冲突：FAIL。

terminal绑定registration/generation、status、last receipt/head、每个plan event的exact
`COMPLETED/FAILED/CLAIMED_INTERRUPTED/UNUSED` partition与reason，fsync后生效。terminal缺失时
可确定性补写；existing identical返回existing。下一generation只接受前代CLOSED或ABANDONED。
M7固定CCC、Gate两个generation；CCC terminal后Gate按预注册derived contract继续，不做replacement。

## 5. No-site trusted replay bootstrap

launcher以显式env dict实现`env -i`等价。允许变量：

```text
LANG=C.UTF-8
LC_ALL=C.UTF-8
TZ=UTC
PYTHONHASHSEED=0
PYTHONNOUSERSITE=1
PYTHONDONTWRITEBYTECODE=1
CUBLAS_WORKSPACE_CONFIG=:4096:8
CUDA_VISIBLE_DEVICES=<bound ordinal>
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
NUMEXPR_NUM_THREADS=1
HOME=<attempt work/home>
TMPDIR=<attempt work/tmp>
LD_LIBRARY_PATH=<trusted runtime policy exact value, or absent>
```

HOME/TMPDIR启动前建0700且位于attempt root。无proxy、PYTHONPATH或额外变量。argv固定：

```text
<trusted absolute python> -B -S -s -P <staged absolute bootstrap>
  --worker <staged absolute worker>
  --invocation <staged absolute invocation>
```

bootstrap本身是hash-bound、stdlib-only单文件；其SHA、expected stdlib `sys.path`和trusted
site-package absolute directory list由runtime policy固定。worker尚未import/执行前bootstrap：

1. 验证`sys.flags.no_site=1,no_user_site=1,safe_path=1,ignore_environment=0,
   dont_write_bytecode=1`；
2. 验证`site/sitecustomize/usercustomize`均不在`sys.modules`；
3. 验证当前`sys.path`与runtime policy的stdlib-only roots逐项exact一致且均位于trusted runtime；
4. 验证executable、version、argv、env digest、hash sentinel、CUDA identity、HOME/TMPDIR mode/path；
5. 仅以`sys.path.insert`加入runtime policy列出的exact trusted package directories。

禁止import `site`、调用`site.addsitedir`或处理任何`.pth`；加入后逐目录验证realpath/device/
owner/mode及closure manifest SHA，再用stdlib `runpy.run_path`执行hash-bound worker。任何startup
hook/module已加载、path多余、`.pth`处理迹象或binding不符，均在worker/import side effect前FAIL。

child回报pre/post-bootstrap path digests、observed env、flags、module origins、runtime/CUDA/
tempdir identity；outer validator逐项复核。input/output按§3事务。每fold score canonicalization与
v29 §5相同；PASS仍要求14 replay、0 fit、ledger unchanged、max date<C、CUDA only。

## 6. 当前 M7 v8 bundle

- `m7_change_design_v8.md`
  SHA `9a5a3c5d1034efdb947f744d124a80e8657ee9c303f6021ffaff02dc77ebbebc`
- `m7_behavior_to_test_matrix_v8.md`
  SHA `932ac1b4dc61e58bf1fd860402d64c5e7d39eafceb37b3563c61c6cd281a7d89`

v8自包含冻结：

1. exact fixed17、exact B001–B004、一T一official FUTURE_POISON manifest；
2. supplement、aux-prefix verifier、review receipt三个closed schemas及canonical hashing；
3. security-lifecycle availability fixed authority；当前缺失必须HOLD，禁止event-date推断；
4. state exact四列、exact-date join、同日bytes一致与side-effect前validation；
5. sorted unique training-date、float64 mean/population std、scale与checkpoint binding；
6. CCC/Gate两个连续独立generations、generic拒绝、special loader与完整CCC；
7. first-event prerequisites、0 replacement及`6/44 -> max8/60`。

M6.5只实现matrix中`M6.5_CONTRACT_ONLY`项目；M7实现和真实接受仍未授权。

## 7. v29 blockers closure 与 verdict

| v29 review blocker | v30 closure |
| --- | --- |
| generation/registration hash DAG | §4.1 registration→commit→receipt单向拓扑 |
| system `.pth/sitecustomize` startup | §5 `-S` + stdlib-only verified bootstrap |
| state join/standardizer不完整 | M7 v8 §3.1–§3.2及matrix STATE/STD |
| aux prefix无证明面 | §2.1 + M7 v8 §2.2/§2.4 exact AP001–AP004 |
| supplement/review receipt非closed | M7 v8 §2.3/§2.5 strict schemas |
| lifecycle availability不可推断 | §2.2 + M7 v8 §2.6 absent→HOLD |
| staging cleanup/capacity/marker mode | §3.1–§3.3，sibling marker固定0440 |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。这不是M6.5 PASS，不授权测试实现以外的产品动作。
