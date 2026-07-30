# M7 first-tranche green-test evidence

## Results

```text
focused first-tranche + PeerLite suite: 23 passed
full repository suite:               99 passed
Ruff:                                PASS
git diff check:                      PASS
```

Coverage was collected with pytest plugin autoload disabled to avoid the known
local pytest-cov/NumPy double-load conflict.

- `models/losses.py`: 33/33 statements, 12/12 branches, 100%.
- Every changed executable line in `PeerLiteModel._market_frame`, the gated
  `fit` entry, `clip_grad_norm_(error_if_nonfinite=True)`, and the gated
  `predict` entry executed.
- Both outcomes of each changed Gate decision execute: non-gated M6 proceeds;
  gated use fails before dataset preparation.
- The complete pre-existing `peerlite.py` module is 78% under this focused
  profile because unrelated legacy defensive branches are outside the M7
  tranche. None of its missing line or branch IDs intersects the changed Gate
  or gradient-guard lines.

The raw branch report is
`m7_first_tranche_coverage.json`.

## Contract assertions

- CCC rejects invalid epsilon, empty/mismatched/non-float32 and non-finite
  inputs.
- Singleton CCC is exact float64 MSE.
- CCC autograd returns finite float32 parameter gradients.
- A non-finite gradient norm stops before optimizer update.
- Plain and self-asserted Gate datasets fail before `prepare()`.
- The legacy `market` channel is never read by a Gate.
- Existing non-gated M6 training, prediction and checkpoint tests remain
  green.

No real data, candidate event, fit event, budget, server run or final OOS was
used.
