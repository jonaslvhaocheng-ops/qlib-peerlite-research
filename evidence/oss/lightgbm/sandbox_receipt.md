# LightGBM sandbox receipt

Status: `PASS`

Executed evidence:

- `uv sync --extra dev --extra qlib`
- `uv run pytest -q` → `19 passed`
- LightGBM version: `4.6.0`
- Synthetic B0 fit and unified `(datetime, instrument) -> score` test passed.
- Environment receipt:
  `evidence/environment/local_v3.json`
- Environment receipt SHA-256:
  `eefe5eef5e202d3cf7d504778fe087e2c2c9570fb24efc880a910fbc8cd9a348`
- Lock SHA-256:
  `b406234ca9f9533c71425e0874d6b158cc2991f70ed1a3c8c9c9835e7c3c29ef`

Boundary:

- LightGBM is only the B0 training runtime;
- label, temporal split, trial budget, costs and OOS remain caller-owned;
- local macOS standalone import still requires OpenMP; the safe project test
  path and Linux training target pass, while the rejected preload experiment is
  retained in `evidence/environment/openmp_failure_receipt.md`.
