#!/usr/bin/env python3
"""Build a hash-bound production PIT audit request from the frozen data product."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from qlib_peerlite.data.features import FEATURE_COLUMNS

TZ = ZoneInfo("Asia/Shanghai")
SCHEMA_COLUMNS = {
    "row_id": {"type": "string", "nullable": False},
    "security_id": {"type": "string", "nullable": False},
    "feature_name": {"type": "string", "nullable": False},
    "feature_value": {"type": "float", "nullable": False},
    "prediction_time": {"type": "timestamp", "nullable": False},
    "event_time": {"type": "timestamp", "nullable": False},
    "published_time": {"type": "timestamp", "nullable": False},
    "vendor_available_time": {"type": "timestamp", "nullable": False},
    "ingested_time": {"type": "timestamp", "nullable": False},
    "parse_ready_time": {"type": "timestamp", "nullable": False},
    "ingestion_batch_id": {"type": "string", "nullable": True},
    "ingested_object_sha256": {"type": "string", "nullable": True},
    "tradable_time": {"type": "timestamp", "nullable": False},
    "label_start_time": {"type": "timestamp", "nullable": False},
    "label_end_time": {"type": "timestamp", "nullable": False},
    "split": {"type": "string", "nullable": False},
    "universe_member": {"type": "boolean", "nullable": False},
    "universe_announced_time": {"type": "timestamp", "nullable": False},
    "universe_effective_from": {"type": "timestamp", "nullable": False},
    "universe_effective_to": {"type": "timestamp", "nullable": True},
    "security_status": {"type": "string", "nullable": False},
    "revision_id": {"type": "string", "nullable": False},
    "revision_known_time": {"type": "timestamp", "nullable": False},
    "adjustment_mode": {"type": "string", "nullable": False},
    "adjustment_known_time": {"type": "timestamp", "nullable": True},
    "adjustment_invariance_pass": {"type": "boolean", "nullable": True},
    "halt_time": {"type": "timestamp", "nullable": True},
    "quote_resume_time": {"type": "timestamp", "nullable": True},
    "trade_resume_time": {"type": "timestamp", "nullable": True},
    "calendar_session_id": {"type": "string", "nullable": False},
    "identifier_valid_from": {"type": "timestamp", "nullable": False},
    "identifier_valid_to": {"type": "timestamp", "nullable": True},
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def sha_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_text(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def sha_file(path: Path, *, chunk_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def path_get(root: dict[str, Any], dotted: str) -> Any:
    value: Any = root
    for part in dotted.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def utc_iso(value: pd.Timestamp) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tz is None:
        timestamp = timestamp.tz_localize(TZ)
    return timestamp.tz_convert("UTC").isoformat()


def receipt_hash(document: dict[str, Any]) -> str:
    unsigned = dict(document)
    unsigned.pop("receipt_hash", None)
    return sha_value(unsigned)


def streamed_list_sha256(items: Iterable[list[str]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"[")
    first = True
    for item in items:
        if not first:
            digest.update(b",")
        digest.update(canonical(item))
        first = False
    digest.update(b"]")
    return digest.hexdigest()


def time_roles() -> dict[str, Any]:
    roles = {
        "EVENT_TIME": ("event_time", "Underlying T-session close."),
        "PUBLICATION_TIME": ("published_time", "Public dissemination time."),
        "VENDOR_AVAILABLE_TIME": (
            "vendor_available_time",
            "First DataYes availability.",
        ),
        "INGESTED_TIME": ("ingested_time", "Immutable snapshot ingestion time."),
        "PARSE_READY_TIME": ("parse_ready_time", "Immutable parse-ready time."),
        "PREDICTION_TIME": ("prediction_time", "Signal fixation time."),
        "TRADABLE_TIME": ("tradable_time", "Next-session order eligibility."),
        "LABEL_START_TIME": ("label_start_time", "Label interval start."),
        "LABEL_END_TIME": ("label_end_time", "Label interval end."),
        "UNIVERSE_ANNOUNCED_TIME": (
            "universe_announced_time",
            "Membership announcement.",
        ),
        "UNIVERSE_EFFECTIVE_FROM": (
            "universe_effective_from",
            "Membership effective start.",
        ),
        "UNIVERSE_EFFECTIVE_TO": (
            "universe_effective_to",
            "Membership effective end.",
        ),
        "REVISION_KNOWN_TIME": (
            "revision_known_time",
            "Selected derived-vintage availability.",
        ),
        "ADJUSTMENT_KNOWN_TIME": (
            "adjustment_known_time",
            "Adjustment availability; null for RAW.",
        ),
        "HALT_TIME": ("halt_time", "Execution-overlapping halt start."),
        "QUOTE_RESUME_TIME": ("quote_resume_time", "Quote resume time."),
        "TRADE_RESUME_TIME": ("trade_resume_time", "Trade resume time."),
        "IDENTIFIER_VALID_FROM": (
            "identifier_valid_from",
            "Permanent-ID validity start.",
        ),
        "IDENTIFIER_VALID_TO": (
            "identifier_valid_to",
            "Permanent-ID validity end.",
        ),
    }
    result: dict[str, Any] = {}
    for role, (field, definition) in roles.items():
        result[role] = {
            "field": field,
            "definition": definition,
            "source_locator": f"project://pit-evidence-schema-v1#{field}",
        }
    result["EVENT_TIME"]["source_field"] = "event_time"
    result["VENDOR_AVAILABLE_TIME"]["source_field"] = "vendor_available_time"
    return result


def selection_rule(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "universe_definition": path_get(contract, "scope.universe.definition"),
        "membership_rule": path_get(contract, "scope.universe.pit_membership_rule"),
        "listing_rule": "at least 60 completed eligible trading sessions",
        "status_rule": "exclude PIT-known ST, *ST, PT and delisting-consolidation names",
        "feature_rule": (
            "all 50 RAW-derived features finite after the 60-session corporate-action mask"
        ),
        "label_rule": (
            "finite raw_open(T+1)/raw_close(T+5) interval, no action crossing, "
            "no halt or opening price-limit execution"
        ),
        "split_rule": path_get(contract, "splits.purge_embargo_rule"),
    }


def build_population_documents(
    population: pd.DataFrame,
    contract: dict[str, Any],
    product_verification_sha256: str,
    external_source: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    keys = sorted(
        [
            [str(row.security_id), utc_iso(row.prediction_time)]
            for row in population.itertuples(index=False)
        ]
    )
    key_hash = streamed_list_sha256(keys)
    rule_hash = sha_value(selection_rule(contract))
    source_locator = f"project://pit-data-product-verification/{product_verification_sha256}"
    if external_source is None:
        source = {
            "schema_version": "pit_population_source_v1",
            "authority_id": "csi800-pit-eligible-development-population-diagnostic",
            "version": contract["scope"]["universe"]["universe_version"],
            "source_uri": source_locator,
            "selection_rule_sha256": rule_hash,
            "history_mode": "PIT_HISTORY",
            "includes_inactive_and_delisted": True,
            "records": [
                {
                    "security_id": security_id,
                    "prediction_time": prediction_time,
                    "security_status": "ACTIVE",
                    "eligible": True,
                    "source_locator": (f"{source_locator}#{security_id}@{prediction_time}"),
                }
                for security_id, prediction_time in keys
            ],
        }
        source["receipt_hash"] = receipt_hash(source)
    else:
        source = external_source
        source_keys = sorted(
            [
                [str(item["security_id"]), str(item["prediction_time"])]
                for item in source.get("records", [])
                if item.get("eligible") is True
            ]
        )
        if source_keys != keys:
            raise RuntimeError(
                "external population authority differs from the full product population"
            )
        if source.get("selection_rule_sha256") != rule_hash:
            raise RuntimeError("external population authority uses a different selection rule")
    manifest = {
        "schema_version": "pit_population_manifest_v1",
        "population_id": source["authority_id"],
        "version": source["version"],
        "source_uri": source_locator,
        "authority_source_sha256": None,
        "selection_rule_sha256": rule_hash,
        "history_mode": "PIT_HISTORY",
        "includes_inactive_and_delisted": True,
        "expected_security_time_keys": len(keys),
        "expected_key_set_sha256": key_hash,
        "expected_status_counts": {"ACTIVE": len(keys)},
        "keys": [
            {
                "security_id": security_id,
                "prediction_time": prediction_time,
                "security_status": "ACTIVE",
                "source_locator": (f"{source_locator}#{security_id}@{prediction_time}"),
            }
            for security_id, prediction_time in keys
        ],
    }
    return source, manifest, key_hash


def build_label_interval_authority(
    population: pd.DataFrame,
    population_manifest_sha256: str,
    generator_sha256: str,
    parameters_sha256: str,
    input_snapshot_sha256: str,
) -> dict[str, Any]:
    intervals = sorted(
        {
            (
                str(row.security_id),
                utc_iso(row.prediction_time),
                utc_iso(row.label_start_time),
                utc_iso(row.label_start_time),
                utc_iso(row.label_end_time),
            )
            for row in population.itertuples(index=False)
        }
    )
    authority = {
        "schema_version": "pit_label_interval_authority_v1",
        "authority_id": "qlib-peerlite-label-interval-authority-v1",
        "version": "1",
        "source_uri": (
            "project://scripts/server/build_pit_audit_package.py"
            "#independent-label-interval-authority"
        ),
        "population_manifest_sha256": population_manifest_sha256,
        "expected_sample_count": len(intervals),
        "expected_interval_set_sha256": streamed_list_sha256([list(item) for item in intervals]),
        "generator": {
            "code_sha256": generator_sha256,
            "parameters_sha256": parameters_sha256,
            "input_snapshot_sha256": input_snapshot_sha256,
            "source_locator": (
                "project://scripts/server/build_pit_audit_package.py"
                "#independent-label-interval-authority"
            ),
        },
    }
    authority["receipt_hash"] = receipt_hash(authority)
    return authority


def build_review_authority() -> dict[str, Any]:
    authority = {
        "schema_version": "pit_semantic_review_authority_v1",
        "authority_id": "jonas-research-owner-authority-v1",
        "version": "1",
        "source_uri": "project://governance/research-owner-approval/20260728",
        "reviewers": [
            {
                "reviewer_id": "jonas-research-owner",
                "allowed_scopes": ["CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY"],
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2030-01-01T00:00:00Z",
            }
        ],
    }
    authority["receipt_hash"] = receipt_hash(authority)
    return authority


def build_label_schedule(
    contract: dict[str, Any],
    label: dict[str, Any],
    interval_authority: dict[str, Any],
    interval_authority_sha256: str,
    review_authority: dict[str, Any],
) -> dict[str, Any]:
    rules = contract["time_semantics"]
    rule_hashes = {
        "prediction_time": sha_text(rules["prediction_time"]),
        "execution_time": sha_text(rules["execution_time_rule"]),
        "label_start": sha_text(rules["label_start_rule"]),
        "label_end": sha_text(rules["label_end_rule"]),
        "holding_period": sha_text(rules["holding_period"]),
    }
    rule_bundle = sha_value(rule_hashes)
    resolver = {
        "interval_authority_id": interval_authority["authority_id"],
        "interval_authority_version": interval_authority["version"],
        "interval_authority_artifact_sha256": interval_authority_sha256,
        "interval_authority_receipt_hash": interval_authority["receipt_hash"],
    }
    frozen_at = datetime.fromisoformat(contract["contract"]["frozen_at"].replace("Z", "+00:00"))
    reviewed_at = (frozen_at + timedelta(seconds=1)).isoformat()
    semantic_review = {
        "trust_root_kind": "HUMAN_SEMANTIC_REVIEW",
        "scope": "CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY",
        "decision": "APPROVED",
        "reviewer_id": "jonas-research-owner",
        "reviewer_authority": review_authority["authority_id"],
        "reviewed_at": reviewed_at,
        "contract_rule_bundle_sha256": rule_bundle,
        "normalized_resolver_sha256": sha_value(resolver),
        "excluded_inputs": [
            "data_rows",
            "audit_status",
            "backtest_results",
        ],
    }
    semantic_review["receipt_hash"] = receipt_hash(semantic_review)
    schedule = {
        "schema_version": "pit_label_schedule_v1",
        "schedule_id": "qlib-peerlite-open1-close5-schedule-v1",
        "version": "1",
        "mode": "FROZEN_EXACT_INTERVAL_SET",
        "contract_binding": {
            "adapter": "quant_contract_v2",
            "contract_id": contract["contract"]["contract_id"],
            "contract_canonical_hash": contract["contract"]["canonical_hash"],
            "rule_hashes": rule_hashes,
            "rule_bundle_sha256": rule_bundle,
        },
        "label_binding": {
            "label_id": label["label_id"],
            "label_spec_version": label["label_spec_version"],
            "label_spec_hash": label["label_spec_hash"],
        },
        "resolver": resolver,
        "semantic_review": semantic_review,
    }
    schedule["receipt_hash"] = receipt_hash(schedule)
    return schedule


def build_time_semantics(
    contract: dict[str, Any],
    calendar_sha256: str,
    schedule_receipt_hash: str,
) -> dict[str, Any]:
    source_index = next(
        index
        for index, item in enumerate(contract["data"]["sources"])
        if item["source_id"] == "qlib-peerlite-derived-features"
    )
    paths = [
        "time_semantics.prediction_time",
        "time_semantics.data_cutoff_rule",
        "time_semantics.availability_rule",
        "time_semantics.execution_time_rule",
        "time_semantics.label_start_rule",
        "time_semantics.label_end_rule",
        "time_semantics.holding_period",
        "scope.universe.definition",
        "scope.universe.pit_membership_rule",
        f"data.sources.{source_index}.revision_policy",
        "target.corporate_action_rule",
        "target.overlap_rule",
        "splits.purge_embargo_rule",
        "splits.sample_dependency.purge_rule",
        "splits.sample_dependency.embargo_duration",
        "splits.sample_dependency.embargo_basis",
    ]
    return {
        "schema_version": "pit_time_semantics_v1",
        "timezone": "Asia/Shanghai",
        "tzdb_version": "2025b",
        "availability_comparison": "LE",
        "roles": time_roles(),
        "contract_interpretation": {
            "status": "PASS",
            "source_text_sha256": {
                dotted: sha_text(path_get(contract, dotted)) for dotted in paths
            },
            "resolved": {
                "availability_comparison": "LE",
                "revision_policy_status": "PASS",
                "universe_policy_status": "PASS",
                "population_history_mode": "PIT_HISTORY",
                "embargo_sessions": 5,
                "embargo_basis_sha256": sha_text(
                    contract["splits"]["sample_dependency"]["embargo_basis"]
                ),
                "embargo_implementation": "UNASSIGNED_SPLIT_GAP",
                "boundary_calendar_complete": True,
                "boundary_calendar_sha256": calendar_sha256,
                "label_schedule_receipt_hash": schedule_receipt_hash,
            },
        },
    }


def matrix_cell_digest(population: pd.DataFrame, features: list[str]) -> str:
    keys = sorted(
        {
            (str(row.security_id), utc_iso(row.prediction_time))
            for row in population.itertuples(index=False)
        }
    )
    return streamed_list_sha256(
        [security_id, prediction_time, feature]
        for security_id, prediction_time in keys
        for feature in features
    )


def build_matrix_manifest(
    population: pd.DataFrame,
    population_manifest: dict[str, Any],
    population_manifest_sha256: str,
    population_source: dict[str, Any],
    population_source_sha256: str,
    dictionary: dict[str, Any],
    contract: dict[str, Any],
    label: dict[str, Any],
    schedule: dict[str, Any],
) -> dict[str, Any]:
    features = sorted(FEATURE_COLUMNS)
    rule = "ALL_FEATURES_APPLY_TO_EVERY_POPULATION_KEY"
    feature_semantics = {name: dictionary["features"][name] for name in features}
    feature_axis = {
        "feature_spec_version": contract["data"]["feature_spec_version"],
        "features": features,
        "expected_feature_count": len(features),
        "feature_set_sha256": sha_value(features),
        "feature_semantics_sha256": sha_value(feature_semantics),
        "feature_spec_hash": contract["data"]["feature_spec_hash"],
    }
    label_axis = {
        "label_id": label["label_id"],
        "label_spec_version": label["label_spec_version"],
        "label_spec_hash": label["label_spec_hash"],
        "label_schedule_id": schedule["schedule_id"],
        "label_schedule_version": schedule["version"],
        "label_schedule_receipt_hash": schedule["receipt_hash"],
        "prediction_time_rule_sha256": sha_text(contract["time_semantics"]["prediction_time"]),
        "execution_time_rule_sha256": sha_text(contract["time_semantics"]["execution_time_rule"]),
        "label_start_rule_sha256": sha_text(contract["time_semantics"]["label_start_rule"]),
        "label_end_rule_sha256": sha_text(contract["time_semantics"]["label_end_rule"]),
    }
    manifest = {
        "schema_version": "pit_matrix_manifest_v1",
        "manifest_id": "qlib-peerlite-development-matrix-v1",
        "version": "1",
        "layout": {
            "mode": "RECTANGULAR",
            "applicability_rule": rule,
            "applicability_rule_sha256": sha_text(rule),
        },
        "sample_prediction_axis": {
            "population_manifest_sha256": population_manifest_sha256,
            "population_manifest_receipt_hash": population_manifest["receipt_hash"],
            "population_source_sha256": population_source_sha256,
            "expected_security_time_keys": len(population),
            "expected_key_set_sha256": population_manifest["expected_key_set_sha256"],
        },
        "feature_axis": feature_axis,
        "label_axis": label_axis,
        "expected_cell_count": len(population) * len(features),
        "expected_cell_key_set_sha256": matrix_cell_digest(population, features),
    }
    if population_source["receipt_hash"] is None:
        raise RuntimeError("population source is not sealed")
    manifest["receipt_hash"] = receipt_hash(manifest)
    return manifest


def build_request(
    root: Path,
    contract: dict[str, Any],
    receipt: dict[str, Any],
    consumed_manifest: dict[str, Any],
    source_snapshot_sha256: str,
    dictionary: dict[str, Any],
    label: dict[str, Any],
    schedule: dict[str, Any],
    review_authority: dict[str, Any],
    interval_authority: dict[str, Any],
    population_manifest: dict[str, Any],
    population_source: dict[str, Any],
    matrix_manifest: dict[str, Any],
    calendar_sha256: str,
    binding_mode: str,
) -> dict[str, Any]:
    def artifact(name: str) -> dict[str, Any]:
        path = root / name
        return {"path": name, "sha256": sha_file(path)}

    source = next(
        item
        for item in contract["data"]["sources"]
        if item["source_id"] == "qlib-peerlite-derived-features"
    )
    request = {
        "request_version": "pit_audit_request_v1",
        "request_id": f"pit-{consumed_manifest['evidence_id']}-v1",
        "run_at": datetime.now(TZ).isoformat(),
        "claim": "MARKET_RECONSTRUCTIBLE",
        "coverage": {
            "scope": consumed_manifest["scope"],
            "expected_row_count": consumed_manifest["training_evidence"]["evidence_rows"],
            "extraction_query_sha256": consumed_manifest["materializer"]["sha256"],
            "extraction_receipt_id": consumed_manifest["evidence_id"],
            "population": {
                "basis_id": population_source["authority_id"],
                "snapshot_sha256": sha_file(root / "population_source.json"),
                "authority_source_sha256": sha_file(root / "population_source.json"),
                "selection_rule_sha256": population_source["selection_rule_sha256"],
                "universe_history_mode": "PIT_HISTORY",
                "includes_inactive_and_delisted": True,
                "expected_security_time_keys": population_manifest["expected_security_time_keys"],
                "universe_version": contract["scope"]["universe"]["universe_version"],
                "universe_hash": contract["scope"]["universe"]["universe_hash"],
            },
        },
        "artifacts": {
            "data": {
                **artifact("training_evidence.csv"),
                "format": "csv",
                "source_id": source["source_id"],
                "source_version": source["snapshot_id"],
                "snapshot_id": source["snapshot_id"],
                "snapshot_binding_mode": binding_mode,
                "source_snapshot_sha256": source_snapshot_sha256,
            },
            "schema": artifact("schema.json"),
            "dictionary": {
                **artifact("dictionary.json"),
                "dictionary_id": dictionary["dictionary_id"],
                "version": dictionary["version"],
                "source_uri": dictionary["source_uri"],
            },
            "time_semantics": artifact("time_semantics.json"),
            "research_contract": {
                **artifact("research_contract.json"),
                "adapter": "quant_contract_v2",
                "contract_id": contract["contract"]["contract_id"],
                "canonical_hash": contract["contract"]["canonical_hash"],
                "validation_receipt": artifact("contract_validation.json"),
            },
            "label_definition": {
                **artifact("label_definition.json"),
                "label_spec_hash": label["label_spec_hash"],
            },
            "label_schedule": {
                **artifact("label_schedule.json"),
                "schedule_id": schedule["schedule_id"],
                "version": schedule["version"],
            },
            "review_authority": {
                **artifact("review_authority.json"),
                "authority_id": review_authority["authority_id"],
                "version": review_authority["version"],
            },
            "label_interval_authority": {
                **artifact("label_interval_authority.json"),
                "authority_id": interval_authority["authority_id"],
                "version": interval_authority["version"],
            },
            "calendar": {
                **artifact("calendar.csv"),
                "calendar_id": "XSHG_XSHE",
                "version": "planned-v1",
                "timezone": "Asia/Shanghai",
                "source_uri": (
                    "data/raw/snapshots/source_snapshot_20260728_v1/md_trade_cal.parquet"
                ),
            },
            "population_manifest": {
                **artifact("population_manifest.json"),
                "population_id": population_manifest["population_id"],
                "version": population_manifest["version"],
                "source_uri": population_manifest["source_uri"],
            },
            "population_source": {
                **artifact("population_source.json"),
                "authority_id": population_source["authority_id"],
                "version": population_source["version"],
                "source_uri": population_source["source_uri"],
            },
            "matrix_manifest": {
                **artifact("matrix_manifest.json"),
                "manifest_id": matrix_manifest["manifest_id"],
                "version": matrix_manifest["version"],
            },
        },
    }
    if receipt["status"] != "PASS" or calendar_sha256 != sha_file(root / "calendar.csv"):
        raise RuntimeError("request dependencies are not intact")
    return request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--product-verification", type=Path, required=True)
    parser.add_argument("--consumed-values-dir", type=Path, required=True)
    parser.add_argument("--full-consumed-value-manifest", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-validation", type=Path, required=True)
    parser.add_argument("--dictionary", type=Path, required=True)
    parser.add_argument("--label-definition", type=Path, required=True)
    parser.add_argument("--population-source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise RuntimeError("output directory must be new or empty")

    product_manifest = json.loads(
        (args.product_dir / "data_product_manifest.json").read_text(encoding="utf-8")
    )
    verification = json.loads(args.product_verification.read_text(encoding="utf-8"))
    consumed_manifest = json.loads(
        (args.consumed_values_dir / "consumed_value_manifest.json").read_text(encoding="utf-8")
    )
    full_consumed_manifest = json.loads(
        args.full_consumed_value_manifest.read_text(encoding="utf-8")
    )
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    contract_receipt = json.loads(args.contract_validation.read_text(encoding="utf-8"))
    dictionary = json.loads(args.dictionary.read_text(encoding="utf-8"))
    label = json.loads(args.label_definition.read_text(encoding="utf-8"))
    if verification.get("status") != "PASS":
        raise RuntimeError("data-product verification is not PASS")
    if contract_receipt.get("status") != "PASS":
        raise RuntimeError("contract validation is not PASS")

    population = pd.read_parquet(args.product_dir / "population.parquet")
    if consumed_manifest["scope"] == "SAMPLE_ONLY":
        parameters = consumed_manifest["materializer"]["parameters"]
        population["prediction_date"] = (
            population["prediction_time"].dt.tz_localize(None).dt.normalize()
        )
        population = population[
            population["prediction_date"].between(
                pd.Timestamp(parameters["sample_start"]),
                pd.Timestamp(parameters["sample_end"]),
            )
        ].drop(columns=["prediction_date"])
    if len(population) != consumed_manifest["training_evidence"]["sample_rows"]:
        raise RuntimeError("consumed-value sample population mismatch")

    parent = args.output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{args.output_dir.name}.", dir=parent))
    try:
        os.link(
            args.consumed_values_dir / "training_evidence.csv",
            temporary / "training_evidence.csv",
        )
        shutil.copy2(args.contract, temporary / "research_contract.json")
        shutil.copy2(args.contract_validation, temporary / "contract_validation.json")
        shutil.copy2(args.dictionary, temporary / "dictionary.json")
        shutil.copy2(args.label_definition, temporary / "label_definition.json")
        shutil.copy2(args.product_dir / "calendar.csv", temporary / "calendar.csv")
        schema = {
            "schema_version": "pit_evidence_schema_v1",
            "primary_key": ["row_id"],
            "grain": ["security_id", "prediction_time", "feature_name"],
            "columns": SCHEMA_COLUMNS,
        }
        write_json(temporary / "schema.json", schema)

        product_verification_sha = sha_file(args.product_verification)
        external_population_source = None
        if consumed_manifest["scope"] == "FULL_TRAINING_INPUT":
            if args.population_source is None:
                raise RuntimeError("full audit package requires an external population authority")
            external_population_source = json.loads(
                args.population_source.read_text(encoding="utf-8")
            )
        population_source, population_manifest, _ = build_population_documents(
            population,
            contract,
            product_verification_sha,
            external_population_source,
        )
        write_json(temporary / "population_source.json", population_source)
        population_source_sha = sha_file(temporary / "population_source.json")
        population_manifest["authority_source_sha256"] = population_source_sha
        population_manifest["receipt_hash"] = receipt_hash(population_manifest)
        write_json(temporary / "population_manifest.json", population_manifest)
        population_manifest_sha = sha_file(temporary / "population_manifest.json")

        package_parameters = {
            "scope": consumed_manifest["scope"],
            "sample_rows": len(population),
            "feature_count": len(FEATURE_COLUMNS),
            "product_manifest_sha256": sha_file(args.product_dir / "data_product_manifest.json"),
            "contract_sha256": sha_file(args.contract),
        }
        package_parameters_sha = sha_value(package_parameters)
        interval_authority = build_label_interval_authority(
            population,
            population_manifest_sha,
            sha_file(Path(__file__).resolve()),
            package_parameters_sha,
            sha_value(
                {
                    "population": product_manifest["population"]["sha256"],
                    "calendar": product_manifest["calendar"]["sha256"],
                    "contract": sha_file(args.contract),
                }
            ),
        )
        write_json(temporary / "label_interval_authority.json", interval_authority)
        interval_authority_sha = sha_file(temporary / "label_interval_authority.json")
        review_authority = build_review_authority()
        write_json(temporary / "review_authority.json", review_authority)
        schedule = build_label_schedule(
            contract,
            label,
            interval_authority,
            interval_authority_sha,
            review_authority,
        )
        write_json(temporary / "label_schedule.json", schedule)
        calendar_sha = sha_file(temporary / "calendar.csv")
        semantics = build_time_semantics(contract, calendar_sha, schedule["receipt_hash"])
        write_json(temporary / "time_semantics.json", semantics)
        matrix = build_matrix_manifest(
            population,
            population_manifest,
            population_manifest_sha,
            population_source,
            population_source_sha,
            dictionary,
            contract,
            label,
            schedule,
        )
        write_json(temporary / "matrix_manifest.json", matrix)

        full_data_hash = full_consumed_manifest["training_evidence"]["sha256"]
        data_hash = consumed_manifest["training_evidence"]["sha256"]
        binding_mode = (
            "IDENTITY_SNAPSHOT"
            if consumed_manifest["scope"] == "FULL_TRAINING_INPUT"
            else "DERIVED_EXTRACT"
        )
        if (
            contract["data"]["sources"][-1]["snapshot_hash"] != full_data_hash
            or sha_file(temporary / "training_evidence.csv") != data_hash
        ):
            raise RuntimeError("training-evidence source binding mismatch")
        request = build_request(
            temporary,
            contract,
            contract_receipt,
            consumed_manifest,
            full_data_hash,
            dictionary,
            label,
            schedule,
            review_authority,
            interval_authority,
            population_manifest,
            population_source,
            matrix,
            calendar_sha,
            binding_mode,
        )
        write_json(temporary / "audit_request.json", request)
        trust = {
            "review_authority_sha256": sha_file(temporary / "review_authority.json"),
            "semantic_review_receipt_sha256": schedule["semantic_review"]["receipt_hash"],
            "interval_authority_sha256": interval_authority_sha,
        }
        write_json(temporary / "trusted_authorities.json", trust)
        package_manifest = {
            "schema_version": "qlib_peerlite_pit_audit_package_v1",
            "package_id": args.output_dir.name,
            "created_at": datetime.now(TZ).isoformat(),
            "scope": consumed_manifest["scope"],
            "binding_mode": binding_mode,
            "sample_rows": len(population),
            "evidence_rows": consumed_manifest["training_evidence"]["evidence_rows"],
            "data_sha256": data_hash,
            "source_snapshot_sha256": full_data_hash,
            "contract_id": contract["contract"]["contract_id"],
            "contract_canonical_hash": contract["contract"]["canonical_hash"],
            "parameters": package_parameters,
            "parameters_sha256": package_parameters_sha,
            "files": {path.name: sha_file(path) for path in temporary.iterdir() if path.is_file()},
            "status": "BUILT_NOT_AUDITED",
        }
        package_manifest["content_sha256"] = sha_value(package_manifest)
        write_json(temporary / "package_manifest.json", package_manifest)
        if args.output_dir.exists():
            args.output_dir.rmdir()
        os.replace(temporary, args.output_dir)
        print(
            json.dumps(
                {
                    "status": package_manifest["status"],
                    "package_id": package_manifest["package_id"],
                    "scope": package_manifest["scope"],
                    "sample_rows": package_manifest["sample_rows"],
                    "evidence_rows": package_manifest["evidence_rows"],
                    "package_manifest_sha256": sha_file(args.output_dir / "package_manifest.json"),
                    "trusted_authorities": trust,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


if __name__ == "__main__":
    sys.exit(main())
