# M6.5 有界修复变更设计 v31

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Owner：`/root`
- Requirement：`contracts/changes/m6_5_pre_m7_quality_gate_v1.json`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v30；历史版本与失败审查保留。

## 1. 精确 composition

base为v30 exact SHA：

```text
28bab313bc07f4d9ffc838a0256f8dbc8f71fb86df320dc31f206c87e7f1746b
```

精确composition：

| v30 section | v31 action |
| --- | --- |
| §1 | 由本文件§1完整替换 |
| §2 | 由本文件§2完整替换 |
| §3.1–§3.2 | 逐字保留 |
| §3.3 | 由本文件§3完整替换 |
| §4.1 | 由本文件§4完整替换 |
| §4.2–§4.3 | 逐字保留 |
| §5 | 由本文件§5完整替换 |
| §6 | 由本文件§6完整替换 |
| §7 | 由本文件§7完整替换 |

v30未替换的normative ancestry继续有效；本表之外无隐式选择。v31不授权产品实现、server replay、
M7、fit、budget变更或final-OOS。

## 2. Behavior qualification 的完整机械证明

future derived contract冻结exact unique horizons；一T一official FUTURE_POISON manifest，official
schema保持不变。完整资格算法与closed schemas以本文件§6绑定的M7 v9 §2为唯一规范：

1. official state `feature_value_json`是`float64.hex()`的JSON **string scalar**，不是object；
2. adapter source放`code_or_query`，T/列序/input manifest SHA/projection spec放`parameters`，
   runtime放`environment`，outputs/snapshots/ledger/receipt使用official既有十slots，不增加key；
3. `BehaviorAvailabilitySupplementV1`逐mutation/field绑定availability；
4. `AuxPrefixBehaviorVerificationV2`把aux、population、state作为exact三个products，分别保存
   baseline/probe schema、key count/digest、value digest、logical digest与equality；
5. AP verifier按M7 v9 §2.4的record views、`LP(uint64 big-endian length)`和canonical JSON算法从
   bound manifests重算；exact AP001–AP004和全部15个equality必须PASS/true，status-only拒绝；
6. review receipt只通过hash DAG证明其复核的exact bytes，不再以filesystem mtime或自报时间声称
   durable publication order；
7. `SecurityLifecycleAvailabilityAuthorityV1`、availability JSONL和independent validation
   receipt使用M7 v9 §2.6的strict shapes、SLA001–SLA006、exact md_security coverage和per-
   prediction-time visibility replay。

security authority使用`statement_sha256 -> validation receipt -> final authority canonical_sha256`
单向DAG。LIST_DATE/DELIST_DATE不允许event-date availability推断。当前fixed slot不存在，因此
只能实现negative fail-closed validator；真实qualification必须HOLD。

## 3. CapacityReservationV2 与 orphan lifecycle

### 3.1 Append-only paths and state

每attempt固定目录：

```text
staging-reservations/<attempt_id>/RESERVED.json
staging-reservations/<attempt_id>/MATERIALIZING.json
staging-reservations/<attempt_id>/COMMITTED.json
staging-reservations/<attempt_id>/ABORTED.json
staging-reservations/<attempt_id>/RELEASED.json
```

全部atomic no-replace、0440、fsync file+directory。attempt ID来自invocation SHA且只能含
`[a-z0-9-]`。`RESERVED`绑定expected logical bytes、transaction target、private staging path、
attempt lease path、runtime policy SHA和source inventory SHA。`MATERIALIZING`绑定RESERVED SHA。
`COMMITTED`绑定MATERIALIZING SHA及v30 §3.1 sibling COMMITTED SHA。`ABORTED`绑定最新state SHA、
reason和“PREPARED/final均不存在”验证receipt。`RELEASED`绑定COMMITTED或ABORTED SHA、cleanup
receipt和post-cleanup zero-entry verification。

合法状态：

```text
RESERVED -> MATERIALIZING -> COMMITTED -> RELEASED
RESERVED -> ABORTED -> RELEASED
RESERVED -> MATERIALIZING -> ABORTED -> RELEASED
```

COMMITTED与ABORTED互斥；RELEASED恰绑定一个terminal。PREPARED一旦存在，不允许ABORTED，只能按
v30 §3.2 exact transaction recovery至COMMITTED或HOLD。

### 3.2 Admission without overcommit

runtime policy继续固定：

```text
per_attempt_staging_byte_cap
aggregate_staging_byte_threshold
minimum_free_filesystem_bytes
```

expected bytes在读取source inventory或安全解压目录表后、创建staging前精确计算。每个regular
file只计一次`st_size`；写入前若next total会超过expected或per-attempt cap，禁止该write并走
owner abort。

admission与所有state transition均在GC lock内；attempt执行期间另持attempt lease。每次admission
no-follow扫描全部reservation与private staging。对每个**没有RELEASED**的attempt：

```text
active_charge = max(RESERVED.expected_logical_bytes, actual_staging_logical_bytes)
```

current aggregate是所有active_charge之和，不再另加裸staging scan，避免双计；无reservation的
orphan staging按actual bytes作为synthetic active charge并阻止新admission，直到按§3.3归属处理。
新attempt必须同时满足：

```text
expected <= per_attempt_cap
current_aggregate + expected <= aggregate_threshold
statvfs_available
 - sum(max(0, expected_i - actual_i) for every active reservation)
 - new_expected
 >= minimum_free_filesystem_bytes
```

然后在同一GC lock临界区发布RESERVED。并发attempt必然看到对方未RELEASED reservation，不能
超卖。MATERIALIZING在创建private staging前发布；actual在每个file写前/后重算且始终
`actual<=expected`。

### 3.3 Recovery, owner abort and post-commit cleanup

crash recovery先nonblocking取得attempt lease，再取得GC lock：

- 只有RESERVED且无staging/PREPARED/final：same attempt可resume；否则发布ABORTED，再RELEASED；
- MATERIALIZING但无PREPARED/final：可resume，或发布ABORTED后owner cleanup；
- PREPARED存在：禁止abort/GC，只允许v30 §3.2 same-claim recovery；conflict HOLD并保持charge；
- sibling COMMITTED验证通过：发布COMMITTED（若缺失），执行post-commit cleanup；
- terminal存在但RELEASED缺失：重入对应cleanup。

**owner abort cleanup**只适用于PREPARED和任何final path都不存在的RESERVED/MATERIALIZING
attempt。持attempt lease+GC lock，从private root FD no-follow确认目录归属和inventory；先发布
ABORTED，然后只chmod private directories 0700、bottom-up unlink entries/rmdir，不chmod/
truncate/write regular files，最后zero-entry验证并发布RELEASED。copy超cap/expected、source
TOCTOU或安全解压失败都走此路径。

**post-commit cleanup**只适用于sibling COMMITTED完整验证通过的attempt，沿用v30 §3.3的
directory-only chmod及unlink-only规则，成功后发布RELEASED。cleanup失败写durable warning，
不得发布RELEASED，reservation继续按active_charge计费并可重入。

无reservation的orphan只在取得其attempt lease、证明path位于fixed staging root、且PREPARED/
final均不存在后，先生成synthetic RESERVED+ABORTED再按owner cleanup；无法证明归属则HOLD且
继续计容量。绝不按age/PID猜测，不处理其他root或final tree。

## 4. AuthorityGenerationCommitV3 exact hash boundary

publication DAG仍为：

```text
authority.json -> registration.json -> generation commit -> optional activation receipt
```

取消所有`authority root hash`字段。registration exact绑定：

- generation number、previous generation commit SHA（首代canonical null）；
- `authority_file_path=<generation-root>/authority.json`；
- `authority_file_sha256`，只对authority.json exact bytes计算；
- generation root relative path（仅定位，不作内容hash）；
- run_id、linear plan SHA、journal/snapshot/output roots；
- ledger H0、M6 prefix、issuer/policy SHA。

registration不得绑定current commit/activation receipt，也不得hash包含自身的directory inventory。
generation commit绑定registration path/SHA、同一authority_file path/SHA及v30 §4.1其余
generation/previous/prior-terminal/H0字段。optional receipt只下游绑定commit和registration。

commit前generation root只允许authority.json、registration.json及其directory fsync痕迹；event
artifacts只能在commit激活后创建。registry扫描直接复核两个file hashes和单向DAG。这样root后续
加入event artifacts不改变authority或registration binding，也没有自引用。

## 5. Replay bootstrap 与完整 score canonicalization

### 5.1 Bootstrap

launcher以显式env dict实现`env -i`等价，允许变量exact为：

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

HOME/TMPDIR启动前建0700并位于attempt root；无proxy、PYTHONPATH或额外变量。唯一argv：

```text
<trusted absolute python> -B -S -s -P <staged absolute bootstrap>
  --worker <staged absolute worker>
  --invocation <staged absolute invocation>
```

bootstrap是hash-bound、stdlib-only单文件；其SHA、expected stdlib sys.path和trusted package
absolute directories由runtime policy固定。它在任何worker/package import前验证：

- `no_site=1,no_user_site=1,safe_path=1,ignore_environment=0,dont_write_bytecode=1`；
- site/sitecustomize/usercustomize未加载；
- stdlib-only sys.path、executable/version、argv/env/hash sentinel、CUDA、HOME/TMPDIR；
- 当前sys.path逐项exact匹配policy且每项位于trusted runtime；
- 然后只用`sys.path.insert`加入exact trusted package dirs，逐目录验证realpath/device/owner/
  mode及closure manifest SHA，禁止import site、`site.addsitedir`和`.pth`；
- 以stdlib `runpy.run_path`执行hash-bound worker。

child/outer receipt绑定pre/post path digests、module origins和全部runtime observations。input/output
继续使用v30 §3.1–§3.2及本文件§3 reservation。

### 5.2 ScoreReplayCanonicalV1

expected与replay对每fold分别执行完全相同算法：

1. 只接受列`datetime,instrument,score`；row count必须大于0；
2. datetime解析后必须表示日频session。aware值先转换`Asia/Shanghai`，再取本地calendar date并
   表示为timezone-naive midnight；naive值直接normalize到midnight；
3. instrument必须是NFC、strip前后相同、non-empty UTF-8 string；禁止隐式数值转string；
4. score显式转native-endian IEEE-754 float64；null、NaN、±Inf拒绝；
5. `(datetime,instrument)`必须unique；按datetime升序、instrument UTF-8 bytes升序做稳定排序；
6. timestamp string固定`YYYY-MM-DDT00:00:00`。

逐row bytes：

```text
key_row =
  timestamp_ascii || 0x1f || instrument_utf8 || 0x0a
score_row =
  timestamp_ascii || 0x1f || instrument_utf8 || 0x1f
  || float64_value.hex().ascii || 0x0a
key_digest   = sha256(concat(key_row))
score_digest = sha256(concat(score_row))
```

两侧必须row count、key digest、score digest一致；canonical MultiIndex逐项一致；最终native
float64 arrays以`np.array_equal` exact。任何timezone/date/instrument/key/score规范化失败即fold
FAIL，不做容差。

outer PASS必须同时满足：exact 14 folds replay、fit调用计数0、candidate/fit ledger bytes与head
unchanged、每foldmax date `< 2025-01-01`、CUDA-only identity、input/output transactions
COMMITTED、所有未清理reservation仍受容量计数。final-OOS partitions opened必须false。

## 6. 当前 M7 v9 bundle

- `m7_change_design_v9.md`
  SHA `ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94`
- `m7_behavior_to_test_matrix_v9.md`
  SHA `0088cf25f5328b4c128d42d4b51772c21648609c41bfaf419fefb19c58841d58`

v9完整冻结official scalar/slot mapping、三产品可重算AP proof、无publication-time伪断言的review
hash DAG、security lifecycle strict authority/rows/receipt与SLA001–SLA006。Gate state、
standardizer、CCC、双generation、budget和first-event边界保持。M6.5只可实现matrix中的
`M6.5_CONTRACT_ONLY`。

## 7. v30 review closure

| v30 finding | v31 closure |
| --- | --- |
| official output object/slot mapping | §2 + M7 v9 §2.2 scalar与十slots |
| AP proof status-only/aggregate | §2 + M7 v9 §2.4 per-product records/digests/recompute |
| capacity concurrent overcommit | §3.2 active reservations全部计费 |
| partial/orphan不可清理 | §3.1/§3.3 append-only lifecycle与owner abort |
| lifecycle authority非closed | M7 v9 §2.6 authority/JSONL/receipt/SLA |
| review publication predicate不可验 | M7 v9 §2.5只声明hash DAG |
| authority root hash边界 | §4仅authority_file_sha256 |
| replaced §5又模糊引用 | §5.2完整重述ScoreReplayCanonicalV1 |

`PASS FOR INDEPENDENT R3 DESIGN REVIEW`。这不等于M6.5 PASS，不授权测试设计之后的动作。
