# M7 behavior-to-test matrix v14

Base v13 matrix SHA：
`b23c66b4edb64c0d7f43cfa081e71632fd1c2cacb593b4065c6f15b584bb1f33`。
V13 rows保留，并新增以下独立负例。每个负例必须断言指定判定及零未授权副作用：

| ID | Fixture | Oracle | Zero side effect |
| --- | --- | --- | --- |
| CAP-05 | one file使temp+final短暂共存 | PASS within filesystem reservation | no false abort |
| CAP-06 | empty source连续attempts | 每个预留2 roots+21 controls；floor不足拒绝 | no RESERVED |
| CAP-07 | free inode恰floor+1的双并发admission | 仅一个可在线性化条件满足时成功 | loser no files |
| CAP-08 | sealed RELEASED metadata累积 | metadata继续计入aggregate inode/entry/bytes | no zero charge |
| MAP-01 | staging缺一个source path | HOLD before PREPARED | no target |
| MAP-02 | final额外/rename/subset path | HOLD | no COMMITTED/RELEASED |
| MAP-03 |同content但不同final inode | HOLD | no sibling COMMITTED |
| TMP-01 | temp valid/final absent | table唯一link→fsync→unlink→fsync | exact final only |
| TMP-02 | temp+final same inode after crash | unlink temp+fsync | final unchanged |
| TMP-03 | temp+final different inode或任一bad bytes | HOLD | no delete/overwrite |
| REG-01 | registration fsync后different run重试 | full scan HOLD | no commit |
| REG-02 | committed generation有第二registration | registry HOLD | no next generation |
| BUD-01 | CCC FAILED/INTERRUPTED/ABORT | committed1/8永久保留 | no replacement |
| BUD-02 | duplicateCCC、Gate-before-CCC、third trial generation | HOLD | no commit |
| EVT-01 | claim无outcome且lease释放 | only CLAIMED_INTERRUPTED outcome | no re-execution |
| EVT-02 | terminal event partition/digest mutation | HOLD | no successor |
| NUM-01 | `0.5,-0.5,0.0001,-0.0001` | accepted exact typed values | no fallback parser |
| NUM-02 | `-0,-0.0,0.50,.5,00.5,1e-3` | FAIL | no observation output |
| PARSER-01 | unbound import/shadow module/domain alias/runtime drift | FAIL before parse | no qualification |
| ISSUER-01 | self-reported backdated verified_at without frozen trust anchor | FAIL | no authority |
| ISSUER-02 | broken registry predecessor/head or inactive anchor | FAIL | no authority |
| SRC-01 | historical source revision changes LIST/DELIST legally | select interval-specific value | no final-value backfill |
| SRC-02 | wrong snapshot/locator/security/record hash/clock | HOLD | no SLA006 PASS |
| SRC-03 | cutoff latest differs from final sealed projection | HOLD | no final authority |
| PTR-01 | any normative bundle hash/path drift | STALE before test/implementation | no execution |
| REPLAY-02 | shared model-level replay output or 13/15 outputs | FAIL | 0 fit, ledger unchanged |

只允许M6.5 contract-only synthetic tests。M7 authority、fit、replay、真实数据、预算mutation与
final-OOS均未授权。
