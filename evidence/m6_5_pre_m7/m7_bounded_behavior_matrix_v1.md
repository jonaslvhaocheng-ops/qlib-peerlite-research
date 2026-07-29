# M7 Bounded Behavior-to-Test Matrix V1

| ID | Stage | Fixture | Oracle |
| --- | --- | --- | --- |
| STATE-01 | M6.5 synthetic | input含label/execution/extra列 | fail before aggregation |
| STATE-02 | M6.5 synthetic | duplicate key、nonboolean status、nonfinite feature | fail |
| STATE-03 | M6.5 synthetic | mutate only data after T | all outputs through T byte-identical |
| STATE-04 | M6.5 synthetic | same date model rows | one exact-date state broadcast |
| LEDGER-01 | M6.5 synthetic | exact M6 6/44 prefix plus new unique starts | append once |
| LEDGER-02 | M6.5 synthetic | rerun same source event | no-op, bytes unchanged |
| LEDGER-03 | M6.5 synthetic | same ID different bytes or semantic duplicate | fail, no append |
| LEDGER-04 | M6.5 synthetic | crash/failure seam around append/fsync | valid prefix or explicit failure, never partial JSONL |
| ARCHIVE-01 | M6.5 synthetic | historical static chain and 6/44 prefix | exact PASS |
| REPLAY-01 | M6.5 synthetic | output directory already exists | fail, no overwrite |
| REPLAY-02 | M6.5 synthetic | archive/receipt/checkpoint/product/fold mismatch | no PASS receipt |
| REPLAY-03 | M6.5 synthetic | score differs by one float64 bit or key | no PASS receipt |
| REPLAY-04 | M6.5 static | AST contains any `fit(...)` call | fail |
| REPLAY-05 | M6.5 synthetic | CPU device, CUDA unavailable or 2025+ row | fail |
| REPLAY-06 | M6.5 synthetic | successful fake 2×7 replay | one v2 receipt, 14 exact, 0 fit, ledger unchanged |
| CCC-01 | M7 implementation | hand-computed normal/singleton/nonfinite cases | exact formula and fallback |
| CCC-02 | M7 implementation | validation tie | earliest checkpoint retained |
| GATE-01 | M7 implementation | state scaling with repeated model rows | fit once per unique train date |
| GATE-02 | M7 implementation | valid/test state distribution shift | no refit |
| GATE-03 | M7 implementation | gate injection shape/permutation | same score order after inverse permutation |
| BUDGET-01 | M6.5 contract | two isolated candidates | `6/44 -> max 8/60`, no replacement |
| PROMOTE-01 | M6.5 contract | one or both candidates fail | failed module deleted; no combination |
| PROMOTE-02 | M6.5 contract | both pass | eligible only; third candidate blocked without new CR |
| OOS-01 | all | any final-OOS access | fail |

当前只允许实现和运行`M6.5 synthetic/static/contract`行。`M7 implementation`行属于第7步后续，
此矩阵本身不授权模型实现或fit。
