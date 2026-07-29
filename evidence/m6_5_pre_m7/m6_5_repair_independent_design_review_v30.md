# M6.5 v30 独立设计审查

- Reviewer：`/root/m65_v25_design_review`
- Subject SHA：`28bab313bc07f4d9ffc838a0256f8dbc8f71fb86df320dc31f206c87e7f1746b`
- M7 v8 SHA：`9a5a3c5d1034efdb947f744d124a80e8657ee9c303f6021ffaff02dc77ebbebc`
- Matrix v8 SHA：`932ac1b4dc61e58bf1fd860402d64c5e7d39eafceb37b3563c61c6cd281a7d89`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=2 / P2=2 / P3=0`

Findings：

1. [P1] `AuxPrefixBehaviorVerificationV1`只有一组aggregate
   count/key/value digest，不能分别表达aux、population、state的original/probe schema、
   key/value/logical digests与逐项相等结论。
2. [P1] capacity admission没有把并发未落盘reservation计入aggregate，也没有
   RESERVED/MATERIALIZING/COMMITTED/ABORTED/RELEASED与orphan恢复/清理状态机。
3. [P2] `SecurityLifecycleAvailabilityAuthorityV1`只有要求，没有exact keys/types、逐row
   available-time表示、canonical hash与validation receipt closed schema。
4. [P2] v30完整替换v29 §5后又以“与v29 §5相同”模糊继承score canonicalization，composition
   不自洽；必须完整重述或绑定独立exact-SHA规范。

已确认关闭：registration→commit→receipt单向DAG、`-S` bootstrap、Gate state join和float64
population standardizer、supplement/review receipt strict schema、lifecycle authority缺失时HOLD、
COMMITTED 0440及M7未授权边界。

M7 v8专用结论：`NEEDS_CHANGES`。只读；未编辑文件/ledger，未运行replay、训练、真实数据、
PIT认证、预算事件或final-OOS。
