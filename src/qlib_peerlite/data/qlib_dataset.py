from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from qlib_peerlite.governance.artifacts import sha256_file

from .splits import FoldSpec, purged_segment_masks

MARKET_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover",
    "label_open",
    "label_close",
)


class QlibDataProductError(RuntimeError):
    """Raised when a bound data product cannot safely enter Qlib."""


@dataclass(frozen=True)
class BoundProductFrame:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    label_end_time: pd.Series
    split: pd.Series
    calendar: pd.DatetimeIndex
    product_id: str
    product_manifest_sha256: str
    source_file_sha256: tuple[str, ...]


@dataclass(frozen=True)
class QlibFold:
    dataset: Any
    fold_id: str
    segments: dict[str, tuple[pd.Timestamp, pd.Timestamp]]
    row_counts: dict[str, int]
    key_sha256: dict[str, str]
    feature_columns: tuple[str, ...]


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QlibDataProductError(f"cannot read data-product manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise QlibDataProductError("data-product manifest root must be an object")
    return value


def _matrix_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = manifest.get("matrix")
    if not isinstance(matrix, dict):
        raise QlibDataProductError("data-product matrix manifest is missing")
    files = matrix.get("files")
    if not isinstance(files, list) or not files:
        raise QlibDataProductError("data-product matrix file inventory is empty")
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("path"), str)
        or not isinstance(item.get("sha256"), str)
        or not isinstance(item.get("year"), int)
        for item in files
    ):
        raise QlibDataProductError("data-product matrix file inventory is malformed")
    return files


def verify_product_boundary(manifest: dict[str, Any]) -> None:
    seal = manifest.get("oos_seal")
    matrix = manifest.get("matrix")
    if not isinstance(seal, dict) or not isinstance(matrix, dict):
        raise QlibDataProductError("data-product OOS seal or matrix metadata is missing")
    if (
        seal.get("final_oos_market_partitions_opened") is not False
        or seal.get("performance_metrics_computed") is not False
    ):
        raise QlibDataProductError("data product has opened final OOS or computed performance")
    if str(matrix.get("date_max", "")) >= "2025-01-01":
        raise QlibDataProductError("data product reaches the sealed final-OOS period")
    files = _matrix_files(manifest)
    if any(item["year"] >= 2025 for item in files):
        raise QlibDataProductError("matrix inventory contains a final-OOS partition")
    features = matrix.get("features")
    if (
        not isinstance(features, list)
        or len(features) != 50
        or len(features) != len(set(features))
        or matrix.get("feature_count") != 50
    ):
        raise QlibDataProductError("matrix does not contain the frozen 50-feature set")


def load_bound_product_frame(
    product_dir: Path,
    *,
    years: set[int] | None = None,
    verify_all_files: bool = True,
) -> BoundProductFrame:
    """Load a hash-verified, pre-final-OOS product into one canonical panel."""

    product_dir = product_dir.resolve()
    manifest_path = product_dir / "data_product_manifest.json"
    manifest = _load_manifest(manifest_path)
    verify_product_boundary(manifest)
    calendar_item = manifest.get("calendar")
    if (
        not isinstance(calendar_item, dict)
        or not isinstance(calendar_item.get("path"), str)
        or not isinstance(calendar_item.get("sha256"), str)
    ):
        raise QlibDataProductError("data-product calendar binding is missing")
    calendar_path = product_dir / calendar_item["path"]
    if not calendar_path.is_file() or sha256_file(calendar_path) != calendar_item["sha256"]:
        raise QlibDataProductError("data-product calendar hash mismatch")
    calendar_frame = pd.read_csv(calendar_path, usecols=["session_id"])
    calendar = pd.DatetimeIndex(
        pd.to_datetime(
            calendar_frame["session_id"].str.replace(r"^XSHG_XSHE-", "", regex=True),
            errors="raise",
        )
    ).normalize()
    if calendar.empty or calendar.duplicated().any() or not calendar.is_monotonic_increasing:
        raise QlibDataProductError("data-product calendar is empty, duplicated or unsorted")
    if calendar.max() >= pd.Timestamp("2025-01-01"):
        raise QlibDataProductError("data-product calendar reaches final OOS")
    inventory = _matrix_files(manifest)
    wanted = {item["year"] for item in inventory} if years is None else set(years)
    declared_years = {item["year"] for item in inventory}
    if not wanted or not wanted <= declared_years:
        raise QlibDataProductError("requested years are empty or outside the manifest")
    if any(year >= 2025 for year in wanted):
        raise QlibDataProductError("requested years reach the sealed final-OOS period")

    verified_hashes: list[str] = []
    selected_paths: list[Path] = []
    expected_rows = 0
    for item in inventory:
        path = product_dir / item["path"]
        if not path.is_file():
            raise QlibDataProductError(f"missing matrix partition: {item['path']}")
        if verify_all_files or item["year"] in wanted:
            actual = sha256_file(path)
            if actual != item["sha256"]:
                raise QlibDataProductError(f"matrix partition hash mismatch: {item['path']}")
            verified_hashes.append(actual)
        if item["year"] in wanted:
            selected_paths.append(path)
            expected_rows += int(item["rows"])

    matrix = manifest["matrix"]
    feature_columns = tuple(matrix["features"])
    required = [
        "datetime",
        "instrument",
        "split",
        "label_end_time",
        "label",
        *MARKET_COLUMNS,
        *feature_columns,
    ]
    frames = [pd.read_parquet(path, columns=required) for path in selected_paths]
    frame = pd.concat(frames, ignore_index=True, copy=False)
    if len(frame) != expected_rows:
        raise QlibDataProductError(
            f"loaded row count {len(frame)} does not match manifest {expected_rows}"
        )
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.tz_localize(None).dt.normalize()
    frame["instrument"] = frame["instrument"].astype(str)
    if frame.duplicated(["datetime", "instrument"]).any():
        raise QlibDataProductError("loaded product has duplicate datetime/instrument keys")
    if frame["datetime"].max() >= pd.Timestamp("2025-01-01"):
        raise QlibDataProductError("loaded rows reach the sealed final-OOS period")
    if frame[list(feature_columns)].isna().any().any() or frame["label"].isna().any():
        raise QlibDataProductError("loaded product contains missing feature or label values")

    frame = frame.sort_values(["datetime", "instrument"], ignore_index=True)
    index = pd.MultiIndex.from_frame(frame[["datetime", "instrument"]])
    index.names = ["datetime", "instrument"]
    flat_columns = [*feature_columns, "label", *MARKET_COLUMNS]
    panel = frame[flat_columns].copy()
    panel.index = index
    panel.columns = pd.MultiIndex.from_tuples(
        [
            *[("feature", name) for name in feature_columns],
            ("label", "label"),
            *[("market", name) for name in MARKET_COLUMNS],
        ]
    )
    panel = panel.sort_index()
    label_end_dates = (
        pd.to_datetime(frame["label_end_time"], utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.tz_localize(None)
        .dt.normalize()
    )
    label_end_time = pd.Series(
        label_end_dates.to_numpy(),
        index=index,
        name="label_end_time",
    ).sort_index()
    split = pd.Series(frame["split"].to_numpy(), index=index, name="split").sort_index()
    return BoundProductFrame(
        frame=panel,
        feature_columns=feature_columns,
        label_end_time=label_end_time,
        split=split,
        calendar=calendar,
        product_id=str(manifest["product_id"]),
        product_manifest_sha256=sha256_file(manifest_path),
        source_file_sha256=tuple(verified_hashes),
    )


def _segment_bounds(
    mask: pd.Series, dates: pd.DatetimeIndex, name: str
) -> tuple[pd.Timestamp, pd.Timestamp]:
    selected = dates[mask.to_numpy(dtype=bool)]
    if selected.empty:
        raise QlibDataProductError(f"fold segment is empty: {name}")
    return pd.Timestamp(selected.min()), pd.Timestamp(selected.max())


def _key_digest(index: pd.MultiIndex) -> str:
    digest = hashlib.sha256()
    for timestamp, instrument in index:
        digest.update(pd.Timestamp(timestamp).isoformat().encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(str(instrument).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_qlib_fold(
    product: BoundProductFrame,
    fold: FoldSpec,
    *,
    embargo_sessions: int = 5,
) -> QlibFold:
    """Create a Qlib DatasetH after explicit label purge and embargo."""

    try:
        from qlib.data.dataset import DatasetH
        from qlib.data.dataset.handler import DataHandlerLP
        from qlib.data.dataset.loader import StaticDataLoader
    except ImportError as exc:
        raise QlibDataProductError("install the optional qlib dependency") from exc

    dates = pd.DatetimeIndex(product.frame.index.get_level_values("datetime"))
    masks = purged_segment_masks(
        dates,
        product.label_end_time,
        fold,
        embargo_sessions=embargo_sessions,
        calendar=product.calendar,
    )
    segments = {name: _segment_bounds(mask, dates, name) for name, mask in masks.items()}
    keep = masks["train"] | masks["valid"] | masks["test"]
    filtered = product.frame.loc[keep.to_numpy(dtype=bool)].copy()
    if filtered.index.duplicated().any():
        raise QlibDataProductError("fold panel has duplicate keys")

    data_loader = StaticDataLoader(
        {
            "feature": filtered["feature"],
            "label": filtered["label"],
            "market": filtered["market"],
        }
    )
    handler = DataHandlerLP(
        instruments=None,
        start_time=min(bound[0] for bound in segments.values()),
        end_time=max(bound[1] for bound in segments.values()),
        data_loader=data_loader,
        infer_processors=[],
        learn_processors=[],
    )
    dataset = DatasetH(handler=handler, segments=segments)

    row_counts: dict[str, int] = {}
    key_sha256: dict[str, str] = {}
    seen: set[tuple[pd.Timestamp, str]] = set()
    for name in ("train", "valid", "test"):
        prepared = dataset.prepare(name, col_set=["feature", "label"])
        if len(prepared.columns.get_level_values(0).unique()) != 2:
            raise QlibDataProductError(f"Qlib segment groups are malformed: {name}")
        if prepared["feature"].shape[1] != len(product.feature_columns):
            raise QlibDataProductError(f"Qlib feature count mismatch: {name}")
        keys = {(pd.Timestamp(ts), str(inst)) for ts, inst in prepared.index}
        if seen & keys:
            raise QlibDataProductError(f"Qlib segment overlap detected: {name}")
        seen |= keys
        row_counts[name] = len(prepared)
        key_sha256[name] = _key_digest(prepared.index)

    return QlibFold(
        dataset=dataset,
        fold_id=fold.fold_id,
        segments=segments,
        row_counts=row_counts,
        key_sha256=key_sha256,
        feature_columns=product.feature_columns,
    )
