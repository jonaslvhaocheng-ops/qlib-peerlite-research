# M6.5 v31 独立设计审查

- Reviewer：`/root/m65_v25_design_review`
- Subject SHA：`f83f2b51861c55f2abd96b051ef6e5546a43c5eff47128aa69c4125f9c28ca87`
- M7 v9 SHA：`ad5ae903ea4eed4593fbb33a33723dea4c653b54cef20519209c5925b315af94`
- Matrix v9 SHA：`0088cf25f5328b4c128d42d4b51772c21648609c41bfaf419fefb19c58841d58`
- Verdict：`NEEDS_CHANGES`
- 严重度：`P0=0 / P1=2 / P2=3 / P3=0`

Findings：

1. [P1] Score replay只接受三列，与冻结M6五列
   `datetime,instrument,score,model_id,fold_id`不兼容；必须先验证model/fold身份再投影。
2. [P1] AP证明没有把official baseline/probe state CSV逐侧连接到从state manifest独立重算的
   state records；遗漏/常量flatten adapter仍可能双边PASS。
3. [P2] 初始admission未明确统一锁序`attempt lease -> GC lock`及lease持有期限。
4. [P2] §4完整替换v30 §4.1后又引用“v30 §4.1其余字段”，composition仍有歧义。
5. [P2] lifecycle逐行`source_record/evidence` hash preimage/locator和session boundary/calendar/
   timezone未闭合，SLA004/SLA006不能机械重算。

已确认改善：official scalar/slots、逐产品15 equality、active reservation计费、owner/post-commit
路径分离、security statement DAG、review hash DAG、authority file binding和M7未授权边界。

M7 v9专用结论：`NEEDS_CHANGES`。只读；未编辑文件/ledger，未运行replay、训练、真实数据、
PIT认证、预算事件或final-OOS。
