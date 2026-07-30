#!/usr/bin/env python3
"""Expected-red probe for the rejected M9 result-bearing contract."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    receipt = json.loads(
        (
            root
            / "evidence/m9/reauthorization_attempt_20260730_v1/validation_receipt.json"
        ).read_text(encoding="utf-8")
    )
    if receipt.get("status") != "FAIL":
        raise RuntimeError("M9 reauthorization unexpectedly escaped the frozen contract gate")
    codes = {item.get("code") for item in receipt.get("errors", [])}
    if "FAIL_OUTCOME_INFORMED_CONTRACT" not in codes:
        raise RuntimeError("M9 receipt lost the outcome-informed contract rejection")
    raise SystemExit(
        "EXPECTED_RED: a rejected result-bearing contract cannot authorize training"
    )


if __name__ == "__main__":
    main()
