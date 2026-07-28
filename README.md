# Qlib PeerLite 机构级量化研究框架

本项目实现一套以 Qlib 为研究底座、以 PyTorch PeerLite 为核心模型的
A 股日频横截面研究框架。第一阶段只产出“研究级 Alpha 候选”，不连接
实盘订单系统。

所有模型共享唯一预测接口：

```text
(datetime, instrument) -> score
```

## 当前研究状态

- 轨道：`STRICT`
- 当前阶段：`M3-STRICT`
- 真实数据研究状态：`DESIGN_ONLY`
- PIT 模式：`VERIFY`
- 允许：工程实现、合成数据测试、从已封存快照构建待审计数据产品、PIT 固定与行为审计
- 禁止：PIT 通过前的真实模型训练、真实回测、最终 OOS 访问和 Alpha 结论

状态真相以 `docs/STATUS.md` 和 `artifacts/progress/events.jsonl` 为准。

## 目录

```text
configs/          冻结前的运行配置
contracts/        研究契约、候选注册表、试验账本、OOS 访问日志
evidence/         OSS 准入、数据源证书和 PIT 证据
scripts/          本地/服务器入口
src/              框架实现
tests/            单元、集成、泄漏与负对照测试
artifacts/        运行产物（大文件默认不进 Git）
```

## 本地安装

本机系统 Python 3.14 不参与项目。项目固定 Python 3.11：

```bash
uv python install 3.11
uv sync --extra dev
uv run pytest
```

Qlib 完整集成是可选依赖，避免基础模型测试被非必要依赖阻塞：

```bash
uv sync --extra dev --extra qlib
```

macOS 上 LightGBM 需要 OpenMP。优先执行 `brew install libomp`；若 Homebrew
源暂时不可用，不要把 Conda 的 `libomp` 强制注入 PyTorch 进程。本机只跑
控制面和合成测试，LightGBM/PyTorch 正式训练放在 Linux 服务器。

## 合成数据端到端演练

```bash
uv run qlib-peerlite synthetic-demo \
  --config configs/synthetic_demo.yaml \
  --output artifacts/runs/synthetic_demo
```

该命令只证明工程闭环，不证明真实数据 PIT、Alpha 或可投资性。

## 真实数据主线

1. 固定官方数据字典、服务器源证书和八个源表的只读快照。
2. 把各源 manifest 和 universe hash 绑定到计划契约。
3. 严格校验并创建新的冻结契约文件，禁止覆盖计划稿。
4. 从固定快照构建完整训练输入并运行 PIT 固定审计。
5. 运行派生特征行为审计；两道 PIT 门都通过后才启用真实训练。

具体命令和门槛见 `docs/RUNBOOK.md`。
