# M8 Test Design

| Behavior | Success evidence | Negative or boundary evidence |
| --- | --- | --- |
| Exact legacy incident parsing | four canonical counted starts | changed fold identity is rejected |
| Accounting | totals become 9 candidates / 64 fits | duplicate semantic identity is rejected by ledger core |
| Evidence integrity | all gate-bound SHA256 values match | any changed artifact makes verifier fail |
| Interrupted fold | wf_2020 has a counted start | wf_2020 completion receipt must not exist |
| Duplicate recovery | first reconciliation receipt retained | second invocation exits non-zero before ledger mutation |
| Final OOS | access-log hash equals frozen prefix | changed access log makes recovery/verifier fail |
| Claims | gate is HOLD, incomplete and not promoted | tests reject completed/promoted/final-OOS claims |

The complete repository test suite and scoped M8 tests are required. The CLI
E2E journeys cover independent verification and duplicate recovery rejection.
