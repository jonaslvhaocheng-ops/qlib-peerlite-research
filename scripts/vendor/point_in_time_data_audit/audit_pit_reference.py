#!/usr/bin/env python3
"""Audit whether every consumed training value was eligible at prediction time."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PASS, NEEDS, FAIL = "PASS", "NEEDS_EVIDENCE", "FAIL"
RANK = {PASS: 0, NEEDS: 1, FAIL: 2}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CLAIMS = {"MARKET_RECONSTRUCTIBLE", "SYSTEM_REPLAYABLE"}
SCOPES = {"FULL_TRAINING_INPUT", "SAMPLE_ONLY"}
SPLITS = {"TRAIN", "MODEL_SELECTION", "OOS"}
CHECKS = {
    "I001": "Input, hash, version, and coverage integrity",
    "I002": "Frozen contract and source/label binding",
    "S001": "Exact schema and field-semantic coverage",
    "T001": "Distinct time roles, timezone, and tzdb evidence",
    "T002": "Feature availability and execution ordering",
    "T003": "Revision and vintage as-of correctness",
    "U001": "Point-in-time universe membership",
    "U002": "Population, survivor, and delisting coverage",
    "C001": "Versioned exchange calendar and session alignment",
    "M001": "Stable security identity and valid-time mapping",
    "A001": "Corporate-action adjustment correctness",
    "H001": "Halt, quote-resume, and trade-resume handling",
    "Q001": "Primary-key, declared-grain, and matrix completeness",
    "Q002": "Required values, types, and finite numerics",
    "Q003": "Declared value-domain and anomaly checks",
    "L001": "Label definition, interval order, and contract hash",
    "L002": "Cross-split label overlap and purge evidence",
}
REQUIRED_ARTIFACTS = {
    "data",
    "schema",
    "dictionary",
    "time_semantics",
    "research_contract",
    "label_definition",
    "label_schedule",
    "review_authority",
    "calendar",
    "population_manifest",
    "population_source",
}
OPTIONAL_ARTIFACTS = {"matrix_manifest", "label_interval_authority"}
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
ROLE_FIELDS = {
    role: field
    for field, role in FIELD_ROLES.items()
    if field.endswith("_time")
    or field
    in {
        "universe_effective_from",
        "universe_effective_to",
        "identifier_valid_from",
        "identifier_valid_to",
    }
}
TIME_FIELDS = set(ROLE_FIELDS.values())
OPTIONAL_TIMES = {
    "adjustment_known_time",
    "halt_time",
    "quote_resume_time",
    "trade_resume_time",
    "universe_effective_to",
    "identifier_valid_to",
}
CALENDAR_FIELDS = {
    "session_id",
    "open_time",
    "close_time",
    "break_start",
    "break_end",
}
NULL_END_POLICIES = {
    "OPEN_ENDED_POSITIVE_INFINITY",
    "UNKNOWN",
    "FORBIDDEN",
}
EMBARGO_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


class InputShapeError(ValueError):
    """Caller-supplied JSON has a known container at the wrong nesting shape."""

    def __init__(self, locator: str, expected: str, actual: Any):
        self.locator = locator
        self.expected = expected
        self.actual_type = type(actual).__name__
        super().__init__(
            f"{locator} must be {expected}, not {self.actual_type}"
        )


def reject_nonfinite_json(token: str) -> None:
    """Reject JSON extensions such as NaN and Infinity."""
    raise ValueError(f"non-standard JSON numeric literal is forbidden: {token}")


def reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Preserve ordinary objects while failing closed on ambiguous duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    return json.loads(
        text,
        parse_constant=reject_nonfinite_json,
        object_pairs_hook=reject_duplicate_json_keys,
    )


def finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


CHECK_FIELD_DEPENDENCIES = {
    "I001": set(),
    "I002": {
        "event_time",
        "vendor_available_time",
        "prediction_time",
        "split",
    },
    "S001": set(FIELD_ROLES),
    "T001": set(TIME_FIELDS),
    "T002": {
        "published_time",
        "vendor_available_time",
        "ingested_time",
        "parse_ready_time",
        "prediction_time",
        "tradable_time",
    },
    "T003": {"revision_id", "revision_known_time", "prediction_time"},
    "U001": {
        "universe_member",
        "universe_announced_time",
        "universe_effective_from",
        "universe_effective_to",
        "prediction_time",
    },
    "U002": {"security_id", "prediction_time", "security_status"},
    "C001": {"calendar_session_id", "tradable_time"},
    "M001": {
        "security_id",
        "identifier_valid_from",
        "identifier_valid_to",
        "prediction_time",
    },
    "A001": {
        "feature_name",
        "adjustment_mode",
        "adjustment_known_time",
        "prediction_time",
    },
    "H001": {
        "halt_time",
        "quote_resume_time",
        "trade_resume_time",
        "tradable_time",
    },
    "Q001": {"row_id", "security_id", "prediction_time", "feature_name"},
    "Q002": set(FIELD_ROLES),
    "Q003": {"feature_name", "feature_value"},
    "L001": {
        "security_id",
        "feature_name",
        "prediction_time",
        "label_start_time",
        "label_end_time",
        "split",
    },
    "L002": {
        "split",
        "prediction_time",
        "label_start_time",
        "label_end_time",
    },
}
FEATURE_POLICY_BY_CHECK = {
    "S001": ("source_locator",),
    "T002": ("source_locator",),
    "A001": ("source_locator", "adjustment_policy.source_locator"),
    "Q003": ("source_locator", "domain_policy.source_locator"),
}
EXTERNAL_LOCATOR_BY_CHECK = {
    "I001": ("dictionary",),
    "I002": ("contract_validation", "label"),
    "U002": ("population",),
    "C001": ("calendar",),
    "L001": ("label",),
    "L002": ("label",),
}
SHAPE_PATHS_BY_CHECK = {
    "I002": (
        ("meta", "research_contract"),
        ("meta", "calendar"),
        ("meta", "data"),
        ("docs", "time_semantics.contract_interpretation"),
        ("docs", "time_semantics.contract_interpretation.source_text_sha256"),
    ),
    "S001": (
        ("docs", "schema.columns"),
        ("docs", "dictionary.fields"),
        ("docs", "dictionary.features"),
        ("meta", "dictionary"),
    ),
    "T001": (("docs", "time_semantics.roles"),),
    "T002": (("docs", "dictionary.features"),),
    "A001": (("docs", "dictionary.features"),),
    "Q003": (("docs", "dictionary.features"),),
    "U002": (
        ("request", "coverage"),
        ("meta", "population_manifest"),
        ("meta", "population_source"),
    ),
    "Q001": (
        ("docs", "matrix_manifest.layout"),
        ("docs", "matrix_manifest.sample_prediction_axis"),
        ("docs", "matrix_manifest.feature_axis"),
        ("docs", "matrix_manifest.label_axis"),
    ),
    "C001": (("meta", "calendar"),),
    "M001": (("docs", "dictionary.fields.security_id"),),
    "Q002": (("docs", "schema.columns"),),
}


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()


def sha_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_text(value: Any) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CsvStructureError(ValueError):
    def __init__(self, locator: str, reason: str):
        super().__init__(reason)
        self.locator = locator


def strict_csv_rows(
    path: Path, artifact: str
) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration as error:
            raise CsvStructureError(
                f"{artifact}.header", "CSV header is missing"
            ) from error
        if not headers or any(not header for header in headers):
            raise CsvStructureError(
                f"{artifact}.header", "CSV header names must be non-empty"
            )
        if len(headers) != len(set(headers)):
            duplicates = sorted(
                {
                    header
                    for header in headers
                    if headers.count(header) > 1
                }
            )
            raise CsvStructureError(
                f"{artifact}.header",
                f"duplicate CSV header names are forbidden: {duplicates}",
            )
        rows: list[dict[str, str]] = []
        for row_number, values in enumerate(reader, start=2):
            if len(values) != len(headers):
                raise CsvStructureError(
                    f"{artifact}#csv_row={row_number}",
                    (
                        f"CSV row width {len(values)} does not match "
                        f"header width {len(headers)}"
                    ),
                )
            rows.append(dict(zip(headers, values)))
    return rows, headers


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def dt(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp is not timezone-aware")
    return parsed


def calendar_date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("must be an ISO-8601 calendar date")
    return date.fromisoformat(value)


def canonical_embargo_sessions(value: Any) -> int | None:
    """Parse only the narrow, auditable QRC duration grammar supported by v1."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"\s*(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+eligible trading day(?:s)?\.?\s*",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    token = match.group(1).lower()
    return int(token) if token.isdigit() else EMBARGO_NUMBER_WORDS[token]


def validator_bundle_sha256(validator: Path, common: Path) -> str:
    digest = hashlib.sha256()
    for path in (validator, common):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValueError("expected true or false")


def path_get(root: dict[str, Any], dotted: str, default: Any = None) -> Any:
    value: Any = root
    for part in dotted.split("."):
        if isinstance(value, list):
            if not part.isdigit() or int(part) >= len(value):
                return default
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    return value


def verdict(failures: list[Any], gaps: list[Any]) -> str:
    return FAIL if failures else NEEDS if gaps else PASS


def before(left: datetime, right: datetime, operator: str) -> bool:
    return left < right if operator == "LT" else left <= right


def locator(row: dict[str, str]) -> str:
    return f"data#row_id={row.get('row_id', '<missing>')}"


def normalized_time_text(value: Any) -> str:
    return dt(value).astimezone(timezone.utc).isoformat()


def normalized_matrix_cell(item: Any) -> tuple[str, str, str]:
    if not isinstance(item, dict):
        raise ValueError("matrix cell must be an object")
    security_id = item.get("security_id")
    feature_name = item.get("feature_name")
    if not isinstance(security_id, str) or not security_id:
        raise ValueError("security_id is required")
    if not isinstance(feature_name, str) or not feature_name:
        raise ValueError("feature_name is required")
    return (
        security_id,
        normalized_time_text(item.get("prediction_time")),
        feature_name,
    )


def feature_spec_binding_payload(matrix_manifest: dict[str, Any]) -> dict[str, Any]:
    feature_axis = path_get(matrix_manifest, "feature_axis", {})
    layout = path_get(matrix_manifest, "layout", {})
    features = feature_axis.get("features", [])
    payload: dict[str, Any] = {
        "schema_version": "pit_matrix_feature_spec_v1",
        "feature_spec_version": feature_axis.get("feature_spec_version"),
        "layout_mode": layout.get("mode"),
        "features": features,
        "feature_semantics_sha256": feature_axis.get(
            "feature_semantics_sha256"
        ),
        "applicability_rule_sha256": layout.get("applicability_rule_sha256"),
    }
    if layout.get("mode") == "SPARSE_EXPLICIT":
        payload["expected_cell_key_set_sha256"] = matrix_manifest.get(
            "expected_cell_key_set_sha256"
        )
    return payload


def label_schedule_content(schedule: dict[str, Any]) -> dict[str, Any]:
    content = dict(schedule)
    content.pop("receipt_hash", None)
    return content


def semantic_review_content(review: dict[str, Any]) -> dict[str, Any]:
    content = dict(review)
    content.pop("receipt_hash", None)
    return content


class Audit:
    def __init__(
        self,
        request_path: Path,
        output_dir: Path,
        *,
        _allow_test_adapter_for_tests: bool = False,
        trusted_review_authority_sha256: set[str] | None = None,
        trusted_semantic_review_receipt_sha256: set[str] | None = None,
        trusted_interval_authority_sha256: set[str] | None = None,
    ):
        self.request_path = request_path.resolve()
        self.root = self.request_path.parent
        self.output_dir = output_dir.resolve()
        self.allow_test_adapter = _allow_test_adapter_for_tests
        self.execution_boundary = (
            "INTERNAL_TEST_ONLY"
            if _allow_test_adapter_for_tests
            else "PRODUCTION_CLI"
        )
        self.trusted_review_authority_sha256 = (
            trusted_review_authority_sha256 or set()
        )
        self.trusted_semantic_review_receipt_sha256 = (
            trusted_semantic_review_receipt_sha256 or set()
        )
        self.trusted_interval_authority_sha256 = (
            trusted_interval_authority_sha256 or set()
        )
        self.request: dict[str, Any] = {}
        self.meta: dict[str, dict[str, Any]] = {}
        self.docs: dict[str, Any] = {}
        self.hashes: dict[str, str] = {}
        self.rows: list[dict[str, str]] = []
        self.times: list[dict[str, datetime | None]] = []
        self.results: dict[str, dict[str, Any]] = {}

    def matrix_manifest(self) -> dict[str, Any]:
        manifest = self.docs.get("matrix_manifest", {})
        return manifest if isinstance(manifest, dict) else {}

    def matrix_feature_names(self) -> list[str]:
        raw = path_get(self.matrix_manifest(), "feature_axis.features", [])
        if not isinstance(raw, list):
            return []
        return sorted(
            {
                item
                for item in raw
                if isinstance(item, str) and item
            }
        )

    def audited_feature_names(self) -> list[str]:
        return sorted(
            {
                name
                for name in [
                    *(row.get("feature_name") for row in self.rows),
                    *self.matrix_feature_names(),
                ]
                if isinstance(name, str) and name
            }
        )

    def evidence(self, *items: Any) -> list[Any]:
        data = self.meta.get("data", {})
        if not isinstance(data, dict):
            data = {}
        dictionary = self.docs.get("dictionary", {})
        base = {
            "source_id": data.get("source_id"),
            "source_version": data.get("source_version"),
            "snapshot_id": data.get("snapshot_id"),
            "snapshot_binding_mode": data.get("snapshot_binding_mode"),
            "source_snapshot_sha256": data.get("source_snapshot_sha256"),
            "data_artifact_sha256": self.hashes.get("data"),
            "dictionary_id": dictionary.get("dictionary_id"),
            "dictionary_version": dictionary.get("version"),
            "dictionary_artifact_sha256": self.hashes.get("dictionary"),
            "schema_artifact_sha256": self.hashes.get("schema"),
            "time_semantics_artifact_sha256": self.hashes.get("time_semantics"),
            "contract_artifact_sha256": self.hashes.get("research_contract"),
            "label_definition_artifact_sha256": self.hashes.get("label_definition"),
            "label_schedule_artifact_sha256": self.hashes.get("label_schedule"),
            "review_authority_artifact_sha256": self.hashes.get(
                "review_authority"
            ),
            "label_interval_authority_artifact_sha256": self.hashes.get(
                "label_interval_authority"
            ),
            "calendar_artifact_sha256": self.hashes.get("calendar"),
            "population_manifest_artifact_sha256": self.hashes.get(
                "population_manifest"
            ),
            "population_source_artifact_sha256": self.hashes.get(
                "population_source"
            ),
            "matrix_manifest_artifact_sha256": self.hashes.get(
                "matrix_manifest"
            ),
            "semantic_source_uri": dictionary.get("source_uri"),
            "semantic_source_document_sha256": dictionary.get(
                "semantic_source_document_sha256"
            ),
        }
        return [base, *items]

    def semantic_trace(
        self, check_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        dictionary = self.docs.get("dictionary", {})
        fields = dictionary.get("fields", {}) if isinstance(dictionary, dict) else {}
        features = dictionary.get("features", {}) if isinstance(dictionary, dict) else {}
        roles = path_get(self.docs.get("time_semantics", {}), "roles", {})
        used_features = self.audited_feature_names()
        field_locators: dict[str, Any] = {}
        role_locators: dict[str, Any] = {}
        feature_locators: dict[str, Any] = {}
        external_locators: dict[str, Any] = {}
        missing: list[dict[str, Any]] = []

        for field in sorted(CHECK_FIELD_DEPENDENCIES.get(check_id, set())):
            locator_value = path_get(fields, f"{field}.source_locator")
            field_locators[field] = locator_value
            if not locator_value:
                missing.append(
                    self.issue(
                        f"dictionary.fields.{field}.source_locator",
                        f"{check_id} requires an exact field-semantic locator",
                    )
                )
            role = FIELD_ROLES.get(field)
            if role in ROLE_FIELDS:
                role_locator = path_get(roles, f"{role}.source_locator")
                role_locators[role] = role_locator
                if not role_locator:
                    missing.append(
                        self.issue(
                            f"time_semantics.roles.{role}.source_locator",
                            f"{check_id} requires an exact time-role locator",
                        )
                    )

        for feature_name in used_features:
            feature = features.get(feature_name, {}) if isinstance(features, dict) else {}
            for policy_path in FEATURE_POLICY_BY_CHECK.get(check_id, ()):
                value = path_get(feature, policy_path)
                key = f"{feature_name}.{policy_path}"
                feature_locators[key] = value
                if not value:
                    missing.append(
                        self.issue(
                            f"dictionary.features.{key}",
                            f"{check_id} requires an exact feature-policy locator",
                        )
                    )

        external_values = {
            "dictionary": dictionary.get("source_uri")
            if isinstance(dictionary, dict)
            else None,
            "contract_validation": path_get(
                self.docs.get("contract_validation", {}), "validator"
            ),
            "label": path_get(
                self.docs.get("label_definition", {}), "source_locator"
            ),
            "population": path_get(
                self.docs.get("population_source", {}), "source_uri"
            ),
            "calendar": path_get(self.meta.get("calendar", {}), "source_uri"),
        }
        for name in EXTERNAL_LOCATOR_BY_CHECK.get(check_id, ()):
            external_locators[name] = external_values.get(name)
            if not external_values.get(name):
                missing.append(
                    self.issue(
                        f"semantic_trace.external.{name}",
                        f"{check_id} requires an exact external-policy locator",
                    )
                )

        trace = {
            "dictionary_fields": field_locators,
            "time_roles": role_locators,
            "feature_policies": feature_locators,
            "external_policies": external_locators,
        }
        trace["binding_sha256"] = sha_value(trace)
        return trace, missing

    def add(
        self,
        check_id: str,
        failures: list[Any],
        gaps: list[Any],
        evidence: list[Any],
        *,
        metrics: dict[str, Any] | None = None,
        notes: list[str] | None = None,
        repair: str,
    ) -> None:
        semantic_trace, trace_gaps = self.semantic_trace(check_id)
        gaps.extend(trace_gaps)
        evidence = [*evidence, {"semantic_trace": semantic_trace}]
        status = verdict(failures, gaps)
        issues = failures + gaps
        evidence = copy.deepcopy(evidence)
        payload = {
            "check_id": check_id,
            "title": CHECKS[check_id],
            "status": status,
            "checked_rows": len(self.rows),
            "evidence": evidence,
            "violation_count": len(issues),
            "issue_set_digest": sha_value(issues),
            "violations": issues[:25],
            "violations_truncated": len(issues) > 25,
            "metrics": metrics or {},
            "notes": notes or [],
            "minimal_remediation": None if status == PASS else repair,
        }
        payload["evidence_digest"] = sha_value(
            {key: value for key, value in payload.items() if key != "minimal_remediation"}
        )
        self.results[check_id] = payload

    def issue(self, where: str, reason: str, **details: Any) -> dict[str, Any]:
        return {"locator": where, "reason": reason, **details}

    def validate_input_shapes(self, check_id: str) -> None:
        """Validate only documented caller containers; do not catch code defects."""
        schema = self.docs.get("schema", {})
        dictionary = self.docs.get("dictionary", {})
        semantics = self.docs.get("time_semantics", {})
        roots = {"request": self.request, "meta": self.meta, "docs": self.docs}
        shape_paths = SHAPE_PATHS_BY_CHECK.get(check_id, ())
        if check_id == "Q001" and not self.docs.get("matrix_manifest"):
            shape_paths = ()
        requirements = [
            (
                f"request.artifacts.{dotted}"
                if root_name == "meta"
                else f"request.{dotted}"
                if root_name == "request"
                else dotted,
                path_get(
                    roots[root_name],
                    dotted,
                    None if check_id == "Q001" else {},
                ),
            )
            for root_name, dotted in shape_paths
        ]

        fields = dictionary.get("fields", {})
        if check_id == "S001" and isinstance(fields, dict):
            requirements.extend(
                (
                    f"dictionary.fields.{field}",
                    entry,
                )
                for field, entry in fields.items()
            )
        roles = semantics.get("roles", {})
        if check_id == "T001" and isinstance(roles, dict):
            requirements.extend(
                (
                    f"time_semantics.roles.{role}",
                    entry,
                )
                for role, entry in roles.items()
            )
        features = dictionary.get("features", {})
        if check_id in {"S001", "T002", "A001", "Q003"} and isinstance(
            features, dict
        ):
            for name in self.audited_feature_names():
                if name in features:
                    requirements.append(
                        (
                            f"dictionary.features.{name}",
                            features[name],
                        )
                    )
        columns = schema.get("columns", {})
        if check_id == "Q002" and isinstance(columns, dict):
            requirements.extend(
                (f"schema.columns.{field}", spec)
                for field, spec in columns.items()
            )

        for locator_value, value in requirements:
            if not isinstance(value, dict):
                raise InputShapeError(
                    locator_value,
                    "dict",
                    value,
                )

    def input_path(self, raw: Any) -> Path:
        if not isinstance(raw, str) or not raw:
            raise ValueError("artifact path must be a non-empty relative path")
        candidate = Path(raw)
        if candidate.is_absolute():
            raise ValueError("artifact path must be relative to the request")
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as error:
            raise ValueError("artifact path escapes the request directory") from error
        return resolved

    def check_i001_inputs(self) -> None:
        failures, gaps = [], []
        try:
            self.request = strict_json_loads(
                self.request_path.read_text(encoding="utf-8")
            )
            if not isinstance(self.request, dict):
                raise ValueError("root must be an object")
        except FileNotFoundError:
            gaps.append(self.issue(str(self.request_path), "request is missing"))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            failures.append(self.issue(str(self.request_path), f"invalid request: {error}"))

        if self.request:
            if self.request.get("request_version") != "pit_audit_request_v1":
                failures.append(
                    self.issue(
                        "request.request_version", "must equal pit_audit_request_v1"
                    )
                )
            if not str(self.request.get("request_id", "")).strip():
                gaps.append(self.issue("request.request_id", "request ID is required"))
            if self.request.get("claim") not in CLAIMS:
                failures.append(
                    self.issue("request.claim", f"must be one of {sorted(CLAIMS)}")
                )
            try:
                dt(self.request.get("run_at"))
            except ValueError as error:
                failures.append(self.issue("request.run_at", str(error)))
            coverage = self.request.get("coverage", {})
            if not isinstance(coverage, dict):
                failures.append(
                    self.issue(
                        "request.coverage",
                        "must be an object with scope, extraction, and population bindings",
                    )
                )
                coverage = {}
            if coverage.get("scope") not in SCOPES:
                failures.append(
                    self.issue(
                        "request.coverage.scope", f"must be one of {sorted(SCOPES)}"
                    )
                )
            for key in ("extraction_query_sha256", "extraction_receipt_id"):
                value = coverage.get(key)
                if not value:
                    gaps.append(
                        self.issue(f"request.coverage.{key}", "provenance is required")
                    )
                elif key.endswith("sha256") and not is_sha(value):
                    failures.append(
                        self.issue(
                            f"request.coverage.{key}", "must be lowercase SHA-256"
                        )
                    )

            raw_meta = self.request.get("artifacts")
            if not isinstance(raw_meta, dict):
                gaps.append(self.issue("request.artifacts", "artifact map is required"))
                raw_meta = {}
            self.meta = raw_meta
            scope = coverage.get("scope")
            artifact_names = REQUIRED_ARTIFACTS | {
                name for name in OPTIONAL_ARTIFACTS if name in raw_meta
            }
            for name in sorted(artifact_names):
                metadata = raw_meta.get(name)
                if not isinstance(metadata, dict):
                    gaps.append(
                        self.issue(f"request.artifacts.{name}", "artifact is required")
                    )
                    continue
                if not is_sha(metadata.get("sha256")):
                    failures.append(
                        self.issue(
                            f"request.artifacts.{name}.sha256",
                            "must be lowercase SHA-256",
                        )
                    )
                if not metadata.get("path"):
                    gaps.append(
                        self.issue(
                            f"request.artifacts.{name}.path", "path is required"
                        )
                    )
                    continue
                try:
                    path = self.input_path(metadata["path"])
                except ValueError as error:
                    failures.append(
                        self.issue(
                            f"request.artifacts.{name}.path",
                            str(error),
                        )
                    )
                    continue
                if not path.is_file():
                    gaps.append(self.issue(str(path), f"{name} is missing"))
                    continue
                try:
                    actual = sha_file(path)
                    self.hashes[name] = actual
                    if actual != metadata.get("sha256"):
                        failures.append(
                            self.issue(
                                f"request.artifacts.{name}",
                                "declared hash does not match bytes",
                                declared=metadata.get("sha256"),
                                actual=actual,
                            )
                        )
                    if name in {"data", "calendar"}:
                        rows, headers = strict_csv_rows(path, name)
                        self.docs[name] = rows
                        self.docs[f"{name}_headers"] = headers
                    else:
                        value = strict_json_loads(path.read_text(encoding="utf-8"))
                        if not isinstance(value, dict):
                            raise ValueError("JSON root must be an object")
                        self.docs[name] = value
                except CsvStructureError as error:
                    failures.append(
                        self.issue(
                            error.locator,
                            f"cannot parse {name}: {error}",
                        )
                    )
                except (
                    OSError,
                    UnicodeError,
                    csv.Error,
                    json.JSONDecodeError,
                    ValueError,
                ) as error:
                    failures.append(
                        self.issue(str(path), f"cannot parse {name}: {error}")
                    )

            data_metadata = raw_meta.get("data", {})
            if not isinstance(data_metadata, dict):
                data_metadata = {}
            snapshot_binding_mode = data_metadata.get(
                "snapshot_binding_mode"
            )
            if not snapshot_binding_mode:
                gaps.append(
                    self.issue(
                        "request.artifacts.data.snapshot_binding_mode",
                        "declare IDENTITY_SNAPSHOT or DERIVED_EXTRACT explicitly",
                    )
                )
            elif snapshot_binding_mode == "IDENTITY_SNAPSHOT":
                source_snapshot_hash = data_metadata.get(
                    "source_snapshot_sha256"
                )
                if not is_sha(source_snapshot_hash):
                    gaps.append(
                        self.issue(
                            "request.artifacts.data.source_snapshot_sha256",
                            "IDENTITY_SNAPSHOT requires the exact source-snapshot hash",
                        )
                    )
                elif (
                    self.hashes.get("data")
                    and source_snapshot_hash != self.hashes["data"]
                ):
                    failures.append(
                        self.issue(
                            "request.artifacts.data.source_snapshot_sha256",
                            "IDENTITY_SNAPSHOT must equal the verified consumed data bytes",
                            expected=self.hashes["data"],
                            actual=source_snapshot_hash,
                        )
                    )
            elif snapshot_binding_mode == "DERIVED_EXTRACT":
                gaps.append(
                    self.issue(
                        "request.artifacts.data.extraction_receipt",
                        "DERIVED_EXTRACT requires a separately hash-bound extraction receipt; v1 does not infer that lineage",
                    )
                )
            else:
                failures.append(
                    self.issue(
                        "request.artifacts.data.snapshot_binding_mode",
                        "unsupported snapshot binding mode",
                        actual=snapshot_binding_mode,
                    )
                )

            matrix_metadata = raw_meta.get("matrix_manifest")
            if matrix_metadata is None:
                if scope == "FULL_TRAINING_INPUT":
                    gaps.append(
                        self.issue(
                            "request.artifacts.matrix_manifest",
                            "FULL_TRAINING_INPUT requires a hash-bound pit_matrix_manifest_v1",
                        )
                    )
            matrix = self.matrix_manifest()
            if matrix:
                unsigned = dict(matrix)
                unsigned.pop("receipt_hash", None)
                if matrix.get("schema_version") != "pit_matrix_manifest_v1":
                    failures.append(self.issue("matrix_manifest.schema_version", "unsupported schema"))
                for key in ("manifest_id", "version"):
                    if not isinstance(matrix.get(key), str) or not matrix[key].strip():
                        gaps.append(
                            self.issue(
                                f"matrix_manifest.{key}",
                                "non-empty matrix identity/version is required",
                            )
                        )
                    elif path_get(raw_meta, f"matrix_manifest.{key}") != matrix.get(key):
                        failures.append(
                            self.issue(
                                f"request.artifacts.matrix_manifest.{key}",
                                "request metadata does not identify the audited matrix manifest",
                                expected=matrix.get(key),
                                actual=path_get(raw_meta, f"matrix_manifest.{key}"),
                            )
                        )
                matrix_mode = path_get(matrix, "layout.mode")
                if matrix_mode == "RECTANGULAR" and "expected_cells" in matrix:
                    failures.append(
                        self.issue(
                            "matrix_manifest.expected_cells",
                            "RECTANGULAR derives its cell set from independent axes and forbids an enumerated override",
                        )
                    )
                elif matrix_mode == "SPARSE_EXPLICIT" and not isinstance(
                    matrix.get("expected_cells"), list
                ):
                    gaps.append(
                        self.issue(
                            "matrix_manifest.expected_cells",
                            "SPARSE_EXPLICIT requires an explicit cell list even though v1 cannot qualify it",
                        )
                    )
                if not matrix.get("receipt_hash"):
                    gaps.append(self.issue("matrix_manifest.receipt_hash", "receipt is required"))
                elif matrix["receipt_hash"] != sha_value(unsigned):
                    failures.append(self.issue("matrix_manifest.receipt_hash", "receipt hash mismatch"))

            schedule = self.docs.get("label_schedule", {})
            schedule_meta = raw_meta.get("label_schedule", {})
            if isinstance(schedule, dict) and schedule:
                if schedule.get("schema_version") != "pit_label_schedule_v1":
                    failures.append(
                        self.issue(
                            "label_schedule.schema_version",
                            "must equal pit_label_schedule_v1",
                        )
                    )
                for key in ("schedule_id", "version"):
                    value = schedule.get(key)
                    if not isinstance(value, str) or not value.strip():
                        gaps.append(
                            self.issue(
                                f"label_schedule.{key}",
                                "non-empty schedule identity/version is required",
                            )
                        )
                    elif not isinstance(schedule_meta, dict) or schedule_meta.get(key) != value:
                        failures.append(
                            self.issue(
                                f"request.artifacts.label_schedule.{key}",
                                "request metadata does not identify the audited label schedule",
                                expected=value,
                                actual=(
                                    schedule_meta.get(key)
                                    if isinstance(schedule_meta, dict)
                                    else None
                                ),
                            )
                        )
                receipt_hash = schedule.get("receipt_hash")
                if not receipt_hash:
                    gaps.append(
                        self.issue(
                            "label_schedule.receipt_hash",
                            "canonical schedule receipt is required",
                        )
                    )
                elif not is_sha(receipt_hash):
                    failures.append(
                        self.issue(
                            "label_schedule.receipt_hash",
                            "must be lowercase SHA-256",
                        )
                    )
                elif receipt_hash != sha_value(label_schedule_content(schedule)):
                    failures.append(
                        self.issue(
                            "label_schedule.receipt_hash",
                            "receipt hash does not bind the schedule content",
                        )
                    )

            review_authority = self.docs.get("review_authority", {})
            review_authority_meta = raw_meta.get("review_authority", {})
            if isinstance(review_authority, dict) and review_authority:
                allowed = {
                    "schema_version",
                    "authority_id",
                    "version",
                    "source_uri",
                    "reviewers",
                    "receipt_hash",
                }
                for key in sorted(set(review_authority) - allowed):
                    failures.append(
                        self.issue(
                            f"review_authority.{key}",
                            "unknown v1 field is forbidden",
                        )
                    )
                if (
                    review_authority.get("schema_version")
                    != "pit_semantic_review_authority_v1"
                ):
                    failures.append(
                        self.issue(
                            "review_authority.schema_version",
                            "must equal pit_semantic_review_authority_v1",
                        )
                    )
                for key in ("authority_id", "version"):
                    value = review_authority.get(key)
                    if not isinstance(value, str) or not value.strip():
                        gaps.append(
                            self.issue(
                                f"review_authority.{key}",
                                "non-empty authority identity/version is required",
                            )
                        )
                    elif (
                        not isinstance(review_authority_meta, dict)
                        or review_authority_meta.get(key) != value
                    ):
                        failures.append(
                            self.issue(
                                f"request.artifacts.review_authority.{key}",
                                "request metadata identifies a different review authority",
                            )
                        )
                if not isinstance(
                    review_authority.get("source_uri"), str
                ) or not review_authority["source_uri"].strip():
                    gaps.append(
                        self.issue(
                            "review_authority.source_uri",
                            "authority provenance locator is required",
                        )
                    )
                unsigned_authority = dict(review_authority)
                unsigned_authority.pop("receipt_hash", None)
                authority_receipt = review_authority.get("receipt_hash")
                if not authority_receipt:
                    gaps.append(
                        self.issue(
                            "review_authority.receipt_hash",
                            "authority receipt is required",
                        )
                    )
                elif not is_sha(authority_receipt) or authority_receipt != sha_value(
                    unsigned_authority
                ):
                    failures.append(
                        self.issue(
                            "review_authority.receipt_hash",
                            "authority receipt hash mismatch",
                        )
                    )
                reviewers = review_authority.get("reviewers")
                if isinstance(reviewers, list):
                    reviewer_allowed = {
                        "reviewer_id",
                        "allowed_scopes",
                        "valid_from",
                        "valid_to",
                    }
                    seen_reviewer_ids: set[str] = set()
                    for index, reviewer in enumerate(reviewers):
                        if isinstance(reviewer, dict):
                            for key in sorted(set(reviewer) - reviewer_allowed):
                                failures.append(
                                    self.issue(
                                        f"review_authority.reviewers[{index}].{key}",
                                        "unknown v1 field is forbidden",
                                    )
                                )
                            reviewer_id = reviewer.get("reviewer_id")
                            if (
                                isinstance(reviewer_id, str)
                                and reviewer_id in seen_reviewer_ids
                            ):
                                failures.append(
                                    self.issue(
                                        f"review_authority.reviewers[{index}].reviewer_id",
                                        "reviewer_id must be unique within a v1 authority artifact",
                                        actual=reviewer_id,
                                    )
                                )
                            elif isinstance(reviewer_id, str):
                                seen_reviewer_ids.add(reviewer_id)

            interval_authority = self.docs.get(
                "label_interval_authority", {}
            )
            interval_meta = raw_meta.get("label_interval_authority", {})
            if isinstance(interval_authority, dict) and interval_authority:
                allowed = {
                    "schema_version",
                    "authority_id",
                    "version",
                    "source_uri",
                    "population_manifest_sha256",
                    "expected_sample_count",
                    "expected_interval_set_sha256",
                    "generator",
                    "receipt_hash",
                }
                for key in sorted(set(interval_authority) - allowed):
                    failures.append(
                        self.issue(
                            f"label_interval_authority.{key}",
                            "unknown v1 field is forbidden",
                        )
                    )
                if (
                    interval_authority.get("schema_version")
                    != "pit_label_interval_authority_v1"
                ):
                    failures.append(
                        self.issue(
                            "label_interval_authority.schema_version",
                            "must equal pit_label_interval_authority_v1",
                        )
                    )
                for key in ("authority_id", "version"):
                    value = interval_authority.get(key)
                    if not isinstance(value, str) or not value.strip():
                        gaps.append(
                            self.issue(
                                f"label_interval_authority.{key}",
                                "non-empty interval-authority identity/version is required",
                            )
                        )
                    elif (
                        not isinstance(interval_meta, dict)
                        or interval_meta.get(key) != value
                    ):
                        failures.append(
                            self.issue(
                                f"request.artifacts.label_interval_authority.{key}",
                                "request metadata identifies a different interval authority",
                            )
                        )
                if not isinstance(
                    interval_authority.get("source_uri"), str
                ) or not interval_authority["source_uri"].strip():
                    gaps.append(
                        self.issue(
                            "label_interval_authority.source_uri",
                            "interval-authority provenance locator is required",
                        )
                    )
                unsigned_interval_authority = dict(interval_authority)
                unsigned_interval_authority.pop("receipt_hash", None)
                interval_receipt = interval_authority.get("receipt_hash")
                if not interval_receipt:
                    gaps.append(
                        self.issue(
                            "label_interval_authority.receipt_hash",
                            "interval-authority receipt is required",
                        )
                    )
                elif not is_sha(interval_receipt) or interval_receipt != sha_value(
                    unsigned_interval_authority
                ):
                    failures.append(
                        self.issue(
                            "label_interval_authority.receipt_hash",
                            "interval-authority receipt hash mismatch",
                        )
                    )
                generator = interval_authority.get("generator")
                if isinstance(generator, dict):
                    generator_allowed = {
                        "code_sha256",
                        "parameters_sha256",
                        "input_snapshot_sha256",
                        "source_locator",
                    }
                    for key in sorted(set(generator) - generator_allowed):
                        failures.append(
                            self.issue(
                                f"label_interval_authority.generator.{key}",
                                "unknown v1 field is forbidden",
                            )
                        )

            self.rows = self.docs.get("data", [])
            expected = coverage.get("expected_row_count")
            if not nonnegative_int(expected):
                failures.append(
                    self.issue(
                        "request.coverage.expected_row_count",
                        "must be a non-negative non-boolean integer",
                    )
                )
            elif "data" in self.docs and expected != len(self.rows):
                failures.append(
                    self.issue(
                        "request.coverage.expected_row_count",
                        "does not match parsed rows",
                        expected=expected,
                        actual=len(self.rows),
                    )
                )
            data_meta = raw_meta.get("data", {})
            if not isinstance(data_meta, dict):
                data_meta = {}
            for key in (
                "source_id",
                "source_version",
                "snapshot_id",
                "source_snapshot_sha256",
            ):
                if not data_meta.get(key):
                    gaps.append(
                        self.issue(
                            f"request.artifacts.data.{key}", "lineage is required"
                        )
                    )
            if data_meta.get("source_snapshot_sha256") and not is_sha(
                data_meta["source_snapshot_sha256"]
            ):
                failures.append(
                    self.issue(
                        "request.artifacts.data.source_snapshot_sha256",
                        "must be lowercase SHA-256",
                    )
                )

        self.add(
            "I001",
            failures,
            gaps,
            self.evidence(
                {
                    "request_file": self.request_path.name,
                    "request_sha256": sha_file(self.request_path)
                    if self.request_path.is_file()
                    else None,
                    "verified_artifact_hashes": self.hashes,
                    "scope": path_get(self.request, "coverage.scope"),
                }
            ),
            metrics={"parsed_rows": len(self.rows), "verified_files": len(self.hashes)},
            repair=(
                "Provide the exact immutable inputs, versions, hashes, counts, and extraction "
                "receipt; regenerate the request instead of editing evidence."
            ),
        )

    def contract_view(self) -> dict[str, Any]:
        contract = self.docs.get("research_contract", {})
        if not isinstance(contract, dict):
            return {
                "adapter": None,
                "status": None,
                "contract_id": None,
                "canonical_hash": None,
                "frozen_at": None,
                "timezone": None,
                "calendar_id": None,
                "calendar_version": None,
                "universe_version": None,
                "universe_hash": None,
                "includes_inactive_and_delisted": None,
                "sources": [],
                "availability_comparison": None,
                "label_id": None,
                "label_spec_version": None,
                "label_spec_hash": None,
                "purge_rule": None,
                "purge_embargo_rule": None,
                "embargo_duration": None,
                "embargo_basis": None,
                "overlap_present": None,
                "split_windows": None,
                "formula": None,
                "neutralization_rule": None,
                "corporate_action_rule": None,
                "overlap_rule": None,
                "feature_spec_version": None,
                "feature_spec_hash": None,
                "prediction_time_rule": None,
                "execution_time_rule": None,
                "label_start_rule": None,
                "label_end_rule": None,
                "holding_period_rule": None,
            }
        if contract.get("schema_version") == "pit_contract_binding_v1":
            policy = contract.get("data_policy", {})
            if not isinstance(policy, dict):
                policy = {}
            return {
                "adapter": "pit_contract_binding_v1",
                "status": contract.get("status"),
                "contract_id": contract.get("contract_id"),
                "canonical_hash": contract.get("canonical_hash"),
                "frozen_at": contract.get("frozen_at"),
                "timezone": contract.get("timezone"),
                "calendar_id": path_get(contract, "calendar.calendar_id"),
                "calendar_version": path_get(contract, "calendar.version"),
                "universe_version": path_get(contract, "universe.version"),
                "universe_hash": path_get(contract, "universe.hash"),
                "includes_inactive_and_delisted": path_get(
                    contract, "universe.includes_inactive_and_delisted"
                ),
                "sources": [
                    {
                        "source_id": policy.get("source_id"),
                        "source_version": policy.get("source_version"),
                        "snapshot_id": policy.get("snapshot_id"),
                        "snapshot_hash": policy.get("snapshot_hash"),
                        "availability_evidence_version": policy.get(
                            "availability_evidence_version"
                        ),
                        "availability_evidence_hash": policy.get(
                            "availability_evidence_hash"
                        ),
                        "event_timestamp_field": policy.get(
                            "event_timestamp_field", "event_time"
                        ),
                        "availability_timestamp_field": policy.get(
                            "availability_timestamp_field",
                            "vendor_available_time",
                        ),
                        "revision_policy": policy.get("revision_policy"),
                        "allowed_fields": policy.get("allowed_features", []),
                    }
                ],
                "availability_comparison": policy.get("availability_comparison"),
                "label_id": contract.get("label_id"),
                "label_spec_version": contract.get("label_spec_version"),
                "label_spec_hash": contract.get("label_spec_hash"),
                "purge_rule": path_get(
                    contract, "split_policy.cross_split_label_overlap"
                ),
                "purge_embargo_rule": path_get(
                    contract, "split_policy.cross_split_label_overlap"
                ),
                "embargo_duration": "0",
                "embargo_basis": "not_applicable_test_adapter",
                "overlap_present": True,
                "split_windows": None,
                "formula": contract.get("label_formula"),
                "neutralization_rule": contract.get(
                    "neutralization_rule"
                ),
                "corporate_action_rule": policy.get("corporate_action_policy"),
                "overlap_rule": path_get(
                    contract, "split_policy.cross_split_label_overlap"
                ),
                "feature_spec_version": policy.get("feature_spec_version"),
                "feature_spec_hash": policy.get("feature_spec_hash"),
                "prediction_time_rule": path_get(
                    contract, "time_rules.prediction_time"
                ),
                "execution_time_rule": path_get(
                    contract, "time_rules.execution_time"
                ),
                "label_start_rule": path_get(
                    contract, "time_rules.label_start_rule"
                ),
                "label_end_rule": path_get(
                    contract, "time_rules.label_end_rule"
                ),
                "holding_period_rule": path_get(
                    contract, "time_rules.holding_period"
                ),
            }
        decision_calendar = path_get(contract, "scope.decision_calendar")
        calendar_id = decision_calendar
        calendar_version = None
        if (
            isinstance(decision_calendar, str)
            and decision_calendar.count("@") == 1
        ):
            candidate_id, candidate_version = decision_calendar.split("@", 1)
            if candidate_id and candidate_version:
                calendar_id = candidate_id
                calendar_version = candidate_version
        qrc_sources = []
        raw_qrc_sources = path_get(contract, "data.sources", [])
        if not isinstance(raw_qrc_sources, list):
            raw_qrc_sources = []
        for item in raw_qrc_sources:
            if isinstance(item, dict):
                adapted = dict(item)
                adapted["source_version"] = item.get("snapshot_id")
                qrc_sources.append(adapted)
        return {
            "adapter": contract.get("schema_version"),
            "status": path_get(contract, "contract.status"),
            "contract_id": path_get(contract, "contract.contract_id"),
            "canonical_hash": path_get(contract, "contract.canonical_hash"),
            "frozen_at": path_get(contract, "contract.frozen_at"),
            "timezone": path_get(contract, "scope.timezone"),
            "calendar_id": calendar_id,
            "calendar_version": calendar_version,
            "universe_version": path_get(
                contract, "scope.universe.universe_version"
            ),
            "universe_hash": path_get(contract, "scope.universe.universe_hash"),
            "includes_inactive_and_delisted": None,
            "sources": qrc_sources,
            "availability_comparison": None,
            "label_id": path_get(contract, "target.label_id"),
            "label_spec_version": path_get(
                contract, "target.label_spec_version"
            ),
            "label_spec_hash": path_get(contract, "target.label_spec_hash"),
            "purge_rule": path_get(
                contract, "splits.sample_dependency.purge_rule"
            ),
            "purge_embargo_rule": path_get(
                contract, "splits.purge_embargo_rule"
            ),
            "embargo_duration": path_get(
                contract, "splits.sample_dependency.embargo_duration"
            ),
            "embargo_basis": path_get(
                contract, "splits.sample_dependency.embargo_basis"
            ),
            "overlap_present": path_get(
                contract, "splits.sample_dependency.overlap_present"
            ),
            "split_windows": {
                "TRAIN": path_get(contract, "splits.train"),
                "MODEL_SELECTION": path_get(contract, "splits.selection"),
                "OOS": path_get(contract, "splits.final_oos"),
            },
            "formula": path_get(contract, "target.formula"),
            "neutralization_rule": path_get(
                contract, "target.neutralization_rule"
            ),
            "corporate_action_rule": path_get(
                contract, "target.corporate_action_rule"
            ),
            "overlap_rule": path_get(contract, "target.overlap_rule"),
            "feature_spec_version": path_get(
                contract, "data.feature_spec_version"
            ),
            "feature_spec_hash": path_get(contract, "data.feature_spec_hash"),
            "prediction_time_rule": path_get(
                contract, "time_semantics.prediction_time"
            ),
            "execution_time_rule": path_get(
                contract, "time_semantics.execution_time_rule"
            ),
            "label_start_rule": path_get(
                contract, "time_semantics.label_start_rule"
            ),
            "label_end_rule": path_get(
                contract, "time_semantics.label_end_rule"
            ),
            "holding_period_rule": path_get(
                contract, "time_semantics.holding_period"
            ),
        }

    def check_i002_contract(self) -> None:
        failures, gaps = [], []
        contract = self.docs.get("research_contract", {})
        view = self.contract_view()
        metadata = self.meta.get("research_contract", {})
        if view["adapter"] not in {"quant_contract_v2", "pit_contract_binding_v1"}:
            failures.append(
                self.issue(
                    "research_contract.schema_version", "unsupported contract adapter"
                )
            )
        if (
            view["adapter"] == "pit_contract_binding_v1"
            and not self.allow_test_adapter
        ):
            failures.append(
                self.issue(
                    "research_contract.schema_version",
                    "pit_contract_binding_v1 is test-only and cannot qualify through the production CLI",
                    execution_boundary=self.execution_boundary,
                )
            )
        if metadata.get("adapter") != view["adapter"]:
            failures.append(
                self.issue(
                    "request.artifacts.research_contract.adapter",
                    "declared adapter does not match the contract",
                )
            )
        if view["status"] != "FROZEN":
            failures.append(
                self.issue(
                    "research_contract.status",
                    "an intact FROZEN research contract is required",
                )
            )
        for key in ("contract_id", "canonical_hash"):
            if not metadata.get(key):
                gaps.append(
                    self.issue(
                        f"request.artifacts.research_contract.{key}",
                        "binding is required",
                    )
                )
            elif metadata[key] != view[key]:
                failures.append(
                    self.issue(
                        f"research_contract.{key}",
                        "request binding conflicts with contract",
                    )
                )
        if view["canonical_hash"] and not is_sha(view["canonical_hash"]):
            failures.append(
                self.issue("research_contract.canonical_hash", "invalid SHA-256")
            )
        if view["adapter"] == "pit_contract_binding_v1":
            unhashed = dict(contract)
            unhashed.pop("canonical_hash", None)
            if view["canonical_hash"] != sha_value(unhashed):
                failures.append(
                    self.issue(
                        "research_contract.canonical_hash",
                        "test-binding canonical hash is invalid",
                    )
                )

        receipt_meta = metadata.get("validation_receipt")
        receipt: dict[str, Any] = {}
        if not isinstance(receipt_meta, dict):
            gaps.append(
                self.issue(
                    "request.artifacts.research_contract.validation_receipt",
                    "strict validation receipt is required for PASS",
                )
            )
        else:
            raw_path = receipt_meta.get("path")
            try:
                path = self.input_path(raw_path) if raw_path else None
            except ValueError as error:
                failures.append(
                    self.issue(
                        "request.artifacts.research_contract.validation_receipt.path",
                        str(error),
                    )
                )
                path = None
            if path is None or not path.is_file():
                gaps.append(
                    self.issue(
                        str(path or "contract_validation"), "receipt is missing"
                    )
                )
            else:
                try:
                    actual = sha_file(path)
                    self.hashes["contract_validation"] = actual
                    if actual != receipt_meta.get("sha256"):
                        failures.append(
                            self.issue(
                                "contract_validation",
                                "receipt hash does not match bytes",
                            )
                        )
                    loaded_receipt = strict_json_loads(
                        path.read_text(encoding="utf-8")
                    )
                    if not isinstance(loaded_receipt, dict):
                        raise ValueError("validation receipt root must be an object")
                    receipt = loaded_receipt
                    self.docs["contract_validation"] = receipt
                except (
                    OSError,
                    UnicodeError,
                    json.JSONDecodeError,
                    ValueError,
                ) as error:
                    failures.append(
                        self.issue(str(path), f"invalid validation receipt: {error}")
                    )
        if receipt:
            expected_receipt_schema = (
                "qrc_validation_receipt_v1"
                if view["adapter"] == "quant_contract_v2"
                else "pit_contract_validation_receipt_v1"
            )
            if receipt.get("schema_version") != expected_receipt_schema:
                failures.append(
                    self.issue(
                        "contract_validation.schema_version",
                        "receipt schema is not authorized for this contract adapter",
                        expected=expected_receipt_schema,
                        actual=receipt.get("schema_version"),
                    )
                )
            expected = {
                "status": "PASS",
                "strict": True,
                "contract_file_sha256": self.hashes.get("research_contract"),
                "contract_id": view["contract_id"],
                "canonical_hash": view["canonical_hash"],
            }
            for key, value in expected.items():
                if receipt.get(key) != value:
                    failures.append(
                        self.issue(
                            f"contract_validation.{key}",
                            "receipt does not bind this frozen contract",
                            expected=value,
                            actual=receipt.get(key),
                        )
                    )
            for key in ("validator", "validator_version"):
                if not receipt.get(key):
                    gaps.append(
                        self.issue(
                            f"contract_validation.{key}",
                            "validator identity/version is required",
                        )
                    )
            if view["adapter"] == "quant_contract_v2":
                if receipt.get("validator") != "quant-research-contract.validate_contract":
                    failures.append(
                        self.issue(
                            "contract_validation.validator",
                            "production contracts require the official QRC validator",
                        )
                    )
                if receipt.get("validator_version") != "quant_contract_v2":
                    failures.append(
                        self.issue(
                            "contract_validation.validator_version",
                            "validator version does not match quant_contract_v2",
                        )
                    )
                if not is_sha(receipt.get("validator_bundle_sha256")):
                    gaps.append(
                        self.issue(
                            "contract_validation.validator_bundle_sha256",
                            "official validator-code digest is required",
                        )
                    )
                validator_path = (
                    Path.home()
                    / ".codex"
                    / "skills"
                    / "quant-research-contract"
                    / "scripts"
                    / "validate_contract.py"
                )
                common_path = validator_path.with_name("contract_common.py")
                if not validator_path.is_file() or not common_path.is_file():
                    gaps.append(
                        self.issue(
                            "quant-research-contract",
                            "the installed official validator and shared validation library are required",
                        )
                    )
                else:
                    try:
                        local_bundle = validator_bundle_sha256(
                            validator_path, common_path
                        )
                    except OSError as error:
                        gaps.append(
                            self.issue(
                                str(validator_path),
                                f"cannot read the installed QRC validator: {error}",
                            )
                        )
                    else:
                        if receipt.get("validator_bundle_sha256") != local_bundle:
                            failures.append(
                                self.issue(
                                    "contract_validation.validator_bundle_sha256",
                                    "receipt is not bound to the installed official validator",
                                    expected=local_bundle,
                                    actual=receipt.get(
                                        "validator_bundle_sha256"
                                    ),
                                )
                            )
                        try:
                            contract_path = self.input_path(metadata.get("path"))
                            revalidation = subprocess.run(
                                [
                                    sys.executable,
                                    str(validator_path),
                                    str(contract_path),
                                    "--strict",
                                ],
                                check=False,
                                capture_output=True,
                                text=True,
                                timeout=30,
                            )
                        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                            gaps.append(
                                self.issue(
                                    "quant-research-contract",
                                    f"official strict revalidation could not run: {error}",
                                )
                            )
                        else:
                            self.docs["qrc_revalidation"] = {
                                "validator_bundle_sha256": local_bundle,
                                "exit_code": revalidation.returncode,
                                "stdout_sha256": sha_text(revalidation.stdout),
                                "stderr_sha256": sha_text(revalidation.stderr),
                            }
                            if revalidation.returncode != 0:
                                failures.append(
                                    self.issue(
                                        "research_contract",
                                        "installed official validator rejected the contract",
                                        exit_code=revalidation.returncode,
                                        stdout=revalidation.stdout.strip()[:500],
                                        stderr=revalidation.stderr.strip()[:500],
                                    )
                                )

        dictionary = self.docs.get("dictionary", {})
        label = self.docs.get("label_definition", {})
        semantics = self.docs.get("time_semantics", {})
        population = path_get(self.request, "coverage.population", {})
        calendar_meta = self.meta.get("calendar", {})
        data_meta = self.meta.get("data", {})
        source_match = next(
            (
                (index, item)
                for index, item in enumerate(view["sources"])
                if item.get("source_id") == data_meta.get("source_id")
            ),
            None,
        )
        source_index: int | None = None
        source: dict[str, Any] | None = None
        if source_match is not None:
            source_index, source = source_match
        if source is None:
            failures.append(
                self.issue(
                    "research_contract.data",
                    "audited source is outside the frozen allowlist",
                )
            )
        else:
            bindings = {
                "source_version": (
                    data_meta.get("source_version"),
                    source.get("source_version"),
                ),
                "snapshot_id": (
                    data_meta.get("snapshot_id"),
                    source.get("snapshot_id"),
                ),
                "snapshot_hash": (
                    data_meta.get("source_snapshot_sha256"),
                    source.get("snapshot_hash"),
                ),
                "availability_evidence_version": (
                    dictionary.get("version"),
                    source.get("availability_evidence_version"),
                ),
                "availability_evidence_hash": (
                    dictionary.get("semantic_source_document_sha256"),
                    source.get("availability_evidence_hash"),
                ),
            }
            for key, (actual, expected) in bindings.items():
                if expected is None:
                    gaps.append(
                        self.issue(
                            f"research_contract.source.{key}",
                            "frozen binding is missing",
                        )
                    )
                elif actual != expected:
                    failures.append(
                        self.issue(
                            f"research_contract.source.{key}",
                            "audited input conflicts with frozen binding",
                            expected=expected,
                            actual=actual,
                        )
                    )
            allowed = set(source.get("allowed_fields", []))
            used = {row.get("feature_name") for row in self.rows}
            if not used.issubset(allowed):
                failures.append(
                    self.issue(
                        "research_contract.source.allowed_fields",
                        "consumed features are outside the frozen allowlist",
                        fields=sorted(used - allowed),
                    )
                )
            role_source_bindings = {
                "EVENT_TIME": source.get("event_timestamp_field"),
                "VENDOR_AVAILABLE_TIME": source.get(
                    "availability_timestamp_field"
                ),
            }
            for role, expected_source_field in role_source_bindings.items():
                actual_source_field = path_get(
                    semantics, f"roles.{role}.source_field"
                )
                if not expected_source_field or not actual_source_field:
                    gaps.append(
                        self.issue(
                            f"time_semantics.roles.{role}.source_field",
                            "raw vendor field binding is required",
                        )
                    )
                elif actual_source_field != expected_source_field:
                    failures.append(
                        self.issue(
                            f"time_semantics.roles.{role}.source_field",
                            "canonical role maps to a different source field than the frozen contract",
                            expected=expected_source_field,
                            actual=actual_source_field,
                        )
                    )

        bindings = {
            "timezone": (semantics.get("timezone"), view["timezone"]),
            "calendar_id": (calendar_meta.get("calendar_id"), view["calendar_id"]),
            "calendar_version": (
                calendar_meta.get("version"),
                view["calendar_version"],
            ),
            "universe_version": (
                population.get("universe_version"),
                view["universe_version"],
            ),
            "universe_hash": (
                population.get("universe_hash"),
                view["universe_hash"],
            ),
            "includes_inactive_and_delisted": (
                population.get("includes_inactive_and_delisted"),
                view["includes_inactive_and_delisted"],
            ),
            "label_spec_hash": (
                label.get("label_spec_hash"),
                view["label_spec_hash"],
            ),
            "label_id": (label.get("label_id"), view["label_id"]),
            "label_spec_version": (
                label.get("label_spec_version"),
                view["label_spec_version"],
            ),
            "request_label_spec_hash": (
                path_get(self.request, "artifacts.label_definition.label_spec_hash"),
                label.get("label_spec_hash"),
            ),
            "availability_comparison": (
                semantics.get("availability_comparison"),
                view["availability_comparison"],
            ),
        }
        for key, (actual, expected) in bindings.items():
            if expected is None:
                if key in {
                    "availability_comparison",
                    "includes_inactive_and_delisted",
                } and view[
                    "adapter"
                ] == "quant_contract_v2":
                    continue
                gaps.append(
                    self.issue(f"contract_binding.{key}", "binding is missing")
                )
            elif actual != expected:
                failures.append(
                    self.issue(
                        f"contract_binding.{key}",
                        "audit input conflicts with frozen contract",
                        expected=expected,
                        actual=actual,
                    )
                )
        if view["adapter"] == "quant_contract_v2":
            interpretation = semantics.get("contract_interpretation", {})
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
            if interpretation.get("status") != "PASS":
                gaps.append(
                    self.issue(
                        "time_semantics.contract_interpretation.status",
                        "review of contract prose is required",
                    )
                )
            for dotted in paths:
                supplied_hash = interpretation.get("source_text_sha256", {}).get(
                    dotted
                )
                if not supplied_hash:
                    gaps.append(
                        self.issue(
                            f"time_semantics.contract_interpretation.{dotted}",
                            "hash-bound interpretation is missing",
                        )
                    )
                elif supplied_hash != sha_text(path_get(contract, dotted)):
                    failures.append(
                        self.issue(
                            f"time_semantics.contract_interpretation.{dotted}",
                            "semantic interpretation is not hash-bound",
                        )
                    )
            resolved = interpretation.get("resolved", {})
            if not isinstance(resolved, dict):
                gaps.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved",
                        "structured interpretation is required",
                    )
                )
                resolved = {}
            if not resolved.get("availability_comparison"):
                gaps.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.availability_comparison",
                        "LT/LE interpretation is required",
                    )
                )
            elif (
                resolved.get("availability_comparison")
                != semantics.get("availability_comparison")
            ):
                failures.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.availability_comparison",
                        "resolved comparison conflicts with the executed predicate",
                    )
                )
            if resolved.get("revision_policy_status") != "PASS":
                gaps.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.revision_policy_status",
                        "the frozen revision-retention policy must be reviewed as PIT-safe",
                    )
                )
            if resolved.get("universe_policy_status") != "PASS":
                gaps.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.universe_policy_status",
                        "the frozen universe rule must be reviewed as point-in-time safe",
                    )
                )
            resolved_history_mode = resolved.get("population_history_mode")
            if not resolved_history_mode:
                gaps.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.population_history_mode",
                        "a structured PIT population-history interpretation is required",
                    )
                )
            elif resolved_history_mode != population.get(
                "universe_history_mode"
            ):
                failures.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.population_history_mode",
                        "resolved universe history mode conflicts with the executed population evidence",
                        expected=population.get("universe_history_mode"),
                        actual=resolved_history_mode,
                    )
                )

        label_bindings = label.get("contract_bindings", {})
        expected_policy_hashes = {
            "formula_sha256": sha_text(view.get("formula")),
            "neutralization_rule_sha256": sha_text(
                view.get("neutralization_rule")
            ),
            "corporate_action_rule_sha256": sha_text(
                view.get("corporate_action_rule")
            ),
            "overlap_rule_sha256": sha_text(view.get("overlap_rule")),
            "purge_rule_sha256": sha_text(view.get("purge_rule")),
            "purge_embargo_rule_sha256": sha_text(
                view.get("purge_embargo_rule")
            ),
            "embargo_duration_sha256": sha_text(view.get("embargo_duration")),
            "embargo_basis_sha256": sha_text(view.get("embargo_basis")),
        }
        if not isinstance(label_bindings, dict):
            gaps.append(
                self.issue(
                    "label_definition.contract_bindings",
                    "target, purge, and embargo bindings are required",
                )
            )
            label_bindings = {}
        for key, expected_hash in expected_policy_hashes.items():
            supplied_hash = label_bindings.get(key)
            if not supplied_hash:
                gaps.append(
                    self.issue(
                        f"label_definition.contract_bindings.{key}",
                        "contract-policy hash is required",
                    )
                )
            elif supplied_hash != expected_hash:
                failures.append(
                    self.issue(
                        f"label_definition.contract_bindings.{key}",
                        "label artifact conflicts with the frozen contract policy",
                        expected=expected_hash,
                        actual=supplied_hash,
                    )
                )

        schedule = self.docs.get("label_schedule", {})
        schedule_receipt = None
        rule_hashes = {
            "prediction_time": (
                sha_text(view.get("prediction_time_rule"))
                if view.get("prediction_time_rule")
                else None
            ),
            "execution_time": (
                sha_text(view.get("execution_time_rule"))
                if view.get("execution_time_rule")
                else None
            ),
            "label_start": (
                sha_text(view.get("label_start_rule"))
                if view.get("label_start_rule")
                else None
            ),
            "label_end": (
                sha_text(view.get("label_end_rule"))
                if view.get("label_end_rule")
                else None
            ),
            "holding_period": (
                sha_text(view.get("holding_period_rule"))
                if view.get("holding_period_rule")
                else None
            ),
        }
        rule_bundle_hash = sha_value(rule_hashes)
        if not isinstance(schedule, dict) or not schedule:
            gaps.append(
                self.issue(
                    "label_schedule",
                    "a separate frozen executable pit_label_schedule_v1 is required",
                )
            )
            schedule = {}
        else:
            schedule_receipt = schedule.get("receipt_hash")
            schedule_allowed = {
                "schema_version",
                "schedule_id",
                "version",
                "mode",
                "contract_binding",
                "label_binding",
                "resolver",
                "semantic_review",
                "receipt_hash",
            }
            for key in sorted(set(schedule) - schedule_allowed):
                failures.append(
                    self.issue(
                        f"label_schedule.{key}",
                        "unknown v1 field is forbidden",
                    )
                )
            mode = schedule.get("mode")
            if mode not in {
                "FROZEN_EXACT_INTERVAL_SET",
                "SESSION_CLOSE_OFFSETS",
            }:
                failures.append(
                    self.issue(
                        "label_schedule.mode",
                        "unsupported label-schedule mode",
                    )
                )

            contract_binding = schedule.get("contract_binding")
            if not isinstance(contract_binding, dict):
                gaps.append(
                    self.issue(
                        "label_schedule.contract_binding",
                        "frozen research-contract binding is required",
                    )
                )
                contract_binding = {}
            else:
                allowed = {
                    "adapter",
                    "contract_id",
                    "contract_canonical_hash",
                    "rule_hashes",
                    "rule_bundle_sha256",
                }
                for key in sorted(set(contract_binding) - allowed):
                    failures.append(
                        self.issue(
                            f"label_schedule.contract_binding.{key}",
                            "unknown v1 field is forbidden",
                        )
                    )
            contract_bindings = {
                "adapter": view.get("adapter"),
                "contract_id": view.get("contract_id"),
                "contract_canonical_hash": view.get("canonical_hash"),
                "rule_bundle_sha256": rule_bundle_hash,
            }
            for key, expected in contract_bindings.items():
                actual = contract_binding.get(key)
                if not actual or not expected:
                    gaps.append(
                        self.issue(
                            f"label_schedule.contract_binding.{key}",
                            "contract binding is required",
                        )
                    )
                elif actual != expected:
                    failures.append(
                        self.issue(
                            f"label_schedule.contract_binding.{key}",
                            "schedule conflicts with the frozen research contract",
                            expected=expected,
                            actual=actual,
                        )
                    )
            bound_rule_hashes = contract_binding.get("rule_hashes")
            if not isinstance(bound_rule_hashes, dict):
                gaps.append(
                    self.issue(
                        "label_schedule.contract_binding.rule_hashes",
                        "all executable contract-rule hashes are required",
                    )
                )
                bound_rule_hashes = {}
            else:
                allowed = {
                    "prediction_time",
                    "execution_time",
                    "label_start",
                    "label_end",
                    "holding_period",
                }
                for key in sorted(set(bound_rule_hashes) - allowed):
                    failures.append(
                        self.issue(
                            f"label_schedule.contract_binding.rule_hashes.{key}",
                            "unknown v1 rule is forbidden",
                        )
                    )
            for key, expected_hash in rule_hashes.items():
                actual_hash = bound_rule_hashes.get(key)
                if not actual_hash or not expected_hash:
                    gaps.append(
                        self.issue(
                            f"label_schedule.contract_binding.rule_hashes.{key}",
                            "frozen contract-rule hash is required",
                        )
                    )
                elif actual_hash != expected_hash:
                    failures.append(
                        self.issue(
                            f"label_schedule.contract_binding.rule_hashes.{key}",
                            "executable schedule conflicts with the frozen contract rule",
                            expected=expected_hash,
                            actual=actual_hash,
                        )
                    )

            label_binding = schedule.get("label_binding")
            if not isinstance(label_binding, dict):
                gaps.append(
                    self.issue(
                        "label_schedule.label_binding",
                        "label identity and specification binding are required",
                    )
                )
                label_binding = {}
            else:
                allowed = {
                    "label_id",
                    "label_spec_version",
                    "label_spec_hash",
                }
                for key in sorted(set(label_binding) - allowed):
                    failures.append(
                        self.issue(
                            f"label_schedule.label_binding.{key}",
                            "unknown v1 field is forbidden",
                        )
                    )
            for key, expected in {
                "label_id": label.get("label_id"),
                "label_spec_version": label.get("label_spec_version"),
                "label_spec_hash": label.get("label_spec_hash"),
            }.items():
                actual = label_binding.get(key)
                if not actual or not expected:
                    gaps.append(
                        self.issue(
                            f"label_schedule.label_binding.{key}",
                            "label binding is required",
                        )
                    )
                elif actual != expected:
                    failures.append(
                        self.issue(
                            f"label_schedule.label_binding.{key}",
                            "schedule binds a different label specification",
                            expected=expected,
                            actual=actual,
                        )
                    )

            resolver = schedule.get("resolver")
            if not isinstance(resolver, dict):
                gaps.append(
                    self.issue(
                        "label_schedule.resolver",
                        "an executable resolver is required",
                    )
                )
                resolver = {}
            if mode == "FROZEN_EXACT_INTERVAL_SET":
                allowed = {
                    "interval_authority_id",
                    "interval_authority_version",
                    "interval_authority_artifact_sha256",
                    "interval_authority_receipt_hash",
                }
                for key in sorted(set(resolver) - allowed):
                    failures.append(
                        self.issue(
                            f"label_schedule.resolver.{key}",
                            "unknown or cross-mode exact resolver field is forbidden",
                        )
                    )
                forbidden = {
                    "calendar_id",
                    "calendar_version",
                    "calendar_artifact_sha256",
                    "timezone",
                    "base_session_field",
                    "prediction_offset_from_session_open_seconds",
                    "execution_offset_sessions",
                    "execution_offset_from_session_open_seconds",
                    "start_offset_sessions",
                    "horizon_sessions",
                }
                for key in sorted(forbidden & set(resolver)):
                    failures.append(
                        self.issue(
                            f"label_schedule.resolver.{key}",
                            "exact-interval mode forbids session-offset fields",
                        )
                    )
                interval_authority = self.docs.get(
                    "label_interval_authority", {}
                )
                if not isinstance(interval_authority, dict) or not interval_authority:
                    gaps.append(
                        self.issue(
                            "request.artifacts.label_interval_authority",
                            "exact-interval mode requires a separately hash-bound interval authority",
                        )
                    )
                    interval_authority = {}
                if self.execution_boundary == "PRODUCTION_CLI":
                    authority_hash = self.hashes.get(
                        "label_interval_authority"
                    )
                    if not self.trusted_interval_authority_sha256:
                        gaps.append(
                            self.issue(
                                "runtime.trusted_interval_authority_sha256",
                                "production qualification requires a request-external interval-authority trust anchor",
                            )
                        )
                    elif authority_hash not in self.trusted_interval_authority_sha256:
                        failures.append(
                            self.issue(
                                "runtime.trusted_interval_authority_sha256",
                                "interval-authority artifact is not trusted by the runtime",
                            )
                        )
                authority_bindings = {
                    "interval_authority_id": interval_authority.get(
                        "authority_id"
                    ),
                    "interval_authority_version": interval_authority.get(
                        "version"
                    ),
                    "interval_authority_artifact_sha256": self.hashes.get(
                        "label_interval_authority"
                    ),
                    "interval_authority_receipt_hash": interval_authority.get(
                        "receipt_hash"
                    ),
                }
                for key, expected in authority_bindings.items():
                    actual = resolver.get(key)
                    if actual is None or expected is None:
                        gaps.append(
                            self.issue(
                                f"label_schedule.resolver.{key}",
                                "independent interval-authority binding is required",
                            )
                        )
                    elif actual != expected:
                        failures.append(
                            self.issue(
                                f"label_schedule.resolver.{key}",
                                "schedule binds a different interval authority",
                            )
                        )
                count = interval_authority.get("expected_sample_count")
                if not nonnegative_int(count):
                    failures.append(
                        self.issue(
                            "label_interval_authority.expected_sample_count",
                            "must be a non-negative non-boolean integer",
                        )
                    )
                for key in (
                    "expected_interval_set_sha256",
                    "population_manifest_sha256",
                ):
                    if not is_sha(interval_authority.get(key)):
                        failures.append(
                            self.issue(
                                f"label_interval_authority.{key}",
                                "must be lowercase SHA-256",
                            )
                        )
                if (
                    is_sha(interval_authority.get("population_manifest_sha256"))
                    and interval_authority.get("population_manifest_sha256")
                    != self.hashes.get("population_manifest")
                ):
                    failures.append(
                        self.issue(
                            "label_interval_authority.population_manifest_sha256",
                            "interval authority was resolved against a different population manifest",
                        )
                    )
                generator = interval_authority.get("generator")
                if not isinstance(generator, dict):
                    gaps.append(
                        self.issue(
                            "label_interval_authority.generator",
                            "independent generator provenance is required",
                        )
                    )
                    generator = {}
                for key in (
                    "code_sha256",
                    "parameters_sha256",
                    "input_snapshot_sha256",
                ):
                    if not is_sha(generator.get(key)):
                        failures.append(
                            self.issue(
                                f"label_interval_authority.generator.{key}",
                                "must be lowercase SHA-256",
                            )
                        )
                if (
                    is_sha(generator.get("input_snapshot_sha256"))
                    and generator.get("input_snapshot_sha256")
                    == self.hashes.get("data")
                ):
                    failures.append(
                        self.issue(
                            "label_interval_authority.generator.input_snapshot_sha256",
                            "the audited training rows cannot be their own interval authority",
                        )
                    )
                if not isinstance(generator.get("source_locator"), str) or not generator[
                    "source_locator"
                ].strip():
                    gaps.append(
                        self.issue(
                            "label_interval_authority.generator.source_locator",
                            "independent generator provenance is required",
                        )
                    )
            elif mode == "SESSION_CLOSE_OFFSETS":
                allowed = {
                    "calendar_id",
                    "calendar_version",
                    "calendar_artifact_sha256",
                    "timezone",
                    "base_session_field",
                    "prediction_offset_from_session_open_seconds",
                    "execution_offset_sessions",
                    "execution_offset_from_session_open_seconds",
                    "start_offset_sessions",
                    "horizon_sessions",
                }
                for key in sorted(set(resolver) - allowed):
                    failures.append(
                        self.issue(
                            f"label_schedule.resolver.{key}",
                            "unknown or cross-mode session resolver field is forbidden",
                        )
                    )
                forbidden = {
                    "expected_sample_count",
                    "expected_interval_set_sha256",
                    "interval_authority_id",
                    "interval_authority_version",
                    "interval_authority_artifact_sha256",
                    "interval_authority_receipt_hash",
                }
                for key in sorted(forbidden & set(resolver)):
                    failures.append(
                        self.issue(
                            f"label_schedule.resolver.{key}",
                            "session-offset mode forbids exact-interval fields",
                        )
                    )
                for key in (
                    "prediction_offset_from_session_open_seconds",
                    "execution_offset_sessions",
                    "execution_offset_from_session_open_seconds",
                    "start_offset_sessions",
                    "horizon_sessions",
                ):
                    value = resolver.get(key)
                    if (
                        not nonnegative_int(value)
                        or key == "horizon_sessions"
                        and value < 1
                    ):
                        failures.append(
                            self.issue(
                                f"label_schedule.resolver.{key}",
                                "must be a non-negative non-boolean integer and horizon must be positive",
                            )
                        )
                if resolver.get("base_session_field") != "calendar_session_id":
                    failures.append(
                        self.issue(
                            "label_schedule.resolver.base_session_field",
                            "must equal calendar_session_id",
                        )
                    )
                for key in (
                    "calendar_artifact_sha256",
                ):
                    if not is_sha(resolver.get(key)):
                        failures.append(
                            self.issue(
                                f"label_schedule.resolver.{key}",
                                "must be lowercase SHA-256",
                            )
                        )

            review = schedule.get("semantic_review")
            if not isinstance(review, dict):
                gaps.append(
                    self.issue(
                        "label_schedule.semantic_review",
                        "an accountable semantic-review trust root is required",
                    )
                )
            else:
                allowed = {
                    "trust_root_kind",
                    "scope",
                    "decision",
                    "reviewer_id",
                    "reviewer_authority",
                    "reviewed_at",
                    "contract_rule_bundle_sha256",
                    "normalized_resolver_sha256",
                    "excluded_inputs",
                    "receipt_hash",
                }
                for key in sorted(set(review) - allowed):
                    failures.append(
                        self.issue(
                            f"label_schedule.semantic_review.{key}",
                            "unknown v1 field is forbidden",
                        )
                    )
                for key in (
                    "reviewer_id",
                    "reviewer_authority",
                    "reviewed_at",
                ):
                    if not isinstance(review.get(key), str) or not review[key].strip():
                        gaps.append(
                            self.issue(
                                f"label_schedule.semantic_review.{key}",
                                "non-empty review provenance is required",
                            )
                        )
                if review.get("trust_root_kind") != "HUMAN_SEMANTIC_REVIEW":
                    failures.append(
                        self.issue(
                            "label_schedule.semantic_review.trust_root_kind",
                            "must explicitly declare HUMAN_SEMANTIC_REVIEW",
                        )
                    )
                if (
                    review.get("scope")
                    != "CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY"
                ):
                    failures.append(
                        self.issue(
                            "label_schedule.semantic_review.scope",
                            "review scope must be limited to contract prose and the normalized schedule",
                        )
                    )
                decision = review.get("decision")
                if decision in {None, "AMBIGUOUS"}:
                    gaps.append(
                        self.issue(
                            "label_schedule.semantic_review.decision",
                            "semantic review must be APPROVED",
                        )
                    )
                elif decision != "APPROVED":
                    failures.append(
                        self.issue(
                            "label_schedule.semantic_review.decision",
                            "semantic review explicitly rejected the schedule or uses an unsupported decision",
                        )
                    )
                expected_review_bindings = {
                    "contract_rule_bundle_sha256": rule_bundle_hash,
                    "normalized_resolver_sha256": sha_value(resolver),
                }
                for key, expected in expected_review_bindings.items():
                    actual = review.get(key)
                    if not actual or not expected:
                        gaps.append(
                            self.issue(
                                f"label_schedule.semantic_review.{key}",
                                "semantic-review binding is required",
                            )
                        )
                    elif actual != expected:
                        failures.append(
                            self.issue(
                                f"label_schedule.semantic_review.{key}",
                                "semantic review does not bind the audited schedule",
                            )
                        )
                excluded = review.get("excluded_inputs")
                required_exclusions = {
                    "data_rows",
                    "audit_status",
                    "backtest_results",
                }
                if not isinstance(excluded, list):
                    gaps.append(
                        self.issue(
                            "label_schedule.semantic_review.excluded_inputs",
                            "review exclusions are required",
                        )
                    )
                elif not required_exclusions.issubset(set(excluded)):
                    failures.append(
                        self.issue(
                            "label_schedule.semantic_review.excluded_inputs",
                            "review must exclude training rows, audit results, and backtest outcomes",
                        )
                    )
                review_receipt = review.get("receipt_hash")
                if not review_receipt:
                    gaps.append(
                        self.issue(
                            "label_schedule.semantic_review.receipt_hash",
                            "semantic-review receipt is required",
                        )
                    )
                elif not is_sha(review_receipt) or review_receipt != sha_value(
                    semantic_review_content(review)
                ):
                    failures.append(
                        self.issue(
                            "label_schedule.semantic_review.receipt_hash",
                            "semantic-review receipt hash mismatch",
                        )
                    )
                if self.execution_boundary == "PRODUCTION_CLI":
                    if not self.trusted_semantic_review_receipt_sha256:
                        gaps.append(
                            self.issue(
                                "runtime.trusted_semantic_review_receipt_sha256",
                                "production qualification requires a request-external anchor for this exact semantic-review receipt",
                            )
                        )
                    elif (
                        review_receipt
                        not in self.trusted_semantic_review_receipt_sha256
                    ):
                        failures.append(
                            self.issue(
                                "runtime.trusted_semantic_review_receipt_sha256",
                                "semantic-review receipt is not trusted by the runtime",
                            )
                        )
                try:
                    reviewed_at = dt(review.get("reviewed_at"))
                    run_at = dt(self.request.get("run_at"))
                    if reviewed_at > run_at:
                        failures.append(
                            self.issue(
                                "label_schedule.semantic_review.reviewed_at",
                                "semantic review cannot occur after the audit run",
                            )
                        )
                    if view.get("adapter") == "quant_contract_v2":
                        frozen_at = dt(view.get("frozen_at"))
                        if reviewed_at < frozen_at:
                            failures.append(
                                self.issue(
                                    "label_schedule.semantic_review.reviewed_at",
                                    "semantic review cannot precede the frozen contract it binds",
                                )
                            )
                        if run_at < frozen_at:
                            failures.append(
                                self.issue(
                                    "request.run_at",
                                    "audit run cannot precede the frozen contract",
                                )
                            )
                except ValueError as error:
                    failures.append(
                        self.issue(
                            "label_schedule.semantic_review.reviewed_at",
                            str(error),
                        )
                    )
                    reviewed_at = None
                review_authority = self.docs.get("review_authority", {})
                if self.execution_boundary == "PRODUCTION_CLI":
                    authority_hash = self.hashes.get("review_authority")
                    if not self.trusted_review_authority_sha256:
                        gaps.append(
                            self.issue(
                                "runtime.trusted_review_authority_sha256",
                                "production qualification requires a request-external review-authority trust anchor",
                            )
                        )
                    elif authority_hash not in self.trusted_review_authority_sha256:
                        failures.append(
                            self.issue(
                                "runtime.trusted_review_authority_sha256",
                                "review-authority artifact is not trusted by the runtime",
                            )
                        )
                reviewers = (
                    review_authority.get("reviewers", [])
                    if isinstance(review_authority, dict)
                    else []
                )
                if not isinstance(reviewers, list):
                    failures.append(
                        self.issue(
                            "review_authority.reviewers",
                            "must be a list of authorized reviewers",
                        )
                    )
                    reviewers = []
                matching_reviewers = [
                    item
                    for item in reviewers
                    if isinstance(item, dict)
                    and item.get("reviewer_id") == review.get("reviewer_id")
                ]
                if not matching_reviewers:
                    gaps.append(
                        self.issue(
                            "label_schedule.semantic_review.reviewer_id",
                            "reviewer is not present in the independent authority artifact",
                        )
                    )
                else:
                    authorization = matching_reviewers[0]
                    if review.get("reviewer_authority") != review_authority.get(
                        "authority_id"
                    ):
                        failures.append(
                            self.issue(
                                "label_schedule.semantic_review.reviewer_authority",
                                "review cites a different authority",
                            )
                        )
                    allowed_scopes = authorization.get("allowed_scopes")
                    if (
                        not isinstance(allowed_scopes, list)
                        or review.get("scope") not in allowed_scopes
                    ):
                        failures.append(
                            self.issue(
                                "label_schedule.semantic_review.scope",
                                "reviewer is not authorized for this semantic-review scope",
                            )
                        )
                    try:
                        valid_from = dt(authorization.get("valid_from"))
                        valid_to = dt(authorization.get("valid_to"))
                        if (
                            reviewed_at is not None
                            and not valid_from <= reviewed_at < valid_to
                        ):
                            failures.append(
                                self.issue(
                                    "label_schedule.semantic_review.reviewed_at",
                                    "review occurred outside the reviewer authorization interval",
                                )
                            )
                    except ValueError as error:
                        failures.append(
                            self.issue(
                                "review_authority.reviewers",
                                f"invalid authorization interval: {error}",
                            )
                        )

        if view.get("adapter") == "quant_contract_v2":
            interpretation = semantics.get("contract_interpretation", {})
            resolved = (
                interpretation.get("resolved", {})
                if isinstance(interpretation, dict)
                else {}
            )
            resolved_schedule_receipt = (
                resolved.get("label_schedule_receipt_hash")
                if isinstance(resolved, dict)
                else None
            )
            if not resolved_schedule_receipt:
                gaps.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.label_schedule_receipt_hash",
                        "resolved interpretation must bind the executable label schedule",
                    )
                )
            elif schedule_receipt and resolved_schedule_receipt != schedule_receipt:
                failures.append(
                    self.issue(
                        "time_semantics.contract_interpretation.resolved.label_schedule_receipt_hash",
                        "resolved label schedule receipt mismatch",
                    )
                )

        matrix_manifest = self.matrix_manifest()
        if matrix_manifest:
            layout = matrix_manifest.get("layout", {})
            feature_axis = matrix_manifest.get("feature_axis", {})
            label_axis = matrix_manifest.get("label_axis", {})
            mode = layout.get("mode")
            rule = layout.get("applicability_rule")
            if mode == "SPARSE_EXPLICIT":
                gaps.append(
                    self.issue(
                        "matrix_manifest.layout.mode",
                        "SPARSE_EXPLICIT needs a complete QRC-bound applicability/cell-set proof; v1 remains diagnostic",
                    )
                )
            elif mode != "RECTANGULAR":
                failures.append(
                    self.issue("matrix_manifest.layout.mode", "unsupported layout mode")
                )
            if mode == "RECTANGULAR" and (
                rule != "ALL_FEATURES_APPLY_TO_EVERY_POPULATION_KEY"
                or layout.get("applicability_rule_sha256") != sha_text(rule)
            ):
                failures.append(
                    self.issue(
                        "matrix_manifest.layout",
                        "rectangular applicability rule/digest is invalid",
                    )
                )
            if mode == "RECTANGULAR":
                feature_names = feature_axis.get("features", [])
                dictionary_features = dictionary.get("features", {})
                feature_semantics_hash = None
                if isinstance(feature_names, list) and isinstance(
                    dictionary_features, dict
                ):
                    feature_semantics_hash = sha_value(
                        {
                            name: dictionary_features.get(name)
                            for name in feature_names
                            if isinstance(name, str)
                        }
                    )
                feature_hash = sha_value(
                    feature_spec_binding_payload(matrix_manifest)
                )
                feature_bindings = {
                    "feature_spec_version": (
                        feature_axis.get("feature_spec_version"),
                        view.get("feature_spec_version"),
                    ),
                    "feature_semantics_sha256": (
                        feature_axis.get("feature_semantics_sha256"),
                        feature_semantics_hash,
                    ),
                    "feature_spec_hash": (
                        feature_axis.get("feature_spec_hash"),
                        feature_hash,
                    ),
                    "contract_feature_spec_hash": (
                        view.get("feature_spec_hash"),
                        feature_hash,
                    ),
                }
                for key, (actual, expected) in feature_bindings.items():
                    if not actual or not expected:
                        gaps.append(
                            self.issue(f"matrix_binding.{key}", "binding is required")
                        )
                    elif actual != expected:
                        failures.append(
                            self.issue(f"matrix_binding.{key}", "binding mismatch")
                        )
            rule_bindings = {
                "label_id": (label_axis.get("label_id"), label.get("label_id")),
                "label_spec_version": (
                    label_axis.get("label_spec_version"),
                    label.get("label_spec_version"),
                ),
                "label_spec_hash": (
                    label_axis.get("label_spec_hash"),
                    label.get("label_spec_hash"),
                ),
                "label_schedule_id": (
                    label_axis.get("label_schedule_id"),
                    schedule.get("schedule_id"),
                ),
                "label_schedule_version": (
                    label_axis.get("label_schedule_version"),
                    schedule.get("version"),
                ),
                "label_schedule_receipt_hash": (
                    label_axis.get("label_schedule_receipt_hash"),
                    schedule_receipt,
                ),
                "prediction_time_rule_sha256": (
                    label_axis.get("prediction_time_rule_sha256"),
                    sha_text(view["prediction_time_rule"])
                    if view.get("prediction_time_rule")
                    else None,
                ),
                "execution_time_rule_sha256": (
                    label_axis.get("execution_time_rule_sha256"),
                    sha_text(view["execution_time_rule"])
                    if view.get("execution_time_rule")
                    else None,
                ),
                "label_start_rule_sha256": (
                    label_axis.get("label_start_rule_sha256"),
                    sha_text(view["label_start_rule"])
                    if view.get("label_start_rule")
                    else None,
                ),
                "label_end_rule_sha256": (
                    label_axis.get("label_end_rule_sha256"),
                    sha_text(view["label_end_rule"])
                    if view.get("label_end_rule")
                    else None,
                ),
            }
            for key, (actual, expected) in rule_bindings.items():
                if not actual or not expected:
                    gaps.append(self.issue(f"matrix_binding.{key}", "binding is required"))
                elif actual != expected:
                    failures.append(
                        self.issue(f"matrix_binding.{key}", "binding mismatch")
                    )

        self.add(
            "I002",
            failures,
            gaps,
            self.evidence(
                {
                    "contract_id": view["contract_id"],
                    "contract_canonical_hash": view["canonical_hash"],
                    "contract_file_sha256": self.hashes.get("research_contract"),
                    "validation_receipt_sha256": self.hashes.get(
                        "contract_validation"
                    ),
                    "qrc_strict_revalidation": self.docs.get(
                        "qrc_revalidation"
                    ),
                    "label_spec_hash": label.get("label_spec_hash"),
                    "label_schedule_id": schedule.get("schedule_id"),
                    "label_schedule_version": schedule.get("version"),
                    "label_schedule_receipt_hash": schedule_receipt,
                    "matrix_feature_spec_hash": path_get(
                        matrix_manifest, "feature_axis.feature_spec_hash"
                    ),
                    "matrix_layout_mode": path_get(
                        matrix_manifest, "layout.mode"
                    ),
                }
            ),
            metrics={"used_features": len({r.get("feature_name") for r in self.rows})},
            repair=(
                "Restore the exact frozen source, label, universe, calendar, and time bindings. "
                "Any intended change must use a quant-research-contract Change Request."
            ),
        )

    def check_s001_schema(self) -> None:
        failures, gaps = [], []
        schema = self.docs.get("schema", {})
        dictionary = self.docs.get("dictionary", {})
        headers = self.docs.get("data_headers", [])
        columns = schema.get("columns", {})
        fields = dictionary.get("fields", {})
        features = dictionary.get("features", {})
        if schema.get("schema_version") != "pit_evidence_schema_v1":
            failures.append(self.issue("schema.schema_version", "unsupported schema"))
        if set(headers) != set(FIELD_ROLES) or set(headers) != set(columns):
            failures.append(
                self.issue(
                    "data.header",
                    "CSV, schema, and fixed v1 columns must agree exactly",
                    missing=sorted(set(FIELD_ROLES) - set(headers)),
                    extra=sorted(set(headers) - set(FIELD_ROLES)),
                )
            )
        if schema.get("primary_key") != ["row_id"]:
            failures.append(
                self.issue("schema.primary_key", "must equal [row_id]")
            )
        if schema.get("grain") != [
            "security_id",
            "prediction_time",
            "feature_name",
        ]:
            failures.append(
                self.issue(
                    "schema.grain",
                    "must bind security_id, prediction_time, and feature_name",
                )
            )
        if set(fields) != set(headers):
            failures.append(
                self.issue(
                    "dictionary.fields",
                    "every consumed column needs one exact dictionary entry",
                    missing=sorted(set(headers) - set(fields)),
                    extra=sorted(set(fields) - set(headers)),
                )
            )
        for field, expected_role in FIELD_ROLES.items():
            entry = fields.get(field, {})
            if entry.get("semantic_role") != expected_role:
                failures.append(
                    self.issue(
                        f"dictionary.fields.{field}.semantic_role",
                        "exact semantic role mismatch; proxy substitution is forbidden",
                        expected=expected_role,
                        actual=entry.get("semantic_role"),
                    )
                )
            for key in ("definition", "source_locator"):
                if not str(entry.get(key, "")).strip():
                    gaps.append(
                        self.issue(
                            f"dictionary.fields.{field}.{key}",
                            "semantic evidence is missing",
                        )
                    )
        for field in ("universe_effective_to", "identifier_valid_to"):
            policy = path_get(fields, f"{field}.null_semantics")
            if policy is None:
                gaps.append(
                    self.issue(
                        f"dictionary.fields.{field}.null_semantics",
                        "structured end-time null semantics are required",
                    )
                )
            elif policy not in NULL_END_POLICIES:
                failures.append(
                    self.issue(
                        f"dictionary.fields.{field}.null_semantics",
                        f"must be one of {sorted(NULL_END_POLICIES)}",
                    )
                )
        for key in (
            "dictionary_id",
            "version",
            "source_uri",
            "semantic_source_document_sha256",
        ):
            if not dictionary.get(key):
                gaps.append(
                    self.issue(f"dictionary.{key}", "provenance is required")
                )
        if dictionary.get("semantic_source_document_sha256") and not is_sha(
            dictionary["semantic_source_document_sha256"]
        ):
            failures.append(
                self.issue(
                    "dictionary.semantic_source_document_sha256",
                    "must be lowercase SHA-256",
                )
            )
        dictionary_meta = self.meta.get("dictionary", {})
        for key in ("dictionary_id", "version", "source_uri"):
            if dictionary_meta.get(key) != dictionary.get(key):
                failures.append(
                    self.issue(
                        f"request.artifacts.dictionary.{key}",
                        "request metadata does not match the dictionary",
                        expected=dictionary.get(key),
                        actual=dictionary_meta.get(key),
                    )
                )
        audited_features = self.audited_feature_names()
        for name in audited_features:
            entry = features.get(name)
            if not isinstance(entry, dict):
                gaps.append(
                    self.issue(
                        f"dictionary.features.{name}",
                        "exact feature semantics are missing",
                    )
                )
                continue
            for key in (
                "definition",
                "source_locator",
                "use",
                "event_time_policy",
                "unit",
                "basis",
                "grain",
                "null_semantics",
            ):
                if not str(entry.get(key, "")).strip():
                    gaps.append(
                        self.issue(
                            f"dictionary.features.{name}.{key}",
                            "feature-semantic evidence is missing",
                        )
                    )
            if entry.get("use") not in {
                "PRICE_LEVEL",
                "RETURN",
                "VOLUME",
                "SHARES",
                "OTHER",
            }:
                failures.append(
                    self.issue(f"dictionary.features.{name}.use", "unknown use")
                )
            if entry.get("event_time_policy") not in {
                "OBSERVED_BY_PREDICTION",
                "KNOWN_FUTURE_OBJECT",
            }:
                failures.append(
                    self.issue(
                        f"dictionary.features.{name}.event_time_policy",
                        "unknown event-time policy",
                    )
                )
        self.add(
            "S001",
            failures,
            gaps,
            self.evidence(
                {
                    "schema_sha256": self.hashes.get("schema"),
                    "field_count": len(fields),
                    "feature_locators": {
                        name: features.get(name, {}).get("source_locator")
                        for name in audited_features
                    },
                }
            ),
            metrics={
                "columns": len(headers),
                "features": len(features),
                "matrix_features": len(self.matrix_feature_names()),
            },
            repair=(
                "Bind every consumed field and feature to its exact documented meaning, version, "
                "and locator. Never substitute a similarly named timestamp."
            ),
        )

    def check_t001_time_roles(self) -> None:
        failures, gaps = [], []
        semantics = self.docs.get("time_semantics", {})
        roles = semantics.get("roles", {})
        if semantics.get("schema_version") != "pit_time_semantics_v1":
            failures.append(
                self.issue("time_semantics.schema_version", "unsupported schema")
            )
        timezone = semantics.get("timezone")
        try:
            ZoneInfo(timezone)
        except (TypeError, ZoneInfoNotFoundError):
            failures.append(
                self.issue(
                    "time_semantics.timezone", "valid IANA timezone is required"
                )
            )
        if not semantics.get("tzdb_version"):
            gaps.append(
                self.issue(
                    "time_semantics.tzdb_version", "tzdb version is required"
                )
            )
        if semantics.get("availability_comparison") not in {"LT", "LE"}:
            failures.append(
                self.issue(
                    "time_semantics.availability_comparison", "must be LT or LE"
                )
            )
        mapped = []
        for role, field in ROLE_FIELDS.items():
            entry = roles.get(role, {})
            if entry.get("field") != field:
                failures.append(
                    self.issue(
                        f"time_semantics.roles.{role}.field",
                        "role must bind its exact v1 field",
                        expected=field,
                        actual=entry.get("field"),
                    )
                )
            mapped.append(entry.get("field"))
            for key in ("definition", "source_locator"):
                if not str(entry.get(key, "")).strip():
                    gaps.append(
                        self.issue(
                            f"time_semantics.roles.{role}.{key}",
                            "time-role evidence is missing",
                        )
                    )
        if len(mapped) != len(set(mapped)):
            failures.append(
                self.issue(
                    "time_semantics.roles",
                    "distinct roles may not alias one consumed field",
                )
            )

        self.times = []
        for row in self.rows:
            parsed: dict[str, datetime | None] = {}
            for field in TIME_FIELDS:
                raw = row.get(field, "")
                if not raw and field in OPTIONAL_TIMES:
                    parsed[field] = None
                    continue
                try:
                    parsed[field] = dt(raw)
                except ValueError as error:
                    parsed[field] = None
                    failures.append(
                        self.issue(f"{locator(row)}.{field}", str(error))
                    )
            self.times.append(parsed)
        self.add(
            "T001",
            failures,
            gaps,
            self.evidence(
                {
                    "time_semantics_sha256": self.hashes.get("time_semantics"),
                    "timezone": timezone,
                    "tzdb_version": semantics.get("tzdb_version"),
                    "role_locators": {
                        role: roles.get(role, {}).get("source_locator")
                        for role in ROLE_FIELDS
                    },
                }
            ),
            metrics={"timestamp_cells": len(self.rows) * len(TIME_FIELDS)},
            repair=(
                "Provide offset-aware timestamps and separate sourced roles for occurrence, "
                "publication, availability, ingestion, execution, revision, and label times."
            ),
        )

    def check_t002_availability(self) -> None:
        failures, gaps = [], []
        op = self.docs.get("time_semantics", {}).get("availability_comparison")
        claim = self.request.get("claim")
        features = self.docs.get("dictionary", {}).get("features", {})
        market_count = system_count = causal_count = 0
        for row, times in zip(self.rows, self.times):
            prediction = times.get("prediction_time")
            policy = features.get(row.get("feature_name"), {}).get(
                "event_time_policy"
            )
            market_fields = ["published_time", "vendor_available_time"]
            system_fields = market_fields + ["ingested_time", "parse_ready_time"]
            needed = system_fields if claim == "SYSTEM_REPLAYABLE" else market_fields
            if prediction is None or any(times.get(key) is None for key in needed):
                gaps.append(
                    self.issue(locator(row), "availability predicate is incomplete")
                )
                continue
            causal_fields = [
                "published_time",
                "vendor_available_time",
                "ingested_time",
                "parse_ready_time",
            ]
            if any(times.get(key) is None for key in causal_fields):
                gaps.append(
                    self.issue(
                        locator(row),
                        "availability-pipeline causal ordering is incomplete",
                    )
                )
            else:
                inversions = [
                    (left, right)
                    for left, right in zip(causal_fields, causal_fields[1:])
                    if times[left] > times[right]
                ]
                if (
                    policy == "OBSERVED_BY_PREDICTION"
                    and times.get("event_time") is not None
                    and times["event_time"] > times["published_time"]
                ):
                    inversions.insert(0, ("event_time", "published_time"))
                if inversions:
                    failures.append(
                        self.issue(
                            locator(row),
                            "availability-pipeline timestamps are causally inverted",
                            inverted_edges=[
                                f"{left}>{right}" for left, right in inversions
                            ],
                        )
                    )
                else:
                    causal_count += 1
            market_ok = all(before(times[key], prediction, op) for key in market_fields)
            system_time_ok = all(
                before(times[key], prediction, op) for key in system_fields
            )
            system_receipt_ok = True
            if claim == "SYSTEM_REPLAYABLE":
                batch_id = row.get("ingestion_batch_id")
                object_hash = row.get("ingested_object_sha256")
                if not batch_id or not object_hash:
                    gaps.append(
                        self.issue(
                            locator(row),
                            "system replay requires ingestion batch and exact object hash",
                        )
                    )
                    system_receipt_ok = False
                elif (
                    not isinstance(batch_id, str)
                    or not batch_id.strip()
                ):
                    failures.append(
                        self.issue(
                            f"{locator(row)}.ingestion_batch_id",
                            "historical ingestion batch ID cannot be blank or whitespace-only",
                        )
                    )
                    system_receipt_ok = False
                elif not is_sha(object_hash):
                    failures.append(
                        self.issue(
                            f"{locator(row)}.ingested_object_sha256",
                            "historical ingested-object hash is malformed",
                        )
                    )
                    system_receipt_ok = False
            system_ok = system_time_ok and system_receipt_ok
            market_count += market_ok
            system_count += system_ok
            selected_time_ok = (
                system_time_ok if claim == "SYSTEM_REPLAYABLE" else market_ok
            )
            if not selected_time_ok:
                failures.append(
                    self.issue(
                        locator(row),
                        f"value is unavailable under {claim}",
                        prediction_time=row.get("prediction_time"),
                        published_time=row.get("published_time"),
                        vendor_available_time=row.get("vendor_available_time"),
                        ingested_time=row.get("ingested_time"),
                        parse_ready_time=row.get("parse_ready_time"),
                    )
                )
            event = times.get("event_time")
            if policy == "OBSERVED_BY_PREDICTION" and (
                event is None or not before(event, prediction, op)
            ):
                failures.append(
                    self.issue(
                        locator(row), "observed event occurs after prediction"
                    )
                )
            elif policy not in {
                "OBSERVED_BY_PREDICTION",
                "KNOWN_FUTURE_OBJECT",
            }:
                gaps.append(
                    self.issue(
                        f"dictionary.features.{row.get('feature_name')}.event_time_policy",
                        "cannot evaluate event-time eligibility",
                    )
                )
            tradable = times.get("tradable_time")
            if tradable is None:
                gaps.append(
                    self.issue(locator(row), "tradable time is unavailable")
                )
            elif prediction > tradable:
                failures.append(
                    self.issue(
                        locator(row), "tradable time precedes the prediction decision"
                    )
                )
        self.add(
            "T002",
            failures,
            gaps,
            self.evidence(
                {
                    "claim": claim,
                    "availability_comparison": op,
                    "market_predicate": (
                        "published_time and vendor_available_time "
                        f"{op} prediction_time"
                    ),
                    "system_extension": (
                        f"ingested_time and parse_ready_time {op} prediction_time"
                    ),
                    "causal_topology": (
                        "published_time <= vendor_available_time <= ingested_time "
                        "<= parse_ready_time; OBSERVED_BY_PREDICTION also requires "
                        "event_time <= published_time"
                    ),
                }
            ),
            metrics={
                "market_reconstructible_rows": market_count,
                "system_replayable_rows": system_count,
                "causally_ordered_rows": causal_count,
            },
            repair=(
                "Remove the row or reconstruct the exact vintage available by the frozen cutoff; "
                "SYSTEM_REPLAYABLE additionally requires historical ingest and parse evidence."
            ),
        )

    def check_t003_revision(self) -> None:
        failures, gaps = [], []
        op = self.docs.get("time_semantics", {}).get("availability_comparison")
        for row, times in zip(self.rows, self.times):
            known, prediction = (
                times.get("revision_known_time"),
                times.get("prediction_time"),
            )
            if not row.get("revision_id"):
                gaps.append(
                    self.issue(
                        f"{locator(row)}.revision_id", "vintage identity is missing"
                    )
                )
            if known is None or prediction is None:
                gaps.append(
                    self.issue(locator(row), "revision predicate is incomplete")
                )
            elif not before(known, prediction, op):
                failures.append(
                    self.issue(
                        locator(row),
                        "selected revision became known after prediction",
                        revision_id=row.get("revision_id"),
                    )
                )
        self.add(
            "T003",
            failures,
            gaps,
            self.evidence(
                {
                    "predicate": f"revision_known_time {op} prediction_time",
                    "semantic_locator": path_get(
                        self.docs.get("dictionary", {}),
                        "fields.revision_known_time.source_locator",
                    ),
                }
            ),
            metrics={"revision_ids": len({r.get("revision_id") for r in self.rows})},
            repair="Use the latest revision known at prediction; retain every earlier vintage.",
        )

    def check_u001_membership(self) -> None:
        failures, gaps = [], []
        op = self.docs.get("time_semantics", {}).get("availability_comparison")
        for row, times in zip(self.rows, self.times):
            try:
                member = boolean(row.get("universe_member"))
            except ValueError:
                member = False
                failures.append(
                    self.issue(
                        f"{locator(row)}.universe_member", "invalid membership flag"
                    )
                )
            if not member:
                failures.append(
                    self.issue(locator(row), "row was outside the eligible universe")
                )
            prediction = times.get("prediction_time")
            announced = times.get("universe_announced_time")
            start = times.get("universe_effective_from")
            end = times.get("universe_effective_to")
            if None in (prediction, announced, start):
                gaps.append(
                    self.issue(
                        locator(row), "membership announcement/interval is incomplete"
                    )
                )
                continue
            if not before(announced, prediction, op):
                failures.append(
                    self.issue(locator(row), "membership was announced after prediction")
                )
            if end is None:
                null_policy = path_get(
                    self.docs.get("dictionary", {}),
                    "fields.universe_effective_to.null_semantics",
                )
                nullable = path_get(
                    self.docs.get("schema", {}),
                    "columns.universe_effective_to.nullable",
                )
                if (
                    null_policy == "OPEN_ENDED_POSITIVE_INFINITY"
                    and nullable is True
                ):
                    pass
                elif null_policy == "FORBIDDEN" or nullable is False:
                    failures.append(
                        self.issue(
                            f"{locator(row)}.universe_effective_to",
                            "null contradicts the declared end-time policy",
                        )
                    )
                else:
                    gaps.append(
                        self.issue(
                            f"{locator(row)}.universe_effective_to",
                            "null does not prove an open-ended membership interval",
                        )
                    )
            if prediction < start or (end is not None and prediction >= end):
                failures.append(
                    self.issue(
                        locator(row), "prediction lies outside the effective membership interval"
                    )
                )
        self.add(
            "U001",
            failures,
            gaps,
            self.evidence(
                {
                    "announcement_predicate": (
                        f"universe_announced_time {op} prediction_time"
                    ),
                    "effective_interval": "[effective_from, effective_to)",
                }
            ),
            metrics={"membership_rows": len(self.rows)},
            repair=(
                "Rebuild the universe from the announcement vintage and effective interval "
                "known at prediction; do not backfill the current constituent list."
            ),
        )

    def check_u002_population(self) -> None:
        failures, gaps = [], []
        coverage = self.request.get("coverage", {})
        population = coverage.get("population")
        manifest = self.docs.get("population_manifest", {})
        manifest_meta = self.meta.get("population_manifest", {})
        authority = self.docs.get("population_source", {})
        authority_meta = self.meta.get("population_source", {})
        view = self.contract_view()
        if coverage.get("scope") == "SAMPLE_ONLY":
            gaps.append(
                self.issue(
                    "request.coverage.scope",
                    "a sample cannot certify the complete training input",
                )
            )
        if not isinstance(population, dict):
            gaps.append(
                self.issue(
                    "request.coverage.population", "population binding is required"
                )
            )
            population = {}
        if not isinstance(manifest, dict) or not manifest:
            gaps.append(
                self.issue(
                    "population_manifest",
                    "a hash-bound population manifest with the complete expected key set is required",
                )
            )
            manifest = {}
        manifest_present = bool(manifest)
        if not isinstance(authority, dict) or not authority:
            gaps.append(
                self.issue(
                    "population_source",
                    "an independent hash-bound PIT population authority snapshot is required",
                )
            )
            authority = {}
        authority_present = bool(authority)

        if (
            authority_present
            and authority.get("schema_version") != "pit_population_source_v1"
        ):
            failures.append(
                self.issue(
                    "population_source.schema_version",
                    "must equal pit_population_source_v1",
                )
            )
        authority_receipt_payload = dict(authority)
        authority_receipt_payload.pop("receipt_hash", None)
        expected_authority_receipt = sha_value(authority_receipt_payload)
        if authority_present and not authority.get("receipt_hash"):
            gaps.append(
                self.issue(
                    "population_source.receipt_hash",
                    "canonical authority-snapshot receipt hash is required",
                )
            )
        elif (
            authority_present
            and authority.get("receipt_hash") != expected_authority_receipt
        ):
            failures.append(
                self.issue(
                    "population_source.receipt_hash",
                    "receipt hash does not bind the authority snapshot",
                )
            )
        for key in (
            ("authority_id", "version", "source_uri")
            if authority_present
            else ()
        ):
            if not authority.get(key):
                gaps.append(
                    self.issue(
                        f"population_source.{key}",
                        "independent population-authority lineage is required",
                    )
                )
            if authority_meta.get(key) != authority.get(key):
                failures.append(
                    self.issue(
                        f"request.artifacts.population_source.{key}",
                        "request metadata conflicts with the authority snapshot",
                        expected=authority.get(key),
                        actual=authority_meta.get(key),
                    )
                )
        if authority_present and not is_sha(
            authority.get("selection_rule_sha256")
        ):
            failures.append(
                self.issue(
                    "population_source.selection_rule_sha256",
                    "must be lowercase SHA-256",
                )
            )
        if authority_present and authority.get("history_mode") != "PIT_HISTORY":
            failures.append(
                self.issue(
                    "population_source.history_mode",
                    "the authority must expose point-in-time lifecycle history",
                )
            )
        if (
            authority_present
            and authority.get("includes_inactive_and_delisted") is not True
        ):
            failures.append(
                self.issue(
                    "population_source.includes_inactive_and_delisted",
                    "the authority snapshot omits inactive or delisted securities",
                )
            )

        authority_keys: set[tuple[str, str]] = set()
        authority_status: dict[tuple[str, str], str] = {}
        raw_authority_records = authority.get("records")
        if not isinstance(raw_authority_records, list):
            gaps.append(
                self.issue(
                    "population_source.records",
                    "the authority snapshot needs the source-derived population records",
                )
            )
            raw_authority_records = []
        seen_authority_records: set[tuple[str, str]] = set()
        for index, item in enumerate(raw_authority_records):
            where = f"population_source.records[{index}]"
            if not isinstance(item, dict):
                failures.append(self.issue(where, "must be an object"))
                continue
            security_id = item.get("security_id")
            status = item.get("security_status")
            eligible = item.get("eligible")
            if not isinstance(security_id, str) or not security_id:
                failures.append(self.issue(f"{where}.security_id", "is required"))
                continue
            if status not in {"ACTIVE", "DELISTED", "SUSPENDED"}:
                failures.append(
                    self.issue(f"{where}.security_status", "invalid lifecycle status")
                )
            if not isinstance(eligible, bool):
                failures.append(
                    self.issue(f"{where}.eligible", "must be a boolean")
                )
            if not item.get("source_locator"):
                gaps.append(
                    self.issue(
                        f"{where}.source_locator",
                        "each authority record needs an exact source locator",
                    )
                )
            try:
                normalized = (
                    dt(item.get("prediction_time"))
                    .astimezone(timezone.utc)
                    .isoformat()
                )
            except ValueError as error:
                failures.append(
                    self.issue(f"{where}.prediction_time", str(error))
                )
                continue
            key_value = (security_id, normalized)
            if key_value in seen_authority_records:
                failures.append(self.issue(where, "duplicate authority key"))
            seen_authority_records.add(key_value)
            if eligible is True:
                authority_keys.add(key_value)
                authority_status[key_value] = status

        if (
            manifest_present
            and manifest.get("schema_version") != "pit_population_manifest_v1"
        ):
            failures.append(
                self.issue(
                    "population_manifest.schema_version",
                    "must equal pit_population_manifest_v1",
                )
            )
        receipt_payload = dict(manifest)
        receipt_payload.pop("receipt_hash", None)
        expected_receipt_hash = sha_value(receipt_payload)
        if manifest_present and not manifest.get("receipt_hash"):
            gaps.append(
                self.issue(
                    "population_manifest.receipt_hash",
                    "canonical population receipt hash is required",
                )
            )
        elif manifest_present and manifest.get("receipt_hash") != expected_receipt_hash:
            failures.append(
                self.issue(
                    "population_manifest.receipt_hash",
                    "receipt hash does not bind the manifest content",
                )
            )

        for key in (
            ("population_id", "version", "source_uri")
            if manifest_present
            else ()
        ):
            if not manifest.get(key):
                gaps.append(
                    self.issue(
                        f"population_manifest.{key}",
                        "population lineage is required",
                    )
                )
            if manifest_meta.get(key) != manifest.get(key):
                failures.append(
                    self.issue(
                        f"request.artifacts.population_manifest.{key}",
                        "request metadata conflicts with the population manifest",
                        expected=manifest.get(key),
                        actual=manifest_meta.get(key),
                    )
                )
        for key in (
            ("selection_rule_sha256", "expected_key_set_sha256")
            if manifest_present
            else ()
        ):
            if not is_sha(manifest.get(key)):
                failures.append(
                    self.issue(
                        f"population_manifest.{key}",
                        "must be lowercase SHA-256",
                    )
                )
        if manifest_present and manifest.get("history_mode") != "PIT_HISTORY":
            failures.append(
                self.issue(
                    "population_manifest.history_mode",
                    "current/final universe snapshots are forward-looking",
                )
            )
        if (
            manifest_present
            and manifest.get("includes_inactive_and_delisted") is not True
        ):
            failures.append(
                self.issue(
                    "population_manifest.includes_inactive_and_delisted",
                    "the expected population omits lifecycle history",
                )
            )

        manifest_keys: set[tuple[str, str]] = set()
        manifest_status: dict[tuple[str, str], str] = {}
        raw_keys = manifest.get("keys")
        if not isinstance(raw_keys, list):
            gaps.append(
                self.issue(
                    "population_manifest.keys",
                    "the complete eligible security-time key list is required",
                )
            )
            raw_keys = []
        for index, item in enumerate(raw_keys):
            where = f"population_manifest.keys[{index}]"
            if not isinstance(item, dict):
                failures.append(self.issue(where, "must be an object"))
                continue
            security_id = item.get("security_id")
            status = item.get("security_status")
            if not isinstance(security_id, str) or not security_id:
                failures.append(self.issue(f"{where}.security_id", "is required"))
                continue
            if status not in {"ACTIVE", "DELISTED", "SUSPENDED"}:
                failures.append(
                    self.issue(f"{where}.security_status", "invalid lifecycle status")
                )
            if not item.get("source_locator"):
                gaps.append(
                    self.issue(
                        f"{where}.source_locator",
                        "each expected key needs exact population evidence",
                    )
                )
            try:
                normalized = (
                    dt(item.get("prediction_time"))
                    .astimezone(timezone.utc)
                    .isoformat()
                )
            except ValueError as error:
                failures.append(
                    self.issue(f"{where}.prediction_time", str(error))
                )
                continue
            key_value = (security_id, normalized)
            if key_value in manifest_keys:
                failures.append(self.issue(where, "duplicate population key"))
            manifest_keys.add(key_value)
            manifest_status[key_value] = status

        key_payload = [list(item) for item in sorted(manifest_keys)]
        actual_key_set_sha256 = sha_value(key_payload)
        if (
            manifest_present
            and manifest.get("expected_key_set_sha256") != actual_key_set_sha256
        ):
            failures.append(
                self.issue(
                    "population_manifest.expected_key_set_sha256",
                    "key-set digest does not bind the listed population",
                )
            )
        declared_key_count = manifest.get("expected_security_time_keys")
        if manifest_present and (
            not nonnegative_int(declared_key_count)
            or declared_key_count != len(manifest_keys)
        ):
            failures.append(
                self.issue(
                    "population_manifest.expected_security_time_keys",
                    "declared non-boolean key count differs from the manifest",
                    expected=declared_key_count,
                    actual=len(manifest_keys),
                )
            )
        computed_status_counts = dict(Counter(manifest_status.values()))
        declared_status_counts = manifest.get("expected_status_counts")
        status_counts_well_typed = (
            isinstance(declared_status_counts, dict)
            and all(
                isinstance(key, str) and nonnegative_int(value)
                for key, value in declared_status_counts.items()
            )
        )
        if manifest_present and (
            not status_counts_well_typed
            or declared_status_counts != computed_status_counts
        ):
            failures.append(
                self.issue(
                    "population_manifest.expected_status_counts",
                    "non-boolean lifecycle counts do not bind the listed population",
                    expected=declared_status_counts,
                    actual=computed_status_counts,
                )
            )
        if authority_present and manifest_present and manifest_keys != authority_keys:
            failures.append(
                self.issue(
                    "population_manifest.keys",
                    "manifest keys differ from the independent authority snapshot",
                    missing_count=len(authority_keys - manifest_keys),
                    extra_count=len(manifest_keys - authority_keys),
                    missing_examples=[
                        list(item)
                        for item in sorted(authority_keys - manifest_keys)[:5]
                    ],
                    extra_examples=[
                        list(item)
                        for item in sorted(manifest_keys - authority_keys)[:5]
                    ],
                )
            )
        for key_value in sorted(manifest_keys & authority_keys):
            if manifest_status.get(key_value) != authority_status.get(key_value):
                failures.append(
                    self.issue(
                        "population_manifest.keys",
                        "manifest lifecycle status differs from the authority snapshot",
                        key=list(key_value),
                        expected=authority_status.get(key_value),
                        actual=manifest_status.get(key_value),
                    )
                )
        if (
            coverage.get("scope") == "FULL_TRAINING_INPUT"
            and authority_present
            and not authority_keys
        ):
            gaps.append(
                self.issue(
                    "population_source.records",
                    "an empty eligible authority population cannot certify a training input",
                )
            )

        observed_keys: set[tuple[str, str]] = set()
        observed_status: dict[tuple[str, str], set[str]] = defaultdict(set)
        for row, times in zip(self.rows, self.times):
            prediction = times.get("prediction_time")
            if prediction is None:
                continue
            key_value = (
                row.get("security_id", ""),
                prediction.astimezone(timezone.utc).isoformat(),
            )
            observed_keys.add(key_value)
            observed_status[key_value].add(row.get("security_status", ""))
        if manifest_present and observed_keys != manifest_keys:
            failures.append(
                self.issue(
                    "population_manifest.keys",
                    "materialized training keys differ from the frozen expected population",
                    missing_count=len(manifest_keys - observed_keys),
                    extra_count=len(observed_keys - manifest_keys),
                    missing_examples=[
                        list(item) for item in sorted(manifest_keys - observed_keys)[:5]
                    ],
                    extra_examples=[
                        list(item) for item in sorted(observed_keys - manifest_keys)[:5]
                    ],
                )
            )
        for key_value in sorted(observed_keys & manifest_keys):
            statuses = observed_status[key_value]
            if statuses != {manifest_status[key_value]}:
                failures.append(
                    self.issue(
                        "population_manifest.keys",
                        "lifecycle status differs between population and consumed data",
                        key=list(key_value),
                        expected=manifest_status[key_value],
                        actual=sorted(statuses),
                    )
                )

        manifest_file_hash = self.hashes.get("population_manifest")
        authority_file_hash = self.hashes.get("population_source")
        bindings = {
            "basis_id": (
                population.get("basis_id"),
                authority.get("authority_id"),
            ),
            "manifest_population_id": (
                manifest.get("population_id"),
                authority.get("authority_id"),
            ),
            "snapshot_sha256": (
                population.get("snapshot_sha256"),
                authority_file_hash,
            ),
            "selection_rule_sha256": (
                population.get("selection_rule_sha256"),
                authority.get("selection_rule_sha256"),
            ),
            "manifest_selection_rule_sha256": (
                manifest.get("selection_rule_sha256"),
                authority.get("selection_rule_sha256"),
            ),
            "universe_history_mode": (
                population.get("universe_history_mode"),
                authority.get("history_mode"),
            ),
            "manifest_history_mode": (
                manifest.get("history_mode"),
                authority.get("history_mode"),
            ),
            "includes_inactive_and_delisted": (
                population.get("includes_inactive_and_delisted"),
                authority.get("includes_inactive_and_delisted"),
            ),
            "manifest_lifecycle_coverage": (
                manifest.get("includes_inactive_and_delisted"),
                authority.get("includes_inactive_and_delisted"),
            ),
            "expected_security_time_keys": (
                population.get("expected_security_time_keys"),
                len(authority_keys),
            ),
            "universe_version": (
                population.get("universe_version"),
                authority.get("version"),
            ),
            "manifest_universe_version": (
                manifest.get("version"),
                authority.get("version"),
            ),
            "manifest_authority_source_sha256": (
                manifest.get("authority_source_sha256"),
                authority_file_hash,
            ),
            "request_authority_source_sha256": (
                population.get("authority_source_sha256"),
                authority_file_hash,
            ),
            "universe_hash": (
                population.get("universe_hash"),
                authority_file_hash,
            ),
            "contract_universe_hash": (
                view.get("universe_hash"),
                authority_file_hash,
            ),
        }
        request_key_count = population.get("expected_security_time_keys")
        if request_key_count is not None and not nonnegative_int(
            request_key_count
        ):
            failures.append(
                self.issue(
                    "request.coverage.population.expected_security_time_keys",
                    "must be a non-negative non-boolean integer",
                )
            )
        for key, (actual, expected) in bindings.items():
            if actual is None or expected is None:
                gaps.append(
                    self.issue(
                        f"population_binding.{key}",
                        "population binding is incomplete",
                    )
                )
            elif actual != expected:
                failures.append(
                    self.issue(
                        f"population_binding.{key}",
                        "population binding conflicts with the manifest",
                        expected=expected,
                        actual=actual,
                    )
                )
        matrix_axis = path_get(
            self.matrix_manifest(), "sample_prediction_axis", {}
        )
        if self.matrix_manifest():
            if not isinstance(matrix_axis, dict):
                failures.append(self.issue("matrix_manifest.sample_prediction_axis", "must be an object"))
                matrix_axis = {}
            matrix_population_bindings = {
                "population_manifest_sha256": manifest_file_hash,
                "population_manifest_receipt_hash": manifest.get("receipt_hash"),
                "population_source_sha256": authority_file_hash,
                "expected_security_time_keys": len(authority_keys),
                "expected_key_set_sha256": manifest.get("expected_key_set_sha256"),
            }
            for key, expected in matrix_population_bindings.items():
                actual = matrix_axis.get(key)
                if (
                    key == "expected_security_time_keys"
                    and actual is not None
                    and not nonnegative_int(actual)
                ):
                    failures.append(
                        self.issue(
                            f"matrix_manifest.sample_prediction_axis.{key}",
                            "must be a non-negative non-boolean integer",
                        )
                    )
                    continue
                if actual is None or expected is None:
                    gaps.append(
                        self.issue(f"matrix_manifest.sample_prediction_axis.{key}", "binding is incomplete")
                    )
                elif actual != expected:
                    failures.append(
                        self.issue(f"matrix_manifest.sample_prediction_axis.{key}", "binding mismatch")
                    )
        self.add(
            "U002",
            failures,
            gaps,
            self.evidence(
                {
                    "scope": coverage.get("scope"),
                    "population_basis_id": population.get("basis_id"),
                    "population_snapshot_sha256": population.get("snapshot_sha256"),
                    "selection_rule_sha256": population.get(
                        "selection_rule_sha256"
                    ),
                    "population_manifest_sha256": self.hashes.get(
                        "population_manifest"
                    ),
                    "population_source_sha256": authority_file_hash,
                    "population_source_receipt_hash": authority.get(
                        "receipt_hash"
                    ),
                    "expected_key_set_sha256": manifest.get(
                        "expected_key_set_sha256"
                    ),
                    "matrix_population_axis": matrix_axis,
                }
            ),
            metrics={
                "security_time_keys": len(observed_keys),
                "security_status_counts": dict(
                    Counter(r.get("security_status") for r in self.rows)
                ),
            },
            repair=(
                "Re-derive the complete manifest and consumed keys from an independently "
                "versioned PIT population authority snapshot; never edit all three in tandem."
            ),
        )

    def check_c001_calendar(self) -> None:
        failures, gaps = [], []
        metadata = self.meta.get("calendar", {})
        semantics = self.docs.get("time_semantics", {})
        schedule = self.docs.get("label_schedule", {})
        resolver = (
            schedule.get("resolver", {})
            if isinstance(schedule, dict)
            else {}
        )
        for key in ("calendar_id", "version", "timezone", "source_uri"):
            if not metadata.get(key):
                gaps.append(
                    self.issue(
                        f"request.artifacts.calendar.{key}",
                        "versioned calendar metadata is required",
                    )
                )
        if metadata.get("timezone") != semantics.get("timezone"):
            failures.append(
                self.issue(
                    "request.artifacts.calendar.timezone",
                    "calendar and audit timezones differ",
                )
            )
        if (
            isinstance(schedule, dict)
            and schedule.get("mode") == "SESSION_CLOSE_OFFSETS"
        ):
            schedule_bindings = {
                "calendar_id": metadata.get("calendar_id"),
                "calendar_version": metadata.get("version"),
                "calendar_artifact_sha256": self.hashes.get("calendar"),
                "timezone": metadata.get("timezone"),
            }
            for key, expected in schedule_bindings.items():
                actual = resolver.get(key) if isinstance(resolver, dict) else None
                if actual is None or expected is None:
                    gaps.append(
                        self.issue(
                            f"label_schedule.resolver.{key}",
                            "session schedule calendar binding is required",
                        )
                    )
                elif actual != expected:
                    failures.append(
                        self.issue(
                            f"label_schedule.resolver.{key}",
                            "session schedule binds a different calendar artifact",
                            expected=expected,
                            actual=actual,
                        )
                    )
        if set(self.docs.get("calendar_headers", [])) != CALENDAR_FIELDS:
            failures.append(
                self.issue("calendar.header", "must equal the fixed v1 session fields")
            )
        sessions: dict[str, dict[str, datetime | None]] = {}
        for row in self.docs.get("calendar", []):
            sid = row.get("session_id")
            if not sid or sid in sessions:
                failures.append(
                    self.issue(
                        f"calendar#session_id={sid}", "missing or duplicate session ID"
                    )
                )
                continue
            parsed: dict[str, datetime | None] = {}
            for key in ("open_time", "close_time"):
                try:
                    parsed[key] = dt(row.get(key))
                except ValueError as error:
                    parsed[key] = None
                    failures.append(
                        self.issue(f"calendar#session_id={sid}.{key}", str(error))
                    )
            for key in ("break_start", "break_end"):
                try:
                    parsed[key] = dt(row[key]) if row.get(key) else None
                except ValueError as error:
                    parsed[key] = None
                    failures.append(
                        self.issue(f"calendar#session_id={sid}.{key}", str(error))
                    )
            if (parsed["break_start"] is None) != (parsed["break_end"] is None):
                failures.append(
                    self.issue(
                        f"calendar#session_id={sid}",
                        "session break is only partially defined",
                    )
                )
            opened, closed = parsed["open_time"], parsed["close_time"]
            if opened is not None and closed is not None and not opened < closed:
                failures.append(
                    self.issue(
                        f"calendar#session_id={sid}",
                        "session requires open_time < close_time",
                    )
                )
            break_start, break_end = parsed["break_start"], parsed["break_end"]
            if (
                opened is not None
                and closed is not None
                and break_start is not None
                and break_end is not None
                and not opened < break_start < break_end < closed
            ):
                failures.append(
                    self.issue(
                        f"calendar#session_id={sid}",
                        "session break requires open < break_start < break_end < close",
                    )
                )
            sessions[sid] = parsed
        ordered_session_ids = sorted(
            sessions,
            key=lambda sid: (
                sessions[sid].get("open_time")
                or datetime.max.replace(tzinfo=timezone.utc)
            ),
        )
        for prior_id, next_id in zip(
            ordered_session_ids, ordered_session_ids[1:]
        ):
            prior_close = sessions[prior_id].get("close_time")
            next_open = sessions[next_id].get("open_time")
            if (
                prior_close is not None
                and next_open is not None
                and prior_close > next_open
            ):
                failures.append(
                    self.issue(
                        f"calendar#session_id={next_id}.open_time",
                        "calendar sessions overlap; each session must start at or after the prior session closes",
                        prior_session_id=prior_id,
                        prior_close=prior_close.isoformat(),
                        next_open=next_open.isoformat(),
                    )
                )
        ordered_session_index = {
            sid: index for index, sid in enumerate(ordered_session_ids)
        }
        for row, times in zip(self.rows, self.times):
            base_session_id = row.get("calendar_session_id")
            execution_session_id = base_session_id
            if (
                isinstance(schedule, dict)
                and schedule.get("mode") == "SESSION_CLOSE_OFFSETS"
                and isinstance(resolver, dict)
                and nonnegative_int(resolver.get("execution_offset_sessions"))
            ):
                base_index = ordered_session_index.get(base_session_id)
                execution_index = (
                    base_index + resolver["execution_offset_sessions"]
                    if base_index is not None
                    else None
                )
                if (
                    execution_index is None
                    or execution_index >= len(ordered_session_ids)
                ):
                    gaps.append(
                        self.issue(
                            locator(row),
                            "calendar does not cover the resolved execution session",
                        )
                    )
                    continue
                execution_session_id = ordered_session_ids[execution_index]
            session = sessions.get(execution_session_id)
            tradable = times.get("tradable_time")
            if session is None:
                failures.append(
                    self.issue(locator(row), "bound calendar session is absent")
                )
                continue
            opened, closed = session["open_time"], session["close_time"]
            if None in (tradable, opened, closed):
                gaps.append(
                    self.issue(locator(row), "session predicate is incomplete")
                )
                continue
            if not opened <= tradable <= closed:
                failures.append(
                    self.issue(locator(row), "tradable time is outside the session")
                )
            if (
                session["break_start"] is not None
                and session["break_end"] is not None
                and session["break_start"] <= tradable < session["break_end"]
            ):
                failures.append(
                    self.issue(locator(row), "tradable time falls inside a break")
                )
        self.add(
            "C001",
            failures,
            gaps,
            self.evidence(
                {
                    "calendar_id": metadata.get("calendar_id"),
                    "calendar_version": metadata.get("version"),
                    "calendar_sha256": self.hashes.get("calendar"),
                    "timezone": metadata.get("timezone"),
                }
            ),
            metrics={"sessions": len(sessions)},
            repair=(
                "Use the versioned venue session containing actual holidays, early closes, and "
                "breaks; change tradable_time only if the frozen execution rule permits."
            ),
        )

    def check_m001_identity(self) -> None:
        failures, gaps = [], []
        identity = path_get(
            self.docs.get("dictionary", {}), "fields.security_id", {}
        )
        stability = identity.get("identity_stability")
        if stability is None:
            gaps.append(
                self.issue(
                    "dictionary.fields.security_id.identity_stability",
                    "identity evidence is missing",
                )
            )
        elif stability != "permanent":
            failures.append(
                self.issue(
                    "dictionary.fields.security_id.identity_stability",
                    "ticker or mutable code cannot be the security key",
                )
            )
        for row, times in zip(self.rows, self.times):
            prediction = times.get("prediction_time")
            start = times.get("identifier_valid_from")
            end = times.get("identifier_valid_to")
            if None in (prediction, start):
                gaps.append(
                    self.issue(locator(row), "identifier interval is incomplete")
                )
            else:
                if end is None:
                    null_policy = path_get(
                        self.docs.get("dictionary", {}),
                        "fields.identifier_valid_to.null_semantics",
                    )
                    nullable = path_get(
                        self.docs.get("schema", {}),
                        "columns.identifier_valid_to.nullable",
                    )
                    if (
                        null_policy == "OPEN_ENDED_POSITIVE_INFINITY"
                        and nullable is True
                    ):
                        pass
                    elif null_policy == "FORBIDDEN" or nullable is False:
                        failures.append(
                            self.issue(
                                f"{locator(row)}.identifier_valid_to",
                                "null contradicts the declared identifier policy",
                            )
                        )
                    else:
                        gaps.append(
                            self.issue(
                                f"{locator(row)}.identifier_valid_to",
                                "null does not prove an open-ended identifier interval",
                            )
                        )
                if prediction < start or (end is not None and prediction >= end):
                    failures.append(
                        self.issue(
                            locator(row), "security identifier is invalid at prediction"
                        )
                    )
        self.add(
            "M001",
            failures,
            gaps,
            self.evidence(
                {
                    "identity_stability": stability,
                    "identity_source_locator": identity.get("source_locator"),
                    "validity_interval": "[identifier_valid_from, identifier_valid_to)",
                }
            ),
            metrics={"security_ids": len({r.get("security_id") for r in self.rows})},
            repair=(
                "Join through a documented permanent ID and versioned valid-time mapping; "
                "never join history on ticker alone."
            ),
        )

    def check_a001_adjustment(self) -> None:
        failures, gaps = [], []
        features = self.docs.get("dictionary", {}).get("features", {})
        for row, times in zip(self.rows, self.times):
            mode = row.get("adjustment_mode")
            feature = features.get(row.get("feature_name"), {})
            adjustment_policy = feature.get("adjustment_policy")
            if not isinstance(adjustment_policy, dict):
                gaps.append(
                    self.issue(
                        f"dictionary.features.{row.get('feature_name')}.adjustment_policy",
                        "adjustment basis and convention are missing",
                    )
                )
                adjustment_policy = {}
            else:
                for key in ("basis", "convention", "source_locator", "allowed_modes"):
                    if not adjustment_policy.get(key):
                        gaps.append(
                            self.issue(
                                f"dictionary.features.{row.get('feature_name')}.adjustment_policy.{key}",
                                "adjustment evidence is missing",
                            )
                        )
            if adjustment_policy.get("allowed_modes") and mode not in adjustment_policy[
                "allowed_modes"
            ]:
                failures.append(
                    self.issue(
                        locator(row),
                        "consumed adjustment mode conflicts with feature semantics",
                        mode=mode,
                    )
                )
            if mode == "RAW":
                continue
            if mode == "PIT_ADJUSTED":
                failures.append(
                    self.issue(
                        locator(row),
                        "v1 fails closed on PIT_ADJUSTED values because the consumed view cannot recompute raw value, factor, ex-date, and base-date provenance",
                    )
                )
                continue
            if mode == "FULL_HISTORY_ADJUSTED":
                failures.append(
                    self.issue(
                        locator(row),
                        "v1 fails closed on FULL_HISTORY_ADJUSTED values; a row boolean or unverified test hash is not proof",
                    )
                )
                continue
            failures.append(
                self.issue(
                    f"{locator(row)}.adjustment_mode", "unknown adjustment mode"
                )
            )
        self.add(
            "A001",
            failures,
            gaps,
            self.evidence(
                {
                    "rule": (
                        "RAW only; PIT_ADJUSTED and FULL_HISTORY_ADJUSTED are "
                        "unsupported and fail closed in v1"
                    )
                }
            ),
            metrics={
                "adjustment_mode_counts": dict(
                    Counter(r.get("adjustment_mode") for r in self.rows)
                )
            },
            repair=(
                "Use raw values. Supporting adjusted values requires a new source-bound "
                "proof artifact that recomputes value, factor, ex-date, and base-date."
            ),
        )

    def check_h001_halts(self) -> None:
        failures, gaps = [], []
        halted = 0
        for row, times in zip(self.rows, self.times):
            halt = times.get("halt_time")
            quote_resumed = times.get("quote_resume_time")
            trade_resumed = times.get("trade_resume_time")
            if halt is None:
                if quote_resumed is not None or trade_resumed is not None:
                    failures.append(
                        self.issue(
                            locator(row),
                            "resume timestamp exists without a halt start",
                        )
                    )
                continue
            halted += 1
            if quote_resumed is not None and quote_resumed < halt:
                failures.append(
                    self.issue(locator(row), "quote resume precedes the halt")
                )
            if trade_resumed is not None and trade_resumed < halt:
                failures.append(
                    self.issue(locator(row), "trade resume precedes the halt")
                )
            if (
                quote_resumed is not None
                and trade_resumed is not None
                and quote_resumed > trade_resumed
            ):
                failures.append(
                    self.issue(
                        locator(row), "trade resume precedes quote resume"
                    )
                )
            tradable, resumed = times.get("tradable_time"), trade_resumed
            if tradable is None:
                gaps.append(self.issue(locator(row), "tradable time is missing"))
            elif halt <= tradable and (resumed is None or tradable < resumed):
                failures.append(
                    self.issue(
                        locator(row),
                        "tradable time occurs while trading remains halted",
                        quote_resume_time=row.get("quote_resume_time"),
                        trade_resume_time=row.get("trade_resume_time"),
                    )
                )
        self.add(
            "H001",
            failures,
            gaps,
            self.evidence(
                {
                    "predicate": (
                        "after halt_time, tradable_time requires trade_resume_time; "
                        "quote_resume_time is not a proxy"
                    ),
                    "source_locator": path_get(
                        self.docs.get("dictionary", {}),
                        "fields.trade_resume_time.source_locator",
                    ),
                }
            ),
            metrics={"halted_rows": halted},
            repair=(
                "Move execution to documented trade resumption or exclude the row under the "
                "frozen rule; quote resumption alone is insufficient."
            ),
        )

    def check_q001_uniqueness(self) -> None:
        schema = self.docs.get("schema", {})
        failures, gaps = [], []
        primary, grain = schema.get("primary_key", []), schema.get("grain", [])
        seen_primary, seen_grain = {}, {}
        for row in self.rows:
            for names, seen, label in (
                (primary, seen_primary, "primary key"),
                (grain, seen_grain, "declared grain"),
            ):
                key_parts: list[Any] = []
                valid_key = True
                for name in names:
                    value = row.get(name)
                    if name == "prediction_time":
                        try:
                            value = normalized_time_text(value)
                        except ValueError:
                            valid_key = False
                            break
                    key_parts.append(value)
                if not valid_key:
                    continue
                key = tuple(key_parts)
                if key in seen:
                    failures.append(
                        self.issue(
                            locator(row),
                            f"duplicate {label}",
                            first=seen[key],
                        )
                    )
                else:
                    seen[key] = locator(row)

        matrix_manifest = self.matrix_manifest()
        expected_cells: set[tuple[str, str, str]] = set()
        observed_cells: set[tuple[str, str, str]] = set()
        layout_mode = path_get(matrix_manifest, "layout.mode")
        if not matrix_manifest:
            gaps.append(
                self.issue(
                    "request.artifacts.matrix_manifest",
                    "matrix-cell completeness requires pit_matrix_manifest_v1; sampled rows remain diagnostic only",
                )
            )
        elif layout_mode == "SPARSE_EXPLICIT":
            gaps.append(
                self.issue(
                    "matrix_manifest.layout.mode",
                    "SPARSE_EXPLICIT requires a QRC-bound expected-cell proof before it can pass",
                )
            )
        else:
            feature_axis = matrix_manifest.get("feature_axis", {})
            features = feature_axis.get("features", [])
            valid_features = (
                isinstance(features, list)
                and bool(features)
                and all(isinstance(item, str) and item for item in features)
                and features == sorted(set(features))
            )
            if not valid_features:
                failures.append(
                    self.issue("matrix_manifest.feature_axis.features", "must be sorted, unique, non-empty strings")
                )
                features = []
            feature_count = feature_axis.get("expected_feature_count")
            if (
                isinstance(feature_count, bool)
                or feature_count != len(features)
                or feature_axis.get("feature_set_sha256") != sha_value(features)
            ):
                failures.append(
                    self.issue("matrix_manifest.feature_axis", "feature count/digest mismatch")
                )
            population_keys = set()
            for index, item in enumerate(
                path_get(self.docs.get("population_manifest", {}), "keys", [])
            ):
                try:
                    population_keys.add(
                        (
                            item["security_id"],
                            normalized_time_text(item["prediction_time"]),
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    failures.append(
                        self.issue(f"population_manifest.keys[{index}]", "invalid matrix-axis key")
                    )
            expected_cells = {
                (*population_key, feature)
                for population_key in population_keys
                for feature in features
            }
            expected_digest = sha_value(
                [list(item) for item in sorted(expected_cells)]
            )
            count = matrix_manifest.get("expected_cell_count")
            if (
                isinstance(count, bool)
                or count != len(expected_cells)
                or matrix_manifest.get("expected_cell_key_set_sha256")
                != expected_digest
            ):
                failures.append(
                    self.issue("matrix_manifest", "rectangular cell count/digest mismatch")
                )
            for row in self.rows:
                try:
                    observed_cells.add(normalized_matrix_cell(row))
                except ValueError:
                    continue
            if observed_cells != expected_cells:
                failures.append(
                    self.issue(
                        "matrix_manifest.expected_cell_key_set_sha256",
                        "materialized matrix cells differ from the frozen exact set",
                        missing_count=len(expected_cells - observed_cells),
                        extra_count=len(observed_cells - expected_cells),
                        missing_examples=[
                            list(item) for item in sorted(expected_cells - observed_cells)[:5]
                        ],
                        extra_examples=[
                            list(item) for item in sorted(observed_cells - expected_cells)[:5]
                        ],
                    )
                )
        self.add(
            "Q001",
            failures,
            gaps,
            self.evidence(
                {
                    "primary_key": primary,
                    "grain": grain,
                    "matrix_manifest_sha256": self.hashes.get(
                        "matrix_manifest"
                    ),
                    "matrix_layout_mode": layout_mode,
                    "expected_cell_key_set_sha256": matrix_manifest.get(
                        "expected_cell_key_set_sha256"
                    ),
                }
            ),
            metrics={
                "unique_primary_keys": len(seen_primary),
                "unique_grain_keys": len(seen_grain),
                "expected_matrix_cells": len(expected_cells),
                "observed_matrix_cells": len(observed_cells),
            },
            repair=(
                "Restore the hash-bound expected matrix set and exact source-grain cells; "
                "do not infer a feature axis from observed rows or silently deduplicate."
            ),
        )

    def check_q002_values(self) -> None:
        failures, gaps = [], []
        schema = self.docs.get("schema", {})
        columns = schema.get("columns", {})
        parsers = {
            "string": lambda value: value,
            "float": lambda value: (
                float(value)
                if math.isfinite(float(value))
                else (_ for _ in ()).throw(ValueError("non-finite numeric"))
            ),
            "integer": int,
            "boolean": boolean,
            "timestamp": dt,
        }
        for row in self.rows:
            for field, spec in columns.items():
                raw = row.get(field, "")
                if raw == "":
                    if spec.get("nullable") is not True:
                        failures.append(
                            self.issue(
                                f"{locator(row)}.{field}", "required value is missing"
                            )
                        )
                    continue
                parser = parsers.get(spec.get("type"))
                if parser is None:
                    gaps.append(
                        self.issue(
                            f"schema.columns.{field}.type",
                            "unknown declared type",
                        )
                    )
                    continue
                try:
                    parser(raw)
                except (ValueError, TypeError) as error:
                    failures.append(
                        self.issue(
                            f"{locator(row)}.{field}",
                            f"type validation failed: {error}",
                        )
                    )
            if row.get("split") not in SPLITS:
                failures.append(
                    self.issue(
                        f"{locator(row)}.split", f"must be one of {sorted(SPLITS)}"
                    )
                )
            if row.get("security_status") not in {
                "ACTIVE",
                "DELISTED",
                "SUSPENDED",
            }:
                failures.append(
                    self.issue(
                        f"{locator(row)}.security_status",
                        "unknown security status",
                    )
                )
        self.add(
            "Q002",
            failures,
            gaps,
            self.evidence(
                {
                    "schema_sha256": self.hashes.get("schema"),
                    "declared_types": columns,
                }
            ),
            metrics={"validated_cells": len(self.rows) * len(columns)},
            repair="Repair only malformed or missing source values; preserve the frozen schema.",
        )

    def check_q003_domains(self) -> None:
        failures, gaps = [], []
        features = self.docs.get("dictionary", {}).get("features", {})
        for name in sorted({row.get("feature_name") for row in self.rows}):
            policy = features.get(name, {}).get("domain_policy")
            if not isinstance(policy, dict):
                gaps.append(
                    self.issue(
                        f"dictionary.features.{name}.domain_policy",
                        "sourced domain policy is required",
                    )
                )
                continue
            kind = policy.get("kind")
            if kind not in {"BOUNDED", "MIN", "MAX", "UNBOUNDED"}:
                failures.append(
                    self.issue(
                        f"dictionary.features.{name}.domain_policy.kind",
                        "unknown policy kind",
                    )
                )
            if not policy.get("source_locator"):
                gaps.append(
                    self.issue(
                        f"dictionary.features.{name}.domain_policy.source_locator",
                        "domain evidence is missing",
                    )
                )
            minimum = policy.get("min")
            maximum = policy.get("max")
            if kind in {"MIN", "BOUNDED"}:
                if "min" not in policy or minimum is None:
                    gaps.append(
                        self.issue(
                            f"dictionary.features.{name}.domain_policy.min",
                            "finite minimum is required",
                        )
                    )
                elif not finite_number(minimum):
                    failures.append(
                        self.issue(
                            f"dictionary.features.{name}.domain_policy.min",
                            "minimum must be a finite non-boolean JSON number",
                            actual_type=type(minimum).__name__,
                        )
                    )
            if kind in {"MAX", "BOUNDED"}:
                if "max" not in policy or maximum is None:
                    gaps.append(
                        self.issue(
                            f"dictionary.features.{name}.domain_policy.max",
                            "finite maximum is required",
                        )
                    )
                elif not finite_number(maximum):
                    failures.append(
                        self.issue(
                            f"dictionary.features.{name}.domain_policy.max",
                            "maximum must be a finite non-boolean JSON number",
                            actual_type=type(maximum).__name__,
                        )
                    )
            if (
                kind == "BOUNDED"
                and finite_number(minimum)
                and finite_number(maximum)
                and float(minimum) > float(maximum)
            ):
                failures.append(
                    self.issue(
                        f"dictionary.features.{name}.domain_policy",
                        "minimum cannot exceed maximum",
                        minimum=minimum,
                        maximum=maximum,
                    )
                )
        for row in self.rows:
            policy = features.get(row.get("feature_name"), {}).get(
                "domain_policy", {}
            )
            try:
                value = float(row.get("feature_value", ""))
            except (TypeError, ValueError):
                continue
            minimum = policy.get("min")
            maximum = policy.get("max")
            below = (
                policy.get("kind") in {"MIN", "BOUNDED"}
                and finite_number(minimum)
                and value < float(minimum)
            )
            above = (
                policy.get("kind") in {"MAX", "BOUNDED"}
                and finite_number(maximum)
                and value > float(maximum)
            )
            if below or above:
                failures.append(
                    self.issue(
                        locator(row),
                        "feature violates its declared hard domain",
                        value=value,
                    )
                )
        self.add(
            "Q003",
            failures,
            gaps,
            self.evidence(
                {
                    "policy": (
                        "Only sourced semantic bounds can hard-fail; no universal z-score "
                        "or outlier cutoff is imposed."
                    ),
                    "domain_locators": {
                        name: features.get(name, {})
                        .get("domain_policy", {})
                        .get("source_locator")
                        for name in sorted({r.get("feature_name") for r in self.rows})
                    },
                }
            ),
            metrics={"feature_values": len(self.rows)},
            repair="Correct the source value or govern a new documented domain; never widen it post hoc.",
        )

    def check_l001_label(self) -> None:
        failures, gaps = [], []
        label = self.docs.get("label_definition", {})
        view = self.contract_view()
        sample_label_intervals: dict[
            tuple[str, str], set[tuple[str, str, str]]
        ] = defaultdict(set)
        if label.get("schema_version") != "pit_label_definition_v1":
            failures.append(
                self.issue("label_definition.schema_version", "unsupported schema")
            )
        for key in (
            "label_id",
            "label_spec_version",
            "definition",
            "label_spec_hash",
            "source_locator",
        ):
            if not label.get(key):
                gaps.append(
                    self.issue(f"label_definition.{key}", "evidence is required")
                )
        unhashed = dict(label)
        unhashed.pop("label_spec_hash", None)
        expected_hash = sha_value(unhashed)
        if label.get("label_spec_hash") != expected_hash:
            failures.append(
                self.issue(
                    "label_definition.label_spec_hash",
                    "canonical label hash is invalid",
                )
            )
        if label.get("label_spec_hash") != view.get("label_spec_hash"):
            failures.append(
                self.issue(
                    "label_definition.label_spec_hash",
                    "label conflicts with frozen contract",
                )
            )
        if label.get("interval_closure") not in {"LEFT", "BOTH"}:
            failures.append(
                self.issue(
                    "label_definition.interval_closure", "must be LEFT or BOTH"
                )
            )
        if label.get("overlap_policy") != "NO_CROSS_SPLIT_OVERLAP":
            failures.append(
                self.issue(
                    "label_definition.overlap_policy",
                    "cross-split overlaps must be forbidden",
                )
            )
        if not str(label.get("purge_rule", "")).strip():
            gaps.append(
                self.issue("label_definition.purge_rule", "purge rule is required")
            )
        for row, times in zip(self.rows, self.times):
            prediction = times.get("prediction_time")
            start = times.get("label_start_time")
            end = times.get("label_end_time")
            if None in (prediction, start, end):
                gaps.append(
                    self.issue(locator(row), "label interval is incomplete")
                )
            elif start < prediction or end <= start:
                failures.append(
                    self.issue(
                        locator(row),
                        "label must start at/after prediction and end after start",
                    )
                )
            if None not in (prediction, start, end):
                sample_key = (
                    row.get("security_id", ""),
                    prediction.astimezone(timezone.utc).isoformat(),
                )
                sample_label_intervals[sample_key].add(
                    (
                        row.get("split", ""),
                        start.astimezone(timezone.utc).isoformat(),
                        end.astimezone(timezone.utc).isoformat(),
                    )
                )
        drifted_samples = {
            key: sorted(intervals)
            for key, intervals in sample_label_intervals.items()
            if len(intervals) > 1
        }
        for key, intervals in sorted(drifted_samples.items()):
            failures.append(
                self.issue(
                    "data",
                    "all features for one security/prediction sample must share the same split and label interval",
                    sample=list(key),
                    variants=[list(item) for item in intervals[:5]],
                )
            )
        schedule = self.docs.get("label_schedule", {})
        schedule_mode = (
            schedule.get("mode") if isinstance(schedule, dict) else None
        )
        resolver = (
            schedule.get("resolver", {})
            if isinstance(schedule, dict)
            else {}
        )
        interval_set = {
            (
                row.get("security_id", ""),
                times["prediction_time"].astimezone(timezone.utc).isoformat(),
                times["tradable_time"].astimezone(timezone.utc).isoformat(),
                times["label_start_time"].astimezone(timezone.utc).isoformat(),
                times["label_end_time"].astimezone(timezone.utc).isoformat(),
            )
            for row, times in zip(self.rows, self.times)
            if None
            not in (
                times.get("prediction_time"),
                times.get("tradable_time"),
                times.get("label_start_time"),
                times.get("label_end_time"),
            )
        }
        if not isinstance(schedule, dict) or not schedule:
            gaps.append(
                self.issue(
                    "label_schedule",
                    "executable label-schedule evidence is unavailable",
                )
            )
        elif schedule_mode == "FROZEN_EXACT_INTERVAL_SET":
            interval_authority = self.docs.get(
                "label_interval_authority", {}
            )
            expected_count = (
                interval_authority.get("expected_sample_count")
                if isinstance(interval_authority, dict)
                else None
            )
            expected_digest = (
                interval_authority.get("expected_interval_set_sha256")
                if isinstance(interval_authority, dict)
                else None
            )
            actual_digest = sha_value(
                [list(item) for item in sorted(interval_set)]
            )
            if expected_count != len(interval_set):
                failures.append(
                    self.issue(
                        "label_interval_authority.expected_sample_count",
                        "materialized sample/interval count differs from the frozen schedule",
                        expected=expected_count,
                        actual=len(interval_set),
                    )
                )
            if expected_digest != actual_digest:
                failures.append(
                    self.issue(
                        "label_interval_authority.expected_interval_set_sha256",
                        "materialized label intervals differ from the frozen exact set",
                        expected=expected_digest,
                        actual=actual_digest,
                    )
                )
        elif schedule_mode == "SESSION_CLOSE_OFFSETS":
            parsed_sessions: list[tuple[datetime, datetime, str]] = []
            for item in self.docs.get("calendar", []):
                try:
                    opened = dt(item.get("open_time"))
                    closed = dt(item.get("close_time"))
                except (AttributeError, ValueError):
                    continue
                session_id = item.get("session_id")
                if isinstance(session_id, str) and session_id:
                    parsed_sessions.append((opened, closed, session_id))
            parsed_sessions.sort()
            session_index = {
                session_id: index
                for index, (_, _, session_id) in enumerate(parsed_sessions)
            }
            prediction_offset = resolver.get(
                "prediction_offset_from_session_open_seconds"
            )
            execution_offset = resolver.get(
                "execution_offset_from_session_open_seconds"
            )
            execution_offset_sessions = resolver.get(
                "execution_offset_sessions"
            )
            start_offset = resolver.get("start_offset_sessions")
            horizon = resolver.get("horizon_sessions")
            if all(
                nonnegative_int(value)
                for value in (
                    prediction_offset,
                    execution_offset_sessions,
                    execution_offset,
                    start_offset,
                    horizon,
                )
            ) and horizon > 0:
                for row, times in zip(self.rows, self.times):
                    base_index = session_index.get(
                        row.get("calendar_session_id")
                    )
                    if base_index is None:
                        gaps.append(
                            self.issue(
                                locator(row),
                                "base calendar session is unavailable for label-schedule execution",
                            )
                        )
                        continue
                    start_index = base_index + start_offset
                    end_index = start_index + horizon
                    execution_index = base_index + execution_offset_sessions
                    if execution_index >= len(parsed_sessions):
                        gaps.append(
                            self.issue(
                                locator(row),
                                "audited calendar does not cover the execution session",
                                required_session_index=execution_index,
                                available_sessions=len(parsed_sessions),
                            )
                        )
                        continue
                    expected_prediction = (
                        parsed_sessions[base_index][0]
                        + timedelta(seconds=prediction_offset)
                    )
                    expected_execution = (
                        parsed_sessions[execution_index][0]
                        + timedelta(seconds=execution_offset)
                    )
                    if (
                        expected_prediction > parsed_sessions[base_index][1]
                        or expected_execution
                        > parsed_sessions[execution_index][1]
                    ):
                        failures.append(
                            self.issue(
                                "label_schedule.resolver",
                                "prediction or execution offset falls outside its resolved trading session",
                                prediction_session_id=parsed_sessions[base_index][2],
                                execution_session_id=parsed_sessions[execution_index][2],
                            )
                        )
                        continue
                    if end_index >= len(parsed_sessions):
                        gaps.append(
                            self.issue(
                                locator(row),
                                "audited calendar does not cover the complete label horizon",
                                required_session_index=end_index,
                                available_sessions=len(parsed_sessions),
                            )
                        )
                        continue
                    expected_label_start = parsed_sessions[start_index][1]
                    if expected_label_start < expected_execution:
                        failures.append(
                            self.issue(
                                "label_schedule.resolver.start_offset_sessions",
                                "label start cannot precede the frozen execution time",
                            )
                        )
                        continue
                    expected_times = {
                        "prediction_time": expected_prediction,
                        "tradable_time": expected_execution,
                        "label_start_time": expected_label_start,
                        "label_end_time": parsed_sessions[end_index][1],
                    }
                    for field, expected in expected_times.items():
                        actual = times.get(field)
                        if actual is not None and actual != expected:
                            failures.append(
                                self.issue(
                                    f"{locator(row)}.{field}",
                                    "timestamp conflicts with the executable session-close label schedule",
                                    expected=expected.isoformat(),
                                    actual=actual.isoformat(),
                                )
                            )
        self.add(
            "L001",
            failures,
            gaps,
            self.evidence(
                {
                    "label_definition_sha256": self.hashes.get("label_definition"),
                    "label_spec_hash": label.get("label_spec_hash"),
                    "label_source_locator": label.get("source_locator"),
                }
            ),
            metrics={
                "label_intervals": len(self.rows),
                "sample_prediction_labels": len(sample_label_intervals),
                "label_drift_samples": len(drifted_samples),
                "label_schedule_mode": schedule_mode,
                "unique_label_intervals": len(interval_set),
            },
            repair=(
                "Restore the frozen label and valid post-prediction interval. A label change "
                "requires a derived research contract."
            ),
        )

    def check_l002_split_isolation(self) -> None:
        failures, gaps = [], []
        label = self.docs.get("label_definition", {})
        view = self.contract_view()
        intervals: list[tuple[datetime, datetime, str, str]] = []
        for row, times in zip(self.rows, self.times):
            start, end = times.get("label_start_time"), times.get("label_end_time")
            if start is not None and end is not None and row.get("split") in SPLITS:
                intervals.append((start, end, row["split"], locator(row)))
        latest: dict[str, tuple[datetime, str]] = {}
        same_overlap = 0
        cross_split_overlap = 0
        closed = label.get("interval_closure") == "BOTH"
        for start, end, split, row_locator in sorted(intervals):
            for prior_split, (prior_end, prior_locator) in latest.items():
                overlaps = prior_end >= start if closed else prior_end > start
                if not overlaps:
                    continue
                if prior_split == split:
                    same_overlap += 1
                else:
                    cross_split_overlap += 1
                    failures.append(
                        self.issue(
                            row_locator,
                            "label interval overlaps a different split",
                            other=prior_locator,
                            split_pair=sorted([split, prior_split]),
                        )
                    )
            if split not in latest or end > latest[split][0]:
                latest[split] = (end, row_locator)
        contract_purge_rule = view.get("purge_rule")
        label_purge_rule = label.get("purge_rule")
        if not contract_purge_rule:
            gaps.append(
                self.issue(
                    "research_contract.split_policy", "frozen purge rule is missing"
                )
            )
        elif label_purge_rule and label_purge_rule != contract_purge_rule:
            failures.append(
                self.issue(
                    "label_definition.purge_rule",
                    "label purge rule differs from the frozen per-sample rule",
                )
            )
        policy_fields = {
            "purge_embargo_rule": view.get("purge_embargo_rule"),
            "embargo_duration": view.get("embargo_duration"),
            "embargo_basis": view.get("embargo_basis"),
        }
        for field, expected_value in policy_fields.items():
            actual_value = label.get(field)
            if not actual_value or not expected_value:
                gaps.append(
                    self.issue(
                        f"label_definition.{field}",
                        "exact frozen purge/embargo text is required",
                    )
                )
            elif actual_value != expected_value:
                failures.append(
                    self.issue(
                        f"label_definition.{field}",
                        "label split policy conflicts with the frozen contract",
                        expected=expected_value,
                        actual=actual_value,
                    )
                )

        if view.get("adapter") == "quant_contract_v2":
            timezone_name = view.get("timezone")
            try:
                local_zone = ZoneInfo(timezone_name)
            except (TypeError, ZoneInfoNotFoundError):
                local_zone = None
                gaps.append(
                    self.issue(
                        "research_contract.scope.timezone",
                        "split-window checks require a valid IANA timezone",
                    )
                )
            window_dates: dict[str, tuple[date, date]] = {}
            raw_windows = view.get("split_windows")
            if not isinstance(raw_windows, dict):
                gaps.append(
                    self.issue(
                        "research_contract.splits",
                        "all production split windows are required",
                    )
                )
            else:
                for split_name in ("TRAIN", "MODEL_SELECTION", "OOS"):
                    raw_window = raw_windows.get(split_name)
                    try:
                        if not isinstance(raw_window, dict):
                            raise ValueError("window is missing")
                        start_date = calendar_date(raw_window.get("start"))
                        end_date = calendar_date(raw_window.get("end"))
                        if start_date > end_date:
                            raise ValueError("start is after end")
                        window_dates[split_name] = (start_date, end_date)
                    except ValueError as error:
                        failures.append(
                            self.issue(
                                f"research_contract.splits.{split_name}",
                                f"invalid split window: {error}",
                            )
                        )

            split_order = ["TRAIN", "MODEL_SELECTION", "OOS"]
            if local_zone is not None and len(window_dates) == 3:
                for row, times in zip(self.rows, self.times):
                    split_name = row.get("split")
                    prediction = times.get("prediction_time")
                    label_start = times.get("label_start_time")
                    label_end = times.get("label_end_time")
                    if (
                        split_name not in window_dates
                        or prediction is None
                        or label_start is None
                        or label_end is None
                    ):
                        continue
                    local_prediction_date = prediction.astimezone(local_zone).date()
                    split_start, split_end = window_dates[split_name]
                    if not split_start <= local_prediction_date <= split_end:
                        failures.append(
                            self.issue(
                                locator(row),
                                "prediction date lies outside its frozen split window",
                                split=split_name,
                                local_date=local_prediction_date.isoformat(),
                            )
                        )
                    current_index = split_order.index(split_name)
                    for future_split in split_order[current_index + 1 :]:
                        future_start_date, future_end_date = window_dates[future_split]
                        future_start = datetime.combine(
                            future_start_date, time.min, tzinfo=local_zone
                        )
                        future_end = datetime.combine(
                            future_end_date + timedelta(days=1),
                            time.min,
                            tzinfo=local_zone,
                        )
                        overlaps = (
                            label_start < future_end
                            and (
                                label_end >= future_start
                                if closed
                                else label_end > future_start
                            )
                        )
                        if overlaps:
                            cross_split_overlap += 1
                            failures.append(
                                self.issue(
                                    locator(row),
                                    "label interval enters a later frozen split window",
                                    row_split=split_name,
                                    later_split=future_split,
                                )
                            )

                resolved = path_get(
                    self.docs.get("time_semantics", {}),
                    "contract_interpretation.resolved",
                    {},
                )
                embargo_sessions = (
                    resolved.get("embargo_sessions")
                    if isinstance(resolved, dict)
                    else None
                )
                contract_embargo_sessions = canonical_embargo_sessions(
                    view.get("embargo_duration")
                )
                if contract_embargo_sessions is None:
                    gaps.append(
                        self.issue(
                            "research_contract.splits.sample_dependency.embargo_duration",
                            "v1 requires canonical '<N> eligible trading days' duration text",
                        )
                    )
                elif (
                    not isinstance(embargo_sessions, int)
                    or isinstance(embargo_sessions, bool)
                    or embargo_sessions != contract_embargo_sessions
                ):
                    failures.append(
                        self.issue(
                            "time_semantics.contract_interpretation.resolved.embargo_sessions",
                            "resolved embargo does not equal the machine-parsed frozen duration",
                            expected=contract_embargo_sessions,
                            actual=embargo_sessions,
                        )
                    )
                expected_basis_hash = sha_text(view.get("embargo_basis"))
                if (
                    not isinstance(resolved, dict)
                    or resolved.get("embargo_basis_sha256")
                    != expected_basis_hash
                ):
                    gaps.append(
                        self.issue(
                            "time_semantics.contract_interpretation.resolved.embargo_basis_sha256",
                            "resolved embargo basis must bind the exact frozen basis text",
                            expected=expected_basis_hash,
                        )
                    )
                if (
                    not isinstance(resolved, dict)
                    or resolved.get("embargo_implementation")
                    != "UNASSIGNED_SPLIT_GAP"
                ):
                    gaps.append(
                        self.issue(
                            "time_semantics.contract_interpretation.resolved.embargo_implementation",
                            "v1 supports only a verified unassigned split-gap embargo",
                        )
                    )
                boundary_complete = (
                    isinstance(resolved, dict)
                    and resolved.get("boundary_calendar_complete") is True
                    and resolved.get("boundary_calendar_sha256")
                    == self.hashes.get("calendar")
                )
                if not boundary_complete:
                    gaps.append(
                        self.issue(
                            "time_semantics.contract_interpretation.resolved.boundary_calendar_sha256",
                            "complete hash-bound calendar evidence around split boundaries is required",
                        )
                    )
                if (
                    boundary_complete
                    and contract_embargo_sessions is not None
                ):
                    calendar_opens: list[datetime] = []
                    for session in self.docs.get("calendar", []):
                        try:
                            calendar_opens.append(
                                dt(session.get("open_time")).astimezone(
                                    local_zone
                                )
                            )
                        except ValueError:
                            continue
                    label_ends_by_split: dict[str, list[datetime]] = defaultdict(
                        list
                    )
                    for row, times in zip(self.rows, self.times):
                        label_end = times.get("label_end_time")
                        split_name = row.get("split")
                        if (
                            label_end is not None
                            and split_name in split_order
                        ):
                            label_ends_by_split[split_name].append(
                                label_end.astimezone(local_zone)
                            )
                    for left, right in zip(split_order, split_order[1:]):
                        left_end = window_dates[left][1]
                        right_start = window_dates[right][0]
                        nominal_boundary = datetime.combine(
                            left_end + timedelta(days=1),
                            time.min,
                            tzinfo=local_zone,
                        )
                        latest_label_end = max(
                            label_ends_by_split.get(left, [nominal_boundary])
                        )
                        clean_after = max(nominal_boundary, latest_label_end)
                        right_boundary = datetime.combine(
                            right_start,
                            time.min,
                            tzinfo=local_zone,
                        )
                        observed_gap_sessions = sum(
                            (
                                opened > clean_after
                                if closed
                                else opened >= clean_after
                            )
                            and opened < right_boundary
                            for opened in calendar_opens
                        )
                        if observed_gap_sessions < contract_embargo_sessions:
                            failures.append(
                                self.issue(
                                    f"research_contract.splits.{left}->{right}",
                                    "clean calendar-backed gap after the latest consumed label is shorter than the frozen embargo",
                                    required_sessions=contract_embargo_sessions,
                                    observed_sessions=observed_gap_sessions,
                                    clean_after=clean_after.isoformat(),
                                )
                            )
        self.add(
            "L002",
            failures,
            gaps,
            self.evidence(
                {
                    "interval_closure": label.get("interval_closure"),
                    "overlap_policy": label.get("overlap_policy"),
                    "purge_rule_sha256": sha_text(label.get("purge_rule")),
                    "contract_purge_rule_sha256": sha_text(view.get("purge_rule")),
                    "split_windows": view.get("split_windows"),
                }
            ),
            metrics={
                "cross_split_overlap_count": cross_split_overlap,
                "same_split_overlap_count": same_overlap,
            },
            notes=[
                "Same-split overlap is reported as dependence, not treated as leakage by itself."
            ],
            repair=(
                "Purge every interval that intersects another split and apply the frozen embargo; "
                "do not move split boundaries or relabel inside this audit."
            ),
        )

    def blocked(self, prerequisite: str) -> None:
        for check_id in CHECKS:
            if check_id not in self.results:
                self.add(
                    check_id,
                    [],
                    [
                        self.issue(
                            prerequisite, "prerequisite evidence is unavailable"
                        )
                    ],
                    [{"blocked_by": prerequisite}],
                    repair="Restore the prerequisite and rerun the audit.",
                )

    def run_check(self, check_id: str, method: Any) -> None:
        """Convert caller-supplied nested-shape errors into a published rejection."""
        try:
            self.validate_input_shapes(check_id)
            method()
        except InputShapeError as error:
            self.add(
                check_id,
                [
                    self.issue(
                        error.locator,
                        "malformed nested input shape prevents this predicate from being evaluated",
                        error_type="InputShapeError",
                        expected_shape=error.expected,
                        actual_type=error.actual_type,
                        detail=str(error)[:300],
                    )
                ],
                [],
                self.evidence({"structured_shape_rejection": True}),
                repair=(
                    "Restore the documented object/list shape for this input and rerun; "
                    "do not treat a structurally invalid artifact as eligible evidence."
                ),
            )

    def run(self) -> dict[str, Any]:
        self.run_check("I001", self.check_i001_inputs)
        if not self.request or "data" not in self.docs:
            self.blocked("I001")
            return self.manifest()
        for check_id, method in (
            ("I002", self.check_i002_contract),
            ("S001", self.check_s001_schema),
            ("T001", self.check_t001_time_roles),
            ("T002", self.check_t002_availability),
            ("T003", self.check_t003_revision),
            ("U001", self.check_u001_membership),
            ("U002", self.check_u002_population),
            ("C001", self.check_c001_calendar),
            ("M001", self.check_m001_identity),
            ("A001", self.check_a001_adjustment),
            ("H001", self.check_h001_halts),
            ("Q001", self.check_q001_uniqueness),
            ("Q002", self.check_q002_values),
            ("Q003", self.check_q003_domains),
            ("L001", self.check_l001_label),
            ("L002", self.check_l002_split_isolation),
        ):
            self.run_check(check_id, method)
        self.blocked("internal")
        return self.manifest()

    def manifest(self) -> dict[str, Any]:
        ordered = [self.results[check_id] for check_id in CHECKS]
        status = max(
            (item["status"] for item in ordered), key=RANK.get, default=NEEDS
        )
        qualification = (
            (
                "TEST_ONLY"
                if self.execution_boundary == "INTERNAL_TEST_ONLY"
                else "QUALIFIED"
            )
            if status == PASS
            else "NOT_QUALIFIED"
            if status == FAIL
            else "UNRESOLVED"
        )
        view = self.contract_view()
        lineage = [
            {
                "artifact": name,
                "path": metadata.get("path"),
                "declared_sha256": metadata.get("sha256"),
                "verified_sha256": self.hashes.get(name),
                "version": metadata.get("version")
                or metadata.get("source_version"),
            }
            for name, metadata in sorted(self.meta.items())
            if isinstance(metadata, dict)
        ]
        receipt_meta = path_get(
            self.request, "artifacts.research_contract.validation_receipt", {}
        )
        if isinstance(receipt_meta, dict):
            lineage.append(
                {
                    "artifact": "contract_validation",
                    "path": receipt_meta.get("path"),
                    "declared_sha256": receipt_meta.get("sha256"),
                    "verified_sha256": self.hashes.get("contract_validation"),
                    "version": path_get(
                        self.docs.get("contract_validation", {}),
                        "validator_version",
                    ),
                }
            )
        lineage.sort(key=lambda item: str(item.get("artifact")))
        blockers = [item for item in ordered if item["status"] != PASS]
        highest_blockers = [
            item for item in ordered if item["status"] == status
        ]
        core = {
            "schema_version": "pit_audit_manifest_v1",
            "request_id": self.request.get("request_id"),
            "request_sha256": sha_file(self.request_path)
            if self.request_path.is_file()
            else None,
            "run_at": self.request.get("run_at"),
            "status": status,
            "pit_qualification": qualification,
            "claim": self.request.get("claim"),
            "evidence_ceiling": (
                PASS
                if path_get(self.request, "coverage.scope")
                == "FULL_TRAINING_INPUT"
                else NEEDS
            ),
            "status_precedence": "FAIL > NEEDS_EVIDENCE > PASS",
            "contract_binding": {
                "adapter": view.get("adapter"),
                "test_only_adapter": (
                    view.get("adapter") == "pit_contract_binding_v1"
                ),
                "execution_boundary": self.execution_boundary,
                "contract_id": view.get("contract_id"),
                "canonical_hash": view.get("canonical_hash"),
                "file_sha256": self.hashes.get("research_contract"),
                "label_spec_hash": path_get(
                    self.docs.get("label_definition", {}), "label_spec_hash"
                ),
            },
            "runtime_trust": {
                "matched_review_authority_sha256": (
                    self.hashes.get("review_authority")
                    if self.hashes.get("review_authority")
                    in self.trusted_review_authority_sha256
                    else None
                ),
                "matched_semantic_review_receipt_sha256": (
                    path_get(
                        self.docs.get("label_schedule", {}),
                        "semantic_review.receipt_hash",
                    )
                    if path_get(
                        self.docs.get("label_schedule", {}),
                        "semantic_review.receipt_hash",
                    )
                    in self.trusted_semantic_review_receipt_sha256
                    else None
                ),
                "matched_interval_authority_sha256": (
                    self.hashes.get("label_interval_authority")
                    if self.hashes.get("label_interval_authority")
                    in self.trusted_interval_authority_sha256
                    else None
                ),
            },
            "input_artifacts": sorted(self.hashes),
            "lineage": lineage,
            "time_semantics": {
                "timezone": path_get(
                    self.docs.get("time_semantics", {}), "timezone"
                ),
                "tzdb_version": path_get(
                    self.docs.get("time_semantics", {}), "tzdb_version"
                ),
                "availability_comparison": path_get(
                    self.docs.get("time_semantics", {}),
                    "availability_comparison",
                ),
            },
            "coverage_matrix": {
                "scope": path_get(self.request, "coverage.scope"),
                "expected_rows": path_get(
                    self.request, "coverage.expected_row_count"
                ),
                "parsed_rows": len(self.rows),
                "expected_security_time_keys": path_get(
                    self.request,
                    "coverage.population.expected_security_time_keys",
                ),
                "observed_security_time_keys": len(
                    {
                        (row.get("security_id"), row.get("prediction_time"))
                        for row in self.rows
                    }
                ),
                "expected_matrix_cells": path_get(
                    self.docs.get("matrix_manifest", {}),
                    "expected_cell_count",
                ),
                "observed_matrix_cells": len(
                    {
                        (
                            row.get("security_id"),
                            row.get("prediction_time"),
                            row.get("feature_name"),
                        )
                        for row in self.rows
                    }
                ),
                "source_id": path_get(self.request, "artifacts.data.source_id"),
                "source_version": path_get(
                    self.request, "artifacts.data.source_version"
                ),
                "snapshot_id": path_get(
                    self.request, "artifacts.data.snapshot_id"
                ),
                "snapshot_binding_mode": path_get(
                    self.request, "artifacts.data.snapshot_binding_mode"
                ),
            },
            "checks": ordered,
            "findings": {
                "fail_check_ids": [
                    item["check_id"] for item in ordered if item["status"] == FAIL
                ],
                "needs_evidence_check_ids": [
                    item["check_id"]
                    for item in ordered
                    if item["status"] == NEEDS
                ],
                "total_reported_issues": sum(
                    item["violation_count"] for item in ordered
                ),
            },
            "limitations": [
                "The audit validates bound evidence; it cannot prove a vendor description is truthful.",
                "Hashes and receipts cannot prove that no off-system future data was consulted.",
                "Qualification applies only to the exact claim, consumed-value view, and hashes shown.",
            ],
            "one_next_action": (
                highest_blockers[0]["minimal_remediation"]
                if highest_blockers
                else None
            ),
            "training_allowed": False,
            "scope_note": (
                "Data eligibility only: no model training, alpha calculation, deployment approval, "
                "or capital decision is performed."
            ),
        }
        content_sha = sha_value(core)
        manifest = {
            **core,
            "audit_id": f"pit-audit-v1-{content_sha[:32]}",
            "content_sha256": content_sha,
        }
        manifest["report_sha256"] = hashlib.sha256(
            report(manifest).encode("utf-8")
        ).hexdigest()
        return manifest


def report(manifest: dict[str, Any]) -> str:
    decision = {
        PASS: (
            "The exact frozen input is PIT-qualified for the stated claim. "
            "This does not authorize training or trading."
        ),
        FAIL: (
            "The input is not PIT-qualified: at least one explicit contradiction "
            "or leakage condition was found."
        ),
        NEEDS: (
            "PIT qualification is withheld because semantic, version, contract, "
            "or coverage evidence is incomplete."
        ),
    }[manifest["status"]]
    lines = [
        "# Point-in-Time Data Audit",
        "",
        "- Report schema: `pit_audit_report_v1`",
        f"- Audit ID: `{manifest['audit_id']}`",
        f"- Manifest content SHA-256: `{manifest['content_sha256']}`",
        f"- Result: **{manifest['status']}**",
        f"- PIT qualification: `{manifest['pit_qualification']}`",
        f"- Claim: `{manifest.get('claim')}`",
        f"- Coverage: `{manifest['coverage_matrix'].get('scope')}`",
        f"- Contract: `{manifest['contract_binding'].get('contract_id')}`",
        f"- Contract adapter: `{manifest['contract_binding'].get('adapter')}`",
        f"- Execution boundary: `{manifest['contract_binding'].get('execution_boundary')}`",
        f"- Matched review-authority anchor: `{manifest['runtime_trust'].get('matched_review_authority_sha256') or 'none'}`",
        f"- Matched semantic-review receipt anchor: `{manifest['runtime_trust'].get('matched_semantic_review_receipt_sha256') or 'none'}`",
        f"- Matched interval-authority anchor: `{manifest['runtime_trust'].get('matched_interval_authority_sha256') or 'none'}`",
        f"- Rows: `{manifest['coverage_matrix'].get('parsed_rows')}`",
        "",
        "## Decision",
        "",
        decision,
        "",
        "## Findings",
        "",
        f"- FAIL checks: `{','.join(manifest['findings']['fail_check_ids']) or 'none'}`",
        f"- NEEDS_EVIDENCE checks: `{','.join(manifest['findings']['needs_evidence_check_ids']) or 'none'}`",
        f"- Total reported issues: `{manifest['findings']['total_reported_issues']}`",
        "",
        "## Lineage",
        "",
        "| Artifact | Version | Verified SHA-256 |",
        "| --- | --- | --- |",
    ]
    for item in manifest["lineage"]:
        lines.append(
            f"| `{item['artifact']}` | `{item.get('version') or 'n/a'}` | "
            f"`{item.get('verified_sha256') or 'unverified'}` |"
        )
    lines += [
        "",
        "## Checks",
        "",
        "| ID | Result | Rows | Issues | Evidence digest |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for item in manifest["checks"]:
        lines.append(
            f"| `{item['check_id']}` {item['title']} | **{item['status']}** | "
            f"{item['checked_rows']} | {item['violation_count']} | "
            f"`{item['evidence_digest']}` |"
        )
    blockers = [item for item in manifest["checks"] if item["status"] != PASS]
    lines += ["", "## Blocking evidence", ""]
    if not blockers:
        lines.append("No blocking evidence.")
    for item in blockers:
        lines += [f"### {item['check_id']} — {item['status']}", ""]
        for issue in item["violations"][:10]:
            lines.append(
                f"- `{issue.get('locator', 'unknown')}`: "
                f"{issue.get('reason', 'unspecified')}"
            )
        lines += ["", f"Minimal repair: {item['minimal_remediation']}", ""]
    lines += [
        "## Boundary",
        "",
        manifest["scope_note"],
        "",
        f"Next action: {manifest['one_next_action'] or 'Preserve and hand off the immutable PASS manifest.'}",
        "",
    ]
    return "\n".join(lines)


def write_outputs(output_dir: Path, manifest: dict[str, Any]) -> None:
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise FileExistsError("output directory must be new or empty")
        output_dir.rmdir()
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-",
            dir=output_dir.parent,
        )
    )
    try:
        report_text = report(manifest)
        if hashlib.sha256(report_text.encode("utf-8")).hexdigest() != manifest.get(
            "report_sha256"
        ):
            raise ValueError("report bytes do not match manifest report_sha256")
        payloads = {
            "audit_report.md": report_text.encode("utf-8"),
            "audit_manifest.json": (
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"),
        }
        for name, payload in payloads.items():
            path = staging / name
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(
    argv: list[str] | None = None,
    *,
    _allow_test_adapter_for_tests: bool = False,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="Path to audit_request.json")
    parser.add_argument("--output-dir", required=True, help="New or empty output directory")
    parser.add_argument(
        "--trusted-review-authority-sha256",
        action="append",
        default=[],
        help="Request-external trusted SHA-256 for review_authority.json; repeatable.",
    )
    parser.add_argument(
        "--trusted-interval-authority-sha256",
        action="append",
        default=[],
        help="Request-external trusted SHA-256 for label_interval_authority.json; repeatable.",
    )
    parser.add_argument(
        "--trusted-semantic-review-receipt-sha256",
        action="append",
        default=[],
        help="Request-external trusted SHA-256 for the exact semantic-review receipt; repeatable.",
    )
    args = parser.parse_args(argv)
    for value in [
        *args.trusted_review_authority_sha256,
        *args.trusted_semantic_review_receipt_sha256,
        *args.trusted_interval_authority_sha256,
    ]:
        if not is_sha(value):
            parser.error("trusted runtime values must be lowercase SHA-256")
    output_dir = Path(args.output_dir)
    if output_dir.exists() and (
        not output_dir.is_dir() or any(output_dir.iterdir())
    ):
        print("ERROR: output directory must be new or empty", file=sys.stderr)
        return 64
    try:
        manifest = Audit(
            Path(args.request),
            output_dir,
            _allow_test_adapter_for_tests=_allow_test_adapter_for_tests,
            trusted_review_authority_sha256=set(
                args.trusted_review_authority_sha256
            ),
            trusted_semantic_review_receipt_sha256=set(
                args.trusted_semantic_review_receipt_sha256
            ),
            trusted_interval_authority_sha256=set(
                args.trusted_interval_authority_sha256
            ),
        ).run()
        write_outputs(output_dir, manifest)
    except Exception as error:  # never emit a qualified artifact after an internal error
        print(f"ERROR: audit aborted without qualification: {error}", file=sys.stderr)
        return 64
    print(f"{manifest['status']}: {manifest['audit_id']}")
    return {PASS: 0, NEEDS: 2, FAIL: 3}[manifest["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
