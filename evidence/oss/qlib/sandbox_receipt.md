# Qlib sandbox receipt

Status: `PASS`

Executed evidence:

- `uv sync --extra dev --extra qlib`
- `uv run pytest -q` → `19 passed`
- Qlib version: `0.9.7`
- Python: `3.11.15`
- Environment receipt:
  `evidence/environment/local_v3.json`
- Environment receipt SHA-256:
  `eefe5eef5e202d3cf7d504778fe087e2c2c9570fb24efc880a910fbc8cd9a348`
- Lock SHA-256:
  `b406234ca9f9533c71425e0874d6b158cc2991f70ed1a3c8c9c9835e7c3c29ef`

Boundary:

- no upstream data was downloaded;
- local label, universe, split, cost and PIT gates remain caller-owned;
- this is an OSS sandbox pass, not Qlib semantic compatibility or alpha evidence.
