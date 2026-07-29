# M7 Bounded Behavior-to-Test Matrix V3

全部rows仅供后续`test-design`；design-review PASS只路由test-design，不授权执行。

| ID | Future stage | Fixture | Oracle / zero unauthorized side effect |
| --- | --- | --- | --- |
| IMPORT-01 | M6.5 static | import package/data/governance | no implicit Torch/PeerLite; exact dependency direction |
| STATE-01 | M6.5 synthetic | forbidden label/execution/halt/limit/crossover fields | fail before aggregation |
| STATE-02 | M6.5 synthetic | unknown bool, duplicate final key, nonfinite | fail; no product |
| STATE-03 | M6.5 synthetic | future row/revision/current-universe substitution | through-T bytes unchanged or fail |
| STATE-04 | M6.5 synthetic | equal eligible time identical duplicates vs conflicting value/revision/hash | identical dedup; conflict fail |
| STATE-05 | M6.5 synthetic | source/calendar/PIT/builder hash mismatch | no PASS manifest |
| STATE-06 | M6.5 synthetic | shuffled instruments, cancellation values, even/odd median, control bytes | exact last-bit reducer and length-prefixed digest |
| STATE-07 | M6.5 contract | replace one state product/source/PIT/calendar/builder ref before first event | 0 journal bytes, 0 fit |
| LEDGER-01 | M6.5 synthetic | exact 14328-byte 6/44 prefix + valid starts | atomic whole-file commit once |
| LEDGER-02 | M6.5 synthetic | same source bytes rerun | NO_OP; bytes unchanged |
| LEDGER-03 | M6.5 synthetic | conflict/semantic duplicate/prefix tamper/limit overflow | fail; old ledger intact |
| LEDGER-04 | M6.5 synthetic | crash before/after replace | exactly old or new; never partial |
| LEDGER-05 | M6.5 synthetic | crash after ledger commit before receipt, then another journal suffix | recover original minimal commit-prefix/slot; no duplicate |
| LEDGER-06 | M6.5 synthetic | two reconcilers plus third contender while ledger inode is replaced | fixed sidecar inode serializes all; one commit/rest no-op |
| LEDGER-07 | M6.5 contract | budget binding path/file/content or nested event binding mismatch | fail before append |
| LEDGER-08 | M6.5 synthetic | replace/unlink/symlink sidecar lock | fail; ledger/receipt unchanged |
| ARCHIVE-01 | M6.5 synthetic | external binding/gate/source/journal/pre-run/close mutation | fail |
| ARCHIVE-02 | M6.5 synthetic | valid 6/44 prefix + legal suffix | PASS without history rewrite |
| REPLAY-01 | M6.5 synthetic | existing or overlapping output dir | fail; no overwrite |
| REPLAY-02 | M6.5 synthetic | caller pairs wrong archive/runtime expected SHA | impossible via CLI; bound identity mismatch fails |
| REPLAY-03 | M6.5 synthetic | archive/full-tree/manifest/checkpoint/product/fold mismatch | no PASS receipt |
| REPLAY-04 | M6.5 synthetic | one-bit score/key/order difference | no PASS receipt |
| REPLAY-05 | M6.5 static | transitive verifier AST contains fit/backward/step/optimizer | fail |
| REPLAY-06 | M6.5 synthetic | direct or alias fit call after guard | counter increments then fail; no receipt |
| REPLAY-07 | M6.5 synthetic | live/transitive project module or editable/mismatched Qlib dependency | fail |
| REPLAY-08 | M6.5 synthetic | runtime/package/CUDA/device/determinism mismatch | fail; no CPU fallback |
| REPLAY-09 | M6.5 synthetic | fake exact bound 2×7 CUDA seam | one V3 receipt; 14 replay, 0 fit |
| OOS-01 | M6.5 static | final-OOS path or 2025+ fixture | reject without opening partition |
| CCC-01 | M7 implementation | normal/singleton/nonfinite | exact binary64 formula/fallback/fail |
| CCC-02 | M7 implementation | split date, two dates/step, gradient accumulation | reject |
| CCC-03 | M7 implementation | unequal date sizes and cancellation-order values | ascending one-date steps and exact epoch objective |
| CCC-04 | M7 implementation | validation tie | earliest checkpoint |
| CCC-05 | M7 implementation | checkpoint reload/refit wf_2018 | date-order/checkpoint/scores bitwise exact; otherwise HOLD |
| GATE-01 | M7 implementation | repeated model rows per date | stats use unique train dates once, ddof0 binary64 |
| GATE-02 | M7 implementation | valid/test shift | no refit |
| GATE-03 | M7 implementation | std threshold/serialization | scale=1; float.hex exact |
| GATE-04 | M7 implementation | stock permutation and cross-date state misalignment | equivariant after inverse permutation; bad alignment fails |
| SCREEN-01 | M6.5 contract | IR delta 0 / fold count 4,5 / stress 0 | strict boundaries |
| SCREEN-02 | M6.5 contract | missing week, overlap, wrong ddof/weighting | FAIL |
| BUDGET-01 | M6.5 contract | two candidates + exact refits | `6/44 -> max8/60`, 0 replacement |
| BUDGET-02 | M6.5 contract | candidate/fit ID not in external binding | 0 event |
| PROMOTE-01 | M6.5 contract | one/both screen pass | only SCREEN_PASS/HOLD |
| PROMOTE-02 | M6.5 contract | third candidate/five-seed confirmation | blocked pending new CR/budget |
