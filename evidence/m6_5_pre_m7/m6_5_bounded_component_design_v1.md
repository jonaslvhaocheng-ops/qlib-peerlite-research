# M6.5 Bounded Component Design V1

- 状态：`DESIGN_ONLY`
- Architecture：`architecture_confirmation_v28.md`
- 范围：M6.5 的 T-known market state、trial-ledger reconciliation、M6 static archive
  verification 与单命令 archival replay。
- 非范围：M7 implementation/fit、生产安全控制面、final-OOS。

## 1. 设计原则

本阶段沿用受信任 research-server operator、单仓库和普通文件权限边界。实现只位于：

```text
src/qlib_peerlite/data/market_state.py
src/qlib_peerlite/governance/trial_ledger.py
src/qlib_peerlite/governance/m6_archive.py
scripts/reconcile_trial_ledger.py
scripts/server/verify_m6_peerlite_archival_replay.py
```

不得新增daemon、privileged helper、multi-process control plane、FD capability passing、namespace、
cgroup、GPU ACL、通用capacity transaction或security-sandbox承诺。历史上为这些能力形成的
capacity/run-authority/sandbox规范全部保留，但分类为
`DEFERRED_PRODUCTION_HARDENING / NON_NORMATIVE_FOR_M6_5`。

## 2. T-known market state

library层是无文件I/O的纯函数，输入唯一键为`(datetime,instrument)`。exact allowlist：

```text
datetime,instrument,in_historical_universe,listed,st,delisting,
tradable,corporate_action_crossover,ret_20,volatility_20,
turnover_mean_20,amount_mean_20
```

任何`label*`、future/execution/purge/embargo字段、额外列、重复键、非布尔状态、非有限特征或
缺失日期均拒绝。`U_state(T)`只含当日已知且
`in_historical_universe & listed & !st & !delisting & tradable &
!corporate_action_crossover`的证券。

每日输出exact：

```text
datetime,population_count,population_key_sha256,
mkt_trend_20,mkt_vol_20,mkt_turnover_20,mkt_amount_20,state_sha256
```

四个state值仅对当日`U_state(T)`聚合；join只能按exact date广播，不得依赖模型行label或未来
股票池。future-poison测试改变`>T`数据后，`<=T` population keys/counts/state bytes必须不变。

## 3. Trial-ledger reconciliation

M6 close prefix是只读历史事实：

```text
candidate_evaluations=6
model_fits=44
prefix_bytes=<immutable binding>
prefix_sha256=<immutable binding>
```

`RunIntent`固定family、run、execution spec content SHA和candidate/fit上限。run-local JSONL
journal中的`CANDIDATE_EVALUATION_STARTED`与`MODEL_FIT_STARTED`在任何未来fit之前durable。

唯一写路径是`reconcile_started_events(...)`：

1. 取得ledger lock；
2. 在byte boundary重验M6 prefix、完整JSONL和event content hash；
3. 验证journal位于声明root，source event identity、family/run/spec与limits一致；
4. source event已存在且bytes/semantic identity相同则no-op；
5. 相同source ID不同bytes、重复evaluation/fit identity或超限则拒绝；
6. 对缺失events按journal顺序追加、flush、fsync；
7. 写独立reconciliation receipt，记录before/after hashes与追加计数。

失败或中断的started event仍计预算；禁止删除、重排或改写历史ledger bytes。

## 4. Static M6 archive verification

`verify_archived_m6_evidence(...)`只读验证：

- M6 gate、run manifest、mechanics和historical verification receipt的file/content hashes；
- frozen Git revision中的verifier/source blobs；
- pre-run和close-time ledger byte prefixes；
- M6 journal started IDs与close prefix中candidate/fit IDs exact集合相等；
- close counts仍为`6/44`，允许ledger在该prefix之后合法追加。

该library函数不加载模型、不写ledger、不运行fit、不生成新的Alpha结论。

## 5. Import and side-effect boundaries

- `data.market_state`只能import schema与NumPy/Pandas；
- governance模块不得import Qlib、Torch或model modules；
- `scripts/**`不能被library import；
- package root import不得隐式加载Torch/PeerLite；
- archival replay是唯一允许加载模型的M6.5 composition root；
- 所有真实CUDA执行属于后续E2E，unit tests只用fake seams。

## 6. Rollback

任一新测试或review失败，只撤回M6.5候选实现/新receipt；M6 immutable evidence、6/44 prefix、
PIT产品和final-OOS seal均不改。本文不授权任何执行。
