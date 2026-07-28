from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = PROJECT_ROOT / "evidence/gates/M6_peerlite_gate.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(value: dict) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    payload = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_m6_gate_binds_verified_receipts_and_trial_ledger() -> None:
    gate = load_json(GATE_PATH)
    assert gate["status"] == "PASS"
    assert gate["passed"] is True
    assert gate["content_sha256"] == content_hash(gate)

    for name in (
        "execution_spec",
        "mechanics",
        "run_manifest",
        "verification",
        "run_journal",
        "cumulative_trial_ledger",
    ):
        binding = gate["evidence"][name]
        path = PROJECT_ROOT / binding["path"]
        assert path.is_file(), name
        assert sha256_file(path) == binding["sha256"], name
        if "content_sha256" in binding:
            receipt = load_json(path)
            assert receipt["content_sha256"] == binding["content_sha256"], name
            assert receipt["content_sha256"] == content_hash(receipt), name

    verification = load_json(
        PROJECT_ROOT / gate["evidence"]["verification"]["path"]
    )
    assert verification["prediction_rows_total"] == 1_898_028
    assert verification["journal"]["counted_candidate_evaluations"] == 2
    assert verification["journal"]["counted_model_fits"] == 15
    assert verification["journal"]["failed_events"] == 0
    assert verification["deterministic_refit"]["status"] == "PASS_EXACT"
    assert verification["final_oos_market_partitions_opened"] is False
    assert verification["selection_performed"] is False
    assert verification["portfolio_backtests"] == 0
    assert verification["cost_adjusted_metrics_computed"] is False
    assert (
        sha256_file(PROJECT_ROOT / verification["verifier"]["path"])
        == verification["verifier"]["sha256"]
    )

    ledger_path = PROJECT_ROOT / gate["evidence"]["cumulative_trial_ledger"]["path"]
    events = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    counts = Counter(
        "candidate"
        if event.get("counts_as_candidate_evaluation") is True
        else "fit"
        if event.get("counts_as_model_fit") is True
        else "other"
        for event in events
    )
    assert counts == Counter({"candidate": 6, "fit": 44, "other": 1})
    assert len({event.get("evaluation_id") for event in events if event.get(
        "counts_as_candidate_evaluation"
    )}) == 6
    assert len({event.get("fit_id") for event in events if event.get(
        "counts_as_model_fit"
    )}) == 44


def test_m6_ledger_preserves_frozen_pre_run_prefix_and_no_large_artifacts() -> None:
    budget = load_json(
        PROJECT_ROOT / "contracts/immutable/m6_trial_budget_start.json"
    )
    expected_prefix_hash = budget["trial_ledger"]["sha256_at_freeze"]
    digest = hashlib.sha256()
    matched_prefix_bytes: int | None = None
    consumed = 0
    ledger_path = PROJECT_ROOT / budget["trial_ledger"]["path"]
    with ledger_path.open("rb") as handle:
        for line in handle:
            digest.update(line)
            consumed += len(line)
            if digest.hexdigest() == expected_prefix_hash:
                matched_prefix_bytes = consumed
                break
    assert matched_prefix_bytes is not None
    assert matched_prefix_bytes < ledger_path.stat().st_size

    evidence_root = PROJECT_ROOT / "evidence/m6"
    assert not list(evidence_root.rglob("predictions.parquet"))
    assert not [path for path in evidence_root.rglob("*") if path.name == "checkpoint"]
