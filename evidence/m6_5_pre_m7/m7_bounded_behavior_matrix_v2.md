# M7 Bounded Behavior-to-Test Matrix V2

当前全部rows仅是后续`test-design`输入。design-review PASS本身不授权执行；路由须依次经过
test-design与expected-red tests。

| ID | Future stage | Fixture | Oracle / zero unauthorized side effect |
| --- | --- | --- | --- |
| IMPORT-01 | M6.5 static | import package/data/governance | no implicit Torch/PeerLite; dependency direction exact |
| STATE-01 | M6.5 synthetic | label/execution/halt/limit/crossover/price-domain/feature-eligible extra | fail before aggregation |
| STATE-02 | M6.5 synthetic | duplicate key, unknown bool, nonfinite source | fail; no product |
| STATE-03 | M6.5 synthetic | future row, T-key future revision, current-universe substitution | through-T bytes unchanged or fail |
| STATE-04 | M6.5 synthetic | shuffled instruments and even/odd medians | fixed float64 state/digest |
| STATE-05 | M6.5 synthetic | source/calendar/PIT/builder hash mismatch | no PASS manifest |
| LEDGER-01 | M6.5 synthetic | exact 14328-byte 6/44 prefix plus unique starts | atomic whole-file commit once |
| LEDGER-02 | M6.5 synthetic | same source bytes rerun | NO_OP, ledger bytes unchanged |
| LEDGER-03 | M6.5 synthetic | same ID different bytes, semantic duplicate, prefix tamper, limit overflow | fail, old ledger intact |
| LEDGER-04 | M6.5 synthetic | crash before/after replace | ledger exactly old or new, never partial |
| LEDGER-05 | M6.5 synthetic | crash after ledger commit before receipt | recovery receipt, no duplicate append |
| LEDGER-06 | M6.5 synthetic | two concurrent reconcilers | serialized; one commit and one no-op |
| ARCHIVE-01 | M6.5 synthetic | gate/source/journal/pre-run/close-prefix mutation | fail |
| ARCHIVE-02 | M6.5 synthetic | valid 6/44 prefix plus legal suffix | PASS without rewriting history |
| REPLAY-01 | M6.5 synthetic | existing or input/project/OOS-overlapping output dir | fail; no overwrite |
| REPLAY-02 | M6.5 synthetic | archive/receipt/checkpoint/product/fold mismatch | no PASS receipt |
| REPLAY-03 | M6.5 synthetic | one-bit score or key difference | no PASS receipt |
| REPLAY-04 | M6.5 static | AST contains fit/backward/optimizer step | fail |
| REPLAY-05 | M6.5 synthetic | live-worktree module origin or frozen blob mismatch | fail |
| REPLAY-06 | M6.5 synthetic | runtime version mismatch, CPU model/input/output, CUDA unavailable | fail |
| REPLAY-07 | M6.5 synthetic | fake exact 2×7 CUDA seam | one exact V2 receipt; 14 replay, 0 fit |
| OOS-01 | M6.5 static | final-OOS path argument or 2025+ fixture | reject without opening final-OOS |
| CCC-01 | M7 implementation | normal/singleton/nonfinite | exact formula/fallback/fail |
| CCC-02 | M7 implementation | attempted split date | sampler rejects |
| CCC-03 | M7 implementation | unequal date sizes and alternate batch packing | equal-date epoch objective invariant |
| CCC-04 | M7 implementation | validation tie | earliest checkpoint |
| GATE-01 | M7 implementation | repeated model rows per date | stats use each train date once, ddof=0 float64 |
| GATE-02 | M7 implementation | valid/test shift | no refit |
| GATE-03 | M7 implementation | std below threshold and serialization | scale=1, float.hex exact |
| SCREEN-01 | M6.5 contract | IR delta exactly 0 / fold count 4,5 / stress exactly 0 | strict boundary decisions |
| SCREEN-02 | M6.5 contract | missing week, duplicate fold week, wrong ddof/weighting | FAIL |
| BUDGET-01 | M6.5 contract | two candidates plus refits | `6/44 -> max8/60`, exact fit IDs, no replacement |
| PROMOTE-01 | M6.5 contract | one/both screen pass | only SCREEN_PASS/HOLD; no promotion/combination |
| PROMOTE-02 | M6.5 contract | attempted third candidate or five-seed confirmation | blocked pending new CR/budget |
