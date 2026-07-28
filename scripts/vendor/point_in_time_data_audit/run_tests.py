#!/usr/bin/env python3
"""Run the deterministic adversarial suite for audit_pit.py."""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


EXPECTED_CASE_COUNT = 89
EXPECTED_CASES_SHA256 = (
    "e493e231f6c7408578256c6a5e2ed0e6efaced42019716630d68f785b8e0684a"
)
EXPECTED_BASE_CASE_SHA256 = (
    "1ccbe716d1ae1fc3324115beb5d580178bc39d8d49dbbdc9eee16eaf7c10f445"
)
EXPECTED_QRC_CASE_COUNT = 46
EXPECTED_QRC_CASES_SHA256 = (
    "f1922ab52556439d33e91c6775eba3f6311f955ca311deff9a6f006605eef8ff"
)
STATUS_EXIT_CODES = {"PASS": 0, "NEEDS_EVIDENCE": 2, "FAIL": 3}
EXECUTION_PATHS = {
    "production_cli",
    "production_cli_without_anchors",
    "internal_test_adapter",
}
INTERNAL_TEST_DRIVER = (
    "import importlib.util,sys;"
    "spec=importlib.util.spec_from_file_location('pit_audit_internal_test',sys.argv[1]);"
    "module=importlib.util.module_from_spec(spec);"
    "spec.loader.exec_module(module);"
    "raise SystemExit(module.main(sys.argv[2:],_allow_test_adapter_for_tests=True))"
)
TRACE_REQUIRED_FIELDS = {
    "I001": set(),
    "I002": {"event_time", "vendor_available_time", "prediction_time", "split"},
    "S001": "__ALL_FIELDS__",
    "T001": "__ALL_TIME_FIELDS__",
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
    "Q002": "__ALL_FIELDS__",
    "Q003": {"feature_name", "feature_value"},
    "L001": {"prediction_time", "label_start_time", "label_end_time"},
    "L002": {
        "split",
        "prediction_time",
        "label_start_time",
        "label_end_time",
    },
}
TRACE_REQUIRED_EXTERNAL = {
    "I001": {"dictionary"},
    "I002": {"contract_validation", "label"},
    "U002": {"population"},
    "C001": {"calendar"},
    "L001": {"label"},
    "L002": {"label"},
}
TRACE_REQUIRED_FEATURE_POLICIES = {
    "S001": {"source_locator"},
    "T002": {"source_locator"},
    "A001": {"source_locator", "adjustment_policy.source_locator"},
    "Q003": {"source_locator", "domain_policy.source_locator"},
}
ZERO_SHA256 = "0" * 64
WRONG_FEATURE_SPEC_SHA256 = (
    "b463b6cf39698985bd669cfcb44cdbad6e1804d304d57c7c2d5790b52d894ed4"
)
CRITICAL_BINDING_MUTATIONS: tuple[tuple[Any, ...], ...] = (
    ("session_prediction_time_mismatch", "session_schedule_pass", "before_hash", "replace", "data_rows", "/0/prediction_time", "2024-04-01T14:01:00Z", "L001", "data#row_id=row-001.prediction_time"),
    ("session_label_start_time_mismatch", "session_schedule_pass", "before_hash", "replace", "data_rows", "/0/label_start_time", "2024-04-01T19:59:00Z", "L001", "data#row_id=row-001.label_start_time"),
    ("session_label_end_time_mismatch", "session_schedule_pass", "before_hash", "replace", "data_rows", "/0/label_end_time", "2024-04-02T19:59:00Z", "L001", "data#row_id=row-001.label_end_time"),
    ("matrix_sample_population_manifest_sha_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/sample_prediction_axis/population_manifest_sha256", ZERO_SHA256, "U002", "matrix_manifest.sample_prediction_axis.population_manifest_sha256"),
    ("matrix_sample_population_manifest_receipt_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/sample_prediction_axis/population_manifest_receipt_hash", ZERO_SHA256, "U002", "matrix_manifest.sample_prediction_axis.population_manifest_receipt_hash"),
    ("matrix_sample_population_source_sha_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/sample_prediction_axis/population_source_sha256", ZERO_SHA256, "U002", "matrix_manifest.sample_prediction_axis.population_source_sha256"),
    ("matrix_sample_expected_key_set_sha_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/sample_prediction_axis/expected_key_set_sha256", ZERO_SHA256, "U002", "matrix_manifest.sample_prediction_axis.expected_key_set_sha256"),
    ("matrix_feature_spec_version_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/feature_axis/feature_spec_version", "wrong-feature-spec-v9", "I002", "matrix_binding.feature_spec_version"),
    ("matrix_feature_spec_hash_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/feature_axis/feature_spec_hash", ZERO_SHA256, "I002", "matrix_binding.feature_spec_hash"),
    ("matrix_feature_expected_count_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/feature_axis/expected_feature_count", 2, "Q001", "matrix_manifest.feature_axis"),
    ("matrix_feature_set_sha_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/feature_axis/feature_set_sha256", ZERO_SHA256, "Q001", "matrix_manifest.feature_axis"),
    ("matrix_label_id_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/label_id", "wrong-label", "I002", "matrix_binding.label_id"),
    ("matrix_label_spec_version_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/label_spec_version", "wrong-label-spec-v9", "I002", "matrix_binding.label_spec_version"),
    ("matrix_label_spec_hash_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/label_spec_hash", ZERO_SHA256, "I002", "matrix_binding.label_spec_hash"),
    ("matrix_label_schedule_id_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/label_schedule_id", "wrong-schedule", "I002", "matrix_binding.label_schedule_id"),
    ("matrix_label_schedule_version_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/label_schedule_version", "999", "I002", "matrix_binding.label_schedule_version"),
    ("matrix_prediction_rule_hash_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/prediction_time_rule_sha256", ZERO_SHA256, "I002", "matrix_binding.prediction_time_rule_sha256"),
    ("matrix_execution_rule_hash_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/execution_time_rule_sha256", ZERO_SHA256, "I002", "matrix_binding.execution_time_rule_sha256"),
    ("matrix_label_start_rule_hash_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/label_start_rule_sha256", ZERO_SHA256, "I002", "matrix_binding.label_start_rule_sha256"),
    ("matrix_label_end_rule_hash_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/label_axis/label_end_rule_sha256", ZERO_SHA256, "I002", "matrix_binding.label_end_rule_sha256"),
    ("matrix_applicability_rule_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/layout/applicability_rule", "SOME_FEATURES_APPLY", "I002", "matrix_manifest.layout"),
    ("matrix_applicability_digest_mismatch", "clean_market_full_pass", "coherent_after_refresh", "replace", "matrix_manifest", "/layout/applicability_rule_sha256", ZERO_SHA256, "I002", "matrix_manifest.layout"),
    ("schedule_top_shadow_rejected", "clean_market_full_pass", "coherent_after_refresh", "add", "label_schedule", "/shadow_field", True, "I002", "label_schedule.shadow_field"),
    ("schedule_contract_binding_shadow_rejected", "clean_market_full_pass", "coherent_after_refresh", "add", "label_schedule", "/contract_binding/shadow_field", True, "I002", "label_schedule.contract_binding.shadow_field"),
    ("schedule_rule_hashes_shadow_rejected", "clean_market_full_pass", "coherent_after_refresh", "add", "label_schedule", "/contract_binding/rule_hashes/shadow_field", ZERO_SHA256, "I002", "label_schedule.contract_binding.rule_hashes.shadow_field"),
    ("schedule_label_binding_shadow_rejected", "clean_market_full_pass", "coherent_after_refresh", "add", "label_schedule", "/label_binding/shadow_field", True, "I002", "label_schedule.label_binding.shadow_field"),
    ("schedule_session_resolver_shadow_rejected", "session_schedule_pass", "coherent_after_refresh", "add", "label_schedule", "/resolver/shadow_field", True, "I002", "label_schedule.resolver.shadow_field"),
    ("schedule_semantic_review_shadow_rejected", "clean_market_full_pass", "coherent_after_refresh", "add", "label_schedule", "/semantic_review/shadow_field", True, "I002", "label_schedule.semantic_review.shadow_field"),
)
EXPECTED_CRITICAL_BINDING_MUTATION_COUNT = 28
EXPECTED_CRITICAL_BINDING_MUTATIONS_SHA256 = (
    "d3cc463f2a7863155b2c1f373210106f634a51cc4f52ca2b0fa459702c0d88c4"
)
QRC_CASES = [
    {
        "case_id": "qrc_clean_production_adapter",
        "variant": "clean",
        "expected": {"status": "PASS", "pit_qualification": "QUALIFIED"},
    },
    {
        "case_id": "qrc_system_blank_ingestion_batch",
        "variant": "system_blank_ingestion_batch",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"T002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_wrong_receipt_schema",
        "variant": "wrong_receipt_schema",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_receipt_contract_hash_mismatch",
        "variant": "receipt_contract_hash_mismatch",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_validator_bundle_forgery",
        "variant": "validator_bundle_forgery",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_event_source_field_conflict",
        "variant": "event_source_field_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_availability_source_field_conflict",
        "variant": "availability_source_field_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_availability_comparator_conflict",
        "variant": "availability_comparator_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_label_id_conflict",
        "variant": "label_id_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_label_spec_version_conflict",
        "variant": "label_spec_version_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_label_formula_conflict",
        "variant": "label_formula_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_neutralization_rule_conflict",
        "variant": "neutralization_rule_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_feature_semantics_drift",
        "variant": "feature_semantics_drift",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_contract_feature_spec_hash_mismatch",
        "variant": "contract_feature_spec_hash_mismatch",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
            "required_issue_locator": {
                "I002": "matrix_binding.contract_feature_spec_hash"
            },
        },
    },
    {
        "case_id": "qrc_rectangular_expected_cells_override",
        "variant": "rectangular_expected_cells_override",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
        },
    },
    {
        "case_id": "qrc_missing_holding_period_binding",
        "variant": "missing_holding_period_binding",
        "expected": {
            "status": "NEEDS_EVIDENCE",
            "pit_qualification": "UNRESOLVED",
            "required_check_status": {"I002": "NEEDS_EVIDENCE"},
        },
    },
    {
        "case_id": "qrc_prediction_outside_split_window",
        "variant": "prediction_outside_split_window",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"L002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_wrong_split_for_valid_date",
        "variant": "wrong_split_for_valid_date",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"L002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_label_crosses_selection_without_peer",
        "variant": "label_crosses_selection_without_peer",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"L002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_label_purge_rule_conflict",
        "variant": "label_purge_rule_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"L002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_missing_purge_binding",
        "variant": "missing_purge_binding",
        "expected": {
            "status": "NEEDS_EVIDENCE",
            "pit_qualification": "UNRESOLVED",
            "required_check_status": {"I002": "NEEDS_EVIDENCE"},
        },
    },
    {
        "case_id": "qrc_embargo_understatement",
        "variant": "embargo_understatement",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"L002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_label_consumes_nominal_embargo_gap",
        "variant": "label_consumes_nominal_embargo_gap",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"L002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_coordinated_data_manifest_deletion",
        "variant": "coordinated_data_manifest_deletion",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"U002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_pit_adjusted_arbitrary_value",
        "variant": "pit_adjusted_arbitrary_value",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"A001": "FAIL"},
        },
    },
    {
        "case_id": "qrc_inverse_availability_pipeline_clocks",
        "variant": "inverse_availability_pipeline_clocks",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"T002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_calendar_version_not_frozen",
        "variant": "calendar_version_not_frozen",
        "expected": {
            "status": "NEEDS_EVIDENCE",
            "pit_qualification": "UNRESOLVED",
            "required_check_status": {"I002": "NEEDS_EVIDENCE"},
        },
    },
    {
        "case_id": "qrc_source_version_conflict",
        "variant": "source_version_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_data_bytes_drift_under_frozen_snapshot",
        "variant": "data_bytes_drift_under_frozen_snapshot",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
            "required_issue_locator": {
                "I001": "request.artifacts.data.source_snapshot_sha256"
            },
        },
    },
    {
        "case_id": "qrc_duplicate_data_header",
        "variant": "duplicate_data_header",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
            "required_issue_locator": {"I001": "data.header"},
        },
    },
    {
        "case_id": "qrc_duplicate_calendar_header",
        "variant": "duplicate_calendar_header",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
            "required_issue_locator": {"I001": "calendar.header"},
        },
    },
    {
        "case_id": "qrc_extra_data_cell",
        "variant": "extra_data_cell",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
            "required_issue_locator": {"I001": "data#csv_row=2"},
        },
    },
    {
        "case_id": "qrc_missing_calendar_cell",
        "variant": "missing_calendar_cell",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
            "required_issue_locator": {"I001": "calendar#csv_row=2"},
        },
    },
    {
        "case_id": "qrc_population_history_interpretation_conflict",
        "variant": "population_history_interpretation_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
        },
    },
    {
        "case_id": "qrc_nan_domain_bound",
        "variant": "nan_domain_bound",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
        },
    },
    {
        "case_id": "qrc_infinity_domain_bound",
        "variant": "infinity_domain_bound",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
        },
    },
    {
        "case_id": "qrc_duplicate_dictionary_key",
        "variant": "duplicate_dictionary_key",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "FAIL"},
        },
    },
    {
        "case_id": "qrc_label_schedule_rule_conflict",
        "variant": "label_schedule_rule_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
            "required_issue_locator": {
                "I002": "label_schedule.contract_binding.rule_hashes.holding_period"
            },
        },
    },
    {
        "case_id": "qrc_execution_schedule_rule_conflict",
        "variant": "execution_schedule_rule_conflict",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
            "required_issue_locator": {
                "I002": "label_schedule.contract_binding.rule_hashes.execution_time"
            },
        },
    },
    {
        "case_id": "qrc_label_interval_drift_after_schedule_freeze",
        "variant": "label_interval_drift_after_schedule_freeze",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "PASS", "I002": "PASS", "L001": "FAIL"},
            "required_issue_locator": {
                "L001": "label_interval_authority.expected_interval_set_sha256"
            },
        },
    },
    {
        "case_id": "qrc_execution_time_drift_after_schedule_freeze",
        "variant": "execution_time_drift_after_schedule_freeze",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I001": "PASS", "I002": "PASS", "L001": "FAIL"},
            "required_issue_locator": {
                "L001": "label_interval_authority.expected_interval_set_sha256"
            },
        },
    },
    {
        "case_id": "qrc_review_before_contract_freeze",
        "variant": "review_before_contract_freeze",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
            "required_issue_locator": {
                "I002": "label_schedule.semantic_review.reviewed_at"
            },
        },
    },
    {
      "case_id": "qrc_untrusted_review_authority",
        "variant": "untrusted_review_authority",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
            "required_issue_locator": {
                "I002": "runtime.trusted_review_authority_sha256"
            },
        },
    },
    {
        "case_id": "qrc_forged_authorized_semantic_review",
        "variant": "forged_authorized_semantic_review",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
            "required_issue_locator": {
                "I002": "runtime.trusted_semantic_review_receipt_sha256"
            },
        },
    },
    {
        "case_id": "qrc_untrusted_interval_authority",
        "variant": "untrusted_interval_authority",
        "expected": {
            "status": "FAIL",
            "pit_qualification": "NOT_QUALIFIED",
            "required_check_status": {"I002": "FAIL"},
            "required_issue_locator": {
                "I002": "runtime.trusted_interval_authority_sha256"
            },
        },
    },
    {
        "case_id": "qrc_missing_runtime_trust_anchors",
        "variant": "missing_runtime_trust_anchors",
        "execution_path": "production_cli_without_anchors",
        "expected": {
            "status": "NEEDS_EVIDENCE",
            "pit_qualification": "UNRESOLVED",
            "required_check_status": {"I002": "NEEDS_EVIDENCE"},
            "required_issue_locator": {
                "I002": [
                    "runtime.trusted_review_authority_sha256",
                    "runtime.trusted_semantic_review_receipt_sha256",
                    "runtime.trusted_interval_authority_sha256"
                ]
            },
        },
    },
]
FILE_NAMES = {
    "request": "audit_request.json",
    "data_rows": "training_evidence.csv",
    "schema": "schema.json",
    "dictionary": "dictionary.json",
    "time_semantics": "time_semantics.json",
    "contract": "research_contract.json",
    "contract_validation": "contract_validation.json",
    "label_definition": "label_definition.json",
    "label_schedule": "label_schedule.json",
    "review_authority": "review_authority.json",
    "label_interval_authority": "label_interval_authority.json",
    "calendar": "calendar.csv",
    "population_manifest": "population_manifest.json",
    "population_source": "population_source.json",
    "matrix_manifest": "matrix_manifest.json",
}


class SuiteError(RuntimeError):
    """Raised when the fixture specification is invalid."""


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    )


def csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: (
                    ""
                    if value is None
                    else str(value).lower()
                    if isinstance(value, bool)
                    else value
                )
                for key, value in row.items()
            }
        )
    return buffer.getvalue().encode("utf-8")


def csv_table_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def duplicate_csv_column(
    payload: bytes, column: str, shadow_value: str
) -> bytes:
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8"))))
    if len(rows) < 2 or column not in rows[0]:
        raise SuiteError(f"cannot duplicate CSV column {column!r}")
    index = rows[0].index(column)
    rows[0].insert(index, column)
    for row in rows[1:]:
        row.insert(index, shadow_value)
    return csv_table_bytes(rows)


def widen_first_csv_row(payload: bytes, extra_value: str) -> bytes:
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8"))))
    if len(rows) < 2:
        raise SuiteError("cannot widen an empty CSV")
    rows[1].append(extra_value)
    return csv_table_bytes(rows)


def narrow_first_csv_row(payload: bytes) -> bytes:
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8"))))
    if len(rows) < 2 or not rows[1]:
        raise SuiteError("cannot narrow an empty CSV")
    rows[1].pop()
    return csv_table_bytes(rows)


def decode_pointer(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise SuiteError(f"invalid RFC 6901 pointer: {pointer!r}")
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer[1:].split("/")
    ]


def list_index(token: str, length: int, *, allow_append: bool) -> int:
    if token == "-" and allow_append:
        return length
    if not token or (token.startswith("0") and token != "0") or not token.isdigit():
        raise SuiteError(f"invalid JSON Pointer list index: {token!r}")
    index = int(token)
    upper = length if allow_append else length - 1
    if index < 0 or index > upper:
        raise SuiteError(f"list index {index} is out of bounds for length {length}")
    return index


def pointer_get(root: Any, pointer: str) -> Any:
    value = root
    for token in decode_pointer(pointer):
        if isinstance(value, list):
            value = value[list_index(token, len(value), allow_append=False)]
        elif isinstance(value, dict):
            if token not in value:
                raise SuiteError(f"JSON Pointer does not exist: {pointer}")
            value = value[token]
        else:
            raise SuiteError(f"JSON Pointer traverses a scalar: {pointer}")
    return value


def path_get(root: Any, dotted: str) -> Any:
    value = root
    for part in dotted.split("."):
        if isinstance(value, list):
            if not part.isdigit() or int(part) >= len(value):
                raise SuiteError(f"dotted path does not exist: {dotted}")
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise SuiteError(f"dotted path does not exist: {dotted}")
    return value


def patch_value(root: Any, raw: Any) -> Any:
    if not isinstance(raw, dict) or "$copy" not in raw:
        return copy.deepcopy(raw)
    if set(raw) - {"$copy", "$overrides"}:
        raise SuiteError("$copy values may contain only $copy and $overrides")
    value = copy.deepcopy(pointer_get(root, raw["$copy"]))
    overrides = raw.get("$overrides", {})
    if not isinstance(value, dict) or not isinstance(overrides, dict):
        raise SuiteError("$copy overrides require object source and object overrides")
    value.update(copy.deepcopy(overrides))
    return value


def apply_mutation(workspace: dict[str, Any], mutation: dict[str, Any]) -> None:
    artifact = mutation.get("artifact")
    if artifact not in workspace:
        raise SuiteError(f"unknown mutation artifact: {artifact!r}")
    operation = mutation.get("op")
    if operation not in {"add", "remove", "replace"}:
        raise SuiteError(f"unsupported mutation operation: {operation!r}")
    pointer = mutation.get("pointer")
    tokens = decode_pointer(pointer)
    if not tokens:
        if operation == "remove":
            raise SuiteError("removing an artifact root is not supported")
        workspace[artifact] = patch_value(workspace[artifact], mutation.get("value"))
        return

    root = workspace[artifact]
    parent = root
    for token in tokens[:-1]:
        if isinstance(parent, list):
            parent = parent[list_index(token, len(parent), allow_append=False)]
        elif isinstance(parent, dict) and token in parent:
            parent = parent[token]
        else:
            raise SuiteError(f"mutation parent does not exist: {pointer}")
    final = tokens[-1]

    if isinstance(parent, list):
        if operation == "add":
            index = list_index(final, len(parent), allow_append=True)
            parent.insert(index, patch_value(root, mutation.get("value")))
        else:
            index = list_index(final, len(parent), allow_append=False)
            if operation == "remove":
                parent.pop(index)
            else:
                parent[index] = patch_value(root, mutation.get("value"))
    elif isinstance(parent, dict):
        if operation in {"remove", "replace"} and final not in parent:
            raise SuiteError(f"mutation target does not exist: {pointer}")
        if operation == "remove":
            del parent[final]
        else:
            parent[final] = patch_value(root, mutation.get("value"))
    else:
        raise SuiteError(f"mutation parent is a scalar: {pointer}")


def replace_token(value: Any, token: str, replacement: str) -> Any:
    if isinstance(value, str):
        return replacement if value == token else value
    if isinstance(value, list):
        return [replace_token(item, token, replacement) for item in value]
    if isinstance(value, dict):
        return {
            key: replace_token(item, token, replacement)
            for key, item in value.items()
        }
    return value


def replace_everywhere(
    workspace: dict[str, Any], token: str, replacement: str
) -> None:
    for name, value in list(workspace.items()):
        workspace[name] = replace_token(value, token, replacement)


def unresolved_tokens(value: Any, where: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, str) and value.startswith("@AUTO_"):
        found.append(f"{where or '/'}={value}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(unresolved_tokens(item, f"{where}/{index}"))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(unresolved_tokens(item, f"{where}/{key}"))
    return found


def serialized_artifacts(workspace: dict[str, Any]) -> dict[str, bytes]:
    schema = workspace["schema"]
    columns = schema.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise SuiteError("base schema must declare ordered columns")
    return {
        "data_rows": csv_bytes(workspace["data_rows"], list(columns)),
        "calendar": csv_bytes(
            workspace["calendar"],
            ["session_id", "open_time", "close_time", "break_start", "break_end"],
        ),
        "schema": json_bytes(workspace["schema"]),
        "dictionary": json_bytes(workspace["dictionary"]),
        "time_semantics": json_bytes(workspace["time_semantics"]),
        "contract": json_bytes(workspace["contract"]),
        "contract_validation": json_bytes(workspace["contract_validation"]),
        "label_definition": json_bytes(workspace["label_definition"]),
        "label_schedule": json_bytes(workspace["label_schedule"]),
        "review_authority": json_bytes(workspace["review_authority"]),
        "label_interval_authority": json_bytes(
            workspace["label_interval_authority"]
        ),
        "population_manifest": json_bytes(workspace["population_manifest"]),
        "population_source": json_bytes(workspace["population_source"]),
        "matrix_manifest": json_bytes(workspace["matrix_manifest"]),
        "request": json_bytes(workspace["request"]),
    }


def freeze_tokens(workspace: dict[str, Any]) -> dict[str, bytes]:
    review_authority = copy.deepcopy(workspace["review_authority"])
    review_authority.pop("receipt_hash", None)
    workspace["review_authority"]["receipt_hash"] = sha256_bytes(
        canonical(review_authority)
    )
    interval_authority = copy.deepcopy(
        workspace["label_interval_authority"]
    )
    interval_authority.pop("receipt_hash", None)
    workspace["label_interval_authority"]["receipt_hash"] = sha256_bytes(
        canonical(interval_authority)
    )
    population_source = copy.deepcopy(workspace["population_source"])
    population_source.pop("receipt_hash", None)
    replace_everywhere(
        workspace,
        "@AUTO_POPULATION_SOURCE_RECEIPT_HASH",
        sha256_bytes(canonical(population_source)),
    )
    replace_everywhere(
        workspace,
        "@AUTO_FILE_SHA256:population_source",
        sha256_bytes(json_bytes(workspace["population_source"])),
    )
    population_keys = sorted(
        {
            (
                item["security_id"],
                item["prediction_time"].replace("Z", "+00:00"),
            )
            for item in workspace["population_manifest"]["keys"]
        }
    )
    replace_everywhere(
        workspace,
        "@AUTO_POPULATION_KEY_SET_SHA256",
        sha256_bytes(canonical([list(item) for item in population_keys])),
    )
    population = copy.deepcopy(workspace["population_manifest"])
    population.pop("receipt_hash", None)
    replace_everywhere(
        workspace,
        "@AUTO_POPULATION_RECEIPT_HASH",
        sha256_bytes(canonical(population)),
    )
    contract_for_policy = workspace["contract"]
    if contract_for_policy.get("schema_version") == "pit_contract_binding_v1":
        policy_values = {
            "FORMULA": pointer_get(
                contract_for_policy, "/label_formula"
            ),
            "NEUTRALIZATION_RULE": pointer_get(
                contract_for_policy, "/neutralization_rule"
            ),
            "CORPORATE_ACTION_RULE": pointer_get(
                contract_for_policy, "/data_policy/corporate_action_policy"
            ),
            "OVERLAP_RULE": pointer_get(
                contract_for_policy,
                "/split_policy/cross_split_label_overlap",
            ),
            "PURGE_RULE": pointer_get(
                contract_for_policy,
                "/split_policy/cross_split_label_overlap",
            ),
            "PURGE_EMBARGO_RULE": pointer_get(
                contract_for_policy,
                "/split_policy/cross_split_label_overlap",
            ),
            "EMBARGO_DURATION": "0",
            "EMBARGO_BASIS": "not_applicable_test_adapter",
        }
    else:
        policy_values = {
            "FORMULA": pointer_get(contract_for_policy, "/target/formula"),
            "NEUTRALIZATION_RULE": pointer_get(
                contract_for_policy, "/target/neutralization_rule"
            ),
            "CORPORATE_ACTION_RULE": pointer_get(
                contract_for_policy, "/target/corporate_action_rule"
            ),
            "OVERLAP_RULE": pointer_get(
                contract_for_policy, "/target/overlap_rule"
            ),
            "PURGE_RULE": pointer_get(
                contract_for_policy, "/splits/sample_dependency/purge_rule"
            ),
            "PURGE_EMBARGO_RULE": pointer_get(
                contract_for_policy, "/splits/purge_embargo_rule"
            ),
            "EMBARGO_DURATION": pointer_get(
                contract_for_policy,
                "/splits/sample_dependency/embargo_duration",
            ),
            "EMBARGO_BASIS": pointer_get(
                contract_for_policy, "/splits/sample_dependency/embargo_basis"
            ),
        }
    for token_name, value in policy_values.items():
        replace_everywhere(
            workspace,
            f"@AUTO_{token_name}_SHA256",
            sha256_bytes(str(value).encode("utf-8")),
        )
    label = copy.deepcopy(workspace["label_definition"])
    label.pop("label_spec_hash", None)
    replace_everywhere(
        workspace, "@AUTO_LABEL_SPEC_HASH", sha256_bytes(canonical(label))
    )

    early = serialized_artifacts(workspace)
    for token_name, artifact_name in (
        ("data", "data_rows"),
        ("calendar", "calendar"),
        ("schema", "schema"),
        ("dictionary", "dictionary"),
        ("label_definition", "label_definition"),
        ("review_authority", "review_authority"),
        ("population_manifest", "population_manifest"),
        ("population_source", "population_source"),
    ):
        replace_everywhere(
            workspace,
            f"@AUTO_FILE_SHA256:{token_name}",
            sha256_bytes(early[artifact_name]),
        )

    refresh_matrix_manifest(workspace, workspace["contract"])

    contract = copy.deepcopy(workspace["contract"])
    contract.pop("canonical_hash", None)
    replace_everywhere(
        workspace,
        "@AUTO_CONTRACT_CANONICAL_HASH",
        sha256_bytes(canonical(contract)),
    )

    refresh_label_schedule(workspace, workspace["contract"])
    refresh_matrix_manifest(workspace, workspace["contract"])
    final_derived = serialized_artifacts(workspace)
    for token_name, artifact_name in (
        ("time_semantics", "time_semantics"),
        ("label_interval_authority", "label_interval_authority"),
        ("label_schedule", "label_schedule"),
        ("matrix_manifest", "matrix_manifest"),
    ):
        replace_everywhere(
            workspace,
            f"@AUTO_FILE_SHA256:{token_name}",
            sha256_bytes(final_derived[artifact_name]),
        )

    contract_bytes = json_bytes(workspace["contract"])
    replace_everywhere(
        workspace, "@AUTO_FILE_SHA256:contract", sha256_bytes(contract_bytes)
    )
    receipt_bytes = json_bytes(workspace["contract_validation"])
    replace_everywhere(
        workspace,
        "@AUTO_FILE_SHA256:contract_validation",
        sha256_bytes(receipt_bytes),
    )
    unresolved = unresolved_tokens(workspace)
    if unresolved:
        raise SuiteError("unresolved fixture tokens: " + ", ".join(unresolved))
    return serialized_artifacts(workspace)


def safe_path(case_dir: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise SuiteError("artifact path must be a non-empty relative path")
    target = (case_dir / relative).resolve()
    try:
        target.relative_to(case_dir.resolve())
    except ValueError as error:
        raise SuiteError(f"artifact path escapes case directory: {relative}") from error
    return target


def output_paths(workspace: dict[str, Any], case_dir: Path) -> dict[str, Path]:
    request = workspace["request"]
    artifacts = request.get("artifacts", {})
    paths = {
        "request": case_dir / FILE_NAMES["request"],
        "data_rows": safe_path(case_dir, artifacts["data"]["path"]),
        "schema": safe_path(case_dir, artifacts["schema"]["path"]),
        "dictionary": safe_path(case_dir, artifacts["dictionary"]["path"]),
        "time_semantics": safe_path(
            case_dir, artifacts["time_semantics"]["path"]
        ),
        "contract": safe_path(
            case_dir, artifacts["research_contract"]["path"]
        ),
        "label_definition": safe_path(
            case_dir, artifacts["label_definition"]["path"]
        ),
        "label_schedule": safe_path(
            case_dir, artifacts["label_schedule"]["path"]
        ),
        "review_authority": safe_path(
            case_dir, artifacts["review_authority"]["path"]
        ),
        "label_interval_authority": safe_path(
            case_dir, artifacts["label_interval_authority"]["path"]
        ),
        "calendar": safe_path(case_dir, artifacts["calendar"]["path"]),
        "population_manifest": safe_path(
            case_dir, artifacts["population_manifest"]["path"]
        ),
        "population_source": safe_path(
            case_dir, artifacts["population_source"]["path"]
        ),
        "matrix_manifest": safe_path(
            case_dir,
            artifacts.get(
                "matrix_manifest",
                {"path": FILE_NAMES["matrix_manifest"]},
            )["path"],
        ),
    }
    receipt = artifacts.get("research_contract", {}).get("validation_receipt")
    paths["contract_validation"] = safe_path(
        case_dir,
        receipt["path"]
        if isinstance(receipt, dict) and receipt.get("path")
        else FILE_NAMES["contract_validation"],
    )
    return paths


def write_artifacts(
    workspace: dict[str, Any],
    case_dir: Path,
    payloads: dict[str, bytes],
    names: set[str] | None = None,
) -> dict[str, Path]:
    paths = output_paths(workspace, case_dir)
    selected = names or set(payloads)
    for name in selected:
        path = paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payloads[name])
    return paths


def materialize_case(
    base: dict[str, Any], case: dict[str, Any], case_dir: Path
) -> Path:
    workspace = copy.deepcopy(base)
    mutations = case.get("mutations")
    if not isinstance(mutations, list):
        raise SuiteError("case mutations must be a list")
    for mutation in mutations:
        if mutation.get("phase") == "before_hash":
            apply_mutation(workspace, mutation)
        elif mutation.get("phase") not in {
            "coherent_after_refresh",
            "after_hash",
        }:
            raise SuiteError(f"unknown mutation phase: {mutation.get('phase')!r}")

    frozen = freeze_tokens(workspace)
    (case_dir / ".trusted_authorities.json").write_bytes(
        json_bytes(
            {
                "review_authority_sha256": sha256_bytes(
                    frozen["review_authority"]
                ),
                "semantic_review_receipt_sha256": workspace[
                    "label_schedule"
                ]["semantic_review"]["receipt_hash"],
                "interval_authority_sha256": sha256_bytes(
                    frozen["label_interval_authority"]
                ),
            }
        )
    )
    coherent_touched: set[str] = set()
    for mutation in mutations:
        if mutation.get("phase") == "coherent_after_refresh":
            apply_mutation(workspace, mutation)
            coherent_touched.add(mutation["artifact"])
    if "review_authority" in coherent_touched:
        reseal_review_authority(workspace)
    if "label_interval_authority" in coherent_touched:
        reseal_interval_authority(workspace)
        coherent_touched.add("label_schedule")
    if "label_schedule" in coherent_touched:
        schedule = workspace["label_schedule"]
        reseal_label_schedule(workspace)
        label_axis = workspace["matrix_manifest"]["label_axis"]
        label_axis["label_schedule_id"] = schedule["schedule_id"]
        label_axis["label_schedule_version"] = schedule["version"]
        label_axis["label_schedule_receipt_hash"] = schedule["receipt_hash"]
        coherent_touched.add("matrix_manifest")
    if "matrix_manifest" in coherent_touched:
        unsigned_matrix = copy.deepcopy(workspace["matrix_manifest"])
        unsigned_matrix.pop("receipt_hash", None)
        workspace["matrix_manifest"]["receipt_hash"] = sha256_bytes(
            canonical(unsigned_matrix)
        )
    if coherent_touched:
        coherent_payloads = serialized_artifacts(workspace)
        request_names = {
            "data_rows": "data",
            "schema": "schema",
            "dictionary": "dictionary",
            "time_semantics": "time_semantics",
            "contract": "research_contract",
            "label_definition": "label_definition",
            "label_schedule": "label_schedule",
            "review_authority": "review_authority",
            "label_interval_authority": "label_interval_authority",
            "calendar": "calendar",
            "population_manifest": "population_manifest",
            "population_source": "population_source",
            "matrix_manifest": "matrix_manifest",
        }
        for artifact_name in coherent_touched:
            request_name = request_names.get(artifact_name)
            if request_name:
                workspace["request"]["artifacts"][request_name]["sha256"] = (
                    sha256_bytes(coherent_payloads[artifact_name])
                )
        frozen = serialized_artifacts(workspace)
    paths = write_artifacts(workspace, case_dir, frozen)

    touched: set[str] = set()
    for mutation in mutations:
        if mutation.get("phase") == "after_hash":
            apply_mutation(workspace, mutation)
            touched.add(mutation["artifact"])
    if touched:
        changed = serialized_artifacts(workspace)
        write_artifacts(workspace, case_dir, changed, touched)
    return paths["request"]


def text_sha256(value: Any) -> str:
    return sha256_bytes(str(value).encode("utf-8"))


def normalized_timestamp(value: str) -> str:
    from datetime import datetime, timezone

    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(timezone.utc)
        .isoformat()
    )


def refresh_label_schedule(
    workspace: dict[str, Any],
    contract: dict[str, Any],
    *,
    refresh_expected_intervals: bool = True,
) -> None:
    label = workspace["label_definition"]
    schedule = workspace["label_schedule"]
    if contract.get("schema_version") == "pit_contract_binding_v1":
        rules = contract["time_rules"]
        adapter = "pit_contract_binding_v1"
        contract_id = contract["contract_id"]
        contract_hash = contract["canonical_hash"]
    else:
        rules = contract["time_semantics"]
        adapter = "quant_contract_v2"
        contract_id = contract["contract"]["contract_id"]
        contract_hash = contract["contract"]["canonical_hash"]
    rule_hashes = {
        "prediction_time": text_sha256(rules["prediction_time"]),
        "execution_time": text_sha256(
            rules[
                "execution_time"
                if adapter == "pit_contract_binding_v1"
                else "execution_time_rule"
            ]
        ),
        "label_start": text_sha256(rules["label_start_rule"]),
        "label_end": text_sha256(rules["label_end_rule"]),
        "holding_period": text_sha256(rules["holding_period"]),
    }
    rule_bundle_hash = sha256_bytes(canonical(rule_hashes))
    schedule["contract_binding"] = {
        "adapter": adapter,
        "contract_id": contract_id,
        "contract_canonical_hash": contract_hash,
        "rule_hashes": rule_hashes,
        "rule_bundle_sha256": rule_bundle_hash,
    }
    schedule["label_binding"] = {
        "label_id": label["label_id"],
        "label_spec_version": label["label_spec_version"],
        "label_spec_hash": label["label_spec_hash"],
    }
    resolver = schedule["resolver"]
    if schedule["mode"] == "FROZEN_EXACT_INTERVAL_SET":
        authority = workspace["label_interval_authority"]
        if refresh_expected_intervals:
            intervals = sorted(
                {
                    (
                        row["security_id"],
                        normalized_timestamp(row["prediction_time"]),
                        normalized_timestamp(row["tradable_time"]),
                        normalized_timestamp(row["label_start_time"]),
                        normalized_timestamp(row["label_end_time"]),
                    )
                    for row in workspace["data_rows"]
                }
            )
            authority["expected_sample_count"] = len(intervals)
            authority["expected_interval_set_sha256"] = sha256_bytes(
                canonical([list(item) for item in intervals])
            )
        authority["population_manifest_sha256"] = sha256_bytes(
            json_bytes(workspace["population_manifest"])
        )
        generator = authority.setdefault("generator", {})
        generator.setdefault(
            "code_sha256",
            text_sha256("pit-label-schedule-reference-generator-v1"),
        )
        generator.setdefault(
            "parameters_sha256",
            text_sha256("frozen-contract-label-rules-v1"),
        )
        generator.setdefault(
            "input_snapshot_sha256",
            text_sha256("independent-label-calendar-and-contract-snapshot-v1"),
        )
        generator.setdefault(
            "source_locator",
            "synthetic://independent-label-interval-authority/v1",
        )
        unsigned_authority = copy.deepcopy(authority)
        unsigned_authority.pop("receipt_hash", None)
        authority["receipt_hash"] = sha256_bytes(
            canonical(unsigned_authority)
        )
        resolver.clear()
        resolver.update(
            {
                "interval_authority_id": authority["authority_id"],
                "interval_authority_version": authority["version"],
                "interval_authority_artifact_sha256": sha256_bytes(
                    json_bytes(authority)
                ),
                "interval_authority_receipt_hash": authority[
                    "receipt_hash"
                ],
            }
        )
    elif schedule["mode"] == "SESSION_CLOSE_OFFSETS":
        calendar_meta = workspace["request"]["artifacts"]["calendar"]
        resolver.update(
            {
                "calendar_id": calendar_meta["calendar_id"],
                "calendar_version": calendar_meta["version"],
                "calendar_artifact_sha256": sha256_bytes(
                    csv_bytes(
                        workspace["calendar"],
                        [
                            "session_id",
                            "open_time",
                            "close_time",
                            "break_start",
                            "break_end",
                        ],
                    )
                ),
                "timezone": calendar_meta["timezone"],
            }
        )
    review = schedule.setdefault("semantic_review", {})
    review.update(
        {
            "trust_root_kind": "HUMAN_SEMANTIC_REVIEW",
            "scope": "CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY",
            "decision": "APPROVED",
            "reviewer_id": review.get("reviewer_id", "synthetic-reviewer-001"),
            "reviewer_authority": review.get(
                "reviewer_authority",
                workspace["review_authority"]["authority_id"],
            ),
            "reviewed_at": review.get(
                "reviewed_at",
                workspace["request"]["run_at"],
            ),
            "contract_rule_bundle_sha256": rule_bundle_hash,
            "normalized_resolver_sha256": sha256_bytes(canonical(resolver)),
            "excluded_inputs": [
                "data_rows",
                "audit_status",
                "backtest_results",
            ],
        }
    )
    review_unsigned = copy.deepcopy(review)
    review_unsigned.pop("receipt_hash", None)
    review["receipt_hash"] = sha256_bytes(canonical(review_unsigned))
    unsigned_schedule = copy.deepcopy(schedule)
    unsigned_schedule.pop("receipt_hash", None)
    schedule["receipt_hash"] = sha256_bytes(canonical(unsigned_schedule))
    interpretation = workspace["time_semantics"].get(
        "contract_interpretation"
    )
    if isinstance(interpretation, dict) and isinstance(
        interpretation.get("resolved"), dict
    ):
        interpretation["resolved"]["label_schedule_receipt_hash"] = schedule[
            "receipt_hash"
        ]


def reseal_label_schedule(workspace: dict[str, Any]) -> None:
    schedule = workspace["label_schedule"]
    binding = schedule["contract_binding"]
    binding["rule_bundle_sha256"] = sha256_bytes(
        canonical(binding["rule_hashes"])
    )
    review = schedule["semantic_review"]
    review["contract_rule_bundle_sha256"] = binding["rule_bundle_sha256"]
    review["normalized_resolver_sha256"] = sha256_bytes(
        canonical(schedule["resolver"])
    )
    unsigned_review = copy.deepcopy(review)
    unsigned_review.pop("receipt_hash", None)
    review["receipt_hash"] = sha256_bytes(canonical(unsigned_review))
    unsigned_schedule = copy.deepcopy(schedule)
    unsigned_schedule.pop("receipt_hash", None)
    schedule["receipt_hash"] = sha256_bytes(canonical(unsigned_schedule))
    interpretation = workspace["time_semantics"].get(
        "contract_interpretation"
    )
    if isinstance(interpretation, dict) and isinstance(
        interpretation.get("resolved"), dict
    ):
        interpretation["resolved"]["label_schedule_receipt_hash"] = schedule[
            "receipt_hash"
        ]


def reseal_review_authority(workspace: dict[str, Any]) -> None:
    authority = workspace["review_authority"]
    unsigned = copy.deepcopy(authority)
    unsigned.pop("receipt_hash", None)
    authority["receipt_hash"] = sha256_bytes(canonical(unsigned))


def reseal_interval_authority(workspace: dict[str, Any]) -> None:
    authority = workspace["label_interval_authority"]
    unsigned = copy.deepcopy(authority)
    unsigned.pop("receipt_hash", None)
    authority["receipt_hash"] = sha256_bytes(canonical(unsigned))
    resolver = workspace["label_schedule"]["resolver"]
    resolver.update(
        {
            "interval_authority_id": authority["authority_id"],
            "interval_authority_version": authority["version"],
            "interval_authority_artifact_sha256": sha256_bytes(
                json_bytes(authority)
            ),
            "interval_authority_receipt_hash": authority["receipt_hash"],
        }
    )
    reseal_label_schedule(workspace)


def refresh_matrix_manifest(
    workspace: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    """Rebuild every derived matrix receipt field from its frozen axes."""
    matrix = workspace["matrix_manifest"]
    layout = matrix["layout"]
    feature_axis = matrix["feature_axis"]
    label_axis = matrix["label_axis"]
    population_manifest = workspace["population_manifest"]
    population_source = workspace["population_source"]
    label = workspace["label_definition"]
    label_schedule = workspace["label_schedule"]

    layout["applicability_rule_sha256"] = text_sha256(
        layout["applicability_rule"]
    )
    features = feature_axis["features"]
    feature_axis["expected_feature_count"] = len(features)
    feature_axis["feature_set_sha256"] = sha256_bytes(canonical(features))

    label_axis["label_id"] = label["label_id"]
    label_axis["label_spec_version"] = label["label_spec_version"]
    label_axis["label_spec_hash"] = label["label_spec_hash"]
    label_axis["label_schedule_id"] = label_schedule["schedule_id"]
    label_axis["label_schedule_version"] = label_schedule["version"]
    label_axis["label_schedule_receipt_hash"] = label_schedule[
        "receipt_hash"
    ]
    if contract.get("schema_version") == "pit_contract_binding_v1":
        rules = contract["time_rules"]
        prediction_rule = rules["prediction_time"]
        execution_rule = rules["execution_time"]
        label_start_rule = rules["label_start_rule"]
        label_end_rule = rules["label_end_rule"]
    else:
        rules = contract["time_semantics"]
        prediction_rule = rules["prediction_time"]
        execution_rule = rules["execution_time_rule"]
        label_start_rule = rules["label_start_rule"]
        label_end_rule = rules["label_end_rule"]
    label_axis["prediction_time_rule_sha256"] = text_sha256(
        prediction_rule
    )
    label_axis["execution_time_rule_sha256"] = text_sha256(
        execution_rule
    )
    label_axis["label_start_rule_sha256"] = text_sha256(label_start_rule)
    label_axis["label_end_rule_sha256"] = text_sha256(label_end_rule)
    if layout["mode"] == "RECTANGULAR":
        population_keys = sorted(
            {
                (
                    item["security_id"],
                    normalized_timestamp(item["prediction_time"]),
                )
                for item in population_manifest["keys"]
            }
        )
        normalized_cells = [
            (security_id, prediction_time, feature_name)
            for security_id, prediction_time in population_keys
            for feature_name in features
        ]
        matrix.pop("expected_cells", None)
    else:
        normalized_cells = sorted(
            {
                (
                    item["security_id"],
                    normalized_timestamp(item["prediction_time"]),
                    item["feature_name"],
                )
                for item in matrix["expected_cells"]
            }
        )
    matrix["expected_cell_count"] = len(normalized_cells)
    matrix["expected_cell_key_set_sha256"] = sha256_bytes(
        canonical([list(item) for item in normalized_cells])
    )

    sample_axis = matrix["sample_prediction_axis"]
    sample_axis["population_manifest_sha256"] = sha256_bytes(
        json_bytes(population_manifest)
    )
    sample_axis["population_manifest_receipt_hash"] = population_manifest[
        "receipt_hash"
    ]
    sample_axis["population_source_sha256"] = sha256_bytes(
        json_bytes(population_source)
    )
    sample_axis["expected_security_time_keys"] = population_manifest[
        "expected_security_time_keys"
    ]
    sample_axis["expected_key_set_sha256"] = population_manifest[
        "expected_key_set_sha256"
    ]

    dictionary_features = workspace["dictionary"].get("features")
    bound_feature_semantics = (
        {name: dictionary_features.get(name) for name in features}
        if isinstance(dictionary_features, dict)
        else None
    )
    feature_payload = {
        "schema_version": "pit_matrix_feature_spec_v1",
        "feature_spec_version": feature_axis["feature_spec_version"],
        "layout_mode": layout["mode"],
        "features": features,
        "feature_semantics_sha256": sha256_bytes(
            canonical(bound_feature_semantics)
        ),
        "applicability_rule_sha256": layout[
            "applicability_rule_sha256"
        ],
    }
    feature_axis["feature_semantics_sha256"] = feature_payload[
        "feature_semantics_sha256"
    ]
    if layout["mode"] == "SPARSE_EXPLICIT":
        feature_payload["expected_cell_key_set_sha256"] = matrix[
            "expected_cell_key_set_sha256"
        ]
    feature_hash = sha256_bytes(canonical(feature_payload))
    feature_axis["feature_spec_hash"] = feature_hash
    contract["data_policy" if contract.get("schema_version") == "pit_contract_binding_v1" else "data"][
        "feature_spec_version"
    ] = feature_axis["feature_spec_version"]
    contract["data_policy" if contract.get("schema_version") == "pit_contract_binding_v1" else "data"][
        "feature_spec_hash"
    ] = feature_hash

    unsigned = copy.deepcopy(matrix)
    unsigned.pop("receipt_hash", None)
    matrix["receipt_hash"] = sha256_bytes(canonical(unsigned))


def run_qrc_tool(command: list[str], *, cwd: Path) -> None:
    process = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise SuiteError(
            "QRC integration command failed: "
            + " ".join(command)
            + f"\nstdout={process.stdout.strip()}\nstderr={process.stderr.strip()}"
        )


def materialize_qrc_case(
    base: dict[str, Any],
    case: dict[str, Any],
    case_dir: Path,
    qrc_skill_dir: Path,
) -> Path:
    """Build a real quant_contract_v2, freeze it, and obtain an official receipt."""
    workspace = copy.deepcopy(base)
    freeze_tokens(workspace)
    variant = case["variant"]

    if variant == "system_blank_ingestion_batch":
        workspace["request"]["claim"] = "SYSTEM_REPLAYABLE"
        workspace["data_rows"][0].update(
            {
                "ingested_time": "2024-04-01T13:50:00Z",
                "parse_ready_time": "2024-04-01T13:55:00Z",
                "ingestion_batch_id": "   ",
            }
        )
    elif variant == "wrong_split_for_valid_date":
        workspace["data_rows"][0]["split"] = "MODEL_SELECTION"
    elif variant == "label_crosses_selection_without_peer":
        workspace["data_rows"][0]["label_end_time"] = "2024-04-02T15:00:00Z"
    elif variant == "label_consumes_nominal_embargo_gap":
        workspace["data_rows"][0]["label_end_time"] = "2024-04-03T19:00:00Z"
        workspace["calendar"].extend(
            [
                {
                    "session_id": "XNYS-2024-04-02",
                    "open_time": "2024-04-02T13:30:00Z",
                    "close_time": "2024-04-02T20:00:00Z",
                    "break_start": None,
                    "break_end": None,
                },
                {
                    "session_id": "XNYS-2024-04-03",
                    "open_time": "2024-04-03T13:30:00Z",
                    "close_time": "2024-04-03T20:00:00Z",
                    "break_start": None,
                    "break_end": None,
                },
            ]
        )
    elif variant == "coordinated_data_manifest_deletion":
        workspace["data_rows"] = []
        manifest = workspace["population_manifest"]
        manifest["keys"] = []
        manifest["expected_security_time_keys"] = 0
        manifest["expected_key_set_sha256"] = sha256_bytes(canonical([]))
        manifest["expected_status_counts"] = {}
        unsigned_manifest = copy.deepcopy(manifest)
        unsigned_manifest.pop("receipt_hash", None)
        manifest["receipt_hash"] = sha256_bytes(canonical(unsigned_manifest))
        workspace["request"]["coverage"]["population"][
            "expected_security_time_keys"
        ] = 0
    elif variant == "pit_adjusted_arbitrary_value":
        row = workspace["data_rows"][0]
        row["feature_value"] = 123456789.0
        row["adjustment_mode"] = "PIT_ADJUSTED"
        row["adjustment_known_time"] = "2024-03-01T13:00:00Z"
        workspace["dictionary"]["features"]["revenue_ttm"][
            "adjustment_policy"
        ]["allowed_modes"] = ["RAW", "PIT_ADJUSTED"]
    elif variant == "inverse_availability_pipeline_clocks":
        row = workspace["data_rows"][0]
        row["vendor_available_time"] = "2024-03-15T12:00:00Z"
        row["ingested_time"] = "2024-03-14T13:00:00Z"
        row["parse_ready_time"] = "2024-03-13T13:00:00Z"
    elif variant == "nan_domain_bound":
        workspace["dictionary"]["features"]["revenue_ttm"]["domain_policy"][
            "min"
        ] = float("nan")
    elif variant == "infinity_domain_bound":
        workspace["dictionary"]["features"]["revenue_ttm"]["domain_policy"][
            "min"
        ] = float("inf")

    qrc_reference = qrc_skill_dir / "references" / "forward_test_contract.yaml"
    try:
        planned = json.loads(qrc_reference.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SuiteError(f"cannot load QRC forward fixture: {error}") from error
    planned["time_semantics"].update(
        {
            "prediction_time": "Use the exact consumed prediction_time.",
            "execution_time_rule": "Use the exact consumed tradable_time.",
            "label_start_rule": (
                "Use the exact consumed label_start_time at or after prediction_time."
            ),
            "label_end_rule": (
                "Use the exact consumed label_end_time after label_start_time."
            ),
            "holding_period": "Use the frozen exact per-sample interval set.",
        }
    )

    contract_snapshot_rows = copy.deepcopy(workspace["data_rows"])
    if variant == "label_interval_drift_after_schedule_freeze":
        contract_snapshot_rows[0]["label_end_time"] = (
            "2024-04-01T19:54:00Z"
        )
    elif variant == "execution_time_drift_after_schedule_freeze":
        contract_snapshot_rows[0]["tradable_time"] = "2024-04-01T14:06:00Z"
    data_payload = csv_bytes(
        contract_snapshot_rows, list(workspace["schema"]["columns"])
    )
    calendar_payload = csv_bytes(
        workspace["calendar"],
        ["session_id", "open_time", "close_time", "break_start", "break_end"],
    )
    if variant == "duplicate_data_header":
        data_payload = duplicate_csv_column(
            data_payload,
            "prediction_time",
            "2099-01-01T00:00:00Z",
        )
    elif variant == "extra_data_cell":
        data_payload = widen_first_csv_row(
            data_payload, "ignored-future-payload"
        )
    if variant == "duplicate_calendar_header":
        calendar_payload = duplicate_csv_column(
            calendar_payload,
            "open_time",
            "2099-01-01T00:00:00Z",
        )
    elif variant == "missing_calendar_cell":
        calendar_payload = narrow_first_csv_row(calendar_payload)
    population_payload = json_bytes(workspace["population_source"])
    data_meta = workspace["request"]["artifacts"]["data"]
    dictionary = workspace["dictionary"]
    population = workspace["request"]["coverage"]["population"]

    calendar_meta = workspace["request"]["artifacts"]["calendar"]
    planned["scope"]["decision_calendar"] = (
        f"{calendar_meta['calendar_id']}@{calendar_meta['version']}"
    )
    if variant == "calendar_version_not_frozen":
        planned["scope"]["decision_calendar"] = calendar_meta["calendar_id"]
    planned["scope"]["timezone"] = workspace["time_semantics"]["timezone"]
    planned["scope"]["universe"]["universe_version"] = population[
        "universe_version"
    ]
    planned["scope"]["universe"]["universe_hash"] = sha256_bytes(
        population_payload
    )

    source = planned["data"]["sources"][0]
    data_meta["source_version"] = data_meta["snapshot_id"]
    if variant == "source_version_conflict":
        data_meta["source_version"] = "different-source-version"
    source.update(
        {
            "source_id": data_meta["source_id"],
            "vendor": "synthetic-fixture-only",
            "snapshot_id": data_meta["snapshot_id"],
            "snapshot_hash": sha256_bytes(data_payload),
            "event_timestamp_field": "event_time",
            "availability_timestamp_field": "vendor_available_time",
            "availability_evidence_uri": dictionary["source_uri"],
            "availability_evidence_version": dictionary["version"],
            "availability_evidence_hash": dictionary[
                "semantic_source_document_sha256"
            ],
            "revision_policy": (
                "Retain every as-received vintage and select only a vintage "
                "known no later than prediction_time."
            ),
            "allowed_fields": ["revenue_ttm"],
        }
    )
    if variant == "event_source_field_conflict":
        source["event_timestamp_field"] = "wrong_event_column"
    if variant == "availability_source_field_conflict":
        source["availability_timestamp_field"] = "period_end_not_release_time"

    purge_rule = (
        "Remove any earlier-split sample whose label interval intersects a "
        "later frozen split window."
    )
    purge_embargo_rule = (
        "Apply the declared per-sample purge and then preserve the declared "
        "eligible-session gap before each later split."
    )
    embargo_duration = "Zero eligible trading days."
    embargo_basis = (
        "No additional gap is required for this non-overlapping synthetic label."
    )
    if variant == "embargo_understatement":
        embargo_duration = "Ten eligible trading days."
        embargo_basis = "Ten sessions are required by the frozen synthetic policy."
    elif variant == "label_consumes_nominal_embargo_gap":
        embargo_duration = "One eligible trading day."
        embargo_basis = "One clean session is required after every consumed label."

    planned["target"].update(
        {
            "label_id": "next-session-return",
            "label_spec_version": "pit-label-definition-v1",
            "formula": "Synthetic raw close-to-close return over the declared interval.",
            "neutralization_rule": "No neutralization is used in this synthetic audit fixture.",
            "corporate_action_rule": "RAW_OR_KNOWN_PIT",
            "overlap_rule": "NO_CROSS_SPLIT_OVERLAP",
        }
    )
    if variant == "label_id_conflict":
        planned["target"]["label_id"] = "different-economic-target"
    elif variant == "label_spec_version_conflict":
        planned["target"]["label_spec_version"] = "different-label-spec-v999"
    planned["splits"]["train"] = {
        "start": "2024-01-01",
        "end": "2024-06-30",
    }
    planned["splits"]["selection"] = {
        "start": "2024-07-08",
        "end": "2024-09-30",
    }
    planned["splits"]["final_oos"] = {
        "start": "2024-10-07",
        "end": "2024-12-31",
    }
    if variant == "prediction_outside_split_window":
        planned["splits"]["train"] = {
            "start": "2022-01-01",
            "end": "2022-12-31",
        }
        planned["splits"]["selection"] = {
            "start": "2023-01-09",
            "end": "2023-06-30",
        }
        planned["splits"]["final_oos"] = {
            "start": "2023-07-10",
            "end": "2023-12-31",
        }
    elif variant in {
        "label_crosses_selection_without_peer",
        "label_consumes_nominal_embargo_gap",
    }:
        planned["splits"]["train"] = {
            "start": "2024-01-01",
            "end": "2024-04-01",
        }
        planned["splits"]["selection"] = {
            "start": (
                "2024-04-02"
                if variant == "label_crosses_selection_without_peer"
                else "2024-04-04"
            ),
            "end": "2024-06-28",
        }
        planned["splits"]["final_oos"] = {
            "start": "2024-07-08",
            "end": "2024-12-31",
        }
    planned["splits"]["purge_embargo_rule"] = purge_embargo_rule
    dependency = planned["splits"]["sample_dependency"]
    dependency.update(
        {
            "label_interval_spec": (
                "[label_start_time, label_end_time) for each consumed row"
            ),
            "feature_lookback_spec": "No additional lookback in this one-row fixture.",
            "overlap_present": False,
            "purge_rule": purge_rule,
            "embargo_duration": embargo_duration,
            "embargo_basis": embargo_basis,
            "cross_series_alignment_policy": (
                "Every consumed value uses the same declared prediction cutoff."
            ),
        }
    )

    label = workspace["label_definition"]
    label.update(
        {
            "label_id": "next-session-return",
            "label_spec_version": "pit-label-definition-v1",
            "purge_rule": (
                "A deliberately conflicting label-side purge rule."
                if variant == "label_purge_rule_conflict"
                else purge_rule
            ),
            "purge_embargo_rule": purge_embargo_rule,
            "embargo_duration": embargo_duration,
            "embargo_basis": embargo_basis,
            "contract_bindings": {
                "formula_sha256": text_sha256(
                    planned["target"]["formula"]
                ),
                "neutralization_rule_sha256": text_sha256(
                    planned["target"]["neutralization_rule"]
                ),
                "corporate_action_rule_sha256": text_sha256(
                    planned["target"]["corporate_action_rule"]
                ),
                "overlap_rule_sha256": text_sha256(
                    planned["target"]["overlap_rule"]
                ),
                "purge_rule_sha256": text_sha256(purge_rule),
                "purge_embargo_rule_sha256": text_sha256(
                    purge_embargo_rule
                ),
                "embargo_duration_sha256": text_sha256(embargo_duration),
                "embargo_basis_sha256": text_sha256(embargo_basis),
            },
        }
    )
    if variant == "missing_purge_binding":
        label["contract_bindings"].pop("purge_rule_sha256")
    label_without_hash = copy.deepcopy(label)
    label_without_hash.pop("label_spec_hash", None)
    label["label_spec_hash"] = sha256_bytes(canonical(label_without_hash))
    planned["target"]["label_spec_hash"] = label["label_spec_hash"]
    if variant == "label_formula_conflict":
        planned["target"]["formula"] = (
            "Employee headcount level, not the declared return label."
        )
    elif variant == "neutralization_rule_conflict":
        planned["target"]["neutralization_rule"] = (
            "Apply an undeclared sector-and-size neutralization."
        )
    elif variant == "label_schedule_rule_conflict":
        planned["time_semantics"]["holding_period"] = (
            "Five eligible trading days."
        )
    elif variant == "execution_schedule_rule_conflict":
        planned["time_semantics"]["execution_time_rule"] = (
            "Execute at the next eligible session open."
        )
    elif variant == "forged_authorized_semantic_review":
        planned["time_semantics"]["execution_time_rule"] = (
            "Tradable time must be the next eligible session open after prediction."
        )

    interpretation_paths = [
        "time_semantics.prediction_time",
        "time_semantics.data_cutoff_rule",
        "time_semantics.availability_rule",
        "time_semantics.execution_time_rule",
        "time_semantics.label_start_rule",
        "time_semantics.label_end_rule",
        "time_semantics.holding_period",
        "scope.universe.definition",
        "scope.universe.pit_membership_rule",
        "data.sources.0.revision_policy",
        "target.corporate_action_rule",
        "target.overlap_rule",
        "splits.purge_embargo_rule",
        "splits.sample_dependency.purge_rule",
        "splits.sample_dependency.embargo_duration",
        "splits.sample_dependency.embargo_basis",
    ]
    source_hashes = {
        dotted: text_sha256(path_get(planned, dotted))
        for dotted in interpretation_paths
    }
    if variant == "missing_holding_period_binding":
        source_hashes.pop("time_semantics.holding_period")
    resolved_sessions = (
        0
        if variant == "embargo_understatement"
        else 1
        if variant == "label_consumes_nominal_embargo_gap"
        else 0
    )
    workspace["time_semantics"]["contract_interpretation"] = {
        "status": "PASS",
        "source_text_sha256": source_hashes,
        "resolved": {
            "availability_comparison": (
                "LT"
                if variant == "availability_comparator_conflict"
                else workspace["time_semantics"]["availability_comparison"]
            ),
            "revision_policy_status": "PASS",
            "universe_policy_status": "PASS",
            "population_history_mode": "PIT_HISTORY",
            "embargo_sessions": resolved_sessions,
            "embargo_basis_sha256": text_sha256(embargo_basis),
            "embargo_implementation": "UNASSIGNED_SPLIT_GAP",
            "boundary_calendar_complete": True,
            "boundary_calendar_sha256": sha256_bytes(calendar_payload),
        },
    }
    if variant == "population_history_interpretation_conflict":
        workspace["time_semantics"]["contract_interpretation"]["resolved"][
            "population_history_mode"
        ] = "CURRENT_SNAPSHOT"

    refresh_matrix_manifest(workspace, planned)
    if variant == "contract_feature_spec_hash_mismatch":
        planned["data"]["feature_spec_hash"] = WRONG_FEATURE_SPEC_SHA256
    if variant == "feature_semantics_drift":
        workspace["dictionary"]["features"]["revenue_ttm"].update(
            {
                "definition": "Number of employees in the selected vintage.",
                "source_locator": "synthetic://vendor-manual/v1#employee-count",
                "unit": "employees",
                "basis": "headcount",
            }
        )
    planned_path = case_dir / ".qrc_planned.json"
    frozen_path = case_dir / FILE_NAMES["contract"]
    receipt_path = case_dir / FILE_NAMES["contract_validation"]
    planned_path.write_bytes(json_bytes(planned))
    freeze_script = qrc_skill_dir / "scripts" / "canonicalize_and_hash.py"
    validate_script = qrc_skill_dir / "scripts" / "validate_contract.py"
    run_qrc_tool(
        [
            sys.executable,
            str(freeze_script),
            "freeze",
            str(planned_path),
            "--output",
            str(frozen_path),
        ],
        cwd=case_dir,
    )
    run_qrc_tool(
        [
            sys.executable,
            str(validate_script),
            str(frozen_path),
            "--strict",
            "--receipt",
            str(receipt_path),
        ],
        cwd=case_dir,
    )
    workspace["contract"] = json.loads(frozen_path.read_text(encoding="utf-8"))
    workspace["contract_validation"] = json.loads(
        receipt_path.read_text(encoding="utf-8")
    )
    frozen_at = workspace["contract"]["contract"]["frozen_at"]
    workspace["request"]["run_at"] = frozen_at
    workspace["label_schedule"].setdefault("semantic_review", {})[
        "reviewed_at"
    ] = frozen_at
    refresh_label_schedule(workspace, workspace["contract"])
    if variant in {
        "label_schedule_rule_conflict",
        "execution_schedule_rule_conflict",
    }:
        schedule = workspace["label_schedule"]
        if variant == "label_schedule_rule_conflict":
            key = "holding_period"
            stale_rule = "Use the frozen exact per-sample interval set."
        else:
            key = "execution_time"
            stale_rule = "Use the exact consumed tradable_time."
        schedule["contract_binding"]["rule_hashes"][key] = text_sha256(
            stale_rule
        )
        reseal_label_schedule(workspace)
    refresh_matrix_manifest(
        workspace,
        (
            copy.deepcopy(workspace["contract"])
            if variant == "contract_feature_spec_hash_mismatch"
            else workspace["contract"]
        ),
    )
    trusted_payloads = serialized_artifacts(workspace)
    (case_dir / ".trusted_authorities.json").write_bytes(
        json_bytes(
            {
                "review_authority_sha256": sha256_bytes(
                    trusted_payloads["review_authority"]
                ),
                "semantic_review_receipt_sha256": (
                    "0" * 64
                    if variant == "forged_authorized_semantic_review"
                    else workspace["label_schedule"]["semantic_review"][
                        "receipt_hash"
                    ]
                ),
                "interval_authority_sha256": sha256_bytes(
                    trusted_payloads["label_interval_authority"]
                ),
            }
        )
    )
    if variant == "label_interval_drift_after_schedule_freeze":
        workspace["data_rows"][0]["label_end_time"] = (
            "2024-04-01T19:54:00Z"
        )
    elif variant == "execution_time_drift_after_schedule_freeze":
        workspace["data_rows"][0]["tradable_time"] = "2024-04-01T14:06:00Z"
    elif variant == "data_bytes_drift_under_frozen_snapshot":
        workspace["data_rows"][0]["feature_value"] = 999999.0
    elif variant == "review_before_contract_freeze":
        workspace["label_schedule"]["semantic_review"]["reviewed_at"] = (
            "2024-04-01T23:00:00Z"
        )
        reseal_label_schedule(workspace)
        refresh_matrix_manifest(workspace, workspace["contract"])
    elif variant == "untrusted_review_authority":
        authority = workspace["review_authority"]
        authority["authority_id"] = "self-declared-review-authority"
        authority["reviewers"] = [
            {
                "reviewer_id": "self-declared-reviewer",
                "allowed_scopes": [
                    "CONTRACT_PROSE_TO_NORMALIZED_LABEL_SCHEDULE_ONLY"
                ],
                "valid_from": "2024-01-01T00:00:00Z",
                "valid_to": "2030-01-01T00:00:00Z",
            }
        ]
        reseal_review_authority(workspace)
        workspace["request"]["artifacts"]["review_authority"][
            "authority_id"
        ] = authority["authority_id"]
        review = workspace["label_schedule"]["semantic_review"]
        review["reviewer_id"] = "self-declared-reviewer"
        review["reviewer_authority"] = authority["authority_id"]
        reseal_label_schedule(workspace)
        refresh_matrix_manifest(workspace, workspace["contract"])
    elif variant == "untrusted_interval_authority":
        generator = workspace["label_interval_authority"]["generator"]
        generator["code_sha256"] = "0" * 64
        generator["source_locator"] = (
            "self-asserted://nonexistent-interval-authority"
        )
        reseal_interval_authority(workspace)
        refresh_matrix_manifest(workspace, workspace["contract"])
    if variant == "rectangular_expected_cells_override":
        workspace["matrix_manifest"]["expected_cells"] = [
            {
                "security_id": "WRONG-SECURITY",
                "prediction_time": "2099-01-01T00:00:00Z",
                "feature_name": "wrong_feature",
            }
        ]
        unsigned_matrix = copy.deepcopy(workspace["matrix_manifest"])
        unsigned_matrix.pop("receipt_hash", None)
        workspace["matrix_manifest"]["receipt_hash"] = sha256_bytes(
            canonical(unsigned_matrix)
        )
    if variant == "wrong_receipt_schema":
        workspace["contract_validation"]["schema_version"] = (
            "pit_contract_validation_receipt_v1"
        )
    elif variant == "receipt_contract_hash_mismatch":
        workspace["contract_validation"]["contract_file_sha256"] = "0" * 64
    elif variant == "validator_bundle_forgery":
        workspace["contract_validation"]["validator_bundle_sha256"] = "0" * 64

    contract_meta = workspace["request"]["artifacts"]["research_contract"]
    contract_meta.update(
        {
            "adapter": "quant_contract_v2",
            "contract_id": workspace["contract"]["contract"]["contract_id"],
            "canonical_hash": workspace["contract"]["contract"][
                "canonical_hash"
            ],
        }
    )
    workspace["request"]["request_id"] = case["case_id"]
    workspace["request"]["coverage"]["expected_row_count"] = len(
        workspace["data_rows"]
    )
    workspace["request"]["artifacts"]["label_definition"][
        "label_spec_hash"
    ] = label["label_spec_hash"]

    payloads = serialized_artifacts(workspace)
    if variant in {"duplicate_data_header", "extra_data_cell"}:
        payloads["data_rows"] = data_payload
    if variant in {"duplicate_calendar_header", "missing_calendar_cell"}:
        payloads["calendar"] = calendar_payload
    duplicate_dictionary_payload: bytes | None = None
    if variant == "duplicate_dictionary_key":
        lines = payloads["dictionary"].splitlines(keepends=True)
        for index, line in enumerate(lines):
            if b'"version":' in line:
                lines.insert(index + 1, line)
                duplicate_dictionary_payload = b"".join(lines)
                break
        if duplicate_dictionary_payload is None:
            raise SuiteError("could not inject duplicate dictionary version key")
        payloads["dictionary"] = duplicate_dictionary_payload
    for artifact_name, request_name in (
        ("data_rows", "data"),
        ("schema", "schema"),
        ("dictionary", "dictionary"),
        ("time_semantics", "time_semantics"),
        ("contract", "research_contract"),
        ("label_definition", "label_definition"),
        ("label_schedule", "label_schedule"),
        ("review_authority", "review_authority"),
        ("label_interval_authority", "label_interval_authority"),
        ("calendar", "calendar"),
        ("population_manifest", "population_manifest"),
        ("population_source", "population_source"),
        ("matrix_manifest", "matrix_manifest"),
    ):
        workspace["request"]["artifacts"][request_name]["sha256"] = (
            sha256_bytes(payloads[artifact_name])
        )
    if variant != "data_bytes_drift_under_frozen_snapshot":
        workspace["request"]["artifacts"]["data"][
            "source_snapshot_sha256"
        ] = sha256_bytes(payloads["data_rows"])
    contract_meta["validation_receipt"]["sha256"] = sha256_bytes(
        payloads["contract_validation"]
    )
    payloads = serialized_artifacts(workspace)
    if variant in {"duplicate_data_header", "extra_data_cell"}:
        payloads["data_rows"] = data_payload
    if variant in {"duplicate_calendar_header", "missing_calendar_cell"}:
        payloads["calendar"] = calendar_payload
    if duplicate_dictionary_payload is not None:
        payloads["dictionary"] = duplicate_dictionary_payload
    write_artifacts(workspace, case_dir, payloads)
    return case_dir / FILE_NAMES["request"]


def check_observation(
    observation: str | None, checks: dict[str, dict[str, Any]]
) -> str | None:
    if observation is None:
        return None
    if observation != "same_split_overlap_count>0":
        return f"unsupported expected observation: {observation!r}"
    actual = (
        checks.get("L002", {})
        .get("metrics", {})
        .get("same_split_overlap_count")
    )
    if not isinstance(actual, int) or actual <= 0:
        return f"expected L002 same_split_overlap_count>0, got {actual!r}"
    return None


def audit_command(
    audit_script: Path,
    request_path: Path,
    output_dir: Path,
    execution_path: str,
) -> list[str]:
    ordinary_args = [
        str(request_path),
        "--output-dir",
        str(output_dir),
    ]
    if execution_path == "production_cli":
        trust_oracle = json.loads(
            (request_path.parent / ".trusted_authorities.json").read_text(
                encoding="utf-8"
            )
        )
        return [
            sys.executable,
            str(audit_script),
            *ordinary_args,
            "--trusted-review-authority-sha256",
            trust_oracle["review_authority_sha256"],
            "--trusted-semantic-review-receipt-sha256",
            trust_oracle["semantic_review_receipt_sha256"],
            "--trusted-interval-authority-sha256",
            trust_oracle["interval_authority_sha256"],
        ]
    if execution_path == "production_cli_without_anchors":
        return [sys.executable, str(audit_script), *ordinary_args]
    if execution_path == "internal_test_adapter":
        return [
            sys.executable,
            "-c",
            INTERNAL_TEST_DRIVER,
            str(audit_script),
            *ordinary_args,
        ]
    raise SuiteError(f"unsupported audit execution path: {execution_path!r}")


def run_case(
    audit_script: Path,
    base: dict[str, Any],
    case: dict[str, Any],
    root: Path,
    materializer: Any = materialize_case,
    *,
    execution_path: str = "production_cli",
) -> dict[str, Any]:
    case_id = case["case_id"]
    case_dir = root / case_id
    case_dir.mkdir()
    request_path = materializer(base, case, case_dir)
    output_dir = case_dir / "output"
    command = audit_command(
        audit_script,
        request_path,
        output_dir,
        execution_path,
    )
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    expected = case["expected"]
    problems: list[str] = []
    expected_code = STATUS_EXIT_CODES[expected["status"]]
    if process.returncode != expected_code:
        problems.append(
            f"exit code expected {expected_code}, got {process.returncode}"
        )

    manifest_path = output_dir / "audit_manifest.json"
    report_path = output_dir / "audit_report.md"
    manifest: dict[str, Any] = {}
    report_text = ""
    if not manifest_path.is_file():
        problems.append("audit_manifest.json was not emitted")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            problems.append(f"audit_manifest.json is invalid: {error}")
    if report_path.is_file():
        report_text = report_path.read_text(encoding="utf-8")
    if not report_text.startswith("# Point-in-Time Data Audit"):
        problems.append("audit_report.md was not emitted in the required format")
    if case_id == "clean_market_full_pass" and manifest_path.is_file():
        before_retry = manifest_path.read_bytes()
        retry = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if retry.returncode != 64 or manifest_path.read_bytes() != before_retry:
            problems.append("non-empty output directory was not protected from overwrite")

    if manifest:
        try:
            request_doc = json.loads(request_path.read_text(encoding="utf-8"))
            declared_adapter = request_doc["artifacts"]["research_contract"][
                "adapter"
            ]
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
            declared_adapter = None
        contract_binding = manifest.get("contract_binding", {})
        expected_boundary = (
            "INTERNAL_TEST_ONLY"
            if execution_path == "internal_test_adapter"
            else "PRODUCTION_CLI"
        )
        if contract_binding.get("adapter") != declared_adapter:
            problems.append("manifest does not disclose the executed contract adapter")
        if contract_binding.get("test_only_adapter") is not (
            declared_adapter == "pit_contract_binding_v1"
        ):
            problems.append("manifest test_only_adapter boundary is incorrect")
        if contract_binding.get("execution_boundary") != expected_boundary:
            problems.append("manifest execution boundary is incorrect")
        if (
            manifest.get("status") == "PASS"
            and execution_path == "production_cli"
        ):
            try:
                trust_oracle = json.loads(
                    (request_path.parent / ".trusted_authorities.json").read_text(
                        encoding="utf-8"
                    )
                )
            except (OSError, UnicodeError, json.JSONDecodeError):
                problems.append("production PASS trust oracle is unreadable")
            else:
                runtime_trust = manifest.get("runtime_trust", {})
                expected_runtime_trust = {
                    "matched_review_authority_sha256": trust_oracle[
                        "review_authority_sha256"
                    ],
                    "matched_semantic_review_receipt_sha256": trust_oracle[
                        "semantic_review_receipt_sha256"
                    ],
                    "matched_interval_authority_sha256": trust_oracle[
                        "interval_authority_sha256"
                    ],
                }
                if runtime_trust != expected_runtime_trust:
                    problems.append(
                        "production PASS does not preserve its matched runtime trust anchors"
                    )
        for token in (declared_adapter, expected_boundary):
            if token and token not in report_text:
                problems.append(f"report omits adapter boundary token {token!r}")
        core = {
            key: value
            for key, value in manifest.items()
            if key not in {"audit_id", "content_sha256", "report_sha256"}
        }
        expected_content_hash = sha256_bytes(canonical(core))
        if manifest.get("content_sha256") != expected_content_hash:
            problems.append("manifest content_sha256 does not bind its canonical content")
        if manifest.get("audit_id") != f"pit-audit-v1-{expected_content_hash[:32]}":
            problems.append("audit_id does not derive from content_sha256")
        if manifest.get("report_sha256") != sha256_bytes(
            report_text.encode("utf-8")
        ):
            problems.append("manifest report_sha256 does not bind audit_report.md")
        for token in (
            manifest.get("audit_id"),
            manifest.get("content_sha256"),
            manifest.get("status"),
            manifest.get("pit_qualification"),
        ):
            if not token or str(token) not in report_text:
                problems.append(f"report omits manifest token {token!r}")
        for lineage_item in manifest.get("lineage", []):
            for token in (
                lineage_item.get("artifact"),
                lineage_item.get("verified_sha256"),
            ):
                if token and str(token) not in report_text:
                    problems.append(
                        f"report omits lineage token {token!r}"
                    )
        for key in ("status", "pit_qualification"):
            if manifest.get(key) != expected[key]:
                problems.append(
                    f"{key} expected {expected[key]!r}, got {manifest.get(key)!r}"
                )
        expected_qualification = {
            "PASS": (
                "TEST_ONLY"
                if execution_path == "internal_test_adapter"
                else "QUALIFIED"
            ),
            "NEEDS_EVIDENCE": "UNRESOLVED",
            "FAIL": "NOT_QUALIFIED",
        }.get(manifest.get("status"))
        if manifest.get("pit_qualification") != expected_qualification:
            problems.append("status and pit_qualification are inconsistent")
        raw_checks = manifest.get("checks")
        if not isinstance(raw_checks, list):
            problems.append("manifest checks must be a list")
            checks: dict[str, dict[str, Any]] = {}
        else:
            checks = {
                item.get("check_id"): item
                for item in raw_checks
                if isinstance(item, dict) and item.get("check_id")
            }
            if len(raw_checks) != 17 or len(checks) != 17:
                problems.append("manifest must contain exactly 17 unique checks")
            for item in raw_checks:
                digest_payload = {
                    key: value
                    for key, value in item.items()
                    if key not in {"evidence_digest", "minimal_remediation"}
                }
                if item.get("evidence_digest") != sha256_bytes(
                    canonical(digest_payload)
                ):
                    problems.append(
                        f"{item.get('check_id')}: invalid evidence_digest"
                    )
                if item.get("status") == "PASS":
                    base_evidence = (
                        item.get("evidence", [{}])[0]
                        if item.get("evidence")
                        else {}
                    )
                    required_trace = {
                        "source_version",
                        "source_snapshot_sha256",
                        "data_artifact_sha256",
                        "dictionary_version",
                        "dictionary_artifact_sha256",
                        "schema_artifact_sha256",
                        "time_semantics_artifact_sha256",
                        "contract_artifact_sha256",
                        "label_definition_artifact_sha256",
                        "label_schedule_artifact_sha256",
                        "review_authority_artifact_sha256",
                        "calendar_artifact_sha256",
                        "population_manifest_artifact_sha256",
                        "population_source_artifact_sha256",
                    }
                    if isinstance(
                        request_doc.get("artifacts", {}).get("matrix_manifest"),
                        dict,
                    ):
                        required_trace.add("matrix_manifest_artifact_sha256")
                    if isinstance(
                        request_doc.get("artifacts", {}).get(
                            "label_interval_authority"
                        ),
                        dict,
                    ):
                        required_trace.add(
                            "label_interval_authority_artifact_sha256"
                        )
                    if not isinstance(base_evidence, dict) or any(
                        not base_evidence.get(key) for key in required_trace
                    ):
                        problems.append(
                            f"{item.get('check_id')}: PASS lacks complete version/hash trace"
                        )
                    semantic_items = [
                        evidence
                        for evidence in item.get("evidence", [])
                        if isinstance(evidence, dict)
                        and isinstance(evidence.get("semantic_trace"), dict)
                    ]
                    if len(semantic_items) != 1:
                        problems.append(
                            f"{item.get('check_id')}: PASS lacks exact semantic trace"
                        )
                    else:
                        trace = semantic_items[0]["semantic_trace"]
                        trace_core = {
                            key: value
                            for key, value in trace.items()
                            if key != "binding_sha256"
                        }
                        if trace.get("binding_sha256") != sha256_bytes(
                            canonical(trace_core)
                        ):
                            problems.append(
                                f"{item.get('check_id')}: semantic trace hash is invalid"
                            )
                        for section in (
                            "dictionary_fields",
                            "time_roles",
                            "feature_policies",
                            "external_policies",
                        ):
                            values = trace.get(section)
                            if not isinstance(values, dict) or any(
                                not value for value in values.values()
                            ):
                                problems.append(
                                    f"{item.get('check_id')}: semantic trace has an empty {section} locator"
                                )
                        check_id = item.get("check_id")
                        required_fields = TRACE_REQUIRED_FIELDS[check_id]
                        if required_fields == "__ALL_FIELDS__":
                            required_fields = set(base["schema"]["columns"])
                        elif required_fields == "__ALL_TIME_FIELDS__":
                            required_fields = {
                                role["field"]
                                for role in base["time_semantics"]["roles"].values()
                            }
                        field_trace = trace.get("dictionary_fields", {})
                        missing_fields = set(required_fields) - set(field_trace)
                        if missing_fields:
                            problems.append(
                                f"{check_id}: semantic trace omits fields {sorted(missing_fields)}"
                            )
                        expected_roles = {
                            base["dictionary"]["fields"][field]["semantic_role"]
                            for field in required_fields
                            if field in base["dictionary"]["fields"]
                            and base["dictionary"]["fields"][field][
                                "semantic_role"
                            ]
                            in base["time_semantics"]["roles"]
                        }
                        missing_roles = expected_roles - set(
                            trace.get("time_roles", {})
                        )
                        if missing_roles:
                            problems.append(
                                f"{check_id}: semantic trace omits time roles {sorted(missing_roles)}"
                            )
                        expected_external = TRACE_REQUIRED_EXTERNAL.get(
                            check_id, set()
                        )
                        missing_external = expected_external - set(
                            trace.get("external_policies", {})
                        )
                        if missing_external:
                            problems.append(
                                f"{check_id}: semantic trace omits external policies {sorted(missing_external)}"
                            )
                        expected_policies = TRACE_REQUIRED_FEATURE_POLICIES.get(
                            check_id, set()
                        )
                        feature_names = (
                            {
                                row["feature_name"]
                                for row in base["data_rows"]
                            }
                            if manifest.get("coverage_matrix", {}).get(
                                "parsed_rows"
                            )
                            else set()
                        )
                        expected_feature_keys = {
                            f"{feature}.{policy}"
                            for feature in feature_names
                            for policy in expected_policies
                        }
                        missing_policies = expected_feature_keys - set(
                            trace.get("feature_policies", {})
                        )
                        if missing_policies:
                            problems.append(
                                f"{check_id}: semantic trace omits feature policies {sorted(missing_policies)}"
                            )
        if isinstance(raw_checks, list):
            derived_fail = [
                item.get("check_id")
                for item in raw_checks
                if item.get("status") == "FAIL"
            ]
            derived_needs = [
                item.get("check_id")
                for item in raw_checks
                if item.get("status") == "NEEDS_EVIDENCE"
            ]
            derived_issues = sum(
                item.get("violation_count", 0)
                for item in raw_checks
                if isinstance(item.get("violation_count"), int)
            )
            findings = manifest.get("findings", {})
            if findings.get("fail_check_ids") != derived_fail:
                problems.append("findings.fail_check_ids is inconsistent")
            if findings.get("needs_evidence_check_ids") != derived_needs:
                problems.append("findings.needs_evidence_check_ids is inconsistent")
            if findings.get("total_reported_issues") != derived_issues:
                problems.append("findings.total_reported_issues is inconsistent")
            highest = manifest.get("status")
            highest_checks = [
                item for item in raw_checks if item.get("status") == highest
            ]
            expected_action = (
                highest_checks[0].get("minimal_remediation")
                if highest_checks
                else None
            )
            if manifest.get("one_next_action") != expected_action:
                problems.append("one_next_action does not follow highest severity")
            for item in raw_checks:
                for token in (
                    str(item.get("check_id")),
                    str(item.get("status")),
                    str(item.get("evidence_digest")),
                ):
                    if token not in report_text:
                        problems.append(
                            f"report omits check evidence token {token!r}"
                        )
                        break
        for check_id, wanted in expected.get(
            "required_check_status", {}
        ).items():
            actual = checks.get(check_id, {}).get("status")
            if actual != wanted:
                problems.append(
                    f"{check_id} expected {wanted!r}, got {actual!r}"
                )
        for check_id, wanted_locator in expected.get(
            "required_issue_locator", {}
        ).items():
            actual_locators = {
                issue.get("locator")
                for issue in checks.get(check_id, {}).get("violations", [])
                if isinstance(issue, dict)
            }
            wanted = (
                {wanted_locator}
                if isinstance(wanted_locator, str)
                else set(wanted_locator)
                if isinstance(wanted_locator, list)
                else set()
            )
            if not wanted or not wanted.issubset(actual_locators):
                problems.append(
                    f"{check_id} missing issue locator(s) {sorted(wanted)!r}; "
                    f"got {sorted(str(item) for item in actual_locators)!r}"
                )
        observation_problem = check_observation(
            expected.get("required_observation"), checks
        )
        if observation_problem:
            problems.append(observation_problem)

    return {
        "case_id": case_id,
        "passed": not problems,
        "problems": problems,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "audit_id": manifest.get("audit_id"),
        "content_sha256": manifest.get("content_sha256"),
        "execution_path": execution_path,
        "report_sha256": (
            sha256_bytes(report_text.encode("utf-8")) if report_text else None
        ),
    }


def validate_case_spec(case: Any) -> str:
    if not isinstance(case, dict):
        raise SuiteError("every case must be an object")
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise SuiteError("every case requires a non-empty case_id")
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise SuiteError(f"{case_id}: expected must be an object")
    if expected.get("status") not in STATUS_EXIT_CODES:
        raise SuiteError(f"{case_id}: invalid expected status")
    if expected.get("pit_qualification") not in {
        "QUALIFIED",
        "TEST_ONLY",
        "UNRESOLVED",
        "NOT_QUALIFIED",
    }:
        raise SuiteError(f"{case_id}: invalid expected pit_qualification")
    required = expected.get("required_check_status", {})
    if not isinstance(required, dict) or any(
        value not in STATUS_EXIT_CODES for value in required.values()
    ):
        raise SuiteError(f"{case_id}: invalid required_check_status")
    locators = expected.get("required_issue_locator", {})
    if not isinstance(locators, dict) or any(
        not isinstance(check_id, str)
        or not (
            isinstance(value, str)
            or isinstance(value, list)
            and value
            and all(isinstance(item, str) and item for item in value)
        )
        for check_id, value in locators.items()
    ):
        raise SuiteError(f"{case_id}: invalid required_issue_locator")
    execution_path = case.get("execution_path")
    if execution_path is not None and execution_path not in EXECUTION_PATHS:
        raise SuiteError(f"{case_id}: invalid execution_path")
    return case_id


def build_critical_binding_cases(
    declared_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(CRITICAL_BINDING_MUTATIONS) != EXPECTED_CRITICAL_BINDING_MUTATION_COUNT:
        raise SuiteError("critical-binding mutation count changed")
    if (
        sha256_bytes(canonical(CRITICAL_BINDING_MUTATIONS))
        != EXPECTED_CRITICAL_BINDING_MUTATIONS_SHA256
    ):
        raise SuiteError(
            "critical-binding mutation registry changed without an explicit reviewed digest update"
        )
    templates = {case["case_id"]: case for case in declared_cases}
    generated: list[dict[str, Any]] = []
    for (
        case_id,
        template_id,
        phase,
        operation,
        artifact,
        pointer,
        value,
        check_id,
        issue_locator,
    ) in CRITICAL_BINDING_MUTATIONS:
        template = templates.get(template_id)
        if template is None:
            raise SuiteError(
                f"{case_id}: missing critical-binding template {template_id!r}"
            )
        generated_case = {
            "case_id": case_id,
            "description": (
                f"Digest-pinned critical binding probe for {artifact}{pointer}."
            ),
            "mutations": [
                *copy.deepcopy(template.get("mutations", [])),
                {
                    "phase": phase,
                    "op": operation,
                    "artifact": artifact,
                    "pointer": pointer,
                    "value": copy.deepcopy(value),
                },
            ],
            "expected": {
                "status": "FAIL",
                "pit_qualification": "NOT_QUALIFIED",
                "required_check_status": {check_id: "FAIL"},
                "required_issue_locator": {check_id: issue_locator},
            },
        }
        validate_case_spec(generated_case)
        generated.append(generated_case)
    if len({case["case_id"] for case in generated}) != len(generated):
        raise SuiteError("critical-binding case IDs must be unique")
    return generated


def validate_suite(suite: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(suite, dict):
        raise SuiteError("suite root must be an object")
    if suite.get("schema_version") != "pit_synthetic_suite_v1":
        raise SuiteError("unsupported synthetic suite version")
    base = suite.get("base_case")
    cases = suite.get("cases")
    if not isinstance(base, dict) or not isinstance(cases, list):
        raise SuiteError("suite requires base_case object and cases list")
    if sha256_bytes(canonical(base)) != EXPECTED_BASE_CASE_SHA256:
        raise SuiteError(
            "synthetic base case changed without an explicit reviewed digest update"
        )
    if len(cases) != EXPECTED_CASE_COUNT:
        raise SuiteError(
            f"expected exactly {EXPECTED_CASE_COUNT} cases, found {len(cases)}"
        )
    ids = [validate_case_spec(case) for case in cases]
    if len(set(ids)) != len(ids):
        raise SuiteError("case_id values must be unique")
    if sha256_bytes(canonical(cases)) != EXPECTED_CASES_SHA256:
        raise SuiteError(
            "synthetic case registry changed without an explicit reviewed digest update"
        )
    return base, cases


def validate_qrc_cases(cases: Any) -> None:
    if not isinstance(cases, list):
        raise SuiteError("QRC case registry must be a list")
    if len(cases) != EXPECTED_QRC_CASE_COUNT:
        raise SuiteError(
            f"expected exactly {EXPECTED_QRC_CASE_COUNT} QRC cases, "
            f"found {len(cases)}"
        )
    ids = [validate_case_spec(case) for case in cases]
    variants = [case.get("variant") for case in cases]
    if len(set(ids)) != len(ids):
        raise SuiteError("QRC case_id values must be unique")
    if any(not isinstance(variant, str) or not variant for variant in variants):
        raise SuiteError("every QRC case requires a non-empty variant")
    if len(set(variants)) != len(variants):
        raise SuiteError("QRC variant values must be unique")
    actual_digest = sha256_bytes(canonical(cases))
    if actual_digest != EXPECTED_QRC_CASES_SHA256:
        raise SuiteError(
            "QRC case registry changed without an explicit reviewed digest update"
        )


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    suite_path = script_dir.parent / "references" / "synthetic_cases.json"
    audit_script = script_dir / "audit_pit.py"
    try:
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        base, cases = validate_suite(suite)
        critical_binding_cases = build_critical_binding_cases(cases)
        validate_qrc_cases(QRC_CASES)
        all_case_ids = [
            *(case["case_id"] for case in cases),
            *(case["case_id"] for case in critical_binding_cases),
            *(case["case_id"] for case in QRC_CASES),
        ]
        if len(set(all_case_ids)) != len(all_case_ids):
            raise SuiteError("case IDs must be unique across all registries")
        if not audit_script.is_file():
            raise SuiteError(f"audit script is missing: {audit_script}")
        qrc_skill_dir = (
            Path.home() / ".codex" / "skills" / "quant-research-contract"
        )
        for required in (
            qrc_skill_dir / "scripts" / "canonicalize_and_hash.py",
            qrc_skill_dir / "scripts" / "validate_contract.py",
            qrc_skill_dir / "references" / "forward_test_contract.yaml",
        ):
            if not required.is_file():
                raise SuiteError(
                    f"installed quant-research-contract dependency is missing: {required}"
                )
        with tempfile.TemporaryDirectory(prefix="pit-audit-tests-") as temp:
            root = Path(temp)
            results = [
                run_case(
                    audit_script,
                    base,
                    case,
                    root,
                    execution_path=case.get(
                        "execution_path", "internal_test_adapter"
                    ),
                )
                for case in cases
            ]
            results.extend(
                run_case(
                    audit_script,
                    base,
                    case,
                    root,
                    execution_path="internal_test_adapter",
                )
                for case in critical_binding_cases
            )
            qrc_root = root / "qrc-production"
            qrc_root.mkdir()
            results.extend(
                run_case(
                    audit_script,
                    base,
                    case,
                    qrc_root,
                    materializer=lambda base_case, selected, case_dir: (
                        materialize_qrc_case(
                            base_case,
                            selected,
                            case_dir,
                            qrc_skill_dir,
                        )
                    ),
                    execution_path=case.get(
                        "execution_path", "production_cli"
                    ),
                )
                for case in QRC_CASES
            )
            replay_root = root / "determinism-replay"
            replay_root.mkdir()
            replay = run_case(
                audit_script,
                base,
                cases[0],
                replay_root,
                execution_path="internal_test_adapter",
            )
            first = results[0]
            if (
                not replay["passed"]
                or replay["audit_id"] != first["audit_id"]
                or replay["content_sha256"] != first["content_sha256"]
                or replay["report_sha256"] != first["report_sha256"]
            ):
                results.append(
                    {
                        "case_id": "deterministic_replay",
                        "passed": False,
                        "problems": [
                            "identical bytes in a different directory changed the audit identity"
                        ],
                        "first": first,
                        "replay": replay,
                    }
                )
    except (OSError, UnicodeError, json.JSONDecodeError, SuiteError, KeyError) as error:
        print(
            json.dumps(
                {
                    "suite": "pit_synthetic_suite_v1",
                    "result": "ERROR",
                    "error": str(error),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    behavior_runner = Path(__file__).with_name("run_behavior_tests.py")
    behavior_process = subprocess.run(
        [sys.executable, str(behavior_runner)],
        check=False,
        capture_output=True,
        text=True,
    )
    behavior_passed = behavior_process.returncode == 0
    if not behavior_passed:
        results.append(
            {
                "case_id": "behavior_probe_suite",
                "passed": False,
                "problems": [
                    "paired-replay behavior suite failed",
                    behavior_process.stdout.strip(),
                    behavior_process.stderr.strip(),
                ],
            }
        )

    failures = [result for result in results if not result["passed"]]
    summary: dict[str, Any] = {
        "suite": "pit_adversarial_suite_v1",
        "result": "PASS" if not failures else "FAIL",
        "cases": len(results),
        "synthetic_adapter_cases": len(cases) + len(critical_binding_cases),
        "declared_synthetic_cases": len(cases),
        "critical_binding_cases": len(critical_binding_cases),
        "qrc_production_cases": len(QRC_CASES),
        "behavior_probe_suite": "PASS" if behavior_passed else "FAIL",
        "behavior_probe_output": behavior_process.stdout.strip(),
        "passed": len(results) - len(failures),
        "failed": len(failures),
    }
    if failures:
        summary["failures"] = failures
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
