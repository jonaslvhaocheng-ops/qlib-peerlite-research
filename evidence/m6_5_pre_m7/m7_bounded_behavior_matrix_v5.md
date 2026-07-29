# M7 Bounded Behavior-to-Test Matrix V5

仅供future test-design；当前不授权执行。

| ID | Fixture | Oracle |
| --- | --- | --- |
| STATE-01 | forbidden/missing/duplicate/nonfinite fields | fail before product |
| STATE-02 | future/current-universe/equal-time revision poisons | through-T unchanged or fail |
| STATE-03 | shuffled/cancellation/even-odd/control bytes/±0/overflow | exact bits; +0; overflow fail |
| STATE-04 | timezone-equivalent microsecond values vs nonzero submicrosecond | canonical equal vs precompare fail |
| STATE-05 | substitute source/PIT/calendar/builder/product refs | no manifest/event/fit |
| LEDGER-01 | exact 6/44 + bound V2 roster | atomic once; max8/60 |
| LEDGER-02 | exact journal rerun after receipt + legal ledger suffix | identical old receipt; zero write |
| LEDGER-03 | commit crash before receipt + later suffix | snapshot recovers original before/after/missing set |
| LEDGER-04 | same journal later appends new events | new snapshot/receipt slots; old bytes unchanged |
| LEDGER-05 | snapshot/receipt slot path or preimage substitution | fail unchanged |
| LEDGER-06 | unlisted evaluation ID/purpose/fit/fold/seed/replacement | 0 append |
| LEDGER-07 | crash before/after replace | old/new only |
| LEDGER-08 | 2+1 reconcilers/ledger inode replace | sidecar serialization |
| LEDGER-09 | lock mutation at every defined injection point | precommit mutation leaves ledger/receipt unchanged |
| ARCHIVE-01 | gate/journal/prefix/archive/tree/manifest mutation | fail, no import/rewrite |
| ARCHIVE-02 | valid close prefix + legal suffix | PASS static |
| REPLAY-01 | caller expected pairing/output overlap | CLI/path reject |
| REPLAY-02 | archive/tree/checkpoint/product/score bit mismatch | no PASS |
| REPLAY-03 | fit ref in defaults/kwdefaults/container/descriptor/callable instance | object graph fail pre-load |
| REPLAY-04 | fit ref via global/class/closure/partial/wrapper | guard or graph fail |
| REPLAY-05 | untraversable object/graph limit | fail closed |
| REPLAY-06 | live project/unmapped/ambiguous/unlocked/wrong-version dependency | fail |
| REPLAY-07 | exact bound 2×7 CUDA seam | V5 receipt; 14/0/no OOS |
| CCC-01 | normal/singleton/nonfinite | formula/fallback/fail |
| CCC-02 | split/multi-date/accumulation | reject |
| CCC-03 | date order/tie/refit | ascending/earliest/semantic exact or HOLD |
| CHECKPOINT-01 | same tensors, different torch container | same semantic digest |
| CHECKPOINT-02 | bit/key/dtype/shape/metadata drift | different digest |
| GATE-01 | unique date stats/valid shift/std threshold | ddof0/no refit/scale1 |
| GATE-02 | stock permutation/cross-date shift | equivariant/fail |
| SCREEN-01 | delta0/fold4,5/stress0/missing week | strict boundaries/fail |
| PROMOTE-01 | screen pass/third candidate/five seed | screen only/block |
