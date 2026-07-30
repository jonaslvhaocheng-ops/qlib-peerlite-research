# M10 Shadow Production Runbook

## Capability

M10 is `SHADOW_ONLY`. It accepts only synthetic score artifacts and produces
local paper intents. There is no live execution adapter.

## Preflight

```bash
uv run qlib-peerlite shadow-preflight \
  --policy configs/m10_shadow.yaml \
  --project-root .
```

The only successful capability is `SHADOW_ONLY`. Any request for live
execution, any unsafe operational key, a modified M9 gate, an opened final OOS
or a changed calendar fails before state mutation.

## Shadow cycle

Prepare:

- a synthetic Parquet with exact columns
  `datetime,instrument,score,model_id,fold_id`;
- instruments matching `SYNTH_[A-Z0-9]{1,24}`;
- one session date;
- a source manifest matching `qlib_peerlite_score_source_v1`;
- an existing, non-symlink local state directory.

The state directory must be owned by the current user and must not be
group/world writable. One M10 process holds an exclusive advisory lock for the
whole cycle. All cooperating M10 processes must use this runner rather than
writing the managed directories directly.

Then run:

```bash
uv run qlib-peerlite shadow-cycle \
  --policy configs/m10_shadow.yaml \
  --predictions /absolute/path/synthetic_predictions.parquet \
  --source-manifest /absolute/path/source_manifest.json \
  --state-root /absolute/path/shadow_state \
  --cycle-id m10s-20260731-164500-abcdef123456 \
  --as-of 2026-07-31T16:45:00+08:00 \
  --project-root .
```

Terminal states:

- `COMPLETE`: validated signal, monitoring and paper intents.
- `HALTED`: monitoring and transactional local alert; no paper intents.
- `NOT_DUE`: terminal manifest only.

Identical replays return the verified original cycle. A reused ID with different
bytes, a corrupt index or a corrupt terminal fails closed.

Terminal publication is atomic and no-replace on macOS and Linux. An existing
destination, including an empty or damaged directory, is retained and blocks
publication. Unsupported platforms fail closed.

## What this does not authorize

- real-data daily signals;
- use of the retained PeerLite research baseline for trading;
- final-OOS access;
- operational connection configuration;
- live or simulated exchange order submission;
- Alpha, capacity or production-readiness claims beyond local shadow mechanics.
