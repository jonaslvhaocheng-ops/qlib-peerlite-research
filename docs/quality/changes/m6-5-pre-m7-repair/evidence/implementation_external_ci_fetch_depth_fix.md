# External CI full-history implementation

## Change

The primary `actions/checkout` step now requests complete Git history with `fetch-depth: 0`.

## Why this is necessary

M6 archival verification is deliberately commit-bound. It reads frozen source blobs from historical commits, so a depth-one checkout cannot satisfy the evidence contract. Fetching full history makes the external runner equivalent to the already-validated local archival-verification environment.

## Scope control

- Workflow-only change.
- No source-code or test-oracle weakening.
- No removal or skipping of the two failing archive tests.
- No unpinning of Actions, Python, uv, dependencies, or the external quality controller.
- No M7 training, real-data access, portfolio backtest, cost metric, selection, or final-OOS access.
