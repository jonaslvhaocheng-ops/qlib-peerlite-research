# M6.5 研究治理威胁模型 v1

状态：`FROZEN_FOR_M6_5_DESIGN_REVIEW`

目标：保持机构级研究治理强度，但不把日频研究框架扩展为生产级 hostile-host 安全平台。

## 受信根

- 服务器治理 supervisor、其受控 root、操作系统 ACL 和冻结代码 revision；
- 已冻结研究契约/计划、M6 close proof、数据 snapshot 与 PIT executor；
- `research-runner` 与 `result-publisher` 两个受控 Unix identity 的职责边界。

## M6.5 必须防止

- 未来标签/执行信息经 legacy Gate、伪造 state 或错误 join 进入官方 M7 输入；
- 服务器 legacy `4/29` ledger 代替已验证 M6 close `6/44` 成为预算起点；
- 正常并发启动、重启、崩溃、半写文件、路径/配置误选造成重复授权 fit、错误输入或半成品官方结果；
- 绑错 archive/verifier/launcher/runtime/environment 的只读 M6 replay；
- 任意研究脚本直接把 staging、checkpoint 或未终态预测当作 official result。

## 明确不在 M6.5 的对手模型

- 已取得 `research-runner` 任意代码执行权的恶意操作者，例如 ctypes/raw syscall 绕过冻结 runner、直接调用
  PyTorch 任意次数或伪造进程内对象；
- governance supervisor/result-publisher/control root、内核或签名密钥被攻破；
- 恶意 native extension、LD_PRELOAD 等在受控 launcher 之外注入。

这些属于生产化阶段的 host/identity compromise，需要独立隔离主机、sandbox/attestation/密钥管理；不能由本项目
内 Python API 或账本格式可信解决。若发生，相关 run/evidence 全部无效。

## M6.5 实现承诺

- authoritative runner 只运行冻结、代码审查过的入口；普通 library 调用是 mechanics-only，不能创建 official result；
- supervisor 将 verified inputs materialize 到私有 immutable job snapshot；runner 无写权限，copy/hash/ACL/FD
  再核验阻止正常 TOCTOU；
- runner 只在计划的 single-worker command 下执行，O_EXCL dispatch claim 处理正常竞争/重启；不将恶意 raw fork
  当作可由 M6.5 防御的普通并发；
- result-publisher 是独立写 final/index 的受控身份；official resolver 仅接受其 terminal receipt；
- replay supervisor 以 `env -i`、固定 runtime/argv 启动批准 launcher，并产生独立可验证 execution receipt。

本阶段结论上限是“可审计、可复现的研究治理系统”，不是交易生产系统或敌对主机安全认证。
