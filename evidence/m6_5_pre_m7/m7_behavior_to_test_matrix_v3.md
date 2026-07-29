# M7 behavior-to-test matrix v3

- 状态：`DESIGN_ONLY / NOT_EXECUTED`
- Subject design：`evidence/m6_5_pre_m7/m7_change_design_v3.md`
- 适用边界：合成测试先行；M6.5 PASS 前无 M7 production code 或 real fit。

| ID | 必须成立的行为 | 层 / oracle |
| --- | --- | --- |
| GATE-01 | 五个 legacy `market_gate=True` 入口在任何 dataset/output/journal/checkpoint load/fit 前拒绝 | unit/integration；固定异常且零副作用 |
| GATE-02 | future adapter只接受 `PIT_QUALIFIED` state product与固定四列顺序 | contract negative；替换 hash/schema/status 均拒绝 |
| STATE-01 | 同日 state 在所有股票行完全一致，exact-date join且无缺日/重复/nonfinite | property/integration；逐日 byte oracle |
| STATE-02 | standardizer只按 unique training dates拟合，valid/test不参与；常量维 scale=1 | unit/metamorphic；股票数变化不改参数 |
| STATE-03 | future membership/status/action/label/execution poison不改变受保护历史 logical payload | PIT behavior；canonical row/schema/null digest相等 |
| CCC-01 | population CCC、eps、date mean reduction与手算一致 | unit；float64 numeric oracle |
| CCC-02 | singleton退化MSE，NaN/Inf失败 | unit negative；精确数值/异常 |
| CCC-03 | train/valid/early-stop使用同一CCC；tie保留最早epoch | unit/integration；固定 checkpoint epoch |
| PEER-01 | Gate分支保持股票顺序置换等变、可变N、单股、mask与跨日期隔离 | property；score permutation/equality oracle |
| SPEC-01 | Gate分支不能改变M6超参；CCC分支不能读取state | contract/mutation；每个越界字段拒绝 |
| BUDGET-01 | M6 `6/44`是唯一 genesis；第一阶段只允许2 candidate/16 fit | contract；第17 fit、第三 candidate拒绝 |
| BUDGET-02 | started即计数；失败/中断不可复用；synthetic authority不能live | fault injection；ledger/claim exact one-shot |
| COMBO-01 | 两隔离分支通过也不能创建组合，除非新预算CR与derived contract存在 | contract negative；无隐式 activation |
| SCORE-01 | 预测唯一键、finite、canonical sort、checkpoint reload exact | integration；key/score digest完全相同 |
| EVAL-01 | benchmark/candidate使用同一weekly mapper、universe与base/stress cost | integration；输入hash和重算指标一致 |
| EVAL-02 | screening固定为IR delta>0、至少5/7正、stress return>=0 | unit/table-driven；边界值oracle |
| OOS-01 | 任何M7 test/runner不得打开2025+或final-OOS | static/fake-fs；open attempt立即失败 |
| RUN-01 | synthetic data→state→adapter→score→manifest→verifier可重复 | synthetic E2E；相同hash、0 real fit |
| RUN-02 | poison、stale head、existing claim、runtime/checkpoint mismatch均无PASS | synthetic fault E2E；fail-closed evidence |

## TDD 与验收顺序

1. 每个行为先产生 reviewed test design。
2. expected-red 必须因目标行为尚未实现而失败。
3. 实现后相同测试转 green；新增/实质修改核心模块 line/branch coverage 100%。
4. independent code review 关闭所有 P0/P1/P2。
5. synthetic E2E 只证明接口与失败边界，不证明 Alpha、PIT certification 或 M7 授权。
6. 真实 M7 只可能在 M6.5 gate、PIT state gate、M6 archival replay、derived contract 与 live
   authority全部 PASS 后启动。

结论：矩阵已覆盖 v3 的数据、模型、预算、组合、复现和 OOS 边界；尚未执行。

