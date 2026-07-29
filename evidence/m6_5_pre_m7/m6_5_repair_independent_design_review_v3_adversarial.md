# M6.5 v3 / v5 / v6 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查方式：只读；未运行训练、真实数据、server replay 或最终 OOS。  
审查对象：

- `m6_5_repair_change_design_v3.md` (`9ac6394aa68deee9a0572e081bdfd500b9de5b4ddfd778bd31222e1efc564ad6`)
- `architecture_confirmation_v5.md` (`60f9352e394cd413e628ddcc02455e6112738281a25a04f4cddce62bd837bec0`)
- `architecture_confirmation_v6.md` (`6ed8486527e49e25fc32cfaca1fcf88c8dc4978cbdcc76439f112137e08b7a68`)

以下 finding 聚焦“普通调用方、错误部署、崩溃恢复和路径替换”这一已声明对手模型；不假设 governance root 或内核已被攻破。

## Findings

### [P0] Legacy public network 仍没有被合同层面彻底移除，Gate 可以绕过 `PeerLiteModel` deny

**Section:** v3 §3.1–3.3；当前公开包边界。  
**Scenario:** 当前 `qlib_peerlite.__init__` 与 `models.__init__` 都导出 `PeerLiteNetwork`，其构造函数公开接受 `market_gate` / `market_dim`，`forward()` 公开接受原始 `market_state` tensor。v3 只明确禁止 `PeerLiteModel` 的 Gate，并以“不能再从公开 M6 model 接收”描述 network；实现者仍可保留这个公开 network，调用方即可直接构造 Gate，完全跳过 config、legacy model、Dataset 和 capability loader。  
**Impact:** 原 P0 的“标签/未来污染 state 进入 Gate”路径会以较低层 API 重新出现；`direct network injection` 测试不能由文字意图自动保证。  
**Evidence:** `src/qlib_peerlite/__init__.py`、`src/qlib_peerlite/models/__init__.py` 均公开导出 `PeerLiteNetwork`；`src/qlib_peerlite/models/peerlite.py` 当前第 40–155 行仍提供该签名。v3 第 43–51 行没有规定 legacy network 的新签名、移除规则或 export 兼容策略。  
**Direction:** 将 `models.peerlite` 中的 legacy network 固定为无 Gate 的 M6-only 类型：公开构造器和 `forward` 都不得出现 `market_gate`、`market_dim`、`market_state` 或 `MarketStateGate`。Gate network 必须迁移到不导出的 M7 implementation module，且只由 M7 runner 内部创建。对顶层/`models` export、反射式 factory、旧 checkpoint、`PeerLiteNetwork(..., market_gate=True)` 和直接 `forward(..., market_state=...)` 写拒绝测试；M6 frozen archive 继续以其隔离的冻结源码 replay，不要求新源码兼容 gated checkpoint。

### [P1] `VerifiedMarketStateCapability` 是 Python 约定而非可验证的公开边界，M7 的“唯一入口”仍可被正常直接调用绕过

**Section:** v3 §2、§3.2；v5 §3.1。  
**Scenario:** v3 将 `M7GatePeerLiteModel.fit(M7BoundFold, VerifiedMarketStateCapability)` 作为公开合同，同时称 capability 的私有 factory 足以使“普通调用方”不能伪造。Python 的私有构造器、frozen dataclass、类型标注和再次比对对象内 digest 都不能证明该对象来自 loader：调用方可导入内部模块、反序列化/复制一个历史对象，或构造具有一致字段和 digest 的对象；无须修改 runner 或 governance root。  
**Impact:** 这会把“只接受已认证 artifact”的数据面规则降级为调用规范。直接调用 M7 library API 还会绕开 authority lease 与 per-fit admission，造成 state 和试验预算的双重旁路。  
**Evidence:** v3 第 55–70 行明确暴露 model `fit/predict` 合同但没有 issuer、会话绑定或唯一 runner admission；第 74–79 行要求拒绝伪造 capability，却未定义“伪造”的可判定来源。v5 第 65–72 行的 private constructor 说明同样不足以形成 Python 级能力安全。  
**Direction:** 明确二选一，不能同时声称 public capability 是安全边界：

1. **推荐：** M7 model/network 不构成 research-public API；唯一可执行入口是已部署、受 authority lease 约束的 runner。loader、bound fold 和 network 仅在 runner 进程内部传递，外部 API 只提交 authority ID；
2. 若必须支持库调用：将其定义为 *non-authoritative mechanics-only API*，永远不能生成可晋级实验产物，并由独立 server admission service/签名 session token 才可进入真实 fit。

无论哪种，都要把 capability 与一次性 lease、exact artifact/binding digest 和 process/session nonce 绑定；不能仅检查 capability 自带的字段。文档需显式限定不抵抗同进程反射的边界，测试应验证“直接 import/构造/复制”不能产生 authoritative fit receipt。

### [P1] PIT 证书、join 证据与 capability 的签发顺序未定义，存在 `FULL_TRAINING_INPUT` 的循环依赖

**Section:** v3 §4.1–4.2；v5 §4.2。  
**Scenario:** `PITFixedCertificate` 被要求为 `CERTIFY + PASS + QUALIFIED + FULL_TRAINING_INPUT`，而 `StateArtifactBinding` 又要求该证书、behavior evidence 与 `StateJoinEvidence` 后 loader 才能 mint capability。若 CERTIFY 的“完整训练输入”是模型实际消费的 joined input，那么生成/验证 join 需要 state 表；设计又规定未经 binding/certificate 的 state 不得开启 Dataset。没有定义 certifier 可以在不 mint capability 的前提下读取何种候选 join，也没有定义证书究竟覆盖 raw state input、construction artifact，还是最终 joined training matrix。  
**Impact:** 实施者只能任选其一：把 certificate scope 缩小为非完整输入，或为做 CERTIFY 临时绕过 loader。两者都会把 `FULL_TRAINING_INPUT` 变成无法审计的自述，或造成证书—loader 的时序死锁。  
**Evidence:** v3 第 110–122 行同时要求 certificate、behavior、join 和 loader；第 99–102 行又规定 construction artifact 不能开启 Dataset。v3 未给出 certificate issuer、输入 manifest、签发前 audit-only access 或 phase order。  
**Direction:** 增加一个不可执行的、单向的签发协议，并把对象范围写死：

```text
construction-only artifact
  -> audit-only CandidateTrainingInputManifest (无 model/runner/capability API)
  -> frozen M7 QRC binds that exact manifest
  -> PIT CERTIFY over exact candidate values and availability clocks
  -> behavior evidence + audit-only join evidence
  -> StateArtifactBinding
  -> verified capability / authoritative runner only
```

`CandidateTrainingInputManifest` 必须包含最终 join 后实际值的 inventory/digest；certifier 可读取它但不能调用模型。明确 certificate issuer/trust anchor、每份 evidence 的 parent hash、以及任何步骤失败时不能回退到 construction artifact。M6.5 只能对带 `SYNTHETIC_NOT_EMPIRICAL` 根的同构 fixture 测试该顺序，生产 loader 必须拒绝该根。

### [P1] Registry 的“content-addressed 文件 + `openat`”没有给出 activation anchor 或跨读取 TOCTOU 语义

**Section:** v3 §5.2；v6 §2。  
**Scenario:** public CLI 只提供 `authority_id`，却未定义它如何被绑定到 **某一个已冻结的 registry snapshot**。即使 registry/grant/authority 各自 hash 正确，调用方/部署层仍可在 runner 开始前或验证后替换为另一个旧但自洽的 snapshot，或在一次多文件读取期间替换 registry/grant/authority。`O_NOFOLLOW` 保护最终路径分量，不自动固定父目录、活跃 snapshot、文件 descriptor 生命周期或读取到执行之间的版本。  
**Impact:** 预算、event plan 或 parent head 可以回滚到另一份有效对象；检查通过的对象不一定是实际授权/执行的对象。此问题不需要攻破 root，只需存在多个可读 version 文件、部署 rollback 或未定义的 activation selection。  
**Evidence:** v3 第 145–161 行只规定 fixed root、content-addressed file 与逐段 `openat`；v6 第 21–34 行画出 QRC→snapshot SHA，但没有规定 runner 获取/固定该 SHA 的受信 activation receipt，也没有规定所有后续文件必须从同一已 pin 的 descriptor tree 使用。  
**Direction:** 为每次 authority admission 定义单一 `AuthorityActivationReceipt`：由 frozen M7 QRC/受控 deployment 在 runner 启动前固定 registry snapshot SHA、namespace、control-root inode/device、grant/authority hash 和 policy key ID。runner 必须从受信 root directory FD 开始，以 `openat` 打开并保留所有对象 FD，`fstat`/hash 后把 canonical bytes 复制到内存；ledger lock 内再次校验同一 activation identity，执行时只使用该内存/FD 派生的路径。生产 schema 必须拒绝 synthetic control-plane root、test signer 和未被 activation receipt 引用的版本文件。增加 old-valid-snapshot rollback、ancestor rename、validate-after-replace、跨文件混配与 test-root-to-prod upgrade 的拒绝测试。

### [P1] “journal start 已计数”不等于“实际 `model.fit` 至多一次”；lease、崩溃恢复与 receipt commit 尚未形成事务

**Section:** v3 §5.2、§7；v5 §5.2。  
**Scenario:** 算法只描述 `journal START fsync -> ledger lock -> append -> receipt`。它没有规定 lease 在何时取得、journal 由谁加锁、fit 如何取得单次 admission、崩溃后同一 `source_event_id` 是否可再次调用 `.fit`，或 ledger replace 成功而 receipt 写入失败时如何恢复。重复 reconcile 可以安全幂等，却可能让重启 runner 将同一已保留 `MODEL_FIT_STARTED` 再次执行一次 fit，预算只记一次。  
**Impact:** 试验/fit 上限可与真实模型调用数分离；并发或 crash recovery 还会留下“ledger 已提交但无 admission receipt”的不确定状态。该问题直接破坏 v0 的试验预算和可复现性。  
**Evidence:** v3 第 163–169 行仅给出 batch 写入顺序；当前 `exclusive_run_lease()` 位于 `trial_ledger.py` 第 443–468 行且 `rg` 显示没有调用方，已有审计也记录此事实。现有 stable ledger lock 是有用基础，但不能单独序列化真实 fit 或 crash 后的执行资格。  
**Direction:** 把它设计为显式的 `FitAdmission` 事务，而不是 reconcile 后的惯例：

- 在不被 replace 的 authority lock 下创建/持有 `RunLease`，其 nonce 绑定 activation、journal inode/digest、event-plan entry 和 exact ledger head；journal append 使用该 lease 的独立稳定锁；
- ledger commit 后生成可恢复的 `AdmissionReceipt`，只有持有该 nonce 的 runner wrapper 才能调用一次 `.fit`；
- `.fit` 进入后任何 crash 都使该 fit ID 不可重放。若确需重试，必须消耗一个预先计划的、独立 counted attempt；
- receipt 写入失败只能重建同一 commit receipt，不能重新执行 fit；所有 lock 必须是不会被 ledger `rename` 替换的固定 lock-file/FD。

测试需要用多进程与 crash injection 证明：同一 event 的真实 fit 调用数永远不超过一次、任何 retry 有独立预算事件、以及 ledger/receipt 任一半提交都不会释放模型执行。

### [P1] Replay 仍缺少独立的签名与 runtime trust root；`python -I` 和 lockfile 不能证明实际执行环境

**Section:** v3 §6；v6 §3。  
**Scenario:** launch grant 只保存 Ed25519 *public-key fingerprint*，但未定义私钥由谁持有、launcher 是否能请求任意签名、签名服务如何重新验证原始 inputs，或 verifier 如何从 grant 独立取得受信公钥。若私钥/签名接口与 launcher 同一 Unix 权限域，修改后的 launcher 仍可签一份自洽的 acceptance receipt。另一个问题是 `python -I` 忽略 user site/PYTHONPATH，并不证明解释器二进制、venv 中已安装 wheel/native extension、动态链接器环境或全局 import 路径与 lockfile 一致；lockfile 是解析意图，不是运行时闭包。
**Impact:** detached signature 可能只是“同一不可信进程为自己的 JSON 背书”；回放可加载与 grant 不同的 pandas/torch/依赖模块或被 runtime 注入，之后仍生成看似完整的 receipt。这正是 v5/v6 要消除的 verifier self-attestation 以另一层形式复现。  
**Evidence:** v3 第 175–191 行与 v6 第 48–55 行要求 fingerprint、`python -I` 和 detached signature，但没有 signer role/key custody、签名 payload/domain separation、public-key activation anchor、runtime inventory/image digest 或 native dependency policy。当前 verifier 也会自行 `sys.path.insert(0, frozen_src)`，说明 import-origin 必须是可验证的 runtime policy，而非仅靠 `-I`。  
**Direction:** 在实施前固定以下最小信任链：

1. `ReplayLaunchGrant` 由独立 control-plane signer 签发；acceptance 只能由与 launcher 不同权限域的 signer/service 在重新验证 deployment/child/output/ledger 后签署，且不能签任意 caller JSON；
2. signature 使用明确的 canonical unsigned payload、domain/version、key ID、grant/deployment nonce、output digest 和 anti-replay sequence；验证公钥从 activation trust root 而非 receipt/grant 自身取得；
3. runtime 改为可验证的闭包（root-owned immutable venv/image 的 inventory digest，或签名 OCI/image digest），并显式清理 `LD_*`/Python startup injection；启动前后验证 interpreter、import origins 和受允许 native modules。`python -I` 仅可作为补充防线。

`M6CloseArchiveProof` 也应由同一类 pre-authorized proof-generation deployment 产生并由独立 signer 绑定；仅在输出 proof 中写入 historical verifier hash 不能授权生成该 proof 的新 verifier。

## 应保留的设计方向

- M6 legacy Gate 与未来 M7 wrapper 分离，而不是在历史类上继续加开关；
- construction-only state artifact 不得被 `VERIFY` 或自述 manifest 放行；
- 6/44 应在全新的 authority namespace 中继承，绝不重写历史 ledger；
- archive verifier 的 self-hash 只能作为交叉检查，不能成为唯一信任根；
- M6.5 只允许 synthetic preflight，M7 contract、真实 fit 和 final OOS 继续封印。

## 给质量路由器的结果

```json
{
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-review",
  "verdict": "NEEDS_CHANGES",
  "issue_type": "architecture",
  "reason_code": "PUBLIC_CAPABILITY_CERTIFICATE_AUTHORITY_AND_REPLAY_TRUST_GAPS",
  "blocking_findings": ["P0 legacy public network bypass", "P1 capability boundary", "P1 certificate ordering", "P1 registry TOCTOU", "P1 fit-admission transaction", "P1 signer/runtime trust root"]
}
```

下一步应回到架构/变更设计修订；在这些项关闭并经新的独立审查 `PASS` 前，不应进入 test design、实现、server replay 或任何 M7 fit。
