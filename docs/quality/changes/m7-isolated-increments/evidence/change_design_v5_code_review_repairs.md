# M7 code-review repair design

- Status: `READY FOR INDEPENDENT REVIEW / SYNTHETIC ENGINEERING ONLY`
- Risk: `R3`
- Supersedes empirical-authority portions of
  `change_design_v4_enforceable.md`
- Trigger:
  `code_review_v1_independent.md`
- Baseline after separate M6.5 archive:
  `964975e`

## 1. Decision

This change will not create, export or accept any empirical fit lease.

The current CR explicitly forbids empirical execution, and the real cost,
benchmark and complete PIT authorities do not exist. Therefore the only honest
complete engineering result is:

```text
CCC synthetic mechanics: TESTED
Gate synthetic mechanics: TESTED
empirical prerequisite preflight: NOT_RUN / NEEDS_EVIDENCE
empirical CCC fit: REJECTED
empirical Gate fit: REJECTED
final OOS: SEALED / NOT_ACCESSED
```

A later CR may design an externally anchored empirical executor. It cannot
reuse a synthetic capability, diagnostic prerequisite bundle or run-state
receipt as fit authority.

## 2. Product repairs

### 2.1 Remove empirical model authorization

- Delete `EmpiricalFitLease` and
  `verify_reconciled_empirical_fit_lease`.
- `PeerLiteModel.fit` accepts only an exact generated
  `SyntheticFitCapability` for the two M7 candidates.
- Every ordinary `PanelDataset`, arbitrary object or empirical-looking lease
  is rejected before `prepare`.
- `validate_screening_prerequisites` remains a read-only diagnostic. Its
  result type contains `claim_ceiling=PRECHECK_ONLY_NOT_FIT_AUTHORITY` and is
  never accepted by a model.

### 2.2 Freeze candidate semantics

At construction, fit and checkpoint load:

| Candidate | Required architecture/objective |
|---|---|
| `PEERLITE_K16_CCC` | K16, hidden64, 4 heads, dropout0.1, no Gate, market_dim0, CCC, seed7 |
| `PEERLITE_K16_MSE_GATE` | K16, hidden64, 4 heads, dropout0.1, Gate enabled, market_dim4, MSE, seed7 |

Input feature count and bounded synthetic training epochs/batch size remain
fixture parameters, not candidate choices. Any model-ID/config mismatch
raises before data access.

### 2.3 Persisted-evidence recovery mechanics

Run state is a synthetic/governance mechanics simulator only. It cannot issue
fit authority.

- Remove recovery APIs that accept digest strings.
- Add `recover_from_persisted_evidence` that reads a v2 journal and
  authoritative reconciled ledger through existing governance validation.
- No reconciled start leaves `FIT_INTENT`.
- A reconciled start with no terminal receipt becomes `FIT_INTERRUPTED`.
- A terminal receipt must be strict canonical JSON and bind run, source event,
  candidate, seed, fold, purpose, outcome and checkpoint/output hashes.
- The receipt can advance the mechanics state only; it cannot be passed to a
  model.

### 2.4 Strict synthetic checkpoint dispatch

- v1 is accepted only for a non-M7 MSE model with Gate disabled.
- v2 is accepted only for the two exact candidate configurations above and
  only with `family_id=SYNTHETIC_M7_ENGINEERING_V1` and
  `purpose=SYNTHETIC_MECHANICS_ONLY`.
- Validate schema, candidate/config, all digest formats and semantic/execution
  hashes before loading weights into the network.
- After safe `weights_only=True` deserialization, validate the state hash
  before `load_state_dict`.
- Unknown, mixed, empirical or cross-candidate contexts fail.

No v2 metadata contains `"externally-bound"` placeholders.

### 2.5 Gate claim boundary

`SyntheticM7Dataset` is the only Gate dataset in this change. The report and
model card must state that verified empirical Gate/PIT binding is not
implemented and remains `NOT_RUN`. Synthetic future-poison tests validate
mechanics only.

## 3. CI and coverage repairs

Add `.github/workflows/m7-quality-gate.yml`:

- pinned checkout/setup-uv/controller commits;
- Python 3.11 and `uv sync --frozen --extra dev`;
- job name `m7-external-quality-gate`;
- ledger `check-ci`, Ruff, full pytest, M7 clean-process E2E and protected
  coverage.

The repository wrapper uses the checked-out pinned controller in CI. Its
absolute workstation fallback is local-development convenience only and can
never satisfy external CI.

Protected coverage includes:

- every authored file under `src/qlib_peerlite/m7`;
- `src/qlib_peerlite/models/losses.py`;
- `src/qlib_peerlite/m7/adapter.py`, which exclusively owns all M7 candidate,
  authority, prediction-binding and checkpoint-dispatch policy branches.

`models.peerlite` calls the adapter and retains generic M6 training mechanics;
it contains no duplicate M7 policy. Because the controller inventories every
file under `src/qlib_peerlite/m7`, `adapter.py` automatically enters the
protected denominator. There is no changed-line fallback, manually declared
branch list, coverage exception, review-only substitute, source exclusion or
hollow assertion. Exact line and branch coverage both remain 100%.

## 4. Required tests

1. Fake prerequisite roots/journals/leases cannot authorize a model.
2. Every candidate-ID/config mismatch rejects before dataset access.
3. Recovery has no raw-digest or boolean API and consumes actual temporary
   journal/ledger/terminal files.
4. v1 CCC/Gate and arbitrary v2 contexts reject; cross-candidate/fixture
   checkpoint use rejects.
5. Future-only state mutation cannot change past generated state or scores.
6. Clean-process E1 CCC, E2 Gate and E3 empirical-preflight journeys emit
   deterministic JSON and `persistent_effects=0`.
7. The M7 workflow parses to the exact pinned job and commands.
8. Full suite and protected M7 line/branch coverage remain 100%.
9. The raw controller report lists `m7/adapter.py`, and mutation tests exercise
   every frozen candidate field and checkpoint dispatch branch.

## 5. Scope separation

The completed M6.5 external-PASS archive is preserved in separate commit
`964975e`. M7 code review uses that commit as its base, so the M7 diff contains
no M6.5 mutation.

## Verdict

`PASS / READY FOR INDEPENDENT R3 REVIEW`

This repair narrows authority to match the CR. It does not reduce the eventual
empirical evidence standard; it prevents unearned authority until that
standard can actually be met.
