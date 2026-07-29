# M6.5 v25 对抗性独立设计审查

- Reviewer：`/root/m65_v24_adversarial_review`
- Author：`/root`
- Reviewed route revision：`163`
- Subject SHA256：
  `f59698a1e76b8bcf9e23895b39222f1abc151c7b36e4cf189d1632d1b9f3f3c2`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=4 / P2=1 / P3=1`

## Findings

### [P1] post-C known clock不能等同source null

`publish<C,effective>=C` 是已公告但尚未生效，不是clock缺失。v25把两者都标UNKNOWN并从
publish起排除，违反冻结 `[effective_from,effective_to)` 与 `max(pub,eff)` 语义。真值表
必须区分 `SOURCE_NULL` 与 `PRESENT_POST_C`；双clock存在且max>=C时transition对pre-C无效，
只有真实缺clock才UNKNOWN。

### [P1] claim后crash无终态，execution不受lease保护

claim fresh CREATED后、observer outcome前crash只能返回consumed，却不能CLOSED或
ABANDONED。global lock在observer前释放还允许下一run并发。需独立execution lease覆盖
claim→durable outcome；crash recovery将已有claim/无outcome确定为
`CLAIMED_INTERRUPTED`，永久消费但不重放。

### [P1] M7 Gate缺少可实现的输入与capability合同

除了V1/V2冲突，还需immutable qualification envelope绑定exact product、fixed PIT audit、
independent behavior audit与derived contract；专用factory必须冻结现有
`2*sigmoid` multiplicative gate、参数、注入点、checkpoint schema，并继续拒绝generic bool。

### [P1] screening前置证据未绑定first fit

当前 `cost_spec` 仍需有效费率receipt，`benchmark_spec`仍需source certificate。derived
contract/live authority/first claim必须在消耗最后16 fits前绑定合格证书、最终spec hash、
weekly mapper与metric implementation hash。

### [P2] CCC accumulation dtype未冻结

必须冻结 prediction/target cast、mean/variance/covariance accumulation dtype、epsilon dtype、
loss return dtype和测试比较规则。

### [P3] private staging清理生命周期未定义

commit后应只unlink staging entries、不修改共享inode，并固定容量告警/回收时机。

## M7 专用结论

`NEEDS_CHANGES`。预算本身可保留：M6 `6/44`，两个隔离分支2 candidate/16 fit，到`8/60`；
第17 fit、第三候选、组合、额外seed、确认和M8 refit继续禁止。

审查只读；未修改文件或ledger，未运行replay、训练、真实数据、PIT CERTIFY或final-OOS。

