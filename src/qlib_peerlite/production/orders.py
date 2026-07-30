from __future__ import annotations

import math

import pandas as pd

from qlib_peerlite.governance.artifacts import sha256_bytes

from .policy import ShadowPolicy


def build_paper_intents(
    frame: pd.DataFrame,
    policy: ShadowPolicy,
    cycle_id: str,
) -> list[dict[str, object]]:
    ordered = frame.sort_values(
        ["score", "instrument"],
        ascending=[False, True],
        kind="mergesort",
    )
    selected_count = min(
        policy.max_paper_intents,
        max(1, math.ceil(len(ordered) * policy.top_fraction)),
    )
    selected = ordered.head(selected_count)
    target_weight = min(1.0 / selected_count, policy.max_name_weight)
    return [
        {
            "schema_version": "qlib_peerlite_paper_intent_v1",
            "cycle_id": cycle_id,
            "rank": rank,
            "instrument": str(row.instrument),
            "target_weight": target_weight,
            "idempotency_key": sha256_bytes(f"{cycle_id}:{row.instrument}".encode()),
            "execution": "PAPER_ONLY",
        }
        for rank, row in enumerate(selected.itertuples(index=False), start=1)
    ]
