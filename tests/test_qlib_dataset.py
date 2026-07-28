from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qlib_peerlite.data.qlib_dataset import (
    MARKET_COLUMNS,
    QlibDataProductError,
    build_qlib_fold,
    load_bound_product_frame,
)
from qlib_peerlite.data.splits import FoldSpec


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _product(tmp_path: Path) -> Path:
    product = tmp_path / "product"
    matrix_dir = product / "matrix"
    matrix_dir.mkdir(parents=True)
    dates = pd.bdate_range("2019-10-01", "2022-12-30")
    instruments = ["1", "2"]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    size = len(index)
    feature_names = [f"f{i:02d}" for i in range(50)]
    frame = pd.DataFrame(
        {
            "datetime": index.get_level_values("datetime"),
            "instrument": index.get_level_values("instrument"),
            "split": "TRAIN",
            "label_end_time": index.get_level_values("datetime") + pd.offsets.BDay(5),
            "label": np.linspace(-0.02, 0.02, size),
        }
    )
    for position, name in enumerate(feature_names):
        frame[name] = np.arange(size, dtype=float) / (position + 1)
    for position, name in enumerate(MARKET_COLUMNS, 1):
        frame[name] = np.arange(size, dtype=float) + position
    path = matrix_dir / "matrix_2020.parquet"
    frame.to_parquet(path, index=False)
    calendar_path = product / "calendar.csv"
    pd.DataFrame({"session_id": "XSHG_XSHE-" + dates.strftime("%Y-%m-%d")}).to_csv(
        calendar_path, index=False
    )
    manifest = {
        "product_id": "test-product",
        "oos_seal": {
            "final_oos_market_partitions_opened": False,
            "performance_metrics_computed": False,
        },
        "matrix": {
            "date_max": "2022-12-30",
            "feature_count": 50,
            "features": feature_names,
            "rows": size,
            "files": [
                {
                    "path": "matrix/matrix_2020.parquet",
                    "year": 2020,
                    "rows": size,
                    "sha256": _sha(path),
                }
            ],
        },
        "calendar": {
            "path": "calendar.csv",
            "sha256": _sha(calendar_path),
        },
    }
    (product / "data_product_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return product


@pytest.mark.qlib
def test_bound_product_builds_purged_nonoverlapping_qlib_fold(tmp_path: Path) -> None:
    pytest.importorskip("qlib")
    product = load_bound_product_frame(_product(tmp_path))
    fold = FoldSpec(
        fold_id="wf_2022",
        train_start=pd.Timestamp("2019-10-01"),
        train_end=pd.Timestamp("2020-12-31"),
        valid_start=pd.Timestamp("2021-01-01"),
        valid_end=pd.Timestamp("2021-12-31"),
        test_start=pd.Timestamp("2022-01-01"),
        test_end=pd.Timestamp("2022-12-31"),
    )
    qlib_fold = build_qlib_fold(product, fold, embargo_sessions=5)
    assert qlib_fold.row_counts["train"] > 0
    assert qlib_fold.row_counts["valid"] > 0
    assert qlib_fold.row_counts["test"] > 0
    assert len(set(qlib_fold.key_sha256.values())) == 3
    train = qlib_fold.dataset.prepare("train", col_set=["feature", "label"])
    valid = qlib_fold.dataset.prepare("valid", col_set=["feature", "label"])
    test = qlib_fold.dataset.prepare("test", col_set=["feature", "label"])
    assert train["feature"].shape[1] == 50
    assert train.index.intersection(valid.index).empty
    assert valid.index.intersection(test.index).empty
    assert valid.index.get_level_values("datetime").min() > pd.Timestamp("2021-01-01")
    assert test.index.get_level_values("datetime").min() > pd.Timestamp("2022-01-01")


def test_bound_product_rejects_partition_hash_drift(tmp_path: Path) -> None:
    product_dir = _product(tmp_path)
    path = product_dir / "matrix" / "matrix_2020.parquet"
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(QlibDataProductError, match="hash mismatch"):
        load_bound_product_frame(product_dir)
