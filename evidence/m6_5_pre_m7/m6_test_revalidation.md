# M6 独立测试与验证复核

状态：`NEEDS_CHANGES`  
审查者：独立子任务 `/root/m6_test_audit`  
范围：M6 PeerLite source、冻结 spec/gate、测试配置与回归证据；只读，不推进 gate。

## 双重结论

- 历史 M6 工程门：`PASS` 仍成立；它未启用 Gate，已完成的 MSE 历史输出不被追溯否定。
- M6.5（进入 M7 前的 design/code/test review）：`NEEDS_CHANGES`；M7 真实训练禁止启动。

## 关键发现

### [P0，M7 PIT 阻断] Gate 有未来标签路径

`qlib_dataset.py` 把 `label_open`、`label_close` 放入 `market`，而 `PeerLiteModel` 启动 Gate
会无白名单读取整个组；数据构建脚本明确这些列是 T+1 open/T+5 close 标签成分。M6
`market_gate=false`，不受影响；M7 必须使用独立的 T 收盘可得、日期常量 state 产品，并做
PIT/poison rejection 测试。

### [P1] Gate 数据通路当前也无法运行

现有 `market` 按股票变化；模型在同日不恒定时抛出 `ValueError`。这不是可以用开关绕过的
问题，M7 必须先定义并物化按日唯一 state。

### [P1] CCC 实验定义不完整

训练 loss 可以是 CCC，但 early stopping 固定为 MSE。派生 M7 spec 必须预先冻结训练/验证
准则、epsilon、reduction、NaN/tie/singleton 规则，并加入可区分 CCC/MSE checkpoint 选择的
测试。

### [P1] 真实试验账本没有自动导入机制

服务器只写 run-local journal；M7 前必须完成幂等、原子 journal→global-ledger import，覆盖
成功、失败、中断与重跑。

### [P2] post-run archival 审计缺失

M6 pre-run spec validator 要求“当前账本等于 pre-run hash”，post-run 自然不成立，而已有
test 在 gate 存在时绕过完整 validator。需新增 archival verifier，验证 frozen ledger prefix、
pre-run Git/code binding 与 run/verifier/gate 链。

### [P2] 覆盖与集成测试不足

全量 pytest 和 Ruff 已绿，但可测基线显示 `peerlite.py` 约 75% line/branch、`m6_spec.py`
约 30%，并缺少 PeerLite + `DatasetH` 集成、Gate rejection、K32、spec rejection 和 malformed
checkpoint 的有效覆盖。M7 新增核心代码必须实际达到 100% line/branch；不得以旧代码的低
覆盖声称 M7 已验证。

## 新鲜主审复验命令

在当前主工作树实际执行：

```text
env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \
  RUFF_CACHE_DIR=/private/tmp/qlib-peerlite-ruff-cache \
  uv run ruff check src tests scripts --exclude scripts/vendor

env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \
  PYTHONDONTWRITEBYTECODE=1 \
  uv run pytest -p no:cacheprovider

env UV_CACHE_DIR=/private/tmp/qlib-peerlite-uv-cache \
  PYTHONDONTWRITEBYTECODE=1 \
  uv run pytest -p no:cacheprovider --cov=qlib_peerlite --cov-branch --cov-report=term-missing
```

结果：Ruff 通过；pytest `41 passed`；可执行 coverage 基线总计 74%。该覆盖率是缺口证据，
不是 M7 或 M6.5 的通过证据。

