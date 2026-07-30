#!/usr/bin/env python3
"""Repository entrypoint for the pinned Engineering Quality controller."""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINNED = (
    ROOT
    / ".engineering-quality"
    / "controller"
    / "skills"
    / "eng-route-quality-work"
    / "scripts"
    / "quality_ledger.py"
)
LOCAL_DEVELOPMENT = Path(
    "/Users/jonas/Desktop/重要资料/各种skill/工程质量技能/"
    "skills/eng-route-quality-work/scripts/quality_ledger.py"
)


def main() -> None:
    controller = PINNED if PINNED.is_file() else LOCAL_DEVELOPMENT
    if not controller.is_file():
        raise SystemExit("pinned Engineering Quality controller is unavailable")
    runpy.run_path(str(controller), run_name="__main__")


if __name__ == "__main__":
    main()

