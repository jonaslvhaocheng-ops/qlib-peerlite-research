# M7 Bounded Behavior-to-Test Matrix V4

全部仅供future test-design；design-review PASS不授权执行。

| ID | Future stage | Fixture | Oracle / zero unauthorized side effect |
| --- | --- | --- | --- |
| IMPORT-01 | M6.5 static | package/data/governance import | no implicit Torch/PeerLite; direction exact |
| STATE-01 | M6.5 synthetic | forbidden label/execution/halt/limit fields | fail before aggregate |
| STATE-02 | M6.5 synthetic | unknown bool/duplicate/nonfinite | fail; no product |
| STATE-03 | M6.5 synthetic | future row/revision/current universe | through-T unchanged or fail |
| STATE-04 | M6.5 synthetic | equal eligible time identical vs conflicting revision | dedup vs fail |
| STATE-05 | M6.5 synthetic | source/calendar/PIT/builder hash mismatch | no PASS manifest |
| STATE-06 | M6.5 synthetic | shuffled rows/cancellation/even-odd median/control bytes | exact last-bit/digest |
| STATE-07 | M6.5 synthetic | `-0/+0`, finite-add overflow, equivalent timezone spellings | +0 canonical; overflow fail; time canonical |
| STATE-08 | M6.5 contract | substitute one state authority ref before event | 0 journal/fit |
| LEDGER-01 | M6.5 synthetic | exact 14328-byte 6/44 + valid roster | atomic once |
| LEDGER-02 | M6.5 synthetic | same source rerun | immutable receipt NO_OP, zero write |
| LEDGER-03 | M6.5 synthetic | conflict/prefix/limit/roster drift | fail; old ledger intact |
| LEDGER-04 | M6.5 synthetic | crash before/after replace | exactly old/new |
| LEDGER-05 | M6.5 synthetic | commit then crash before receipt then later suffix | snapshot recovers original minimal prefix |
| LEDGER-06 | M6.5 synthetic | existing receipt then legal later suffix then rerun | return identical receipt bytes; zero write |
| LEDGER-07 | M6.5 synthetic | two reconcilers + third contender across ledger inode replace | stable sidecar serializes |
| LEDGER-08 | M6.5 synthetic | lock path mutation at every defined injection boundary | precommit drift leaves ledger/receipt unchanged |
| LEDGER-09 | M6.5 contract | wrong budget binding/unlisted model/seed/fit ID/replacement | 0 append |
| ARCHIVE-01 | M6.5 synthetic | gate/journal/prefix/frozen archive/tree/manifest mutation | fail |
| ARCHIVE-02 | M6.5 synthetic | valid 6/44 + legal suffix | PASS without rewrite/import |
| REPLAY-01 | M6.5 synthetic | existing/overlapping output | fail; no overwrite |
| REPLAY-02 | M6.5 synthetic | caller-paired expected hash attempt | CLI rejects; binding rules |
| REPLAY-03 | M6.5 synthetic | archive/full-tree/checkpoint/product mismatch | no PASS |
| REPLAY-04 | M6.5 synthetic | one-bit score/key/order | no PASS |
| REPLAY-05 | M6.5 static | reachable wrapper/dynamic alias invokes fit/backward/optimizer | fail |
| REPLAY-06 | M6.5 synthetic | private alias/saved bound method/partial/closure fit | guarded or pre-load fail |
| REPLAY-07 | M6.5 synthetic | live project module or editable project dependency | fail |
| REPLAY-08 | M6.5 synthetic | imported unbound/unmapped/ambiguous/wrong-version third-party module | fail |
| REPLAY-09 | M6.5 synthetic | runtime/CUDA/device/determinism mismatch | fail; no CPU fallback |
| REPLAY-10 | M6.5 synthetic | fake exact bound 2×7 seam | V4 receipt; 14 replay, 0 fit |
| OOS-01 | M6.5 static | final-OOS path/2025+ fixture | reject unopened |
| CCC-01 | M7 implementation | normal/singleton/nonfinite | formula/fallback/fail |
| CCC-02 | M7 implementation | split/multi-date step/accumulation | reject |
| CCC-03 | M7 implementation | unequal dates/cancellation | ascending one-date exact objective |
| CCC-04 | M7 implementation | validation tie | earliest checkpoint |
| CCC-05 | M7 implementation | wf_2018 refit | semantic checkpoint/state/epoch/scores exact or HOLD |
| CHECKPOINT-01 | M7 implementation | same tensors in different torch.save containers | same semantic digest |
| CHECKPOINT-02 | M7 implementation | tensor bit/key/dtype/shape/metadata change | different digest |
| GATE-01 | M7 implementation | repeated rows/date | unique train dates, ddof0 |
| GATE-02 | M7 implementation | valid/test shift | no refit |
| GATE-03 | M7 implementation | std threshold/serialization | scale1/float.hex |
| GATE-04 | M7 implementation | stock permutation/cross-date shift | equivariant/fail |
| SCREEN-01 | M6.5 contract | IR delta0 / fold4,5 / stress0 | strict boundary |
| SCREEN-02 | M6.5 contract | missing/overlap/wrong ddof | FAIL |
| BUDGET-01 | M6.5 contract | two candidates + refits | 6/44→max8/60; 0 replacement |
| PROMOTE-01 | M6.5 contract | screen result | only SCREEN_PASS/HOLD |
| PROMOTE-02 | M6.5 contract | third candidate/five-seed | blocked new CR |
