# M6.5 R3 修复设计 v3 — 封住旧 Gate、认证 state、外部授权与可信 replay 启动

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
质量变更：`m6-5-pre-m7-repair`；风险：`R3`。  
替代：本文件替代 `m6_5_repair_change_design_v2.md` 作为唯一实现依据；其架构依据为
`architecture_confirmation_v5.md` + `architecture_confirmation_v6.md`；v1/v2 和所有否决审查保留为历史证据。  
禁止：M7 derived contract freeze、真实 M7 fit、CCC/Gate 实验、2025+ final OOS、M6 immutable artifact 修改、历史 ledger 行重写或删除。

## 1. 已验证问题与边界

本变更只修复 M6.5 工程可信边界，绝不产生 Alpha 或 M7 研究结论。以下对象保持不可变：

```text
contracts/immutable/m6_trial_budget_start.json
contracts/immutable/m6_peerlite_execution_spec_v1.json
evidence/gates/M6_peerlite_gate.json
历史 M5/M6 ledger 行、M6 checkpoint、M6 score 和 OOS 边界
```

已核验的 P0 调用链是：公开 `PeerLiteModel` 接收 YAML/CLI `market_gate=true`，在 `fit()`/`predict()`
经 `_market_frame()` 读取 `dataset.prepare(..., col_set="market")`；M3 `MARKET_COLUMNS` 含
`label_open,label_close`。gated checkpoint reload 也会恢复这条路径。现在没有任何实际
`StateArtifactBinding` 或 verified loader 实现，因此新增一个推荐 loader 并不能封住入口。

所有新的 binding/receipt 使用 canonical JSON（UTF-8、sorted keys、no NaN、content hash 不包含自身），
只允许 controlled-root relative POSIX paths 或 sanitised IDs。解析器一律拒绝 absolute path、`..`、空路径、
symlink/hard-link escape、非 regular input、未知键、重复 semantic ID、noncanonical JSON 与错误 self-hash。

## 2. 模块与公开合同

| 交付物 | 位置 | 唯一公开合同 | 明确禁止 |
| --- | --- | --- | --- |
| legacy deny | `models/peerlite.py`、config/factory/CLI/registry | M6 `PeerLiteModel` 只允许 `market_gate=false` | 读取任意 M7 state 或 M3 `market` 作为 Gate |
| state data plane | `data/state_artifact.py`、`data/market_state.py`、server builder | construction artifact；经认证后才生成 `VerifiedMarketStateCapability` | 凭 DataFrame、path、VERIFY 或自述 manifest 放行 |
| M7 Gate adapter | `models/m7_gate_peerlite.py`、M7 runner adapter | `fit(M7BoundFold, VerifiedMarketStateCapability)` / `predict(...)` | Qlib `market`、裸 frame/tensor、duck-typed Dataset |
| ledger authority | `governance/run_authority.py`、`trial_ledger.py`、install/reconcile CLI | close proof → genesis → registry grant → lease | caller 自定 path/head/limit/budget/plan |
| replay | archive/deploy/launcher scripts | binding → deployment receipt → launch receipt → replay receipt | verifier self-report 单独作为证据 |

## 3. P0：legacy Gate 必须永久 fail-closed

### 3.1 历史 M6 API

1. `PeerLiteModel.__init__` 收到任何非 false `market_gate` 值立即抛 `LegacyMarketGateForbidden`；错误发生于
   Dataset prepare、journal/checkpoint 写入、fit/predict 前。
2. `PeerLiteModel.fit/predict/_market_frame` 不保留可触发 `col_set="market"` 的 Gate 分支。M6 的
   no-gate path 保持兼容，M6 immutable spec 继续绑定 false。
3. config parser、factory、CLI、`configs/model_registry.yaml` 都拒绝 gated legacy candidate。checkpoint 保存
   `model_kind=M6_PEERLITE_NO_GATE`；load 缺少它或遇到 gated metadata 都拒绝。`models.__init__` 不导出
   M7 Gate internals。
4. `PeerLiteNetwork` 不能再从公开 M6 model 接收原始 state tensor；若保留 Gate network，它仅属于 M7
   私有 module，不能由 legacy class/factory 注入。

### 3.2 M7 的唯一状态消费路径

新增 `M7GatePeerLiteModel`，不继承可读 M3 `market` 的 public behavior：

```python
fit(bound_fold: M7BoundFold, state: VerifiedMarketStateCapability) -> Self
predict(bound_fold: M7BoundFold, state: VerifiedMarketStateCapability) -> pd.Series
```

`M7BoundFold` 由 M7 adapter 从冻结 supervised Dataset manifest、state join evidence、segment/spec 构造，
不是可伪装的 `prepare()` provider。loader 私有工厂生成 frozen `VerifiedMarketStateCapability`，其中含
binding/artifact/certificate bundle SHA、four-column schema/order、date→state 表、population/key/state digest、
join identity、date range 与 canonical payload digest。M7 model/runner 在 fit、predict、checkpoint load 时再次
核验全部 identity、date coverage、同日常量与 schema；不接 DataFrame、tensor、`market_state` col_set 或
artifact path。checkpoint 记录同样的 identities，load/predict 需要重新 loader 验证后的精确等价 capability。

此 capability 是冻结 runner 中支持接口的边界，不声称对抗拥有任意同进程 Python 权限的人；后者由受控
代码 revision、registry deployment、最小运行账户与独立 readback 约束，发现后全部 receipt 无效。

### 3.3 Red/green 必测项

- ctor/config/CLI/factory、old M3 Dataset、old gated checkpoint、label 聚合为日内常量的 `market`、伪造
  `market_state` group、direct network injection 都在任何 fit/journal 前拒绝。
- 裸 frame/tensor、duck Dataset、伪造 capability、错 binding/artifact/schema/digest、state date 缺失/重复/
  非常量、checkpoint-capability mismatch 全部拒绝。
- 合成 sealed artifact 经 loader→bound fold→M7 adapter 可成功，并以 spy 证明从未请求
  `col_set="market"`，只使用四维 date-constant state。

## 4. P0：construction 永远不等于 empirical eligibility

### 4.1 `StateBuildBinding v2`

唯一 builder CLI：

```text
build_m7_market_state_population.py
  --state-build-binding <controlled binding>
  --snapshot-dir <sealed snapshot>
  --output-dir <new output directory>
```

binding 固定 snapshot bundle、source manifest allowlist、columns/schema/availability clocks、builder/causal
feature/predicate/schema blobs、selection reason order、date upper bound 和 publication protocol。resolver 对每一
文件做 fd/file type、realpath containment、SHA/bytes/schema/columns 校验；builder/imports 明确禁止
label/execution/purge/M3 reader modules。

同父目录临时树依序 fsync `state_input_audit.parquet`、`population.parquet`、`daily_state.parquet`、manifest、
最后 `COMPLETED`，再 atomic rename + parent fsync。manifest 固定
`status=BUILT_NOT_EMPIRICALLY_CERTIFIED`，绑定 inventories、selection/key/state digests 与 availability lineage。
任何错误只留下旧 artifact 或无 published output。

audit 每行含 raw key、four sources、source partition、seven flags、outcome/first reason；population 只能有
selected key + four sources；daily 只能有 `DAILY_PRODUCT_COLUMNS`。M3 projection、label、execution、T+1
limit、action-cross-label、purge/embargo 都不得出现在 allowlist、imports 或 output schema。

### 4.2 `StateArtifactBinding v2` 的唯一正向条件

真实 artifact 仅在未来 **M7 derived QRC 已 FROZEN** 后方可申请 PIT `CERTIFY`。binding 必须连接这四类
immutable evidence：

| 对象 | 必需内容 | 作用 |
| --- | --- | --- |
| `PITFixedCertificate` | `mode=CERTIFY`、`PASS`、`QUALIFIED`、`FULL_TRAINING_INPUT`、frozen M7 QRC ID/SHA、runtime trust anchor、exact state audit/inventory/raw snapshot/clock | 唯一 PIT 正向 eligibility |
| `StateBehaviorEvidence` | exact fixed-certificate parent；future label/execution/action/revision/universe canary；保护 selection outcome、population key/count、daily state digest | 必需派生路径负证据，仍是 `NOVEL_CANDIDATE`，不提升 fixed claim |
| `StateJoinEvidence` | exact supervised Dataset + state manifest；all dates 1:1；schema/order、date-constant broadcast、missing/duplicate rejection | model-input join audit |
| `StateArtifactManifest` | build binding、audit/population/daily inventory、code/predicate/schema/date bound/marker | 被认证的构建输出 |

loader 重算 inventory/hash/parent links 后才 mint capability。construction status、PIT `VERIFY`、合成证据冒充真实、
缺 behavior/join、trust-anchor 变化、scope 不等于 exact training input 均 fail-closed。`VERIFY` 可在 M6.5
诊断，但只能写 `NEEDS_EVIDENCE`，绝不称 PASS/QUALIFIED/certified，也绝不用于训练。

### 4.3 state 测试

测试覆盖 allowlist/path/link、source clock/column/schema、七 flags/reasons、M3 projected-label、future label/
execution/action/revision/universe poison、marker/inventory digest、atomic crash retry、fake VERIFY、缺 behavior/
join 与 construction-only loader。M6.5 不对真实 raw data 出具 PIT 结论。

## 5. P1/P2：6/44 genesis、external registry grant 与 batch-atomic ledger

### 5.1 可定位的 close proof

修正后的 archive verifier 唯一生成 `M6CloseArchiveProof v1`：proof relative path/SHA/bytes/schema/content hash；
M6 gate path/SHA/content hash；批准 historical verifier git blob；pre-run `4/29`；close snapshot path/SHA/bytes/
`6/44`；static-evidence verdict；journal-start ↔ retained-ID set；terminal chain。`LedgerAuthorityGenesis v2` 绑定
全部这些字段，不能只写 `archive_proof_sha256`。

installer 只接 genesis ID + controlled source root，锁内 no-link resolve proof/snapshot/gate，拒 legacy
`contracts/trial_ledger.jsonl`，用 close bytes + genesis record 原子创建 policy-derived **new** authority ledger。
重复 exact install 返回同 receipt；bad proof/schema/path、wrong target、race、fsync/rename fault 零覆盖/零 partial。

### 5.2 external `RunAuthorityRegistry v1`

`RunAuthority` 只描述计划，不能自我授权。真实 registry 只能由未来 frozen M7 derived contract 的
`RunAuthorityRegistrySnapshot` 原子部署至 genesis policy 的 governance-owned control-plane root；研究 runner
对该 root、registry、grant 与 ledger 均无写权限。所有 registry/grant/authority 都是 content-addressed
version files，禁止可变 `current.json`。M6.5 仅用 synthetic contract fixtures，不创建真实 M7 grant。

`RunAuthorityRegistry v1` 仅登记已批准 grant；每项固定 grant ID/path/SHA、authority ID/SHA、ledger/genesis、
parent head/receipt、spec SHA、budget SHA/max counts、journal/output paths 与 event-plan SHA。相应
`RunAuthorityGrant v1` 重复并完整绑定 authority、budget、spec、parent、journal/output 与 event plan；它与
registry entry 必须逐字段一致。`EventPlanEntry` 固定 sequence/source ID/type/count/evaluation/fit/model/fold/
seed/purpose/canonical-event-payload SHA。registry 绑定 source QRC ID/SHA、control profile SHA、content SHA、
namespace。

公共命令只接 `--authority-id`，从 fixed root registry 解析所有对象；不存在 caller `--run-authority`、
`--budget`、`--limit-*`、`--expected-head-*`、output root 或 parent。解析使用逐段 `openat` + `O_NOFOLLOW`，
并检查 owner/mode、regular-file、`nlink==1` 和 canonical bytes；不能以 `Path.resolve()` 替代。锁内验证
deployment→registry→grant→authority→budget→receipt→raw head→event，任意 substitution/mutation/unknown tail
零字节失败。

写入算法：journal START fsync → ledger lock → full validation + semantic uniqueness → sibling tempfile 写 old raw
bytes + full canonical batch → fsync → replace → parent fsync → receipt。完整 normalised retained payload 相同才
幂等；已开始 event 永远保守计数。server 是唯一 writer，本机仅验证镜像。

测试包括 6/44、legacy 8d08 reject、bad proof/path/link、idempotent/race/fault、合法 future suffix 不破坏 M6
proof、forged registry/grant/authority/budget/plan/head、parent mismatch、semantic collision、overbudget、bad journal、
double reconcile、crash retry、concurrent import 和所有 reject 的 ledger bytes unchanged。

## 6. P1：trusted launcher 替代 verifier 自证

`M6ReplayInputBinding v2` 额外绑定 launcher SHA、launcher validation library SHA、deployment policy、output
protocol、controlled deployment root，及既有 transfer/archive/internal manifest/tree/M6 evidence/verifier/profile。
冻结的 `M6ReplayLaunchGrant v1` 再绑定 input binding 原始 SHA/content SHA、launcher bundle/entrypoint SHA、
受控 Python/venv/lockfile runtime identity、archive/product/run/historical receipt/ledger logical identity、唯一
新 output path、execution profile 与验收公钥指纹。profile 固定 `checkpoint_replays=14`、`model_fit_calls=0`、
`final_oos=false`、legacy ledger read-only pre/post hash。

1. `install_m6_replay_bundle.py --launch-grant-id` 只从 governance control root 获取 grant/binding/runtime，验证
   bytes/type/no-link/owner/mode，锁内原子创建 content-addressed deployment，并写 `ReplayDeploymentReceipt`
   （grant、binding、launcher、verifier、archive/tree、runtime、deployment inventory、installer identity）。
2. `launch_m6_archival_replay.py --deployment-id` 只从 deployment receipt/grant/binding 推导输入。它用 `O_NOFOLLOW`
   打开 verifier/archive，从**同一 fd** hash+copy 至 governance-owned private staging，再用固定 interpreter
   `python -I`、清空 `PYTHONPATH`/user-site、固定 cwd/环境白名单、binding-derived argv 启动 copied verifier。
   它在 child 生命周期持有 legacy ledger shared lock，独立验证 child receipt/output/profile/ledger，并只在新的
   output path 写 `M6ReplayAcceptanceReceipt`。

`m6_archive` 必须验证 deployment + acceptance + child receipt；verifier self-hash 只作交叉检查。若 acceptance
receipt 被复制出 governance server root，governance control plane 必须用 launch grant 固定公钥的 detached Ed25519
签名 canonical receipt；否则本地复制 JSON 不是可独立验收的证据。测试覆盖 wrong launcher/runtime/root、bind 后
verifier/archive/tree mutation、self-report fake、hash-to-exec swap、tar link/duplicate/root、module decoy/import
origin、ledger write、pre-existing output 与 synthetic public CLI E2E。

## 7. 实施次序与验收

1. 先写所有上述 P0/P1/P2 red tests，执行并保存预期失败证据。
2. 实现 legacy deny、synthetic state binding/loader/capability/adapter；跑 mutation/boundary tests。
3. 实现 close proof/genesis、registry/grant、lease/reconciliation；跑 atomic/concurrency tests。
4. 实现 replay binding/deployment/FD-copy launcher；跑 synthetic public CLI E2E。
5. 为所有 changed core modules/public CLIs 设 frozen `coverage.py` include，达到 100% line **及** branch；存 raw
   coverage JSON/report/argv/source digest，禁止 omit/exclude/阈值放宽。
6. 全量 unit/integration、lint/type、public synthetic E2E 后，进行独立 code review 和 test review。
7. 这些通过后才上传 pinned bundle 并跑 server v3 read-only 14-fold replay（无 fit、无 ledger 写、无 M7 data、
   无 final OOS），再让 M6.5 gate 决定。

M6.5 PASS 本身不授权真实 M7。下一独立阶段还必须 freeze derived QRC、获得 real PIT CERTIFY + behavior/join
evidence、部署 real registry grant，并通过自己的 gate 后才可能启动任何 fit。
