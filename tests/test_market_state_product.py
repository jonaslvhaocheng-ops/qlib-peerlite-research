from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from qlib_peerlite.data.market_state import aggregate_daily_state
from qlib_peerlite.data.market_state_product import (
    MarketStateProductError,
    load_qualified_market_state_product,
)
from qlib_peerlite.governance.artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)


def _content_sha256(value: dict[str, object]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _write_product(tmp_path: Path) -> tuple[Path, Path]:
    product = tmp_path / "product"
    product.mkdir()
    index = pd.MultiIndex.from_product(
        [
            pd.to_datetime(["2012-01-04", "2012-01-05"]),
            ["000001.SZ", "600000.SH"],
        ],
        names=["datetime", "instrument"],
    )
    population = pd.DataFrame(
        {
            "ret_mean_20": [0.01, 0.02, 0.03, 0.04],
            "ret_std_20": [0.10, 0.20, 0.30, 0.40],
            "ret_1d": [0.01, -0.01, 0.02, 0.03],
            "turnover_mean_20": [0.05, 0.06, 0.07, 0.08],
        },
        index=index,
    )
    state = aggregate_daily_state(population)
    state_path = product / "market_state.parquet"
    population_path = product / "selected_population.parquet"
    state.reset_index().to_parquet(state_path, index=False)
    population.reset_index().to_parquet(population_path, index=False)
    manifest: dict[str, object] = {
        "schema_version": "qlib_peerlite_market_state_product_v1",
        "semantic_version": "m7_market_state_product_v1",
        "status": "BUILT_NOT_PIT_QUALIFIED",
        "product_id": "synthetic_state_v1",
        "policy": {"labels_or_execution_fields_consumed": False},
        "state": {
            "path": state_path.name,
            "sha256": sha256_file(state_path),
            "rows": len(state),
            "date_min": "2012-01-04",
            "date_max": "2012-01-05",
        },
        "population": {
            "path": population_path.name,
            "sha256": sha256_file(population_path),
            "rows": len(population),
        },
        "oos_seal": {
            "final_oos_start": "2025-01-01",
            "final_oos_market_partitions_opened": False,
        },
    }
    manifest["content_sha256"] = _content_sha256(manifest)
    manifest_path = product / "market_state_manifest.json"
    atomic_write_json(manifest_path, manifest)
    receipt: dict[str, object] = {
        "schema_version": "qlib_peerlite_market_state_qualification_receipt_v1",
        "semantic_version": "m7_market_state_qualification_v1",
        "status": "PASS",
        "claim": "MARKET_RECONSTRUCTIBLE",
        "product_manifest_file_sha256": sha256_file(manifest_path),
        "product_manifest_content_sha256": manifest["content_sha256"],
        "parent_fixed_pit_manifest_sha256": "a" * 64,
        "parent_fixed_pit_content_sha256": "b" * 64,
        "parent_behavior_manifest_sha256": "c" * 64,
        "parent_behavior_content_sha256": "d" * 64,
        "checks": {
            "source_snapshot_binding": "PASS",
            "parent_fixed_pit": "PASS",
            "parent_behavior_pit": "PASS",
            "independent_recompute": "PASS",
            "future_poison_prefix": "PASS",
            "date_coverage": "PASS",
            "schema_and_digests": "PASS",
        },
        "final_oos_market_partitions_opened": False,
        "final_oos_metrics_computed": False,
    }
    receipt["content_sha256"] = _content_sha256(receipt)
    receipt_path = tmp_path / "qualification_receipt.json"
    atomic_write_json(receipt_path, receipt)
    return product, receipt_path


def test_load_qualified_market_state_product_binds_exact_chain(tmp_path: Path) -> None:
    product, receipt = _write_product(tmp_path)
    loaded = load_qualified_market_state_product(product, receipt)
    assert len(loaded.state) == 2
    assert loaded.state.index.max() < pd.Timestamp("2025-01-01")
    assert len(loaded.product_manifest_sha256) == 64
    assert len(loaded.qualification_receipt_sha256) == 64


@pytest.mark.parametrize(
    ("target", "mutation", "message"),
    [
        ("receipt", ("status", "HOLD"), "qualification"),
        ("receipt", ("claim", "SYSTEM_REPLAYABLE"), "qualification"),
        ("receipt", ("final_oos_metrics_computed", True), "coverage"),
        ("manifest", ("status", "PIT_QUALIFIED"), "manifest"),
    ],
)
def test_market_state_product_rejects_mutated_evidence(
    tmp_path: Path,
    target: str,
    mutation: tuple[str, object],
    message: str,
) -> None:
    product, receipt = _write_product(tmp_path)
    path = receipt if target == "receipt" else product / "market_state_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[mutation[0]] = mutation[1]
    payload["content_sha256"] = _content_sha256(payload)
    atomic_write_json(path, payload)
    with pytest.raises(MarketStateProductError, match=message):
        load_qualified_market_state_product(product, receipt)


def test_market_state_product_rejects_state_file_mutation(tmp_path: Path) -> None:
    product, receipt = _write_product(tmp_path)
    state_path = product / "market_state.parquet"
    state = pd.read_parquet(state_path)
    state.loc[0, "mkt_trend_20"] += 1.0
    state.to_parquet(state_path, index=False)
    with pytest.raises(MarketStateProductError, match="hash mismatch"):
        load_qualified_market_state_product(product, receipt)
