#!/usr/bin/env python3
"""Expected-red probe: a retry attempt must terminate before side effects."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def main() -> None:
    root = Path(__file__).parents[2]
    path = root / "scripts/server/run_m8_confirmation.py"
    spec = importlib.util.spec_from_file_location("m8_closed_runner_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load M8 runner")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.run(root, root, root / "artifacts/forbidden_m8_retry_probe")


if __name__ == "__main__":
    main()
