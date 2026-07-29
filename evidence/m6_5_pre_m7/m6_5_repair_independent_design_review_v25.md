# M6.5 v25 独立设计审查

- Reviewer：`/root/m65_v25_design_review`
- Author：`/root`
- Subject SHA256：
  `f59698a1e76b8bcf9e23895b39222f1abc151c7b36e4cf189d1632d1b9f3f3c2`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=4 / P2=1 / P3=0`

## Findings

### [P1] PIT source逐日生命周期不完整

v25没有明确恢复 `known_entry=max(into_pub,into_eff)`、`T>=known_entry` 和
`T>=delist_date`才排除的逐日语义，也没有逐表列出完整 Arrow schema、primary key、冲突
规则和默认状态。实现可提前使用退市事实或得到不同 U_state(T)。

### [P1] run-level ABANDONED会破坏合法多事件run

E1之后合法E2会使 current head超过E1 H_after；E1幂等retry按当前规则会终止整个
registration。claim CREATED后、observer前crash又没有 outcome terminal，既不能重放也不能
CLOSED。需要 event/run两层状态机和 `CLAIMED_INTERRUPTED` 终态。

### [P1] replay staging的prepare/seal/publish/consume顺序不闭合

若 attempt transaction先完成，再添加seal会改变inventory；若尚未完成，child可见点与输出
边界未定义。必须固定：
private build → payload inventory → seal → chmod/fsync/recheck → prepared claim →
publication/completion → child read-only；输出使用另一个事务。

### [P1] M7 v3未绑定V2 product，也没有唯一Gate capability

M7 v3仍写 PreOOSAuxSnapshotV1，而v25只接受V2；`PIT_QUALIFIED`没有不可伪造的
receipt envelope；专用adapter如何在generic Gate永久关闭时构造固定Gate也未定义。

### [P2] M7矩阵混合当前与未来责任

矩阵要求CCC/Gate/score/evaluation全转green，但M6.5只允许design-only。每行必须标注
`M6.5_CONTRACT_ONLY`、`M7_IMPLEMENTATION` 或 `M7_REAL_ACCEPTANCE` owner stage。

## M7 专用结论

`NEEDS_CHANGES`。V1/V2 lineage、PIT qualification handoff、唯一Gate capability及测试责任
分层关闭前，不能形成专用PASS。

审查只读；未编辑仓库/ledger，未运行测试、replay、训练、真实数据、PIT认证、预算事件或
final-OOS。

