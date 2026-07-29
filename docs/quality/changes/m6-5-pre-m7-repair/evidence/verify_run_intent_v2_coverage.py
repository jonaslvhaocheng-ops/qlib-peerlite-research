from __future__ import annotations

import json
from pathlib import Path

REPORT = Path(__file__).with_name("run_intent_v2_coverage.json")
SOURCE = "src/qlib_peerlite/governance/trial_ledger.py"
PROTECTED_RANGES = ((69, 138), (180, 330))


def protected(line: int) -> bool:
    return any(start <= line <= end for start, end in PROTECTED_RANGES)


report = json.loads(REPORT.read_text(encoding="utf-8"))
source = report["files"][SOURCE]
missing_lines = [line for line in source["missing_lines"] if protected(line)]
missing_branches = [
    branch for branch in source["missing_branches"] if protected(branch[0])
]
if missing_lines or missing_branches:
    raise SystemExit(
        f"RunIntent V2 coverage gap: lines={missing_lines}, branches={missing_branches}"
    )
print("PASS: RunIntent V2 protected ranges have 100% line and branch coverage")
