from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from qlib_peerlite.governance.artifacts import canonical_json_bytes, sha256_file

from .market_state import DAILY_PRODUCT_COLUMNS, validate_state_product


class MarketStateProductError(RuntimeError):
    """Raised when the immutable M7 market-state evidence chain is incomplete."""


@dataclass(frozen=True)
class QualifiedMarketStateProduct:
    state: pd.DataFrame
    product_id: str
    claim: str
    product_manifest_sha256: str
    qualification_receipt_sha256: str
    state_file_sha256: str


def _strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise MarketStateProductError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                MarketStateProductError(f"non-finite JSON number in {path}: {token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MarketStateProductError(f"cannot read strict JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MarketStateProductError(f"JSON root must be an object: {path}")
    return value


def _content_sha256(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _safe_bound_file(root: Path, relative: object, digest: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise MarketStateProductError("bound product path is missing")
    if not isinstance(digest, str) or len(digest) != 64:
        raise MarketStateProductError("bound product digest is invalid")
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise MarketStateProductError(f"bound product file is missing: {relative}") from exc
    if (
        not resolved.is_relative_to(root)
        or candidate.is_symlink()
        or not resolved.is_file()
    ):
        raise MarketStateProductError(f"unsafe bound product path: {relative}")
    if sha256_file(resolved) != digest:
        raise MarketStateProductError(f"bound product hash mismatch: {relative}")
    return resolved


def load_qualified_market_state_product(
    product_dir: str | Path,
    qualification_receipt: str | Path,
) -> QualifiedMarketStateProduct:
    root = Path(product_dir).resolve(strict=True)
    manifest_path = root / "market_state_manifest.json"
    manifest = _strict_json(manifest_path)
    receipt_path = Path(qualification_receipt).resolve(strict=True)
    receipt = _strict_json(receipt_path)

    if (
        manifest.get("schema_version") != "qlib_peerlite_market_state_product_v1"
        or manifest.get("status") != "BUILT_NOT_PIT_QUALIFIED"
        or manifest.get("content_sha256") != _content_sha256(manifest)
        or manifest.get("policy", {}).get("labels_or_execution_fields_consumed")
        is not False
        or manifest.get("oos_seal", {}).get("final_oos_market_partitions_opened")
        is not False
    ):
        raise MarketStateProductError("market-state manifest identity/status is invalid")
    manifest_file_sha256 = sha256_file(manifest_path)
    if (
        receipt.get("schema_version")
        != "qlib_peerlite_market_state_qualification_receipt_v1"
        or receipt.get("status") != "PASS"
        or receipt.get("claim") != "MARKET_RECONSTRUCTIBLE"
        or receipt.get("content_sha256") != _content_sha256(receipt)
        or receipt.get("product_manifest_file_sha256") != manifest_file_sha256
        or receipt.get("product_manifest_content_sha256") != manifest["content_sha256"]
        or receipt.get("final_oos_market_partitions_opened") is not False
    ):
        raise MarketStateProductError("market-state qualification binding/status is invalid")
    checks = receipt.get("checks")
    if not isinstance(checks, dict) or set(checks) != {
        "source_snapshot_binding",
        "parent_fixed_pit",
        "parent_behavior_pit",
        "independent_recompute",
        "future_poison_prefix",
        "date_coverage",
        "schema_and_digests",
    }:
        raise MarketStateProductError("market-state qualification check inventory is invalid")
    if any(value != "PASS" for value in checks.values()):
        raise MarketStateProductError("market-state qualification contains an unpassed check")
    for field in (
        "parent_fixed_pit_manifest_sha256",
        "parent_fixed_pit_content_sha256",
        "parent_behavior_manifest_sha256",
        "parent_behavior_content_sha256",
    ):
        digest = receipt.get(field)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise MarketStateProductError(f"market-state qualification {field} is invalid")

    state_item = manifest.get("state")
    if not isinstance(state_item, dict):
        raise MarketStateProductError("market-state file binding is missing")
    state_path = _safe_bound_file(root, state_item.get("path"), state_item.get("sha256"))
    state = pd.read_parquet(state_path)
    if tuple(state.columns) != ("datetime", *DAILY_PRODUCT_COLUMNS):
        raise MarketStateProductError("market-state parquet schema/order mismatch")
    state["datetime"] = pd.to_datetime(state["datetime"]).dt.tz_localize(None).dt.normalize()
    state = state.set_index("datetime")
    validate_state_product(state)
    if (
        state.index.max() >= pd.Timestamp("2025-01-01")
        or state.index.min() < pd.Timestamp("2012-01-01")
        or manifest.get("oos_seal", {}).get("final_oos_start") != "2025-01-01"
        or receipt.get("final_oos_metrics_computed") is not False
        or
        len(state) != state_item.get("rows")
        or str(state.index.min().date()) != state_item.get("date_min")
        or str(state.index.max().date()) != state_item.get("date_max")
    ):
        raise MarketStateProductError("market-state parquet coverage mismatch")
    return QualifiedMarketStateProduct(
        state=state,
        product_id=str(manifest["product_id"]),
        claim=str(receipt["claim"]),
        product_manifest_sha256=manifest_file_sha256,
        qualification_receipt_sha256=sha256_file(receipt_path),
        state_file_sha256=str(state_item["sha256"]),
    )


__all__ = [
    "MarketStateProductError",
    "QualifiedMarketStateProduct",
    "load_qualified_market_state_product",
]
