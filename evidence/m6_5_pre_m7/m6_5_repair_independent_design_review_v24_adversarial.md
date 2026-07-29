# M6.5 v24 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Author：`/root`
- 模式：独立只读 R3 adversarial design review
- Subject：`evidence/m6_5_pre_m7/m6_5_repair_change_design_v24.md`
- Subject SHA256：
  `6a4a744aa60fbde0cd037b481f15be9c4ad573087b009e87f00d3f0f228721b6`
- Reviewed route revision：`159`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=2 / P2=4 / P3=0`

## Findings

### [P1] 当前 M7 design/test/review 工件链为空

批准的 change request 与 v28 architecture 要求 M6.5 产出当前 hash-bound 的独立 M7
design review 和 behavior-to-test matrix。旧 M7 v2 工件已被明确降为历史 reference，v24
却只安排 compatibility pointer。因此即使实现、测试、code review 和 E2E 均完成，M6.5
仍没有可执行的 PASS 路径。

修复要求：在当前成功路径中加入 v28/当前 canonical design 绑定的 M7 design-only spec、
CCC/组合/预算规则、行为测试矩阵及独立 R3 review；继续禁止 runner、live authority、真实
fit、预算消费和 final-OOS。

### [P1] 目录 publication recovery 依赖尚不存在的 marker

publisher 占用 final namespace 并发布部分 payload 后、在最终 marker 前崩溃时，loader
拒读而 retry 没有 durable inventory、owner token、generation 或 recovery lock，无法区分
死亡 publisher 与慢 publisher。

修复要求：冻结私有 sibling staging、durable prepared inventory/owner token、单一
recovery lock/lease 和明确 commit point；或者采用能提供完整目录原子发布的更小协议。

### [P2] one-shot claim 未冻结 canonical slot 与 CREATED/EXISTS 语义

通用 no-replace helper 把相同 bytes 的既有文件视为 idempotent success，但 claim 的既有
文件必须永不再次放行 observer。设计也没有冻结 claim 唯一派生路径。

修复要求：claim slot 只能由 registration 与 source-event/attempt identity 派生；publish
API 必须返回 `CREATED` 或 `ALREADY_EXISTS_IDENTICAL`，只有 `CREATED` 可放行 observer。

### [P2] staging 未兑现 runner 无写权限

copy/hash 后 staged worker、checkpoint 或 product 仍可能由 child identity 写入。post-run
rehash 也不能发现“短暂修改后恢复”的输入。

修复要求：child 启动前冻结 file/directory mode、reader/writer boundary 或 FD policy，并
执行 pre/post inventory checks；same-uid 边界只能给出 cooperative-process 证明上限。

### [P2] future-poison 比较对象与 canonicalization 未定义

比较整个 product 会因 provenance source SHA 变化而必然不同；比较 Parquet bytes 又受 scan
chunking、row group、compression 和 metadata 影响；只比较 logical rows 时当前没有唯一
tuple/schema/null serialization。

修复要求：使用 canonical sorted logical payload + schema/null semantics 作为 protected
oracle，original/poison source identity、mutation ledger、code/env 单独绑定。

### [P2] RuntimeBinding 是 issuer 自采 identity

issuer 从任意同版本环境启动后可把自身 executable/module origins 写入 binding，child 与
issuer 自洽即通过；module origin 也未绑定 module/shared-library bytes。

修复要求：pre-execution trusted policy 提供允许的 executable hash/path 与 dependency
binary closure，issuer/child 均验证外部 expected identity。历史缺失的 driver/cuDNN
identity继续标为 compatibility-only，14-fold exact score承担功能兼容判据。

## Preserved strengths

保留 v28 有界架构、v27 特权控制面禁入、Gate fail-closed、独立 aux verifier、M6 `6/44`
prefix/current head 分离、count-before-attempt、attempt staging、safe extraction、
`14 replay / 0 fit / ledger unchanged` 与 M7/final-OOS 封印。

## Review limits

本审查未读取真实 source values、Parquet row groups、checkpoint 或 CUDA runtime；未给出 PIT
PASS、row-group acceptance 或 replay acceptance。审查只读，未编辑仓库、调用 quality
ledger、运行 replay/训练/真实数据/PIT CERTIFY 或访问 final-OOS。

