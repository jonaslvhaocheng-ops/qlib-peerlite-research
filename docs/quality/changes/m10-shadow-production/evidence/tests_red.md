# Expected-red evidence

The M10 expected-red probe is intentionally independent of pytest collection.
Before production code exists it exits 1 with:

```text
EXPECTED_RED: M10 production package is not implemented
```

After implementation began, the same probe was replayed with
`PYTHONPATH=/tmp/qlib-peerlite-m10-red-base/src`, where the detached worktree is
the exact pre-change commit `53d123e`. It produced the same expected failure
while using the current locked Python dependencies. This is the approved
missing-behavior failure, not a syntax, dependency or fixture failure.
