# M6.5 R3 修复设计独立快速审查

状态：`NEEDS_CHANGES`  
审查性质：只读设计审查；未修改产品代码、测试、契约或历史 ledger；未执行训练或访问最终 OOS。  
审查对象：`m6_5_repair_change_design_v1.md`（SHA256 `27a88f…bd53`）、
`architecture_confirmation_v3.md`，以及 `market_state.py`、`trial_ledger.py`、
`verify_m6_peerlite_archival_replay.py` 和两份独立审计。

## 结论

三条修复方向是正确的：raw-snapshot state artifact、精确 ledger head/run authority、
archive-only replay 都比当前实现更强。但设计尚未把这些对象锚定到外部冻结身份；目前的
自描述 hash/receipt 只能证明内部一致，不能证明来源、前驱 head 或实际 verifier。存在 1 个
P0、2 个 P1 和 1 个 P2，故不得放行 M7。

## Findings

### [P0] state artifact 只有自证明，没有可验证的 provenance trust anchor

**位置：** 设计 §3.1「artifact 格式和 loader」（尤其是 manifest/self-hash 与
`load_verified_market_state_artifact(path)`）；架构确认的 “allowed source kind” 边界。

**触发：** 调用方从 future-conditioned M3 行集合构造 `population.parquet` / `daily_state.parquet`，
重算文件 hash、daily digest、`content_sha256`，并在 manifest 写入
`source_kind: SEALED_RAW_SNAPSHOT`、已知 snapshot bundle SHA 和其自选 builder/predicate SHA；再将
该目录交给计划中的 path-only loader。设计没有要求 loader 对照一个预先冻结的 build binding 或
预期 artifact manifest hash，因此所有列出的内部检查都可通过。

**影响：** T+1 label/execution/purge 已条件化的成员集可再次进入 `U_state(T)`，重开独立代码审计
已证明的 PIT 漏洞；`BUILT_NOT_PIT_QUALIFIED` 状态不能补足来源真实性。

**最小修复：** 在 build 前冻结一个独立的 `market_state_build_binding`：精确绑定 snapshot bundle
及允许 source-manifest inventory、builder/feature/predicate/schema blob hash 和输出协议。loader 必须
接收并验证该外部 binding（而不只接收目录），后续 M7 derived spec 再绑定最终 artifact manifest
SHA。新增“篡改后重算所有 self-hash”的 M3/future-condition regression，仍须 fail-closed。

### [P1] exact-head、续接链和预算仍可由调用方替换

**位置：** 设计 §3.2 的 `RunIntent.initial_ledger_head`、
`register_run_authority(..., expected_head)`、`reconcile_started_events(..., expected_ledger_head)` 与
CLI 的 `--expected-head-*` / limits 输入。

**触发：** 冻结 intent 的 `initial_ledger_head=H0` 后，ledger 已合法推进至 `H1`；调用方传
`expected_head=H1` 注册。文本要求 ledger 等于 `expected_head`，却未要求它等于 intent 内的 `H0`。
同样，某次 receipt 后若出现未知后缀，调用方可读取当前 head 并作为下一次 CLI 输入；设计未要求
该 head 是同一 authority 上一张 receipt/retained chain 的后继。`TrialLimits` 也仍是分散 CLI 输入，
不在给出的 canonical `RunIntent` 内。

**影响：** 过期 intent 可从较晚 head 启动，或在未知后缀后继续写入；预算上限也可被替换。这样正好
违背设计声称的 “initial exact head / unknown suffix fail-closed”，并使 crash recovery 无法区分自身
注册后的可恢复状态与外来 tail。

**最小修复：** 删除注册时独立的 head/limit 权威输入：注册时只比较锁内 raw bytes 与
`intent.initial_ledger_head`，并把 limits（或 immutable budget/spec binding）放入 canonical intent。
每条 authority/reconcile retained record 应保存 `intent_sha256`、前/后 exact head 与前一 receipt/chain
hash；续接仅接受该 authority 的最后一个已验证链头。CLI 只能提供该 receipt/binding，不能自由填写
current head 或 limits。将 run lease 作为实际 public operation 的强制前置条件，并测试 H0/H1 替换、
未知 tail、注册后崩溃和 budget-flag 替换均零字节写入。

### [P1] archive-only import 尚未形成受冻结 verifier/archive/tree 绑定的可执行闭环

**位置：** 设计 §3.3、§4；现有
`scripts/server/verify_m6_peerlite_archival_replay.py` 的外部 source root 接口；
`m6_frozen_source_0af4572_manifest.json`。

**触发：** 用修改过的 verifier 执行 replay，并让 receipt 写入它自己的 SHA；或用另一 archive 及其
自报 SHA/tree digest。设计说 receipt “绑定”这些值，却未定义一个**执行前冻结**且由
`m6_archive.py`/M6.5 gate 精确比较的 verifier+archive+manifest/tree binding。另，现有 transfer
manifest schema 是 `qlib_peerlite_m6_frozen_source_transfer_v1`，设计要求 extracted tree 中的
`qlib_peerlite_frozen_source_v1`，但没有迁移、位置或 inventory-digest 比较规则。

**影响：** receipt content hash 只能证明自报字段彼此一致，不能证明产生 14/14 replay 的就是批准的
verifier 和已批准 archive；按字面实现还可能对现有正确 archive fail-closed，无法完成 required
server replay。仅清除 `sys.modules` / 插入 `sys.path[0]` 也不足以留下已导入模块 origin 都在 extract
tree 内的证据。

**最小修复：** replay 前冻结 `m6_archival_replay_binding_v1`，精确锁定 verifier blob SHA、archive
SHA/bytes、single root、internal manifest schema/path/SHA、canonical tree-inventory algorithm+digest、
historical receipt 与 run/product/ledger bindings；receipt validator 必须与该 binding 比较。明确是重建
含 v1 manifest 的 archive，还是版本化验证既有 transfer-v1，并将其纳入上述 binding。safe extractor
只允许规范化后的 regular file/directory member；import 后断言所有 `qlib_peerlite*.__file__` 位于
temporary tree，并恢复 import state。补充 decoy pre-import、verifier mutation、tree/manifest mutation
与 schema-mismatch tests。

### [P2] state artifact 的可重复发布与 summary digest 协议未冻结

**位置：** 设计 §3.1 artifact layout/manifest、§3.4 failure handling。

**触发：** builder 在两个 parquet 文件与 manifest 之间崩溃，或两种实现对 “daily state/keyset digest
summary” 使用不同排序、float serialization 或 inventory 规则。

**影响：** loader 虽可拒绝部分目录，但重试、证据复算和跨环境审计没有唯一 publish/digest 语义；这不
直接放开未来信息，却会削弱可复现性和故障证据。

**最小修复：** 固定 canonical summary 算法（日期排序、字段顺序、float64 encoding、文件 inventory）
并给出已知 digest oracle；以同目录 temp build + fsync + atomic directory publish 写出 manifest，
loader 只接受带 completed publish marker 的 artifact。加入 mid-publish crash/retry 测试。

## 已确认的正向边界

- 保留 `LedgerPrefixBinding` 只服务 M6 archive 历史 prefix，而不是新 run 的 current head，方向正确。
- archive-only temporary extraction 与清理预导入 `qlib_peerlite` 模块是必要控制；问题是仍需预冻结
  identity 及 origin postcondition。
- 本设计没有授权真实 fit、CCC/Gate、组合或最终 OOS；这些限制应维持到上述问题和后续独立测试
  receipt 全部 PASS。

```json
{
  "stage_id": "design-review-fast",
  "mode": "read-only-independent-review",
  "verdict": "NEEDS_CHANGES",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 1, "P1": 2, "P2": 1},
  "reason_code": "UNANCHORED_PROVENANCE_HEAD_AND_REPLAY_IDENTITY"
}
```
