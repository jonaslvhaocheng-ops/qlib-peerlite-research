# M6 独立代码审查

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/m6_code_review`  
审查范围：`3854cd1^..82f19ec` 的 M6 PeerLite 模型、冻结规范、运行器、验证器、数据接口、
证据和测试。  
审查性质：只读；未修改代码、未运行真实服务器训练、未消耗试验预算。

## 结论

M6 历史 MSE 结论保持有效：M6 明确关闭了 CCC 和 market Gate，且冻结输入/代码/receipt 链
仍可读取。可是 M6.5 进入 M7 的工程审查为 `NEEDS_CHANGES`；以下 P1/P2 均须关闭。

## Findings

### [P1] 将市场状态与未来标签彻底分离

- 位置：`src/qlib_peerlite/data/qlib_dataset.py:15-25,193-201`；
  `scripts/server/build_pit_data_product.py:355-373`；
  `src/qlib_peerlite/models/peerlite.py:263-288`。
- 触发：M7 启用 `market_gate=True` 并读取既有 Qlib `market` 列组。
- 影响：该列组含 T+1 开盘的 `label_open` 与 T+5 收盘的 `label_close`，会形成未来泄漏；
  同时每股不同，而 Gate 要求每日期唯一状态，当前会 fail-closed。
- 方向：建立独立、因果、按日唯一的 `market_state` 产品；物理排除 `label_*`，并增加
  PIT、future poison、同日唯一性和 label-column 拒绝测试。

### [P1] 使 M6 的全局试验账本证据可追加

- 位置：`evidence/gates/M6_peerlite_gate.json:90-96`；
  `tests/test_m6_evidence.py:39-54,73-92`。
- 触发：任何合规 M7 event 追加至 `contracts/trial_ledger.jsonl`。
- 影响：M6 gate 绑定了完整可追加文件的 SHA，测试也把总数永久断言为 `6/44`；合法 M7
  追加会令历史 M6 验收错误变红。
- 方向：保持历史 M6 gate 不变；改为验证 M6 close-time ledger 前缀 hash/字节边界/事件集合，
  并允许后续 append。

### [P1] 将已启动或失败的 fit 自动纳入全局预算账本

- 位置：`scripts/server/run_m6_peerlite.py:143-153,243-257,659-714`。
- 触发：服务器在 `MODEL_FIT_STARTED` 后中断、异常或人工停止。
- 影响：run-local journal 有记录，但不存在受测的 journal→global-ledger 原子、幂等导入；
  后续 preflight 可能漏计已消耗的真实 fit，突破试验预算。
- 方向：M7 前实现含锁、source-event identity、前缀校验和幂等的 reconciliation；fit 启动即
  占用预算，失败/中断同样落账。

### [P2] 独立验证器未实际验证逐折预测与 checkpoint 对应关系

- 位置：`scripts/server/verify_m6_peerlite.py:201-242,311-350`。
- 触发：逐折预测错配、fold ID 错标或 checkpoint 与预测不一致，而 receipt 自身仍一致。
- 影响：验证器仅验证 inventory/receipt 声明与合并 prediction schema，未消费每折
  `row_counts`/`key_sha256`，也未真正加载 checkpoint 重放；“独立 replay”证据不足。
- 方向：新增 versioned archival verifier，在绑定 product 与历史代码版本上重建每折、加载
  checkpoint，并比较 test key 与 score digest；不覆盖旧 verifier receipt。

## 审查证据

- 相关 focused tests 14 项、全量 tests 41 项通过。
- Ruff、`git diff --check` 通过。
- M6 frozen spec、gate、run manifest、verification receipt、ledger 和上游标签构建路径已交叉
  检查；`0af4572` 绑定的 10 个代码/锁文件 hash 匹配。
- 未运行真实训练或最终 OOS。

## 残余风险

- CCC 当前训练使用 CCC 但 early stopping 验证仍为 MSE；M7 派生规范必须明确 checkpoint
  选择语义。
- M6 pre-run validator 本就不能在 post-run ledger 上再次作为“pre-run PASS”运行；需要新增
  archival verifier，而非篡改历史。

