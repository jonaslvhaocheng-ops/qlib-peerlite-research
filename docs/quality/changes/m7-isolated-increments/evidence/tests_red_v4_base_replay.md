# M7 complete expected-red base replay

- Exact pre-change base:
  `deed0a6314a90099f4b9c0c258a89e36f7c95423`
- Method: detached temporary Git worktree; copy only the approved behavioral
  test; run it with the base `src` on `PYTHONPATH`; remove worktree.
- Exit code: `1`
- Expected failure:
  `ModuleNotFoundError: No module named 'qlib_peerlite.m7'`
- Harness status: pytest collected and executed normally.

This proves the current test detects the exact missing package behavior against
the pre-change base after implementation already exists in the working tree.

Verdict: `PASS` for `tests-red` only.

