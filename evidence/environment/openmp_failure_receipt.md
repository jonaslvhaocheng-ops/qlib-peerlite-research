# macOS OpenMP failure receipt

- Classification: `resource/operational`
- Affected scope: clean standalone LightGBM import on the local Mac
- Observed failure 1: Homebrew `libomp` installation could not complete because
  the formula source timed out.
- Observed failure 2: preloading Conda's `libomp.dylib` allowed a standalone
  LightGBM import but produced a segmentation fault when the same process also
  loaded PyTorch.
- Decision: reject dynamic-library injection and preserve the safe environment.
- Current safe path:
  - local Mac: governance, Qlib interface and deterministic synthetic mechanics;
  - Linux RTX 4090 server: LightGBM/PyTorch training after server smoke tests;
  - preferred local repair: official Homebrew `libomp`, followed by full rerun.
- Historical artifact `evidence/environment/local_v2.json` belongs to the rejected
  preload experiment and is not an M0 pass receipt.
