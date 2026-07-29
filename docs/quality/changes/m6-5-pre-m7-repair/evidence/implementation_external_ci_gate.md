# M6.5 external CI gate implementation

## Scope

This implementation adds only the external transport and verification needed
to close the already-required CI stage:

- public GitHub repository identity with a documented no-license-grant boundary;
- pull-request/manual GitHub Actions workflow;
- locked Python 3.11 environment restoration;
- canonical source-digest, ledger and evidence verification by the externally
  pinned engineering-quality controller;
- self-authored source Ruff gate;
- complete 86-test repository suite;
- M6 archival-evidence and replay-mechanics verification.

The Ruff command excludes `scripts/vendor/` because that directory is an
immutable third-party PIT-audit snapshot with its own validation and hashes.
It remains covered by repository source binding and the complete test suite.

## Mainline invariants

- No M7 candidate, fit, model, parameter, threshold, portfolio rule, or final
  OOS state was executed or changed.
- The M7 budget remains unused.
- M6 archival evidence remains immutable.
- The external CI verifier is read-only and cannot self-sign the ledger CI
  stage.

## Local verification

- Workflow structure: PASS.
- CI verifier Ruff: PASS.
- Project Ruff (`src`, `tests`, non-vendor `scripts`): PASS.
- Complete test suite: `86 passed`.

Verdict: `PASS`, ready for router-selected green tests.
