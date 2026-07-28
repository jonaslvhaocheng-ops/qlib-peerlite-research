#!/usr/bin/env python3
"""Prepare the bound QRC change payload required by the derived PIT product."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from qlib_peerlite.data.features import FEATURE_COLUMNS

FIELD_ROLES = {
    "row_id": "ROW_ID",
    "security_id": "PERMANENT_SECURITY_ID",
    "feature_name": "FEATURE_NAME",
    "feature_value": "FEATURE_VALUE",
    "prediction_time": "PREDICTION_TIME",
    "event_time": "EVENT_TIME",
    "published_time": "PUBLICATION_TIME",
    "vendor_available_time": "VENDOR_AVAILABLE_TIME",
    "ingested_time": "INGESTED_TIME",
    "parse_ready_time": "PARSE_READY_TIME",
    "ingestion_batch_id": "INGESTION_BATCH_ID",
    "ingested_object_sha256": "INGESTED_OBJECT_SHA256",
    "tradable_time": "TRADABLE_TIME",
    "label_start_time": "LABEL_START_TIME",
    "label_end_time": "LABEL_END_TIME",
    "split": "SPLIT",
    "universe_member": "UNIVERSE_MEMBER",
    "universe_announced_time": "UNIVERSE_ANNOUNCED_TIME",
    "universe_effective_from": "UNIVERSE_EFFECTIVE_FROM",
    "universe_effective_to": "UNIVERSE_EFFECTIVE_TO",
    "security_status": "SECURITY_STATUS",
    "revision_id": "REVISION_ID",
    "revision_known_time": "REVISION_KNOWN_TIME",
    "adjustment_mode": "ADJUSTMENT_MODE",
    "adjustment_known_time": "ADJUSTMENT_KNOWN_TIME",
    "adjustment_invariance_pass": "ADJUSTMENT_INVARIANCE_TEST",
    "halt_time": "HALT_TIME",
    "quote_resume_time": "QUOTE_RESUME_TIME",
    "trade_resume_time": "TRADE_RESUME_TIME",
    "calendar_session_id": "CALENDAR_SESSION_ID",
    "identifier_valid_from": "IDENTIFIER_VALID_FROM",
    "identifier_valid_to": "IDENTIFIER_VALID_TO",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def sha_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_text(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
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


def field_dictionary(semantics: dict[str, Any], semantics_sha256: str) -> dict[str, Any]:
    definitions = {
        "row_id": "Immutable row locator in the consumed-value snapshot.",
        "security_id": "Permanent DataYes SECURITY_ID, never ticker.",
        "feature_name": "Exact frozen derived-feature identifier.",
        "feature_value": "Finite numeric value consumed by the model matrix.",
        "prediction_time": "Signal fixation at 16:00 Asia/Shanghai after T close.",
        "event_time": "T session close represented by the derived feature.",
        "published_time": "Public daily-quote dissemination time.",
        "vendor_available_time": "First declared DataYes daily-quote availability.",
        "ingested_time": "Immutable source-snapshot creation time.",
        "parse_ready_time": "Time the immutable source snapshot was parse-ready.",
        "ingestion_batch_id": "Historical system batch; nullable for market claim.",
        "ingested_object_sha256": "Historical object hash; nullable for market claim.",
        "tradable_time": "T+1 eligible session open intended for execution.",
        "label_start_time": "Raw-price label interval start at T+1 open.",
        "label_end_time": "Raw-price label interval end at T+5 close.",
        "split": "Frozen TRAIN or MODEL_SELECTION assignment.",
        "universe_member": "Eligibility under the frozen CSI800 PIT rule.",
        "universe_announced_time": "Public inclusion announcement timestamp.",
        "universe_effective_from": "Inclusive membership effective start.",
        "universe_effective_to": "Exclusive membership effective end.",
        "security_status": "PIT lifecycle state at prediction.",
        "revision_id": "Immutable derived-feature snapshot revision identifier.",
        "revision_known_time": "Time the selected derived revision became available.",
        "adjustment_mode": "RAW/PIT_ADJUSTED/FULL_HISTORY_ADJUSTED basis.",
        "adjustment_known_time": "Applied adjustment availability; null for RAW.",
        "adjustment_invariance_pass": "Adjustment invariance result; null for RAW.",
        "halt_time": "Execution-overlapping halt start; null when absent.",
        "quote_resume_time": "Quote resume time; null when absent.",
        "trade_resume_time": "Trade resume time; null when absent.",
        "calendar_session_id": "Versioned XSHG/XSHE eligible-session key.",
        "identifier_valid_from": "Inclusive permanent-ID validity start.",
        "identifier_valid_to": "Exclusive permanent-ID validity end.",
    }
    fields: dict[str, Any] = {}
    for name, role in FIELD_ROLES.items():
        entry: dict[str, Any] = {
            "semantic_role": role,
            "definition": definitions[name],
            "source_locator": f"project://pit-evidence-schema-v1#{name}",
        }
        if name == "security_id":
            entry["identity_stability"] = "permanent"
        if name in {"universe_effective_to", "identifier_valid_to"}:
            entry["null_semantics"] = "OPEN_ENDED_POSITIVE_INFINITY"
        fields[name] = entry

    semantic_features = {item["feature_name"]: item for item in semantics["features"]}
    features: dict[str, Any] = {}
    for name in sorted(FEATURE_COLUMNS):
        source = semantic_features[name]
        features[name] = {
            "definition": source["formula"],
            "source_locator": (
                f"project://qlib-peerlite-derived-feature-semantics-v1#feature={name}"
            ),
            "use": source["use"],
            "event_time_policy": source["event_time_policy"],
            "unit": source["unit"],
            "basis": source["basis"],
            "grain": source["grain"],
            "null_semantics": source["null_policy"],
            "adjustment_policy": {
                **source["adjustment_policy"],
                "source_locator": (
                    "project://qlib-peerlite-derived-feature-semantics-v1"
                    f"#feature={name}/adjustment"
                ),
            },
            "domain_policy": {
                "kind": "UNBOUNDED",
                "source_locator": (
                    f"project://qlib-peerlite-derived-feature-semantics-v1#feature={name}/domain"
                ),
            },
            "adjustment_invariance": {
                "claimed": False,
                "evidence_locator": None,
            },
        }
    return {
        "schema_version": "pit_field_dictionary_v1",
        "dictionary_id": "qlib-peerlite-derived-feature-dictionary-v1",
        "version": "qlib-peerlite-derived-feature-semantics-v1",
        "source_uri": "project://qlib-peerlite-derived-feature-semantics-v1",
        "semantic_source_document_sha256": semantics_sha256,
        "fields": fields,
        "features": features,
    }


def label_definition(contract: dict[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    splits = contract["splits"]
    dependency = splits["sample_dependency"]
    label = {
        "schema_version": "pit_label_definition_v1",
        "label_id": target["label_id"],
        "label_spec_version": target["label_spec_version"],
        "definition": {
            "target": "raw open-to-close forward return",
            "formula": target["formula"],
            "start_field": "label_start_time",
            "end_field": "label_end_time",
            "holding_period": contract["time_semantics"]["holding_period"],
            "price_basis": "RAW",
        },
        "interval_closure": "BOTH",
        "overlap_policy": "NO_CROSS_SPLIT_OVERLAP",
        "purge_rule": dependency["purge_rule"],
        "purge_embargo_rule": splits["purge_embargo_rule"],
        "embargo_duration": dependency["embargo_duration"],
        "embargo_basis": dependency["embargo_basis"],
        "contract_bindings": {
            "formula_sha256": sha_text(target["formula"]),
            "neutralization_rule_sha256": sha_text(target["neutralization_rule"]),
            "corporate_action_rule_sha256": sha_text(target["corporate_action_rule"]),
            "overlap_rule_sha256": sha_text(target["overlap_rule"]),
            "purge_rule_sha256": sha_text(dependency["purge_rule"]),
            "purge_embargo_rule_sha256": sha_text(splits["purge_embargo_rule"]),
            "embargo_duration_sha256": sha_text(dependency["embargo_duration"]),
            "embargo_basis_sha256": sha_text(dependency["embargo_basis"]),
        },
        "source_locator": "project://frozen-research-contract#target",
    }
    label["label_spec_hash"] = sha_value(label)
    return label


def matrix_feature_hash(dictionary: dict[str, Any], version: str) -> str:
    features = sorted(FEATURE_COLUMNS)
    rule = "ALL_FEATURES_APPLY_TO_EVERY_POPULATION_KEY"
    feature_semantics = {name: dictionary["features"][name] for name in features}
    payload = {
        "schema_version": "pit_matrix_feature_spec_v1",
        "feature_spec_version": version,
        "layout_mode": "RECTANGULAR",
        "features": features,
        "feature_semantics_sha256": sha_value(feature_semantics),
        "applicability_rule_sha256": sha_text(rule),
    }
    return sha_value(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-contract", type=Path, required=True)
    parser.add_argument("--consumed-value-manifest", type=Path, required=True)
    parser.add_argument("--derived-semantics", type=Path, required=True)
    parser.add_argument("--population-source", type=Path)
    parser.add_argument("--train-end")
    parser.add_argument("--selection-start")
    parser.add_argument("--selection-end")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise RuntimeError("output directory already exists")
    args.output_dir.mkdir(parents=True)

    contract = json.loads(args.parent_contract.read_text(encoding="utf-8"))
    consumed = json.loads(args.consumed_value_manifest.read_text(encoding="utf-8"))
    semantics = json.loads(args.derived_semantics.read_text(encoding="utf-8"))
    if consumed["scope"] != "FULL_TRAINING_INPUT":
        raise RuntimeError("production contract change requires the full consumed-value snapshot")
    semantics_sha256 = sha_file(args.derived_semantics)
    if consumed["feature_semantics"]["sha256"] != semantics_sha256:
        raise RuntimeError("derived semantics hash mismatch")
    evidence_sha256 = consumed["training_evidence"]["sha256"]
    boundary_values = (
        args.train_end,
        args.selection_start,
        args.selection_end,
    )
    if any(value is not None for value in boundary_values) and not all(
        value is not None for value in boundary_values
    ):
        raise RuntimeError("train-end, selection-start and selection-end must be supplied together")

    dictionary = field_dictionary(semantics, semantics_sha256)
    label = label_definition(contract)
    feature_hash = matrix_feature_hash(dictionary, contract["data"]["feature_spec_version"])
    derived_source = {
        "source_id": "qlib-peerlite-derived-features",
        "vendor": "Qlib PeerLite deterministic project pipeline",
        "snapshot_id": (f"{consumed['evidence_id']}:training_evidence"),
        "snapshot_hash": evidence_sha256,
        "event_timestamp_field": "event_time",
        "availability_timestamp_field": "vendor_available_time",
        "availability_evidence_uri": (
            f"data/manifests/{consumed['evidence_id']}/derived_feature_semantics.json"
        ),
        "availability_evidence_version": dictionary["version"],
        "availability_evidence_hash": semantics_sha256,
        "revision_policy": (
            "派生特征只由冻结RAW源、因果窗口和已声明掩码确定；"
            "revision_known_time不得晚于prediction_time。任何源快照、公式或代码变化"
            "必须生成新的不可变派生快照，禁止覆盖本快照。"
        ),
        "allowed_fields": sorted(FEATURE_COLUMNS),
    }
    non_derived_sources = [
        source
        for source in contract["data"]["sources"]
        if source["source_id"] != "qlib-peerlite-derived-features"
    ]
    changes: dict[str, Any] = {
        "data": {
            "sources": [*non_derived_sources, derived_source],
            "feature_spec_hash": feature_hash,
        },
        "target": {
            "label_spec_hash": label["label_spec_hash"],
        },
    }
    changed_fields = [
        "data.sources",
        "data.feature_spec_hash",
    ]
    if label["label_spec_hash"] != contract["target"]["label_spec_hash"]:
        changed_fields.append("target.label_spec_hash")
    else:
        changes.pop("target")

    population_source_sha256 = None
    if args.population_source is not None:
        population_source = json.loads(args.population_source.read_text(encoding="utf-8"))
        population_source_sha256 = sha_file(args.population_source)
        changes["scope"] = {
            "universe": {
                "universe_version": population_source["version"],
                "universe_hash": population_source_sha256,
            }
        }
        changed_fields.extend(
            [
                "scope.universe.universe_version",
                "scope.universe.universe_hash",
            ]
        )
    if all(value is not None for value in boundary_values):
        changes["splits"] = {
            "train": {
                "end": args.train_end,
            },
            "selection": {
                "start": args.selection_start,
                "end": args.selection_end,
            },
        }
        changed_fields.extend(
            [
                "splits.train.end",
                "splits.selection.start",
                "splits.selection.end",
            ]
        )
    write_json(args.output_dir / "dictionary.json", dictionary)
    write_json(args.output_dir / "label_definition.json", label)
    write_json(args.output_dir / "proposed_changes.json", changes)
    shutil.copy2(args.derived_semantics, args.output_dir / args.derived_semantics.name)
    receipt = {
        "schema_version": "qlib_peerlite_pit_contract_change_preparation_v1",
        "parent_contract_id": contract["contract"]["contract_id"],
        "parent_canonical_hash": contract["contract"]["canonical_hash"],
        "full_training_evidence_sha256": evidence_sha256,
        "derived_semantics_sha256": semantics_sha256,
        "dictionary_sha256": sha_file(args.output_dir / "dictionary.json"),
        "feature_spec_hash": feature_hash,
        "label_definition_sha256": sha_file(args.output_dir / "label_definition.json"),
        "label_spec_hash": label["label_spec_hash"],
        "population_source_sha256": population_source_sha256,
        "changed_fields": changed_fields,
        "reason": (
            "Bind the corrected materialized evidence, the separately frozen "
            "eligible-population authority and calendar-backed split gaps required "
            "by the fixed PIT auditor. No outcome or final-OOS value informed this "
            "change."
        ),
    }
    write_json(args.output_dir / "preparation_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
