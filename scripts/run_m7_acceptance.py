from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np

from qlib_peerlite.m7.market_state import SyntheticFixtureSpec, build_synthetic_m7_fixture
from qlib_peerlite.m7.prerequisites import validate_screening_prerequisites
from qlib_peerlite.models.peerlite import PeerLiteModel

_SNAPSHOT_EXCLUDED_PARTS = {".git", ".venv", ".pytest_cache", "__pycache__"}


def _repository_snapshot(repo_root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(repo_root.rglob("*")):
        relative = path.relative_to(repo_root)
        if (
            not path.is_file()
            or any(part in _SNAPSHOT_EXCLUDED_PARTS for part in relative.parts)
            or path.name in {".coverage", "coverage.json"}
        ):
            continue
        snapshot[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _persistent_effects(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _candidate_config(journey: str) -> dict[str, object]:
    gate = journey == "gate"
    return {
        "input_dim": 4,
        "hidden_dim": 64,
        "num_peers": 16,
        "num_heads": 4,
        "dropout": 0.1,
        "market_dim": 4 if gate else 0,
        "market_gate": gate,
        "loss": "mse" if gate else "ccc",
        "seed": 7,
        "epochs": 1,
        "patience": 1,
        "cross_section_batch_size": 2,
        "device": "cpu",
        "model_id": "PEERLITE_K16_MSE_GATE" if gate else "PEERLITE_K16_CCC",
    }


def run_candidate(journey: str) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    before = _repository_snapshot(repo_root)
    dataset, capability = build_synthetic_m7_fixture(
        SyntheticFixtureSpec(
            fixture_version="m7-synthetic-v1",
            seed=7,
            start_date="2000-01-03",
            trading_days=12,
            instruments=4,
            feature_count=4,
        )
    )
    config = _candidate_config(journey)
    model_id = str(config["model_id"])
    model = PeerLiteModel(**config)
    model.fit(dataset, m7_authority=capability.for_candidate(model_id))
    expected = model.predict(dataset)
    with tempfile.TemporaryDirectory(prefix=f"m7-{journey}-") as directory:
        checkpoint = Path(directory) / "checkpoint"
        model.save_checkpoint(checkpoint)
        replay = PeerLiteModel.load_checkpoint(checkpoint, device="cpu").predict(dataset)
    if not np.array_equal(expected.to_numpy(), replay.to_numpy()):
        raise RuntimeError("checkpoint replay changed the score")
    effects = _persistent_effects(before, _repository_snapshot(repo_root))
    if effects:
        raise RuntimeError(f"acceptance journey changed repository state: {effects}")
    return {
        "journey": journey,
        "status": "PASS",
        "claim_ceiling": dataset.claim_ceiling,
        "model_id": model_id,
        "score_rows": len(expected),
        "checkpoint_replay_exact": True,
        "persistent_effects": len(effects),
        "persistent_effect_paths": effects,
    }


def run_preflight() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    before = _repository_snapshot(repo_root)
    bundle = validate_screening_prerequisites(repo_root)
    effects = _persistent_effects(before, _repository_snapshot(repo_root))
    if effects:
        raise RuntimeError(f"preflight changed repository state: {effects}")
    return {
        "journey": "preflight",
        "status": "PASS",
        "claim_ceiling": bundle.claim_ceiling,
        "prerequisite_bundle_sha256": bundle.bundle_sha256,
        "artifact_count": len(bundle.artifact_sha256),
        "persistent_effects": len(effects),
        "persistent_effect_paths": effects,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("journey", choices=("ccc", "gate", "preflight"))
    args = parser.parse_args()
    result = run_preflight() if args.journey == "preflight" else run_candidate(args.journey)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
