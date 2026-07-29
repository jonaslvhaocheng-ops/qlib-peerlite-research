# M7 Bounded Behavior-to-Test Matrix V6

仅供future test-design，当前不执行。

| ID | Fixture | Oracle |
| --- | --- | --- |
| STATE-01 | forbidden/missing/duplicate/nonfinite | fail before product |
| STATE-02 | future/equal-time/current-universe poison | through-T unchanged or fail |
| STATE-03 | cancellation/median/control/±0/overflow/submicrosecond | exact/+0/fail |
| STATE-04 | state authority substitution | 0 event/fit |
| LEDGER-01 | exact 6/44 + budget V2 roster | atomic max8/60 |
| LEDGER-02 | exact rerun after receipt + legal suffix | original receipt bytes NO_OP |
| LEDGER-03 | commit crash before receipt + later suffix | recover original counts/set |
| LEDGER-04 | snapshot publish, crash before replace, other journal commits, retry | new ledger-before slot commits; old snapshot unchanged |
| LEDGER-05 | same journal later adds events | new journal family slots; old bytes unchanged |
| LEDGER-06 | old missing ID partially/interleaved appears | fail; no rebase |
| LEDGER-07 | multiple recoverable snapshots or receipts | fail ambiguity |
| LEDGER-08 | wrong slot/preimage/roster/purpose/seed/fit | fail unchanged |
| LEDGER-09 | 2+1 reconcilers/ledger inode and lock injections | serialized; precommit drift unchanged |
| ARCHIVE-01 | artifact/prefix/archive/tree mutation | static fail/no import |
| REPLAY-01 | caller pairing/output overlap/tree/score mismatch | fail |
| REPLAY-02 | fit ref in any reachable object/default/container | graph fail pre-load |
| REPLAY-03 | untraversable/unlocked/live/wrong dependency | fail closed |
| REPLAY-04 | exact bound 2×7 CUDA seam | V5 receipt 14/0/no OOS |
| CCC-01 | formula/singleton/date split/multi-step/tie | exact/fallback/reject/earliest |
| CCC-02 | refit and semantic checkpoint | exact or HOLD |
| GATE-01 | date stats/shift/permutation | ddof0/no refit/equivariant |
| SCREEN-01 | IR/fold/stress boundaries | exact screen only |
| PROMOTE-01 | third candidate/five seed/promotion | blocked |
