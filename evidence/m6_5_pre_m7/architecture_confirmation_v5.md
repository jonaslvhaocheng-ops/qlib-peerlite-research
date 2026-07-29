# M6.5 架构确认 v5 — 不可绕过的 Gate、认证数据面与外部运行授权

状态：`PASS — revised bounded architecture confirmation`  
替代：`architecture_confirmation_v4.md` 作为当前 M6.5 修复架构依据；v4 与其全部独立审查均保留为历史证据。  
风险：`R3`。本确认**不**通过 M6.5 gate，不授权冻结 M7 派生契约、真实 M7 fit、CCC/Gate、server replay 或最终 OOS。

## 1. 本轮设计审查要求关闭的边界

独立审查 v2 指出，v4/v2 仍有五个不能靠“多写测试”弥补的信任缺口：

1. 旧 `PeerLiteModel(market_gate=True)` 仍能直接读取 M3 `market`，而该列组含
   `label_open` / `label_close`；新的 state loader 不会自动挡住它。
2. PIT `VERIFY` 被误写成真实训练的正向放行条件，且四个派生 state source 缺少 fixed audit 与
   behavior audit 的独立绑定。
3. `RunAuthority` 可由调用方自制；内部 hash 连续不等于外部预先授权的预算与事件计划。
4. replay verifier 自验自己的 SHA；receipt 不能证明实际启动的是冻结 verifier 字节。
5. 6/44 genesis 只写了 archive proof hash，尚不能定位、解释和验证该 proof。

以下架构只封住这些入口；M6 历史证据、M7 科学设计、模型族、数据范围与最终 OOS 边界均不扩大。

## 2. 总体信任链与唯一公开入口

```text
M6 immutable gate + M6CloseArchiveProof + byte-exact 6/44 snapshot
    └─> LedgerAuthorityGenesis ─> new server authority ledger
          └─> immutable RunAuthorityRegistry/Grant ─> RunAuthority lease ─> future fit

sealed raw snapshot ─> StateBuildBinding ─> construction-only state artifact
    └─> PIT CERTIFY fixed evidence + behavior evidence + join evidence
          └─> StateArtifactBinding ─> verified state capability ─> M7 wrapper only

frozen replay input binding + independently pinned launcher bundle
    └─> deployment receipt ─> FD-pinned launcher ─> copied verifier execution
          └─> launch receipt + replay receipt ─> archival acceptance
```

三条规则不可例外：

- 任何历史 M6 公共入口都不得消费 M7 Gate state。
- 任何数据 artifact 的自描述、`VERIFY` 输出或合成 fixture 都不能产生真实训练 capability。
- 任何 caller supplied path、head、limit、budget、authority 或 verifier hash 都不是权威输入。

本设计的对手模型是“错误配置、错误路径、错误 artifact、崩溃恢复和未经授权的普通调用方”。它不声称
在服务器 root 已被恶意控制或允许任意 in-process Python monkey patch 的情况下提供密码学隔离；这类情形
由冻结代码 revision、受控部署根、最小运行账户和独立 readback 共同约束，发生时全部证据应降级为无效。

## 3. Gate 消费边界：M6 legacy 禁止，M7 wrapper 唯一允许

### 3.1 明确分裂历史与未来 API

`PeerLiteModel` 是 M6 历史模型。它保持 `market_gate=false` 的现有 M6 行为，但其构造函数、配置
解析器、factory、通用 CLI 和 checkpoint reload 中只要收到 `market_gate=true`，均必须在读 Dataset、写
journal 或调用 fit 前抛出 `LegacyMarketGateForbidden`。它不得调用 `dataset.prepare(..., col_set="market")`
作为 Gate 的任何输入。

未来 M7 Gate 不在该类中“打开一个开关”。它的唯一入口是新的 `M7PeerLiteModel` + `M7Runner`：

```text
StateArtifactBinding
  -> load_certified_market_state_artifact(artifact_dir, binding)
  -> VerifiedMarketState capability
  -> M7PeerLiteModel.fit(dataset, verified_state)
```

`VerifiedMarketState` 是由 loader 在重新验证 binding、inventory、certificate links 和 schema 后构造的
冻结值对象；它携带四维 state 表、binding/artifact identity、schema/order、date/key digests。M7 model
不接受裸 DataFrame、`market_state` col_set 或任意路径。`M7Runner` 是唯一 composition root，且只能从
受控 registry 中解析其 model/authority/spec；其 source revision 锁定后不得加载任意用户模块。

这里的 capability 是受控运行边界，而非宣称抵抗恶意同进程反射。为使普通调用方无法“假装已验证”，
capability 构造器不属于公共 API；runner 会再次校验其 binding digest 和 state table digest。部署时只有
冻结源码版本和固定 runner 可执行，任何 direct instantiation/手工 state object 都视作未授权并 fail-closed。

### 3.2 必须存在的拒绝测试

- `PeerLiteModel(market_gate=True)`、历史 config、factory、CLI、checkpoint reload 全部在训练前拒绝；
  ledger/journal 字节为零变化。
- 旧 M3 Dataset、其 `market` projection、伪造 `market_state` col_set、手工 DataFrame、错误/缺失
  capability、错 schema/order、非 date-constant state、错误 binding 都不可到达 Gate。
- 仅含四列且从已认证 artifact loader 得到的 capability 可被 M7 wrapper 接受；同日 broadcast、date join
  和 training-only standardizer 的边界另有 M7 测试，不能由此预先宣称通过。

## 4. State 数据面：construction 与 empirical eligibility 严格分离

### 4.1 construction-only `StateBuildBinding`

M6.5 仅实现可测试的、sealed-snapshot allowlist builder。它固定原始 input manifest/columns、可得性时钟、
causal feature/predicate/schema blob、日期上界与 atomic publish 协议，产出：

- `state_input_audit.parquet`：每个候选 key、四个 source、七个 eligibility flag、selection outcome/reason、
  source partition 和 availability lineage；
- `population.parquet`：所选 key + 精确四个 source；
- `daily_state.parquet`：四维 daily state、population/key/state digest；
- inventory manifest 与最后写入的 `COMPLETED` marker。

builder 只能经 allowlist resolver 从 raw snapshot 读取 regular file，执行 realpath/root containment、
no-link、SHA/bytes/schema/column 校验；不得 import/call M3 product、labels、execution、purge、future
action 或其 helper。输出由同父目录临时树 fsync 后原子 rename；已有非同一 artifact 不可覆盖。

任何这种 artifact 的状态都是 `BUILT_NOT_EMPIRICALLY_CERTIFIED`。合成 fixture、局部检查、`VERIFY`、
自报 manifest 以及 construction success 永远不能开启 Dataset。

### 4.2 真实训练前的正向认证对象

只有未来 **M7 派生 research contract 已 FROZEN** 后，才可以为 exact state input 申请 PIT `CERTIFY`。
真实 `StateArtifactBinding v2` 必须同时绑定下列不可变对象，缺任何一个均无法 mint capability：

| 证据 | 正向/负向角色 | 必须绑定的内容 |
| --- | --- | --- |
| `PITFixedCertificate` | 唯一正向 PIT eligibility | `CERTIFY`、`PASS`、`QUALIFIED`、`FULL_TRAINING_INPUT`、冻结 QRC ID/content hash、runtime trust-anchor match、exact state-input audit/inventory hashes、raw snapshot and availability-clock identities。 |
| `StateBehaviorEvidence` | 必需的派生路径负证据，不提升 fixed claim | parent 为上项 exact fixed certificate；对 future label、execution eligibility、corporate action/revision 与 universe canary 的真实 raw-snapshot 扰动，证明 cutoff 及以前的 selection outcome、population key/count、daily state digest 未变；保留其 `NOVEL_CANDIDATE` 边界。 |
| `StateJoinEvidence` | 连接 model input 的审计 | exact supervised Dataset manifest、state artifact manifest、每个 model date 的 1:1 state date、同日常量性、schema/order、missing/duplicate fail-closed 结果。 |
| `StateArtifactManifest` | 受认证的构建输出 | build binding、audit/population/daily inventories、code/predicate/schema hashes、date bound、completed marker。 |

loader 要逐字节重新验证上述 parent links，而不接受“有个通过的 audit 文件”。`VERIFY` 仍可用于发现或诊断，
绝不使用 `PASS`、`QUALIFIED`、`certified` 等语言，不能被写入正向 binding。四个 derived source 的
behavior tests 要覆盖它们的原始窗口输入和 selection predicate，而不仅是最终四个值。

## 5. 账本：可验证 6/44 genesis、外部 grant 与一次性 authority

### 5.1 可定位的 M6 close proof

新增 `M6CloseArchiveProof v1`，由未来修正后的 archive verifier 产生。它不是 v2 server replay receipt，
且必须包含：

- controlled-root relative path、file SHA/bytes、schema/version 与 canonical content hash；
- M6 immutable gate path/SHA/content hash、批准的 historical verifier git blob identity；
- byte-exact close snapshot path/SHA/bytes、`6 candidate / 44 fit`、M6 pre-run `4/29` prefix；
- journal-to-ledger retained-ID 集合、terminal journal chain 与 static evidence 的验证结论。

`LedgerAuthorityGenesis v2` 同时绑定该 proof 的完整 identity、M6 gate 和 close snapshot；installer 从
controlled root 按 normalised relative path 解析，拒绝 `..`、symlink/hard-link escape、错误 schema、错误
proof、legacy ledger path 和已存在的不相同 target。它以 lock + temp/fsync/replace 创建全新 authority
namespace，绝不覆盖 `contracts/trial_ledger.jsonl` 或 M6 历史行。

### 5.2 `RunAuthorityRegistry` 是 caller 之外的授权根

真实 M7 run 只有在 M7 derived contract 冻结后才可获得 registry grant。M6.5 只提供 schema、synthetic
fixtures和拒绝路径；不创建真实 M7 grant。

`RunAuthorityRegistry v1` 是受控 server authority root 下原子安装的 immutable snapshot。每一 grant
以 authority ID 为键、以 canonical authority SHA 为值，固定：

- authority ledger ID/genesis SHA 与唯一 parent receipt 或 exact initial head；
- execution spec SHA、immutable budget artifact path/SHA/content hash、maximum candidate/fit counts；
- journal/output logical paths、event-plan SHA、每个 event 的 model/fold/seed/purpose/count flags；
- source frozen M7 contract ID/SHA、registry version/content SHA 与唯一 namespace。

CLI 只接收 `authority_id`；它从 fixed authority root 读取 registry，再由 grant 决定 authority/budget/
journal/output 的唯一路径。不存在 `--run-authority`、`--expected-head-*`、`--limit-*` 或 caller supplied
budget path。注册、reconcile 和 future fit preflight 均在同一 ledger lock 内重新核对 registry→grant→
authority→budget→current head；任何 registry substitution、authority reuse、path traversal、head/plan/
budget mutation或 unknown tail 都零字节失败。

账本写入使用 canonical batch bytes：journal `START` fsync → lock → revalidate all bindings/current head/
semantic uniqueness/budget → temp file with old exact bytes + full canonical records → fsync + replace + parent
fsync → receipt。journal 已写而 ledger 未写可幂等恢复；任意已开始 event 永远保守计数。服务器是唯一写
authority，本机只读验证同步 receipt。

## 6. replay：独立 launcher 与部署证明，而非 verifier 自证

`M6ReplayInputBinding v2` 除 archive/transfer/internal manifest/tree/M6 evidence/verifier/profile 外，还绑定
trusted launcher source SHA、launcher validation library SHA、部署 policy、output protocol 和 server logical
deployment root。所有文件均采用 controlled-root relative path 和 no-link 解析。

运行分为两层：

1. `install_m6_replay_bundle.py` 在受控 server root 从 binding 指定的字节构造 content-addressed deployment
   directory，验证 launcher/verifier/archive/binding 的 bytes/SHA、拒绝已有不一致目录，并以原子发布写
   `ReplayDeploymentReceipt`（deployment root identity、binding/launcher/verifier/archive/tree digests、
   file types、sanitized installer identity）。
2. 独立 `launch_m6_archival_replay.py` 只读取该 deployment receipt/binding。它以 `O_NOFOLLOW` 打开并从
   同一 file descriptor 流式 hash+copy verifier 与 archive 到私有临时目录；随后用 copied frozen verifier
   启动，故 hash→exec 之间没有可替换的路径。launcher 以最小环境/明确 argv 执行，验证 child receipt、
   output inventory、14 folds、`model_fit_calls=0`、OOS=false、ledger pre/post unchanged，并写
   `ReplayLaunchReceipt`。

archival acceptance 需要 deployment receipt、launch receipt 与 verifier receipt 三者都重新按 binding
校验；verifier 的 self-hash 仅为交叉检查，不能单独成为证据。任何 bind 后 archive/verifier/tree mutation、
fake self-report、wrong launcher、hash-to-exec swap、module decoy、deployment-root substitution 或 ledger
write 都不得产生 acceptance receipt。

## 7. 责任、兼容与最小验收

| 边界 | 允许职责 | 禁止职责 |
| --- | --- | --- |
| `data` | raw allowlist、state audit/build/loader | M3 label/execution/purge，ledger，portfolio/OOS 决策 |
| `governance` | binding、proof、registry、receipts、validation | 派生数据行或模型训练 |
| M6 `PeerLiteModel` | 复现历史 `market_gate=false` | 任意 Gate state 输入 |
| M7 wrapper/runner | certificate-bound state join、future Gate | path-only state、裸 DataFrame、自由 config |
| server scripts | 受控 composition、locks、atomic publish | caller-defined authority/replay trust roots |

实现后的最低阻断验收包括：旧 Gate bypass、VERIFY-as-PASS、forged state/binding、future poison、
forged authority/grant/registry、head/plan/budget swap、ledger crash/concurrency、bad close proof、
replay self-report/hash-to-exec swap，以及 public CLI synthetic E2E。所有新核心模块/CLI 需要冻结 include list
下 100% line + branch coverage；真实 M7 fit 和最终 OOS 不属于 M6.5 E2E。

## 8. 当前阶段结论

`PASS` 只表示架构层已把独立审查 v2 的 P0/P1/P2 边界映射为可实现、可拒绝、可测试的接口。下一步必须
依据本文件写新的 change design，再取得新的独立 design-review `PASS`；在此之前不写修复产品代码，
不冻结 M7 contract，不启动任何训练或 OOS。
