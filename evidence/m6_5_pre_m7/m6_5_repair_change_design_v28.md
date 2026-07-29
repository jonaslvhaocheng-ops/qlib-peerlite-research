# M6.5 有界修复变更设计 v28

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v27作为canonical subject；v27及失败审查保留。

## 1. 精确 normative composition

v28由以下两个固定层组成：

1. base：`m6_5_repair_change_design_v27.md` exact SHA
   `1517a81b731444e5c9a8528566d1e2fe97da9f183b9838441d6706a68051ced9`；
2. 本文件的精确replacement。

保留v27：§1、§2、§3.1–§3.4、§4、§5.1、§7.1–§7.2、§9。

精确替换：

| v27 | v28 replacement |
| --- | --- |
| §3.5 | 本文件§2 |
| §5.2 | 本文件§3 |
| §6全部 | 本文件§4 |
| §7.3全部 | 本文件§5 |
| §8全部 | 本文件§6 |

不存在“对应段落”或隐式继承；未列入保留的v27内容不再normative。v28仍不授权test-design前的
实现、replay、M7、fit、budget或final-OOS。

## 2. ProtectedPrefixV2(T) 与 canonical sort

future-poison统一使用**per-T prefix oracle**，不再要求whole pre-C table不变。

每个behavior request必须冻结一个或多个`protected_through=T`。mutation只允许改变
`vendor_available_time > T`的字段/row；availability由v27 §3.3–§3.4政策判定：

- membership/status：pre-T公告携带的future effective value视为已可得，禁止mutation；
- missing publication的event在effective date可观察时按UNKNOWN；
- security list/delist按event date可得；
- action在ex-div date 09:00可得；
- daily quote在T收盘数据截止可得；
- calendar由冻结calendar snapshot identity保护，不作为per-T poison mutation对象。

比较面：

1. 每个aux table只比较其`availability_time<=T`的projected rows/fields canonical prefix；
2. population/state只比较`datetime<=T`的keys、counts、values和logical digest；
3. `>T` rows/digests允许变化；
4. mutation ledger逐项记录source field、before/after、availability、T和为何允许；
5. original/probe必须使用相同policy/code/env和相同T。

实际qualification behavior request绑定exact horizon list；B004验证每个T的protected prefix。
adapter unit/property tests另覆盖每类clock/event边界。由此不混用cutoff-wide与per-T oracle。

Canonical sort逐列固定：

- null永远排在nonnull之后；
- string先NFC，按UTF-8 bytes lexicographic；
- date按Unix epoch以来signed day ordinal；
- bool `false < true`；
- 多列按schema列顺序lexicographic；
- exact duplicate在sort前dedup，冲突规则沿用v27。

JSONL仍按schema顺序序列化；prefix manifest绑定T、row count、key digest、value/logical digest。

## 3. Nested PreparedDirectoryTransactionV2

### 3.1 Inventory与输入限制

prepared claim的expected inventory同时包含：

- directory item：`{type:"directory",relative_path,final_mode:"0550"}`；
- regular file item：
  `{type:"file",relative_path,byte_length,sha256,final_mode:"0440"}`。

path必须normalized UTF-8 POSIX relative path，拒绝空组件、`.`、`..`、absolute、duplicate及
prefix type conflict；sort按UTF-8 path bytes，同path不允许两item。input/output都只允许
directory与regular file，拒绝symlink/hardlink source outside staging/device/FIFO/socket。

固定siblings仍为publish lock、PREPARED、final root与completion。prepared还绑定完整directory
inventory、private staging inventory、policy/code/content UUID。

### 3.2 Publish/recovery

在parent publish lock内：

1. private staging dirs保持`0700`，files写满/fsync并设`0440`；
2. no-replace发布prepared；same bytes可resume，不同conflict；
3. final root及descendant dirs按depth top-down以`0700`创建；
4. 逐file从staging执行no-follow hardlink；existing必须type/size/hash一致；
5. fsync files，再按depth bottom-up fsync dirs；
6. files确认为`0440`，descendant dirs bottom-up chmod/fsync为`0550`，root暂留`0700`；
7. no-replace发布`PUBLISH_COMPLETE.json`并fsync root；
8. root chmod/fsync为`0550`，fsync parent。

loader要求prepared、completion、inventory、所有final modes均一致；marker存在但root/descendant
mode未完成时仍拒读。

crash recovery只在same claim+lock下：

- missing dir/file按同顺序补齐；
- 若需在已0550目录补file，先验证已有contents，再临时chmod 0700，补齐后恢复0550；
- marker后只允许完成mode/fsync校验，不允许改payload；
- conflict HOLD，不覆盖/删除/quarantine。

commit后private dirs可chmod 0700并unlink directory entries，不修改hardlinkedinode；失败计容量。
input和output均使用本协议。

## 4. AuthorityGenerationCommitV1 与线性event plan

### 4.1 单一commit point

取消run-index文件。global registry只有：

```text
authority-generations/0000000000000001.json
authority-generations/0000000000000002.json
...
```

每个generation commit绑定：

- generation number与previous commit SHA；
- immutable authority root/path/hash；
- registration path/hash、run_id、linear event-plan hash；
- prior generation terminal path/hash；
- ledger H0与M6 prefix；
- issuer/policy hash。

在global control lock内扫描所有连续commits，验证run_id从未出现、latest generation已有terminal、
current ledger head匹配。新root中的authority/registration先以no-replace inert files发布；
**generation commit最后发布，是唯一activation/commit point**。

crash：

- commit前：inert root无权威；same request可按exact bytes resume，不同bytes conflict；
- commit后：generation已激活，retry只返回existing；
- generation number不连续、previous/terminal/hash不符FAIL。

不存在可部分激活的run-index/registration组合，也无mutable active pointer。每root只一个run。

### 4.2 无conditional retry的事件状态机

event plan是固定线性序列，不含conditional retry。实际副作用worker直接取得并持有server-wide
execution lease，parent launcher没有claim/outcome写权限。worker固定顺序：

1. 取得execution lease；
2. 取得global control lock，再取得ledger lock；
3. 验generation/registration/current head/linear plan/caps；
4. 要求所有前序event已有durable COMPLETED outcome；
5. append或exact recover ledger batch与receipt；
6. no-replace发布claim；只有fresh CREATED可执行；
7. 释放global/ledger，worker继续持execution lease；
8. worker执行fake observer，并no-replace写durable outcome、fsync；
9. 释放execution lease。

parent死亡不影响worker lease；worker死亡由OS释放lease。recovery worker取得lease后若发现claim
存在但无outcome，发布CLAIMED_INTERRUPTED且不重放原attempt。

结果规则：

- outcome COMPLETED：可进入下一event；
- outcome FAILED或CLAIMED_INTERRUPTED：run立即ABANDONED/HOLD；
- terminal将所有remaining events标UNUSED并给reason；
- 不启动replacement event；
- terminal的COMPLETED/FAILED/CLAIMED_INTERRUPTED/UNUSED exact partition整个plan。

M6.5 synthetic fake observer也使用线性plan。future M7的16 fits没有replacement；若要retry须新
用户预算CR和新authority generation。

## 5. Replay clean launcher、retry与score

replay继续是只读、可安全以新verification attempt ID重跑，不用exactly-once状态机。

launcher以subprocess显式env dict实现`env -i`等价，只允许：

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
HOME=<attempt private work/home>
LD_LIBRARY_PATH=<exact value from trusted runtime policy, or absent>
```

无proxy、PYTHONPATH、sitecustomize或额外变量。完整argv固定为：

```text
<trusted absolute python> -I -B <staged absolute worker>
  --invocation <staged absolute invocation>
```

binding/launcher record写exact argv、允许变量（HOME以attempt-relative token canonicalize）和
environment digest；child启动后回报并复核实际argv/env/runtime。

input/work/output、runtime closure和safe extraction沿用v27 §7.1–§7.2及本文件nested transaction。
score normalize为timezone-naive datetime、canonical instrument string、unique key、
`(datetime,instrument)` stable升序、finite native float64。key digest逐行：
`timestamp.isoformat UTF-8 + 0x1f + instrument UTF-8 + newline`；score digest逐行在key后加
`0x1f + float(value).hex() ASCII + newline`。expected/replay使用相同index并
`np.array_equal(float64 arrays)` exact。PASS仍要求14 replay、0 fit、ledger unchanged、
max date<C、CUDA only。

## 6. 当前M7 v6 bundle

- `m7_change_design_v6.md`
  SHA `a2614e2050abf9e51e945ff33c37fedab7f1bca00e1142a46c5313d056231238`
- `m7_behavior_to_test_matrix_v6.md`
  SHA `6d04df448757519596fd57a27dff47050bfd89a6a6ad8440eee59b512b66c984`

v6冻结：

1. exact fixed check IDs：
   `I001,I002,S001,T001,T002,T003,U001,U002,C001,M001,A001,H001,Q001,Q002,Q003,L001,L002`；
2. exact behavior IDs `B001,B002,B003,B004`；
3. parent PIT manifest承载PRODUCTION_CLI/test-only=false；
4. official behavior manifest保持closed schema，另以外部independent review receipt绑定；
5. 当前16-fit预算内任一失败/中断即分支HOLD，0 replacement；
6. Gate create/reload、完整CCC公式、first-event prerequisites与test owner保持。

M6.5只实现contract-only tests，不写M7 production code。

## 7. Closure 与 verdict

| v27 finding | v28 closure |
| --- | --- |
| poison horizon | §2单一per-T prefix oracle |
| nested dirs | §3 typed dir/file inventory与top-down/bottom-up recovery |
| generation crash | §4单一generation commit activation |
| conditional skip | §4线性plan，失败即HOLD，无skip后继续 |
| retry超预算 | §4/§6明确0 replacement |
| 17+4 identity/schema | §6 exact IDs、parent字段、外部review receipt |
| nullable sort | §2 null/UTF-8/date/bool规则 |
| clean launcher | §5 env allowlist、argv/env digest |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。这仍不是M6.5 PASS或M7授权。
