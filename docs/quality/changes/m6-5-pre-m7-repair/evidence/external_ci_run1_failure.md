# External CI run 1 — bounded failure analysis

- Run: https://github.com/jonaslvhaocheng-ops/qlib-peerlite-research/actions/runs/30461005976
- Head: `ca17f81796f0ae371b85d22bac858ec188e56f44`
- Result: `FAIL`
- Passing before failure: pinned controller checkout, locked environment restore, canonical pre-merge ledger check, Ruff.
- Failing command: complete `pytest` suite.
- Observed result: `80 passed, 4 skipped, 2 failed`.

Both failures came from the same environmental mismatch. The M6 archive verifier intentionally executes:

```text
git show 0af4572:scripts/server/run_m6_peerlite.py
```

The primary GitHub Actions checkout used the default shallow history, so the frozen M6 commit object was absent. The same tests pass in a checkout with repository history. This is not an Alpha, model, PIT, label, portfolio, or final-OOS failure.

The bounded correction is to set `fetch-depth: 0` on the primary repository checkout only. No production Python, research rule, evidence binding, M7 code, training input, model parameter, or final-OOS boundary is changed.
