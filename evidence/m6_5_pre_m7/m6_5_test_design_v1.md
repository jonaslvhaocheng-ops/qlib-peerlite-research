# M6.5 Pre-M7 Executable Test Design V1

- Stage: `test-design`
- Risk: `R3`
- Design basis: `m6_5_repair_change_design_v48.md`
- Normative closure: `m6_5_normative_closure_manifest_v6.json`
- Status: `PASS / TESTS_NOT_WRITTEN_OR_RUN`
- Boundary: synthetic/static fixtures only; no real replay, fit, PIT rerun, real data, budget mutation or OOS.

## 1. Scope and observable behavior

In scope:

1. T-close source selection, bit-exact state reduction, manifest and authority binding.
2. Exact budget roster, immutable reconciliation snapshots/receipts, atomic append and cooperative concurrency.
3. Static M6 archive binding and fail-closed no-fit archival replay verifier.
4. Future M7 CCC, semantic checkpoint, Gate alignment/statistics and screen-only policy.

Non-goals: Alpha quality, real model fitting, server capacity, production security/control plane, portfolio
economics, final OOS and promotion.

## 2. Behavior-to-test matrix

Every row is required. “Synthetic” doubles only an external boundary; the production policy/reducer/parser
under test is never mocked or reimplemented as the oracle.

| ID | Behavior / invariant | Case | Layer | Setup / input | Exact oracle | Doubles / isolation | Coverage obligation | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STATE-U1 | Only safe T-known schema enters state | failure/boundary | unit | minimal valid panel; then each forbidden, missing, duplicate, unknown-bool and nonfinite mutation | typed error before any output path exists | tmp_path only | every schema/predicate rejection branch | Required |
| STATE-U2 | Latest eligible revision is selected without future leakage | transition/metamorphic | unit | rows just before/at/after T-close; equal-time identical and conflicting revisions; shuffled order; current-universe poison | before/at selected; after ignored; identical dedup; conflict fails; through-T bytes/digests invariant | synthetic rows | eligibility, max-time, dedup, conflict and poison branches | Required |
| STATE-U3 | Reducer and encodings are bit exact | boundary/property | unit | cancellation values, odd/even median, 1 and many instruments, control bytes, `-0/+0`, finite-add overflow | known `struct.pack` binary64 bits and fixed SHA; zero is +0; overflow fails | standard library `decimal` only for independent fixture constants | left-fold, median, key/state digest and intermediate-finite branches | Required |
| STATE-U4 | Time canonicalization is injective at supported precision | boundary | unit | equivalent aware timezone instants, naive value, microsecond max, nonzero nanosecond remainder | equivalent canonical bytes; naive/submicrosecond fail before comparison | pandas Timestamp fixtures | timezone/precision branches | Required |
| STATE-C1 | Manifest/state authority is hash bound | contract | contract | valid refs then one-at-a-time source/PIT/calendar/builder/product substitution | no PASS manifest, journal byte or fit seam call | recording fit seam only to assert zero calls | every external-ref mismatch | Required |
| LEDGER-U1 | Budget V2 roster is authoritative | decision table | unit | exact two candidates; mutate family/model/seed/evaluation ID/purpose/fit/fold/flags/replacement | only exact roster accepted; counts never exceed 8/60; invalid ledger bytes unchanged | synthetic exact 14328-byte prefix | each roster field and cap branch | Required |
| LEDGER-I1 | Append is whole-file atomic and idempotent | success/fault | integration | valid snapshot/journal; inject failure before temp fsync, pre-replace and replace | ledger exactly old or new; valid JSONL; one append; retry returns immutable receipt | monkeypatch OS failure boundary, not policy | every write/replace/readback/error branch | Required |
| LEDGER-I2 | Existing receipt survives later legal suffix | recovery | integration | commit A+receipt, append B, rerun A | byte-identical A receipt, `NO_OP`, zero writes, A minimal prefix still current prefix | tmp filesystem and write-call recorder | NO_OP with advanced ledger | Required |
| LEDGER-I3 | Commit-before-receipt recovers after suffix | recovery | integration | crash immediately after A ledger replace, commit B, retry A | A `LEDGER_ALREADY_COMMITTED`; original before/after/missing set; no duplicate | named fault hook after replace | recovery branch and original-count oracle | Required |
| LEDGER-I4 | Precommit snapshot can rebase after another append | concurrency/recovery | integration | publish A snapshot, crash before replace, commit B, retry A | new A slot binds B head; old snapshot unchanged; A commits once | deterministic barrier around replace | V6 state-machine branch 3 | Required |
| LEDGER-I5 | Partial/ambiguous recovery fails closed | failure | integration | one old missing ID interleaved; two recoverable snapshots; two receipts | typed ambiguity/partial error; ledger/snapshots/receipts unchanged | hand-built canonical JSONL fixtures | V6 branches 1/2/4 rejection | Required |
| LEDGER-I6 | Stable sidecar serializes 2+1 contenders | concurrency | integration | three processes/threads at barriers; ledger inode replaced; inject lock-path drift at each defined boundary | one commit, remaining no-op/rebase as applicable; precommit drift leaves ledger/receipt unchanged | multiprocessing or flock-capable subprocess fixture | lock identity checks and serialization | Required |
| LEDGER-C1 | Slot names and immutable contents are derivable | contract/property | contract | valid snapshot/receipt then mutate each preimage component, filename, hash and path | only exact slot/path accepted; same slot different bytes fails | tmp fixed 0700 control root | parser/schema/no-replace branches | Required |
| ARCHIVE-C1 | Static authority binds history and frozen source | contract | contract | exact v2 binding; mutate gate, journal, both prefixes, archive/tree/internal-manifest refs; add legal suffix | mutations fail without import/write; legal suffix passes | copied small evidence fixture; import spy | all static ref and prefix branches | Required |
| REPLAY-S1 | CLI cannot accept caller-paired identities or overlap output | static/contract | static + contract | inspect parser; invoke with unexpected expected-hash option and overlapping/existing output | parser/path rejection; no PASS receipt | tmp paths | CLI argument and containment branches | Required |
| REPLAY-U1 | Reachable fit references fail before checkpoint load | property/failure | unit | place original fit in global, default, kwdefault, closure, nested container, descriptor, callable instance and partial | object traversal reports reachable target; checkpoint-load spy remains zero | tiny synthetic object graph | every reference family and repeat traversal point | Required |
| REPLAY-U2 | Traversal/dependency verification fails closed | failure | unit | untraversable referent, graph cap, live project module, unmapped/ambiguous/unlocked/wrong-version distribution | typed failure; no checkpoint/PASS receipt | fake import metadata boundary and module objects | fail-closed/object/dependency branches | Required |
| REPLAY-I1 | Bound no-fit 2×7 replay contract can close mechanically | integration | integration | fake two models×seven folds with canonical saved scores, bound fake CUDA tensors and exact manifests | one V5 receipt; 14 replay; fit=0; ledger unchanged; OOS=false | explicit fake CUDA/checkpoint boundary because real replay prohibited | receipt schema, order, CUDA and terminal branches | Required |
| CCC-U1 | CCC uses one complete date per step | unit/property | unit | hand-calculated normal/singleton/nonfinite panels; split/multi-date/accumulation attempts; unequal date sizes | independent numeric constants; singleton MSE; invalid layouts fail; date order ascending | no model mock; minimal tensor fixtures | formula, sampler, finite and tie branches | Required |
| CHECKPOINT-U1 | Semantic checkpoint digest ignores container noise only | property | unit | same tensors saved in two container layouts; then mutate bit/key/dtype/shape/metadata | same semantic digest for equal state; every semantic mutation changes digest | temporary serialized containers are inputs, not oracle | supported/unsupported tensor and metadata branches | Required |
| GATE-U1 | Gate uses unique train dates and exact alignment | unit/metamorphic | unit | repeated stock rows, valid/test distribution shift, std around threshold, stock permutation, cross-date shift | ddof0 stats once/date; no refit; threshold scale1; inverse permutation exact; shift fails | small fixed tensors/state table | stats, threshold, join and equivariance branches | Required |
| SCREEN-C1 | Screen policy is strict and cannot promote | decision table/contract | contract | IR delta below/at/above0; fold positive count4/5; stress below/at0; missing/overlap week; third candidate/five seed | exact SCREEN_PASS/HOLD boundaries; invalid weeks FAIL; promotion/extra candidate blocked | fixed weekly-return rows | every policy decision and invalid-return branch | Required |

## 3. Fixtures, seams and determinism

- `tests/fixtures/m6_close_prefix.jsonl`: exact 14,328-byte 6/44 prefix copied from the immutable ledger and
  hash-asserted before every ledger test.
- All artifact fixtures are miniature, repository-local and synthetic; no fixture path contains 2025+ or the
  final-OOS root.
- Time is explicit in fixture rows; no wall clock calls. Randomness is prohibited except property generators
  with a fixed reported seed.
- File-fault seams are named checkpoints around temp fsync, pre-replace, post-replace/pre-receipt and receipt
  publish. They may raise only; they cannot choose policy outcomes.
- Concurrency uses explicit barriers and bounded subprocess joins, never sleep-based ordering.
- Import/dependency doubles replace `importlib.metadata` and module inventories only; the production traversal
  and validation logic remains real.
- The fake CUDA replay seam supplies device-tagged tensors and fixed fold artifacts solely because real replay
  is explicitly unauthorized. It must not expose `fit`.
- Numeric expected values are fixed external constants derived with standard-library `decimal`/`struct`, not
  by calling the production reducer twice.

## 4. Planned test files and ownership

- `tests/test_market_state_v2.py`: STATE rows.
- `tests/test_trial_ledger_v3.py`: ledger unit/contract rows.
- `tests/test_reconcile_trial_ledger_recovery.py`: atomic, recovery and concurrency rows.
- `tests/test_m6_archive_binding_v2.py`: ARCHIVE rows.
- `tests/test_m6_archival_replay_contract_v5.py`: REPLAY rows.
- `tests/test_m7_ccc_gate_policy.py`: CCC/CHECKPOINT/GATE/SCREEN rows.
- `tests/e2e/test_m65_pre_m7_synthetic_cli.py`: critical public journeys.

`eng-write-tests` owns unit/integration/contract/static rows. `eng-validate-e2e` owns the E2E journeys below.

## 5. Coverage obligations

Required include-list after implementation:

```text
src/qlib_peerlite/data/market_state.py
src/qlib_peerlite/governance/trial_ledger.py
src/qlib_peerlite/governance/m6_archive.py
scripts/reconcile_trial_ledger.py
scripts/server/verify_m6_peerlite_archival_replay.py
future bounded CCC/checkpoint/Gate/screen modules named by implementation
```

Requirement: 100% line and branch coverage for the include-list, with no `pragma: no cover`, assertion-free
execution cases or broad exclusions. Exclusions are limited to type-check-only blocks and the CLI
`if __name__ == "__main__"` line when the same `main(argv)` path is exercised directly. Existing unrelated
legacy modules are outside the protected percentage but remain in the full regression suite.

## 6. Critical synthetic E2E journeys

1. `STATE→JOIN`: build a three-date T-known state product and manifest from sealed synthetic rows, then exact
   join to a tiny panel; assert hashes and no 2025/OOS access.
2. `JOURNAL→LEDGER→RECEIPT`: invoke the real reconciliation CLI on the exact prefix and Budget V2 roster;
   inject precommit crash/other append/rebase; assert one retained set and immutable receipts.
3. `ARCHIVE→REPLAY RECEIPT`: invoke the real verifier command with the bound synthetic 2×7 CUDA seam; assert
   static binding, exhaustive no-fit/dependency evidence, 14/0 and unchanged ledger.
4. `M7 POLICY`: run CCC/Gate mechanics only on synthetic labels/state and feed fixed weekly returns to screen
   policy; assert HOLD/PASS boundaries and absence of promotion or any persistent trial event.

## 7. Verdict and next boundary

Verdict: `PASS`. Every approved behavior has success plus failure/boundary/recovery coverage, an exact oracle,
fixture, layer and branch obligation. No unresolved business rule or dependency contract remains.

This document authorizes only the router to move to expected-red test writing. It does not authorize production
implementation, test-green claims, real replay, fitting, PIT rerun, budget mutation or final OOS.
