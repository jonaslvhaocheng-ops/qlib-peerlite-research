# M6.5 第七步前独立测试与覆盖率审计

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/m6_5_test_audit`  
审查方式：只读；未修改产品代码、测试代码、契约、历史账本或服务器数据；未启动训练、未访问最终 OOS。  
审查时间：2026-07-29（Asia/Shanghai）

## 审查结论

现有 M6.5 测试能证明若干局部机制可工作，但不足以放行 M6.5 或授权 M7。没有发现已经执行真实训练或最终 OOS 访问的证据；因此没有 P0。以下 P1 必须先关闭。

## Findings

### [P1] 新增核心模块未满足已冻结的 100% line/branch 覆盖率门槛

- **位置：** `evidence/m6_5_pre_m7/m7_test_plan_v2.md:35-38`；
  `src/qlib_peerlite/governance/trial_ledger.py:1-637`；
  `src/qlib_peerlite/governance/m6_archive.py:1-372`；
  `src/qlib_peerlite/data/market_state.py:1-285`；
  `scripts/server/verify_m6_peerlite_archival_replay.py:1-426`。
- **触发：** 将当前 61 个测试或 22 个 M6.5-focused 测试作为 M6.5 PASS 证据。
- **影响：** 账本的错误/锁分支、M6 evidence-chain 的篡改分支、state product 的 fail-closed 分支及 replay 主流程尚未被证明；绿灯测试数量不能替代门槛。
- **证据：** 本次使用可工作的路径式 coverage 命令测得：
  - `trial_ledger.py`：81%；
  - `m6_archive.py`：72%；
  - `market_state.py`：79%；
  - `verify_m6_peerlite_archival_replay.py`：20%；
  - `reconcile_trial_ledger.py`：98%（仍有一个 CLI exit 分支未覆盖）。
- **最小修复方向：** 根据本报告的“最低补测矩阵”补齐行为和故障分支；重新执行 line + branch coverage，并把原始命令、输出和各新模块 100% 结果写入不可变 M6.5 测试 receipt。不得降低 `m7_test_plan_v2` 的门槛。

### [P1] 14 折 M6 server replay receipt 没有绑定实际执行的 verifier 或冻结源码归档

- **位置：** `evidence/m6_5_pre_m7/m6_archival_replay_server_receipt.json:1-178`；
  `scripts/server/verify_m6_peerlite_archival_replay.py:195-383`；
  `tests/test_m6_archive.py:39-64`。
- **触发：** verifier 脚本在实际 server replay 后发生修改，或以不同脚本/源码归档生成同格式 receipt。
- **影响：** 当前测试仅固定本地 receipt 文件的 SHA 和其自报字段；receipt 不含 `verifier.path/sha256`，也不含冻结 source archive/manifest 的可验证 binding。因此不能独立证明当前审查的 replay 代码正是产生“14 个 checkpoint exact match”的代码。
- **证据：** 当前 replay 脚本在 `:354-357` 已写出 verifier binding，但现有 server receipt 中没有该字段；现有脚本测试仅覆盖 `score_digest`、parquet loader 和 score mismatch helper（`tests/test_m6_archival_replay_script.py:22-70`），没有覆盖 `run()` 的 source/product/checkpoint/ledger safety path。
- **最小修复方向：** 固定并哈希实际执行的 verifier 与 source archive/manifest，写入新的只读 server replay receipt；以该冻结版本重新运行 14 折 checkpoint replay（`model_fit_calls == 0`、无 2025+、ledger 不变）。测试必须拒绝：缺 verifier hash、错误 archive hash、篡改 checkpoint/prediction/fold receipt，且验证 receipt 的 verifier SHA 与冻结脚本一致。

### [P1] 账本的并发 lease、run-ID 重用和 crash-recovery 公共路径没有被测试或接入可执行 runner

- **位置：** `src/qlib_peerlite/governance/trial_ledger.py:463-469,528-630`；
  `scripts/reconcile_trial_ledger.py:71-84`；
  `tests/test_trial_ledger.py:121-301`；
  `evidence/m6_5_pre_m7/m7_test_plan_v2.md:13-15`。
- **触发：** 两个进程同时 reconcile、一个进程在 journal fsync 后停止、或一个已完成的 `run_id` 被再次用于真实 fit。
- **影响：** `exclusive_run_lease()` 存在但当前 CLI 不持有它，且没有 M7 runner/preflight 调用点；现有测试只验证同一 journal 的串行幂等导入。它不能证明“同一 run 不会二次 fit”或“并发情况下前缀、预算和结果仍只提交一次”。这直接关系到不可挪用的 fit budget。
- **证据：** `tests/test_trial_ledger.py` 没有多进程/锁竞争测试、没有 `exclusive_run_lease()` 测试，也没有 run-ID completed/reuse rejection 测试；`rg` 显示该 lease 没有实际调用方。
- **最小修复方向：** 在真实 M7 run public boundary 固定以下顺序并测试：journal fsync → 同一 server authority 下 reconcile（锁内 prefix + semantic ID + budget）→ exact reconciliation preflight → 持续 run lease → 才可 `fit`。新增双进程竞争、lock-held fail、replace/write 故障后重试、同 run-ID 重用拒绝和已启动未完成 fit 保守计数测试。若 M7 runner 尚未实施，这一项只能标记 `NOT_IMPLEMENTED`，不能以 library unit test 通过替代。

### [P2] M6 archive 的篡改测试只覆盖了最外层 gate content hash，未覆盖 A2 所要求的证据链突变

- **位置：** `tests/test_m6_archive.py:28-36`；
  `src/qlib_peerlite/governance/m6_archive.py:104-287`；
  `evidence/m6_5_pre_m7/m7_test_plan_v2.md:10-12`。
- **触发：** execution spec、static receipt、M6 close-time ledger prefix、journal-to-ledger ID mapping 或 frozen Git blob 被篡改且攻击者/错误同时重算外层 gate content hash。
- **影响：** 现有 test 改 gate 内一个字段但不重算 `content_sha256`，因此在最早的 gate-hash 检查即失败；这不是 `_verify_static_evidence`、pre-run prefix、journal mapping 或 frozen-code validator 的 mutation proof。
- **证据：** `test_archival_verifier_rejects_tampered_gate_copy` 只断言 `match="content hash"`。`M65-A2` 明确要求 receipt/spec/score/checkpoint mutation 均导致 verifier fail。
- **最小修复方向：** 用内容 hash 已重新计算的临时 gate/evidence fixture，分别突变 spec binding、M6 close prefix、run journal ID、historical verifier Git revision、fold receipt、checkpoint/prediction digest；每例断言具体 fail-closed error，且不允许产出 PASS receipt。

### [P2] market-state 测试只证明纯 DataFrame primitive，未证明真实 PIT artifact 边界；其中“顺序稳定性”测试实际把输入排回原顺序

- **位置：** `src/qlib_peerlite/data/market_state.py:144-285`；
  `tests/test_market_state.py:71-76,104-121,124-165`；
  `evidence/m6_5_pre_m7/m7_change_design_v2.md:32-67`。
- **触发：** source projection 在上游引入 label/execution/future-action 语义，或内部股票排序变化影响 daily state digest。
- **影响：** 目前没有 sealed raw snapshot → independent `market_state_population` artifact/manifest builder，也没有 source snapshot、feature-spec、code hash 的测试。因此测试不能证明 opaque `feature_eligible` 或其他资格布尔值没有来自未来条件。另 `reordered.sort_index()` 把第 71 行的 descending-instrument 重排恢复为默认排序，故第 76 行并未真正检验 permutation invariant。
- **证据：** 当前 module 自述为 pure primitive（`market_state.py:1-5`），且 repository 没有该 population artifact builder；现有 future poison 只改变未来日期数值，label poison 则通过“输入字段被拒绝”证明，而非 source-lineage mutation。
- **最小修复方向：** 在合成 sealed-source fixture 上增加独立 builder/manifest contract test：future label、T+1 limit/halt、future action、label-validity 变化都不能改变早于该事件日期的 keyset/count/state SHA；manifest 必须绑定 source snapshot、feature spec、predicate/code hash。将顺序测试改为直接传入仍按日期单调但同日 instrument 逆序的 frame，并加入固定已知 `state_sha256` oracle、错误 state digest、非有限 daily state、错误布尔类型和重复 state date 测试。真实 raw snapshot PIT audit 仍须在派生契约冻结后单独完成，不能把合成测试描述为 PIT PASS。

## 通过但不足以放行的证据

| 检查 | 结果 | 限制 |
| --- | --- | --- |
| Ruff | PASS | 仅静态风格/部分静态错误；不证明治理行为。 |
| M6.5 focused tests | PASS，22 passed | 没有覆盖前述 P1/P2 分支。 |
| 全量 pytest | PASS，61 passed | 同上；不等于 coverage/故障/服务器路径验收。 |
| 历史 M6 archive verifier | PASS（本机 evidence-chain） | 不替代绑定了 verifier 的逐折 server replay 证据。 |
| 已保存 server replay receipt | 存在，self-reported 14 folds / 0 fits | 缺执行 verifier/source archive 的不可变 binding。 |

## 与 `m7_test_plan_v2` 的覆盖映射

| 计划 ID | 当前状态 | 说明 |
| --- | --- | --- |
| M65-A1 | PARTIAL | close-prefix append 和 archive happy path 有覆盖；完整 mutation coverage 缺失。 |
| M65-A2 | FAIL | 没有 receipt/spec/score/checkpoint 的可归因 mutation test。 |
| M65-A3 | PARTIAL | 有 server receipt，但没有 executable verifier binding；local test 未执行 replay main path。 |
| LEDGER-U1 | PARTIAL | started event/import/idempotency 有测试；crash/restart/terminal event lifecycle 不完整。 |
| LEDGER-U2 | PARTIAL | prefix、budget、semantic ID、wrapper replace-failure 有测试；锁竞争/真实 write fault 缺失。 |
| LEDGER-U3 | FAIL | same-journal unreconciled 检查存在；duplicate run ID 与 real-run preflight 尚未实现/测试。 |
| POP-U1 | PARTIAL | narrow schema/forbidden fields有单元测试；无真实 source builder/lineage binding。 |
| POP-U2 | PARTIAL | future-date numerical mutation有测试；T+1/execution/action/raw-source mutation与 artifact digest缺失。 |
| POP-U3 / STATE-U1 / STATE-U2 | PARTIAL | 若干 empty/duplicate/missing-date case 有测试；状态 digest、malformed product、全分支 fail-closed 缺失。 |
| CCC-U1 及以后 M7 行为 | NOT_IMPLEMENTED | 合理地未运行；不得在本 M6.5 audit 中宣称 PASS。 |

## 最低补测矩阵

| ID | 层 | 最小确定性场景 | Oracle |
| --- | --- | --- | --- |
| QA-L1 | unit/fault | 在 `_atomic_replace_bytes` 的真实写入/replace/fsync 子步骤注入故障 | 旧 ledger bytes 不变、无 partial JSONL、重试只追加一次。 |
| QA-L2 | integration/multiprocess | 两个独立进程对同一 ledger reconcile；另一个持有 run lease | 每个 source event 至多一次；一个 lease 请求 fail-closed；预算不超限。 |
| QA-L3 | public-boundary | 已 reconciliation 的 run-ID 再次请求 `fit` | 明确拒绝且 ledger/输出不变。 |
| QA-A1 | server acceptance | frozen verifier + frozen archive 只读重放 14 folds | receipt 中 verifier/archive/manifest SHA 与实际 bytes 相等，`model_fit_calls=0`，ledger hash 前后相同。 |
| QA-A2 | unit/mutation | 重新签名外层 hash 后分别损坏 gate/spec/prefix/journal/Git blob/checkpoint/prediction | 每一种在相应 validator 处 fail，不能误报 PASS。 |
| QA-S1 | unit/property | 同日 instrument 真正逆序、固定 digest oracle、坏 digest/NaN/重复日期/错误 bool | state 值和 digest 不变或明确 fail-closed。 |
| QA-S2 | synthetic integration | sealed raw source builder 的 future label/execution/future-action poison | 过去日期 keyset/count/state digest byte-identical；manifest binding 完整。 |
| QA-C1 | measurement | 只覆盖新增/变更核心模块的 line + branch run | 每个目标模块 100%；原始输出入 receipt。 |

## 执行证据

```text
env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \
  PYTHONDONTWRITEBYTECODE=1 \
  uv run ruff check src tests scripts --exclude scripts/vendor
# PASS

env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \
  PYTHONDONTWRITEBYTECODE=1 \
  uv run pytest -p no:cacheprovider -q
# 61 passed in 6.88s

env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \
  PYTHONDONTWRITEBYTECODE=1 \
  COVERAGE_FILE=/private/tmp/m65_test_audit_coverage_src_scripts \
  uv run pytest -p no:cacheprovider --cov=src --cov=scripts --cov-branch \
  --cov-report=term-missing \
  tests/test_trial_ledger.py tests/test_reconcile_trial_ledger_cli.py \
  tests/test_m6_archive.py tests/test_m6_evidence.py \
  tests/test_market_state.py tests/test_panel_dataset.py \
  tests/test_m6_archival_replay_script.py -q
# 22 passed; target coverage values reported above
```

审查快照：Git `82f19ec05deef809d5321568ef7b9aa279c384f6` 加未提交 M6.5 文件；关键文件 SHA256 已由本审查运行记录。当前输出不授权 M7、CCC/Gate、组合、真实 fit 或 final OOS。

## Verdict

`NEEDS_CHANGES`。下一步应先修复最早的 P1：coverage 与 server-replay evidence binding；随后完成 ledger 的并发/run-ID public-boundary proof，再重新进行独立 tests-green/code-review/E2E 审计。
