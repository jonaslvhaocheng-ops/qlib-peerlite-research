# M6.5 修复包独立代码审查

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/m6_5_code_review`  
审查性质：只读；未修改产品或测试代码，未运行真实训练，未访问最终 OOS，未消耗试验预算。  
审查快照：`2026-07-29T00:21:05+08:00`，基线提交
`82f19ec05deef809d5321568ef7b9aa279c384f6`，工作树含未提交 M6.5 修复。  
质量工作流：`eng-review-code`；风险等级：`R3`。

## 审查范围

- `src/qlib_peerlite/governance/trial_ledger.py`
  (`67f1b545fd718506dc533e8c395a7ce00e9839d900023b7ba15eb4dcd487252d`)
- `src/qlib_peerlite/governance/m6_archive.py`
  (`98a10e539edf62892425478ee1cec95468a7bc147823ddf8836bdbdcf756c3e9`)
- `src/qlib_peerlite/data/market_state.py`
  (`b9b8b1052ae32bf3812a06b42d83520a089cbb9bb3604cc755362375fc470706`)
- `src/qlib_peerlite/data/dataset.py`
  (`2d7880d6f5c2d588db0d8aa09839c47c38b9a53608e81ad1fe1e1cb3bd6b56cc`)
- `scripts/reconcile_trial_ledger.py`
  (`cf518a8435b0c882a49d005d95a7a9435ec3486e3a4a341e5be83d87bf35a8e9`)
- `scripts/server/verify_m6_peerlite_archival_replay.py`
  (`1454f2530c97ed409a4bf5cbc82b9cf71a0e8ea18663abb4067036557571b3dc`)
- 上述模块对应的新测试、M6 evidence 回归测试、M6.5 v2 设计和测试矩阵。

M6 历史 MSE 结论不因本审查失效：M6 未启用 Gate 或 CCC。本报告仅决定 M6.5 能否授权
M7；结论是不能。

## Findings

### [P0] 禁列检查无法阻止 future-conditioned M3 行集合进入 market state

- **位置：** `src/qlib_peerlite/data/market_state.py:77-85,144-168`；
  `tests/test_market_state.py:79-121`。
- **触发：** 先用 M3 supervised matrix 的 `label`、T+1 execution、purge 或 label-action
  条件筛行，再在调用前投影为 `STATE_INPUT_COLUMNS`（必要时补齐 eligibility 布尔列）。
- **影响：** `select_state_population()` 只看调用时的列名，无法观察已经发生的未来条件化。
  因而同日 T+1/T+5 信息可以改变 `U_state(T)`、population count 和 Gate 输入，同时所有当前
  “禁用 label 列”测试仍会通过。这正是 M6.5 要关闭的 Gate PIT 漏洞，M7 Gate 不能在此状态下
  获准。
- **复现证据：** 在临时内存 DataFrame 中，按未来 `label > 0` 过滤三只股票后仅传入
  `STATE_INPUT_COLUMNS`，函数成功接受；只修改同日第二只股票的未来 label，daily
  population 从 `2` 变为 `3`，`state_sha256` 改变。没有真实数据或 OOS 被读取。
- **方向：** 将本纯聚合函数降级为内部 primitive；新增独立的、可验证的
  `market_state_population` builder，只接受 sealed raw snapshot manifest 和 allowlisted raw
  partitions，内部重建 T-known membership/status/feature predicates。其 receipt 必须绑定 raw
  snapshot/partition hash、predicate 与 builder code hash、每日 key/count/state digest；M7 adapter
  必须只接受该已验证 artifact。必须新增“未来筛行后投影掉禁列”的 regression test，且把 M3
  manifest/path 作为 state source 时 fail-closed。

### [P1] Reconcile 将历史 prefix 当成当前 ledger head，允许过期启动状态继续写入

- **位置：** `src/qlib_peerlite/governance/trial_ledger.py:189-228,528-588`；
  `scripts/reconcile_trial_ledger.py:54-84`。
- **触发：** 某 run 在冻结的 prefix 后已有任何合法或未批准 append 时，仍向 CLI 传原
  `LedgerPrefixBinding`；包括 `LedgerPrefixBinding.empty()`。
- **影响：** `_verify_ledger_prefix_bytes()` 只要求该 digest 出现在任意 JSONL 行边界，并不要求
  `raw_before` 就是冻结启动 ledger。因此旧 spec/run 可在未知后缀存在时继续 reconcile，破坏
  预注册 trial 顺序、精确预算前置条件和 crash/recovery 审计；总上限检查不能补救“从错误 head
  启动”的问题。
- **复现证据：** 在临时账本中，先从 empty prefix reconcile `first`，再以同一个 empty prefix
  reconcile `stale`，两次都返回 `appended_events=1`，第二次累计 candidate 为 `2`。无真实账本
  被写入。
- **方向：** 保留 `LedgerPrefixBinding` 仅用于 M6 历史归档验证；为 real-run reconciliation
  单独引入 `LedgerHeadBinding`。只要存在新增 event，就必须在同一 ledger lock 内验证
  `sha256(raw_before)`、bytes 和计数与冻结 head **精确相等**。已经完整 reconciliation 的同一
  journal 才可 no-op；增量 journal 则必须携带上次 reconciliation receipt 的新 exact head。
  增加 stale-head、未知后缀、锁竞争和无字节写入的测试。

### [P1] 同一 run ID 可以用第二份 journal 追加新的 source event

- **位置：** `src/qlib_peerlite/governance/trial_ledger.py:257-264,370-398,515-568`。
- **触发：** 对同一 `run_id` 创建另一份位于 `journal_root` 下的 journal，使用未占用
  `event_seq`/`source_event_id`，再给出当前 prefix。
- **影响：** 代码只确保一个 `source_event_id` 唯一，并没有冻结 `run_id -> journal path /
  output root / allowed event set` 的唯一映射。它允许同一 run 的第二份 journal 扩写 event，直接
  违反 v2 设计的“重复 run ID fail-closed”；这可在预算以内形成未注册的额外 fit 或改变恢复边界。
- **复现证据：** 在临时账本中，`same-run/a.jsonl` 的 seq 1 成功后，
  `same-run/b.jsonl` 的 seq 2 也被接受；ledger 中同时出现
  `same-run/a.jsonl` 与 `same-run/b.jsonl`，返回 `appended_events=1`。
- **方向：** 先冻结并注册不可变 run-intent（run ID、journal relative path、output root、
  execution spec hash、允许的 deterministic source event IDs）；每个 journal event 绑定 intent
  hash。首次注册后，同 run ID 的不同 path、不同 allowed ID set 或不同 payload 必须拒绝；相同
  journal 的完整重试才可幂等。真实 runner 还必须在全程持有 `exclusive_run_lease()`，而不是仅
  定义该 helper。

### [P1] M6 archival replay 未证明实际导入的 source tree 来自受验 frozen archive

- **位置：** `scripts/server/verify_m6_peerlite_archival_replay.py:138-158,195-244,322-379`；
  `evidence/m6_5_pre_m7/m6_frozen_source_0af4572_manifest.json:2`；
  `tests/test_m6_archival_replay_script.py:22-70`。
- **触发：** 用正确 archive 文件配合另一 source root，或按当前本地 evidence 重新执行脚本。
- **影响：** 当前 verifier 要求 schema `qlib_peerlite_frozen_source_v1`，但保留的 transfer
  manifest 使用 `qlib_peerlite_m6_frozen_source_transfer_v1`；因此现有测试没有证明实际 server
  replay 可重跑。即使略过 schema 不一致，archive SHA 和 source root 也是彼此独立校验：脚本
  没有验证 root 是从该 archive 解出的完整 tree，且 receipt 不绑定 archive/manifest/verifier
  digest。未绑定的 import 仍可能来自错误或被修改的模块，削弱“历史 Git 代码上逐 fold replay”的
  证据。
- **复现证据：** 静态交叉检查已确认上述两个 schema literal 不相等；现有测试仅覆盖
  score-digest/fold-loader helpers 和静态 receipt，不调用 `verify_frozen_source()` 或完整
  `run()` 的 source/archive binding 路径。
- **方向：** 统一并冻结 manifest schema。最稳妥做法是 verifier 自行解压已验 SHA 的 archive 到
  临时目录并只从该目录 import；或者验证 manifest 的 archive SHA、完整 deterministic tree
  inventory/digest 与实际 root。receipt 必须写入 archive、manifest、tree 和 verifier source
  digests（以及受控 argv/environment 摘要），M6.5 gate 再绑定 receipt。新增 fake frozen tree 的
  success、schema/archive/root/tree mutation、已预导入 `qlib_peerlite` module isolation tests。

### [P2] 新增核心模块未达到冻结测试计划承诺的 100% line/branch coverage

- **位置：** `evidence/m6_5_pre_m7/m7_test_plan_v2.md:33-38`；当前 coverage database。
- **触发：** 执行当前可用 coverage report。
- **影响：** M6.5 v2 明确要求新增/实质变更核心生产代码达到 100% line 与 branch coverage，
  但没有对应的 pass receipt 或 CI 约束；关键错误路径（坏 JSONL、锁竞争、source conflict、
  archive/source mutation、state provenance）仍未全部被执行。绿色单测不能构成 M6.5 PASS。
- **复现证据：** 当前 `.coverage`（`2026-07-29 00:15 +08:00`）报告：
  `trial_ledger.py` 81%，`m6_archive.py` 72%，`market_state.py` 79%，变更的 `dataset.py` 83%。
  当前 `pyproject.toml` 没有 coverage fail-under/branch gate。
- **方向：** 先添加本报告 P0/P1 所需的 red/green regression 与 fault-injection tests，再用
  `pytest --cov --cov-branch` 对 changed core modules 建立 100% line/branch hard gate，并将原始
  command/output、覆盖率和 source digest 写入 M6.5 receipt。不要通过降低阈值或排除核心模块
  获得 pass。

### [P2] `market_state` col_set 本身没有 schema 或禁列约束

- **位置：** `src/qlib_peerlite/data/dataset.py:22-50`；
  `tests/test_panel_dataset.py:33-40`。
- **触发：** 调用方把 `label`、旧 `market` 字段或少于/多于四个字段放进
  `market_state_columns`。
- **影响：** `PanelDataset.prepare(..., col_set="market_state")` 将原样返回调用方声明的列；
  新 colset 不是安全边界。M7 wrapper 若未另行强制 exact 4D schema，就仍可将 label/旧 market
  送入 Gate。当前测试只证明 happy path 和未知字符串，不证明这个负面契约。
- **方向：** 在将该数据集用于 M7 前，强制 `DAILY_STATE_COLUMNS` 的精确顺序、存在性、与
  feature/label/market 的不相交，并给出 label/old-market/维度/缺列拒绝测试；M7 wrapper 也必须
  独立验证同日广播一致性，不能只相信 Dataset 声明。

## Verdict

`NEEDS_CHANGES`。存在 1 个 P0、3 个 P1 和 2 个 P2；M7 derived contract freeze、真实标签训练、
CCC+Gate 组合和最终 OOS 继续禁止。M6 历史 PASS 保留，但不能用作这些新增 M7 安全边界已通过的
证据。

## Evidence checked

- 设计：`architecture_confirmation_v2.md`、`m7_change_design_v2.md`、
  `m7_test_plan_v2.md`、独立 v2 design review。
- 新鲜静态检查：

  ```text
  env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \\
    RUFF_CACHE_DIR=/private/tmp/qlib-peerlite-ruff-cache \\
    PYTHONDONTWRITEBYTECODE=1 \\
    uv run ruff check src tests scripts --exclude scripts/vendor
  # All checks passed!
  ```

- 新鲜 focused tests：

  ```text
  env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \\
    PYTHONDONTWRITEBYTECODE=1 \\
    uv run pytest -p no:cacheprovider \\
      tests/test_trial_ledger.py tests/test_m6_archive.py \\
      tests/test_market_state.py tests/test_panel_dataset.py \\
      tests/test_reconcile_trial_ledger_cli.py \\
      tests/test_m6_archival_replay_script.py tests/test_m6_evidence.py
  # 22 passed in 3.74s
  ```

绿色结果仅说明现有测试未覆盖上述路径，不改变 findings。

## Residual risks / unverified items

- 未运行真实 server archival replay、真实 M7 fit 或 OOS；这符合任务边界。
- `m6_archive.py` 对 M6 close-time prefix 的历史验证方向正确；本报告不要求更改 immutable
  M6 gate/spec/历史 ledger 行。
- CCC daily validation/early-stop 的实现、M7 wrapper 和真实 raw state-product builder 尚未进入
  本次代码范围；在这些 P0/P1 关闭并取得新的独立审查前，不能把它们视为已实现。

```json
{
  "stage_id": "code-review",
  "skill": "eng-review-code",
  "mode": "review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "PIT_PROVENANCE_AND_TRIAL_LEDGER_IDENTITY_NOT_FAIL_CLOSED",
  "issue_type": "correctness_data_integrity",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 1, "P1": 3, "P2": 2, "P3": 0},
  "reviewer_context": "/root/m6_5_code_review",
  "author_context": "/root",
  "reviewed_head": "82f19ec05deef809d5321568ef7b9aa279c384f6",
  "reviewed_snapshot_at": "2026-07-29T00:21:05+08:00"
}
```
