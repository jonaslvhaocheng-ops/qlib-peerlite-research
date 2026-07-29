# M6.5 有界修复变更设计 v29

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v28；历史版本与失败审查保留。

## 1. 精确 composition

base是v28 exact SHA
`d9851b71e2688645538b03eadc282480add1706329db0583e66bd5a064f6db39`。

保留v28：§1、§3.1。精确替换：

| v28 | v29 |
| --- | --- |
| §2 | 本文件§2 |
| §3.2 | 本文件§3 |
| §4全部 | 本文件§4 |
| §5全部 | 本文件§5 |
| §6全部 | 本文件§6 |
| §7全部 | 本文件§7 |

v28通过其§1固定的v27 base/replacements继续提供未被本表替换的normative内容。没有隐式段落
选择。v29不授权实现、replay、M7、fit、budget或final-OOS。

## 2. Official single-horizon ProtectedPrefixV3

每个official behavior request/manifest只允许一个scalar
`protection.protected_through=T`。需要多个T时，future derived contract冻结exact unique
horizon list，并要求一T一manifest；envelope按T升序绑定完整manifest list。

每个manifest必须`probe_type=FUTURE_POISON`。mutation只改
`vendor_available_time>T`的字段/row；比较aux availability-projected prefix及
population/state `datetime<=T`的keys/counts/values/digests，`>T`允许变化。

official perturbation ledger保持closed schema。额外
`BehaviorAvailabilitySupplementV1`逐项绑定source field、before/after、availability、T与允许
理由，并绑定official ledger/manifest SHA；它不是official manifest的一部分。

availability规则、calendar不可poison、canonical null/string/date/bool sort与JSONL规则保持v28
§2其余定义。original/probe必须同policy/code/env。B004逐manifest验证该单一T prefix。

## 3. Durable Nested Directory CommitV3

typed directory/file payload inventory与path限制使用保留的v28 §3.1。完整publish步骤为：

1. private staging dirs保持0700，regular files写满/fsync/chmod 0440；
2. prepared claim绑定target、schema、content UUID、directory/file payload inventory、staging
   inventory和policy/code SHA，并在parent publish lock下no-replace发布；
3. final root/descendant dirs按depth top-down以0700创建；
4. regular files从staging no-follow hardlink；existing必须type/size/hash相同；
5. fsync files，再bottom-up fsync dirs；
6. files确认0440，descendant dirs bottom-up chmod/fsync 0550，root暂留0700；
7. 执行下述completion与durability commit。

唯一commit语义：

- payload inventory**不含**`PUBLISH_COMPLETE.json`；
- internal completion marker内容固定绑定prepared SHA与payload inventory SHA，先在private
  temp写满/fsync/chmod `0440`，再no-replace link到final root；
- root仍0700时发布internal marker并fsync root，随后root chmod/fsync 0550，再fsync parent；
- 最后以atomic file no-replace发布sibling
  `.<target>.COMMITTED.json`，内容绑定target path、prepared SHA、completion SHA、payload
  inventory SHA和final mode；其helper再次fsync parent；
- sibling COMMITTED是唯一durability commit point。

loader必须取得同一个publish lock，并同时验证PREPARED、internal completion、sibling
COMMITTED、payload inventory、marker0440与所有directory/file modes；COMMITTED前永不读取。

crash recovery：

- internal marker前：same claim补payload；
- marker后/COMMITTED前：只完成root mode、parent fsync与COMMITTED；
- COMMITTED后：只验证，不能改payload；
- conflict HOLD。

input/output均使用该协议。

## 4. Canonical run artifacts、worker与terminal reconciler

### 4.1 Synthetic/live guard与paths

M6.5只接受authority
`purpose=M6_5_SYNTHETIC_TEST_ONLY`。任何LIVE/M7 purpose或固定live slot不存在时，在
registration/journal/output/claim前抛`LiveRunAuthorityNotFrozen`。

每generation root固定：

```text
authority.json
registration.json
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

所有object使用atomic file no-replace。registration绑定generation commit、run_id、linear plan、
journal/snapshot/output roots、H0和M6 prefix。snapshot绑定完整journal prefix、previous snapshot、
ordered source events和expected head。receipt绑定snapshot、H_before/H_after、appended event IDs/
counts。claim绑定receipt/source event/attempt identity。outcome绑定claim与
COMPLETED/FAILED/CLAIMED_INTERRUPTED。相同bytes idempotent，不同bytes conflict。

AuthorityGenerationCommitV1的单一activation、generation continuity与inert-root recovery沿用
v28 §4.1。

### 4.2 Worker与linear plan

实际副作用worker直接持server-wide execution lease：

1. lease；
2. global control→ledger locks；
3. 验generation/registration/head/plan/caps及全部前序COMPLETED；
4. append/recover batch+receipt；
5. fresh claim；
6. 释放global/ledger但保留lease；
7. worker执行fake observer并写/fsync outcome；
8. 进入terminal decision；
9. 最后释放lease。

parent无claim/outcome权限。worker死亡后lease由OS释放；recovery若见claim无outcome，写
CLAIMED_INTERRUPTED，不重放。

### 4.3 Idempotent TerminalReconcilerV1

worker写outcome后仍持lease，重新取得global→ledger locks并运行terminal reconciler。任何crash
后的recovery worker也可按相同锁顺序重入。

reconciler验证generation commit、registration、current ledger head、全部receipt/claim/outcome
和linear plan：

- all events COMPLETED：no-replace发布`CLOSED`；
- first FAILED或CLAIMED_INTERRUPTED：no-replace发布`ABANDONED`，其后全部events列UNUSED；
- completed但尚有next event：不发布terminal；
- outcome/partition/head冲突：FAIL。

terminal绑定registration/generation、status、last receipt/head、每个plan event的exact
`COMPLETED/FAILED/CLAIMED_INTERRUPTED/UNUSED` partition与reason，fsync后生效。terminal缺失时
可确定性补写；existing identical返回existing。下一generation只接受前代CLOSED或ABANDONED。

当前M7固定两个generation：CCC generation terminal后，Gate generation按预注册derived
contract继续，无论前者CLOSED还是ABANDONED。每generation内部无replacement。

## 5. Effective clean replay launcher

显式env dict实现`env -i`等价。允许变量：

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

HOME/TMPDIR启动前建为0700且位于attempt root。无proxy/PYTHONPATH/额外变量。argv：

```text
<trusted absolute python> -B -s -P <staged absolute worker>
  --invocation <staged absolute invocation>
```

不用`-I`，所以PYTHONHASHSEED生效；`-s/-P`与无PYTHONPATH阻止user site/unsafe prepend。
runtime policy冻结seed=0下的
`hash("qlib-peerlite-replay-sentinel")` expected value。child回报：

- exact observed env digest；
- `sys.flags.no_user_site=1,safe_path=1,ignore_environment=0,dont_write_bytecode=1`；
- hash sentinel；
- `tempfile.gettempdir()` resolved在bound TMPDIR；
- argv/runtime/module/CUDA identity。

outer validator逐项复核。input/output事务使用本文件§3；read-only replay可用新verification
attempt安全重跑。

每fold expected/replay均normalize timezone-naive datetime、canonical instrument string、
unique key、`(datetime,instrument)` stable升序与finite native float64。key digest逐行：
`timestamp.isoformat UTF-8 + 0x1f + instrument UTF-8 + newline`；score digest在key后加
`0x1f + float(value).hex() ASCII + newline`。相同index且
`np.array_equal(float64 arrays)` exact。PASS要求14 replay、0 fit、ledger unchanged、
max date<C、CUDA only。

## 6. 当前M7 v7 bundle

- `m7_change_design_v7.md`
  SHA `ee5cf78709abaeee910fa7fe6c9bbaea8e6deae42e33b96785db4739b3985d06`
- `m7_behavior_to_test_matrix_v7.md`
  SHA `9bd49a3257f216fcbb2a9a744b322ddd20326fa815a689b78a6821a5dd67d5bf`

v7自包含冻结：

1. 每T一个official FUTURE_POISON manifest、exact 17+4、supplement与independent review receipt；
2. CCC/Gate两个连续独立generations，前者terminal后后者仍执行；
3. generic拒绝、专用create/reload签名、完整checkpoint bindings；
4. unique-date standardizer与scale规则；
5. 完整CCC公式、float32 input/float64 accumulation+return；
6. first-event prerequisites、0 replacement及`6/44 -> max8/60`。

M6.5只实现contract-only tests。

## 7. Closure 与 verdict

| v28 blocker | v29 closure |
| --- | --- |
| official single horizon/probe | §2一T一manifest + FUTURE_POISON |
| event identities/live guard | §4.1 canonical slots/schema/guard |
| terminal recovery | §4.3 idempotent reconciler |
| branch mapping | §4.3与M7 v7两个generations |
| M7 contract regression | §6绑定self-contained v7 |
| marker/durability | §3 marker0440 + sibling COMMITTED + loader lock |
| effective hash seed/TMPDIR | §5去-I、flags/sentinel/private TMPDIR |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。仍不等于M6.5 PASS或M7授权。
