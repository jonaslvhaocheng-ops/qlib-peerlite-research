# Qlib PeerLite 数据源证书

- 生成时间：`2026-07-28T15:06:12.780166+08:00`
- 模式：`DISCOVER`
- 正面证据上限：`CANDIDATE_PATH_ONLY`
- 状态：`NEEDS_EVIDENCE`

当前物理字段、样本和数据库可读性不能证明历史市场可得时间、修订保留、
公告时点、公司行动或完整 PIT 股票池。

## 表级摘要

| 来源 | 角色 | 存在 | 日期范围 | 列数 |
| --- | --- | ---: | --- | ---: |
| `datayes.mkt_equd` | raw_daily_market | True | 1990-12-19 ~ 2026-07-27 | 22 |
| `datayes.md_security` | security_master | True | 1870-05-30 ~ 2026-08-03 | 18 |
| `datayes.md_trade_cal` | trade_calendar | True | 1990-12-19 ~ 2027-12-31 | 14 |
| `datayes.mkt_equd_eval_new` | valuation_liquidity_candidate | True | 2007-04-06 ~ 2026-07-27 | 19 |
| `datayes.mkt_equd_ind` | daily_trade_state_candidate | True | 2007-01-04 ~ 2026-07-27 | 17 |
| `datayes.mkt_limit` | price_limit_state | True | 2007-01-04 ~ 2026-07-28 | 11 |
| `datayes.abm_stock_pool` | daily_stock_pool_candidate | True | 1990-12-19 ~ 2026-07-28 | 6 |
| `datayes.abm_is_ST` | daily_st_state_candidate | True | 1990-12-19 ~ 2024-01-26 | 3 |
| `datayes.idx_cons` | historical_index_membership_candidate | True | 1964-07-31 ~ 2026-08-03 | 7 |
| `abmdata.qt_idx_constituents` | historical_index_membership_candidate | False | None ~ None | 0 |

## 当前阻塞

- version-matched authoritative field dictionary and source locators
- historical vendor_available_time or equivalent market-availability evidence
- revision-retention policy for every consumed raw field
- independent CSI300/CSI500 announcement/effective-date authority including exits and delistings
- immutable full extraction snapshot and receipt
- current statutory/broker fee receipt

## 下一项唯一高信息动作

Review qt_idx_constituents index-code coverage and the DataYes raw-field dictionary; then decide whether the candidate universe and daily RAW path are eligible to enter VERIFY.
