# M7 behavior-to-test matrix v15

Base v14 matrix SHA：
`641a8560ec704908976023ea2bc37b5c2e1cd1605f38872ae2a9ec5f41087c76`。
V14 rows保留，新增：

| ID | Fixture | Oracle | Zero side effect |
| --- | --- | --- | --- |
| BLOCK-01 | F个1-byte/zero-byte files | fragment+overhead blocks足额；不足拒绝 | no attempt paths |
| BLOCK-02 | deep dirs+19 empty controls | directory/control block ceiling足额 | no floor breach |
| LEASE-01 | floor+1下多attempt抢pool | GC内仅可承诺的attempt绑定slot | losers no paths |
| LEASE-02 | pool exhausted或bad slot inode | reject before reservation | no RESERVED |
| INV-01 | 0700 pre-seal→0550 sealed→cleanup→restart | long-term COMMITTED validates | final unchanged |
| INV-02 | final-root extra PUBLISH_COMPLETE/unknown | sibling-only control；root extra HOLD | no COMMITTED |
| DUR-01 | crash after chmod before second file fsync | deterministic temp recovery | no bad final |
| LEDGER-01 | skipped STARTED或duplicated/forked head | HOLD before execution/terminal | no fit or successor |
| LEDGER-02 | foreign result or result→claim mismatch | HOLD | no OUTCOME receipt |
| LEDGER-03 | out-of-order next claim | HOLD | no next STARTED |
| EVENT-01 | duplicate source_event_id/seq/event_key | activation FAIL | no registration |
| TRUST-01 | anchor references derived contract or private registry | FAIL DAG/policy | no M7 authority |
| TRUST-02 | bad external predecessor/head/freeze receipt | FAIL | no anchor |
| CLOSURE-01 | unbound config/resource/env/network/time/random | FAIL before parser/resolver | no qualification |
| SOURCE-04 | resolver/schema/locator digest drift | HOLD | no SLA006 PASS |
| CLOCK-01 | vendor>source或source>observation | HOLD | no final authority |
| REPLAY-03 | key/score/identity preimage delimiter/float drift | digest mismatch FAIL | ledger unchanged |

所有test仍为M6.5 contract-only synthetic；不得创建真实M7 authority、运行fit/replay、读取真实数据
或final-OOS。
