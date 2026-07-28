#!/usr/bin/env python3
"""Hash-bound, paired-replay behavior proof for PIT feature pipelines."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PASS, NEEDS, FAIL = "PASS", "NEEDS_EVIDENCE", "FAIL"
RANK = {PASS: 0, NEEDS: 1, FAIL: 2}
EXIT = {PASS: 0, NEEDS: 2, FAIL: 3}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PROBES = {"PREFIX_REPLAY", "FUTURE_POISON", "REVISION_REPLAY", "UNIVERSE_CANARY"}
ARTIFACTS = (
    "baseline_raw_snapshot",
    "probe_raw_snapshot",
    "code_or_query",
    "parameters",
    "environment",
    "baseline_output",
    "probe_output",
    "pit_audit_manifest",
    "perturbation_ledger",
    "pipeline_receipt",
)
RECEIPT_BOUND = ARTIFACTS[:-1]
OUTPUT_FIELDS = [
    "sample_id",
    "prediction_time",
    "feature_name",
    "feature_value_json",
]
CHECK_NAMES = {
    "B001": "Request artifacts and exact hashes",
    "B002": "Pipeline receipt and probe construction",
    "B003": "Canonical paired-output integrity",
    "B004": "Protected-prefix behavior invariant",
}
PARENT_CHECKS = {
    "I001",
    "I002",
    "S001",
    "T001",
    "T002",
    "T003",
    "U001",
    "U002",
    "C001",
    "M001",
    "A001",
    "H001",
    "Q001",
    "Q002",
    "Q003",
    "L001",
    "L002",
}


def reject_constant(token: str) -> None:
    raise ValueError(f"non-standard JSON number: {token}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_loads(text: str, *, decimal_numbers: bool = False) -> Any:
    kwargs: dict[str, Any] = {
        "parse_constant": reject_constant,
        "object_pairs_hook": reject_duplicates,
    }
    if decimal_numbers:
        kwargs.update(parse_int=Decimal, parse_float=Decimal)
    return json.loads(text, **kwargs)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def aware_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be a non-empty string")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be offset-aware")
    return parsed.astimezone(timezone.utc)


def canonical_time(value: Any) -> tuple[str, datetime]:
    parsed = aware_time(value)
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z"), parsed


def canonical_scalar(text: str) -> str:
    value = strict_loads(text, decimal_numbers=True)
    if isinstance(value, (list, dict)):
        raise ValueError("feature value must be a JSON scalar")
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return canonical_json(value)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("feature number must be finite")
    if value == 0:
        return "0"
    try:
        rendered = format(value, "f")
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid feature number") from exc
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def key_digest(keys: set[tuple[str, str, str]]) -> str:
    payload = [[sample, prediction, feature] for sample, prediction, feature in sorted(keys)]
    return sha_bytes(canonical_json(payload).encode("utf-8"))


class BehaviorAudit:
    def __init__(self, request_path: Path, request: Any, initial_failure: str = ""):
        self.request_path = request_path
        self.base = request_path.resolve().parent
        self.request = request if isinstance(request, dict) else {}
        self.checks = {
            key: {"id": key, "name": name, "status": PASS, "messages": []}
            for key, name in CHECK_NAMES.items()
        }
        self.lineage: dict[str, dict[str, Any]] = {}
        self.files: dict[str, Path] = {}
        self.receipt: dict[str, Any] | None = None
        self.parent_audit: dict[str, Any] | None = None
        self.documents: dict[str, dict[str, Any]] = {}
        self.probe_type = self.request.get("probe_type")
        self.cutoff: datetime | None = None
        self.expected_count: int | None = None
        self.expected_digest: str | None = None
        self.canaries: set[str] = set()
        self.canaries_valid = False
        self.outputs: dict[str, dict[tuple[str, str, str], tuple[str, datetime]]] = {}
        self.protected: dict[str, dict[tuple[str, str, str], str]] = {}
        if initial_failure:
            self.mark("B001", FAIL, initial_failure)
        if not isinstance(request, dict):
            self.mark("B001", FAIL, "request root must be a JSON object")

    def mark(self, check: str, status: str, message: str) -> None:
        item = self.checks[check]
        if RANK[status] > RANK[item["status"]]:
            item["status"] = status
        if message not in item["messages"]:
            item["messages"].append(message)

    def need(self, check: str, message: str) -> None:
        self.mark(check, NEEDS, message)

    def fail(self, check: str, message: str) -> None:
        self.mark(check, FAIL, message)

    def check_inputs(self) -> None:
        version = self.request.get("request_version")
        if version is None:
            self.need("B001", "missing request_version")
        elif version != "pit_behavior_request_v1":
            self.fail("B001", f"unsupported request_version: {version!r}")
        request_id = self.request.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            self.need("B001", "missing non-empty request_id")
        if self.probe_type is None:
            self.need("B001", "missing probe_type")
        elif self.probe_type not in PROBES:
            self.fail("B001", f"unsupported probe_type: {self.probe_type!r}")

        declared = self.request.get("artifacts")
        if not isinstance(declared, dict):
            self.need("B001", "missing artifacts object")
            declared = {}
        for name in ARTIFACTS:
            item = declared.get(name)
            if not isinstance(item, dict):
                self.need("B001", f"missing artifact declaration: {name}")
                continue
            relpath, declared_sha = item.get("path"), item.get("sha256")
            if not isinstance(relpath, str) or not relpath:
                self.need("B001", f"missing artifact path: {name}")
                continue
            if declared_sha is None:
                self.need("B001", f"missing artifact sha256: {name}")
                continue
            if not isinstance(declared_sha, str) or not SHA_RE.fullmatch(declared_sha):
                self.fail("B001", f"malformed artifact sha256: {name}")
                continue
            path = Path(relpath)
            path = path if path.is_absolute() else self.base / path
            if not path.is_file():
                self.need("B001", f"artifact file is unavailable: {name}")
                continue
            try:
                actual_sha = sha_file(path)
                size = path.stat().st_size
            except OSError as exc:
                self.need("B001", f"cannot read artifact {name}: {exc}")
                continue
            self.files[name] = path
            self.lineage[name] = {
                "path": relpath,
                "declared_sha256": declared_sha,
                "actual_sha256": actual_sha,
                "size_bytes": size,
            }
            if actual_sha != declared_sha:
                self.fail("B001", f"artifact sha256 mismatch: {name}")

        receipt_path = self.files.get("pipeline_receipt")
        if receipt_path:
            try:
                parsed = strict_loads(receipt_path.read_text(encoding="utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("receipt root must be an object")
                self.receipt = parsed
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                self.fail("B001", f"malformed pipeline receipt: {exc}")
        else:
            self.need("B002", "pipeline receipt is unavailable")
        for name, check in (
            ("pit_audit_manifest", "B001"),
            ("baseline_raw_snapshot", "B002"),
            ("probe_raw_snapshot", "B002"),
            ("perturbation_ledger", "B002"),
        ):
            path = self.files.get(name)
            if path is None:
                self.need(check, f"{name} is unavailable")
                continue
            try:
                document = strict_loads(path.read_text(encoding="utf-8"))
                if not isinstance(document, dict):
                    raise ValueError("root must be an object")
                self.documents[name] = document
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                self.fail(check, f"malformed {name}: {exc}")
        self.parent_audit = self.documents.get("pit_audit_manifest")
        if self.parent_audit is not None:
            schema = self.parent_audit.get("schema_version")
            if schema is None:
                self.need("B001", "parent PIT audit lacks schema_version")
            elif schema != "pit_audit_manifest_v1":
                self.fail("B001", f"unsupported parent PIT audit schema: {schema!r}")
            parent_status = self.parent_audit.get("status")
            if parent_status is None:
                self.need("B001", "parent PIT audit lacks status")
            elif parent_status == NEEDS:
                self.need("B001", "parent PIT audit is NEEDS_EVIDENCE")
            elif parent_status == FAIL:
                self.fail("B001", "parent PIT audit is FAIL")
            elif parent_status != PASS:
                self.fail("B001", f"invalid parent PIT audit status: {parent_status!r}")
            qualification = self.parent_audit.get("pit_qualification")
            if qualification is None:
                self.need("B001", "parent PIT audit lacks pit_qualification")
            elif parent_status == PASS and qualification != "QUALIFIED":
                self.fail("B001", "PASS parent PIT audit is not QUALIFIED")
            elif parent_status == NEEDS and qualification != "UNRESOLVED":
                self.fail("B001", "unresolved parent has contradictory qualification")
            ceiling = self.parent_audit.get("evidence_ceiling")
            if ceiling is None:
                self.need("B001", "parent PIT audit lacks evidence_ceiling")
            elif ceiling != PASS:
                if parent_status == PASS:
                    self.fail("B001", "PASS parent PIT audit evidence_ceiling is not PASS")
                else:
                    self.need("B001", "parent PIT audit evidence ceiling is unresolved")
            coverage = self.parent_audit.get("coverage_matrix")
            if not isinstance(coverage, dict):
                self.need("B001", "parent PIT audit lacks coverage_matrix")
            elif coverage.get("scope") is None:
                self.need("B001", "parent PIT audit lacks coverage scope")
            elif coverage.get("scope") != "FULL_TRAINING_INPUT":
                if parent_status == PASS:
                    self.fail("B001", "PASS parent scope is not FULL_TRAINING_INPUT")
                else:
                    self.need("B001", "parent PIT audit lacks full-input coverage")
            parent_checks = self.parent_audit.get("checks")
            if not isinstance(parent_checks, list):
                self.need("B001", "parent PIT audit lacks fixed checks")
            else:
                check_ids = [
                    item.get("check_id")
                    for item in parent_checks
                    if isinstance(item, dict)
                ]
                if (
                    len(parent_checks) != len(PARENT_CHECKS)
                    or len(check_ids) != len(PARENT_CHECKS)
                    or set(check_ids) != PARENT_CHECKS
                ):
                    self.fail("B001", "parent PIT audit fixed-check inventory mismatch")
                elif any(item.get("status") == FAIL for item in parent_checks):
                    self.fail("B001", "parent PIT audit contains a FAIL check")
                elif any(item.get("status") != PASS for item in parent_checks):
                    if parent_status == PASS:
                        self.fail("B001", "PASS parent has a non-PASS fixed check")
                    else:
                        self.need("B001", "parent PIT audit contains an unresolved check")
            binding = self.parent_audit.get("contract_binding")
            if binding is None:
                self.need("B001", "parent PIT audit lacks contract_binding")
            elif not isinstance(binding, dict):
                self.fail("B001", "parent PIT audit contract_binding must be an object")
            else:
                if binding.get("adapter") != "quant_contract_v2":
                    self.fail(
                        "B001", "parent PIT audit must use production quant_contract_v2"
                    )
                if binding.get("execution_boundary") != "PRODUCTION_CLI":
                    self.fail(
                        "B001", "parent PIT audit execution_boundary must be PRODUCTION_CLI"
                    )
                if binding.get("test_only_adapter") is not False:
                    self.fail(
                        "B001", "parent PIT audit test_only_adapter must be false"
                    )
            for field in ("audit_id", "content_sha256"):
                value = self.parent_audit.get(field)
                if value is None:
                    self.need("B001", f"parent PIT audit lacks {field}")
                elif field.endswith("sha256") and (
                    not isinstance(value, str) or not SHA_RE.fullmatch(value)
                ):
                    self.fail("B001", f"parent PIT audit has malformed {field}")
                elif field == "audit_id" and (not isinstance(value, str) or not value):
                    self.fail("B001", "parent PIT audit has invalid audit_id")
            parent_core = {
                key: value
                for key, value in self.parent_audit.items()
                if key not in {"audit_id", "content_sha256", "report_sha256"}
            }
            expected_content = sha_bytes(canonical_json(parent_core).encode("utf-8"))
            if self.parent_audit.get("content_sha256") != expected_content:
                self.fail("B001", "parent PIT audit content_sha256 is not canonical")
            if self.parent_audit.get("audit_id") != (
                f"pit-audit-v1-{expected_content[:32]}"
            ):
                self.fail("B001", "parent PIT audit audit_id does not derive from content")

    def check_receipt(self) -> None:
        if self.receipt is None:
            self.need("B002", "cannot validate absent or malformed receipt")
            self.need("B003", "receipt protection evidence is unavailable")
            self.need("B004", "receipt protection evidence is unavailable")
            return
        receipt = self.receipt
        version = receipt.get("receipt_version")
        if version is None:
            self.need("B002", "missing receipt_version")
        elif version != "pit_behavior_receipt_v1":
            self.fail("B002", f"unsupported receipt_version: {version!r}")
        for field in ("receipt_id", "baseline_run_id", "probe_run_id"):
            if not isinstance(receipt.get(field), str) or not receipt.get(field):
                self.need("B002", f"missing non-empty receipt field: {field}")
        if (
            isinstance(receipt.get("baseline_run_id"), str)
            and receipt.get("baseline_run_id") == receipt.get("probe_run_id")
        ):
            self.fail("B002", "baseline_run_id and probe_run_id must differ")
        for field in ("request_id", "probe_type"):
            value = receipt.get(field)
            if value is None:
                self.need("B002", f"missing receipt field: {field}")
            elif value != self.request.get(field):
                self.fail("B002", f"request/receipt {field} mismatch")
        parent_binding = receipt.get("parent_audit")
        if not isinstance(parent_binding, dict):
            self.need("B002", "missing parent_audit receipt binding")
        elif self.parent_audit is None:
            self.need("B002", "parent PIT audit cannot be checked against receipt")
        else:
            for field in ("audit_id", "content_sha256", "status"):
                value = parent_binding.get(field)
                if value is None:
                    self.need("B002", f"parent_audit receipt binding lacks {field}")
                elif value != self.parent_audit.get(field):
                    self.fail("B002", f"parent_audit receipt {field} mismatch")

        bindings = receipt.get("artifact_sha256")
        if not isinstance(bindings, dict):
            self.need("B002", "missing receipt artifact_sha256 object")
            bindings = {}
        declared = self.request.get("artifacts")
        declared = declared if isinstance(declared, dict) else {}
        for name in RECEIPT_BOUND:
            bound = bindings.get(name)
            if bound is None:
                self.need("B002", f"receipt does not bind artifact: {name}")
                continue
            if not isinstance(bound, str) or not SHA_RE.fullmatch(bound):
                self.fail("B002", f"receipt has malformed artifact hash: {name}")
                continue
            request_hash = declared.get(name, {}).get("sha256") if isinstance(
                declared.get(name), dict
            ) else None
            if request_hash is None:
                self.need("B002", f"request artifact binding is unavailable: {name}")
            elif bound != request_hash:
                self.fail("B002", f"request/receipt artifact hash mismatch: {name}")
            actual = self.lineage.get(name, {}).get("actual_sha256")
            if actual is None:
                self.need("B002", f"actual artifact hash is unavailable: {name}")
            elif bound != actual:
                self.fail("B002", f"receipt/actual artifact hash mismatch: {name}")

        protection = receipt.get("protection")
        if not isinstance(protection, dict):
            self.need("B002", "missing protection object")
            self.need("B003", "missing protected-key declaration")
            self.need("B004", "missing protected cutoff")
        else:
            if protection.get("comparison") is None:
                self.need("B002", "missing protection comparison")
            elif protection.get("comparison") != "LE":
                self.fail("B002", "protection comparison must be LE")
            if protection.get("protected_through") is None:
                self.need("B002", "missing protected_through")
                self.need("B004", "missing protected cutoff")
            else:
                try:
                    self.cutoff = aware_time(protection["protected_through"])
                except (TypeError, ValueError) as exc:
                    self.fail("B002", f"invalid protected_through: {exc}")
                    self.need("B004", "valid protected cutoff is unavailable")
            count = protection.get("expected_key_count")
            if count is None:
                self.need("B003", "missing expected_key_count")
            elif isinstance(count, bool) or not isinstance(count, int) or count < 1:
                self.fail("B003", "expected_key_count must be a positive integer")
            else:
                self.expected_count = count
            digest = protection.get("expected_keys_sha256")
            if digest is None:
                self.need("B003", "missing expected_keys_sha256")
            elif not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
                self.fail("B003", "expected_keys_sha256 is malformed")
            else:
                self.expected_digest = digest

        probe = receipt.get("probe")
        if not isinstance(probe, dict):
            self.need("B002", "missing probe descriptor")
            return
        mutation_type = probe.get("mutation_type")
        if mutation_type is None:
            self.need("B002", "missing probe mutation_type")
        elif mutation_type != self.probe_type:
            self.fail("B002", "probe mutation_type does not match probe_type")
        baseline_hash = bindings.get("baseline_raw_snapshot")
        probe_hash = bindings.get("probe_raw_snapshot")
        if (
            isinstance(baseline_hash, str)
            and SHA_RE.fullmatch(baseline_hash)
            and isinstance(probe_hash, str)
            and SHA_RE.fullmatch(probe_hash)
        ):
            if self.probe_type == "PREFIX_REPLAY" and baseline_hash != probe_hash:
                self.fail("B002", "PREFIX_REPLAY requires identical raw snapshots")
            if self.probe_type in PROBES - {"PREFIX_REPLAY"} and baseline_hash == probe_hash:
                self.fail("B002", f"{self.probe_type} requires a changed raw snapshot")

        if self.probe_type in {"FUTURE_POISON", "REVISION_REPLAY"}:
            mutation_time = probe.get("mutation_time_min")
            if mutation_time is None:
                self.need("B002", "missing mutation_time_min")
            else:
                try:
                    parsed = aware_time(mutation_time)
                    if self.cutoff is not None and parsed <= self.cutoff:
                        self.fail(
                            "B002",
                            "mutation_time_min must be strictly after protected_through",
                        )
                except (TypeError, ValueError) as exc:
                    self.fail("B002", f"invalid mutation_time_min: {exc}")
        if self.probe_type == "UNIVERSE_CANARY":
            canaries = probe.get("canary_sample_ids")
            if canaries is None:
                self.need("B002", "missing canary_sample_ids")
            elif (
                not isinstance(canaries, list)
                or not canaries
                or any(
                    not isinstance(value, str)
                    or not value
                    or value != value.strip()
                    for value in canaries
                )
            ):
                self.fail("B002", "canary_sample_ids must be a non-empty string list")
            elif len(canaries) != len(set(canaries)):
                self.fail("B002", "canary_sample_ids must be unique")
            else:
                self.canaries = set(canaries)
                self.canaries_valid = True

    def parse_snapshot(
        self, name: str
    ) -> dict[str, tuple[dict[str, Any], str]] | None:
        document = self.documents.get(name)
        if document is None:
            self.need("B002", f"cannot verify absent {name}")
            return None
        version = document.get("snapshot_version")
        if version is None:
            self.need("B002", f"{name} lacks snapshot_version")
            return None
        if version != "pit_behavior_snapshot_v1":
            self.fail("B002", f"{name} has unsupported snapshot_version")
            return None
        records = document.get("records")
        if records is None:
            self.need("B002", f"{name} lacks records")
            return None
        if not isinstance(records, list):
            self.fail("B002", f"{name} records must be a list")
            return None
        parsed: dict[str, tuple[dict[str, Any], str]] = {}
        incomplete = False
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                self.fail("B002", f"{name} record {index} must be an object")
                return None
            raw_key = record.get("raw_key")
            if raw_key is None:
                self.need("B002", f"{name} record {index} lacks raw_key")
                incomplete = True
                continue
            if not isinstance(raw_key, str) or not raw_key or raw_key != raw_key.strip():
                self.fail("B002", f"{name} record {index} has invalid raw_key")
                return None
            if raw_key in parsed:
                self.fail("B002", f"{name} duplicates raw_key {raw_key!r}")
                return None
            parsed[raw_key] = (
                record,
                sha_bytes(canonical_json(record).encode("utf-8")),
            )
        return None if incomplete else parsed

    def parse_ledger(self) -> dict[str, dict[str, Any]] | None:
        ledger = self.documents.get("perturbation_ledger")
        if ledger is None:
            self.need("B002", "cannot verify absent perturbation_ledger")
            return None
        version = ledger.get("ledger_version")
        if version is None:
            self.need("B002", "perturbation ledger lacks ledger_version")
            return None
        if version != "pit_perturbation_ledger_v1":
            self.fail("B002", "unsupported perturbation ledger version")
            return None
        for field, artifact in (
            ("baseline_snapshot_sha256", "baseline_raw_snapshot"),
            ("probe_snapshot_sha256", "probe_raw_snapshot"),
        ):
            value = ledger.get(field)
            if value is None:
                self.need("B002", f"perturbation ledger lacks {field}")
            elif not isinstance(value, str) or not SHA_RE.fullmatch(value):
                self.fail("B002", f"perturbation ledger has malformed {field}")
            elif value != self.lineage.get(artifact, {}).get("actual_sha256"):
                self.fail("B002", f"perturbation ledger {field} mismatch")
        entries = ledger.get("entries")
        if entries is None:
            self.need("B002", "perturbation ledger lacks entries")
            return None
        if not isinstance(entries, list):
            self.fail("B002", "perturbation ledger entries must be a list")
            return None
        parsed: dict[str, dict[str, Any]] = {}
        incomplete = False
        required = {
            "raw_key",
            "operation",
            "change_type",
            "known_time",
            "baseline_record_sha256",
            "probe_record_sha256",
        }
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                self.fail("B002", f"ledger entry {index} must be an object")
                return None
            missing = required - set(entry)
            if missing:
                self.need("B002", f"ledger entry {index} lacks {sorted(missing)}")
                incomplete = True
                continue
            raw_key = entry["raw_key"]
            if not isinstance(raw_key, str) or not raw_key:
                self.fail("B002", f"ledger entry {index} has invalid raw_key")
                return None
            if raw_key in parsed:
                self.fail("B002", f"ledger duplicates raw_key {raw_key!r}")
                return None
            if entry["operation"] not in {"ADD", "UPDATE", "DELETE"}:
                self.fail("B002", f"ledger entry {index} has invalid operation")
                return None
            if entry["change_type"] != self.probe_type:
                self.fail("B002", f"ledger entry {index} has wrong change_type")
            try:
                aware_time(entry["known_time"])
            except (TypeError, ValueError) as exc:
                self.fail("B002", f"ledger entry {index} has invalid known_time: {exc}")
            for field in ("baseline_record_sha256", "probe_record_sha256"):
                value = entry[field]
                if value is not None and (
                    not isinstance(value, str) or not SHA_RE.fullmatch(value)
                ):
                    self.fail("B002", f"ledger entry {index} has malformed {field}")
                    return None
            parsed[raw_key] = entry
        return None if incomplete else parsed

    def check_perturbation(self) -> None:
        baseline = self.parse_snapshot("baseline_raw_snapshot")
        probe = self.parse_snapshot("probe_raw_snapshot")
        ledger = self.parse_ledger()
        if baseline is None or probe is None or ledger is None:
            self.need("B002", "complete snapshots and ledger are required")
            return
        changed = {
            key
            for key in set(baseline) | set(probe)
            if baseline.get(key, (None, None))[1] != probe.get(key, (None, None))[1]
        }
        if set(ledger) != changed:
            self.fail(
                "B002",
                f"ledger/diff key mismatch: actual={len(changed)}, ledger={len(ledger)}",
            )
            return
        actual: dict[str, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {}
        for raw_key in sorted(changed):
            before = baseline.get(raw_key)
            after = probe.get(raw_key)
            operation = "ADD" if before is None else "DELETE" if after is None else "UPDATE"
            entry = ledger[raw_key]
            expected = {
                "operation": operation,
                "baseline_record_sha256": before[1] if before else None,
                "probe_record_sha256": after[1] if after else None,
            }
            for field, value in expected.items():
                if entry.get(field) != value:
                    self.fail("B002", f"ledger {field} mismatch for {raw_key!r}")
            actual[raw_key] = (
                before[0] if before else None,
                after[0] if after else None,
            )
        if self.probe_type == "PREFIX_REPLAY":
            if changed:
                self.fail("B002", "PREFIX_REPLAY snapshot diff must be empty")
            return
        if self.probe_type in PROBES - {"PREFIX_REPLAY"} and not changed:
            self.fail("B002", f"{self.probe_type} requires a non-empty record diff")
            return

        scope_field = {
            "FUTURE_POISON": "available_time",
            "REVISION_REPLAY": "revision_known_time",
            "UNIVERSE_CANARY": "universe_known_time",
        }.get(self.probe_type)
        observed_all: list[datetime] = []
        for raw_key, pair in actual.items():
            entry_times: list[datetime] = []
            for side, record in zip(("baseline", "probe"), pair):
                if record is None:
                    continue
                if self.probe_type == "UNIVERSE_CANARY":
                    sample = record.get("sample_id")
                    if sample is None:
                        self.need(
                            "B002", f"{side} changed record {raw_key!r} lacks sample_id"
                        )
                    elif self.canaries_valid and sample not in self.canaries:
                        self.fail(
                            "B002",
                            f"changed record {raw_key!r} is outside declared canaries",
                        )
                value = record.get(scope_field) if scope_field else None
                if value is None:
                    self.need(
                        "B002", f"{side} changed record {raw_key!r} lacks {scope_field}"
                    )
                    continue
                try:
                    parsed = aware_time(value)
                except (TypeError, ValueError) as exc:
                    self.fail(
                        "B002",
                        f"{side} changed record {raw_key!r} has invalid "
                        f"{scope_field}: {exc}",
                    )
                    continue
                entry_times.append(parsed)
                observed_all.append(parsed)
                if self.cutoff is not None and parsed <= self.cutoff:
                    self.fail(
                        "B002",
                        f"changed record {raw_key!r} has {scope_field} "
                        "inside protected prefix",
                    )
            if entry_times:
                try:
                    ledger_time = aware_time(ledger[raw_key]["known_time"])
                except (TypeError, ValueError):
                    continue
                if ledger_time != min(entry_times):
                    self.fail("B002", f"ledger known_time mismatch for {raw_key!r}")
        if (
            self.probe_type in {"FUTURE_POISON", "REVISION_REPLAY"}
            and observed_all
            and self.receipt is not None
            and isinstance(self.receipt.get("probe"), dict)
        ):
            try:
                declared = aware_time(self.receipt["probe"].get("mutation_time_min"))
            except (TypeError, ValueError):
                return
            if declared != min(observed_all):
                self.fail("B002", "mutation_time_min does not equal recomputed minimum")

    def read_output(
        self, path: Path
    ) -> dict[tuple[str, str, str], tuple[str, datetime]]:
        result: dict[tuple[str, str, str], tuple[str, datetime]] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError("empty CSV") from exc
            if header != OUTPUT_FIELDS:
                raise ValueError(f"header must be exactly {','.join(OUTPUT_FIELDS)}")
            for row_number, row in enumerate(reader, 2):
                if len(row) != len(OUTPUT_FIELDS):
                    raise ValueError(f"row {row_number} has {len(row)} columns")
                sample, prediction, feature, raw_value = row
                if not sample or sample != sample.strip():
                    raise ValueError(f"row {row_number} has invalid sample_id")
                if not feature or feature != feature.strip():
                    raise ValueError(f"row {row_number} has invalid feature_name")
                normalized_time, parsed_time = canonical_time(prediction)
                value = canonical_scalar(raw_value)
                key = (sample, normalized_time, feature)
                if key in result:
                    raise ValueError(f"row {row_number} duplicates canonical key {key!r}")
                result[key] = (value, parsed_time)
        return result

    def check_outputs(self) -> None:
        for label, artifact in (
            ("baseline", "baseline_output"),
            ("probe", "probe_output"),
        ):
            path = self.files.get(artifact)
            if path is None:
                self.need("B003", f"{artifact} is unavailable")
                self.need("B004", f"{artifact} is unavailable")
                continue
            try:
                self.outputs[label] = self.read_output(path)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                self.fail("B003", f"malformed {artifact}: {exc}")
                self.need("B004", f"canonical {artifact} is unavailable")
        if self.cutoff is None:
            return
        for label, rows in self.outputs.items():
            self.protected[label] = {
                key: value
                for key, (value, prediction) in rows.items()
                if prediction <= self.cutoff
            }
        baseline = self.protected.get("baseline")
        if baseline is not None:
            keys = set(baseline)
            if not keys:
                self.need("B003", "baseline protected key set is empty")
                self.need("B004", "no protected observations exist")
            if self.expected_count is not None and len(keys) != self.expected_count:
                self.fail(
                    "B003",
                    f"baseline protected key count {len(keys)} != {self.expected_count}",
                )
            digest = key_digest(keys)
            if self.expected_digest is not None and digest != self.expected_digest:
                self.fail("B003", "baseline protected key digest mismatch")

    def check_invariant(self) -> None:
        baseline = self.protected.get("baseline")
        probe = self.protected.get("probe")
        if baseline is None or probe is None:
            self.need("B004", "both canonical protected outputs are required")
            return
        base_keys, probe_keys = set(baseline), set(probe)
        if not base_keys:
            self.need("B004", "protected invariant has no observations")
            return
        if self.probe_type == "UNIVERSE_CANARY" and self.canaries:
            emitted = sorted(
                {key[0] for key in base_keys | probe_keys if key[0] in self.canaries}
            )
            if emitted:
                self.fail("B004", f"protected canary samples were emitted: {emitted[:5]}")
        missing = sorted(base_keys - probe_keys)
        added = sorted(probe_keys - base_keys)
        if missing or added:
            self.fail(
                "B004",
                f"protected key drift: missing={len(missing)}, added={len(added)}",
            )
        changed = sorted(
            key for key in base_keys & probe_keys if baseline[key] != probe[key]
        )
        if changed:
            self.fail("B004", f"protected value drift at {len(changed)} key(s)")

    def run(self) -> dict[str, Any]:
        self.check_inputs()
        self.check_receipt()
        self.check_perturbation()
        self.check_outputs()
        self.check_invariant()
        status = max(
            (item["status"] for item in self.checks.values()), key=lambda value: RANK[value]
        )
        findings = [
            {"check_id": item["id"], "status": item["status"], "message": message}
            for item in self.checks.values()
            for message in item["messages"]
        ]
        baseline_keys = set(self.protected.get("baseline", {}))
        probe_keys = set(self.protected.get("probe", {}))
        core = {
            "manifest_version": "pit_behavior_manifest_v1",
            "spec_version": "pit_behavior_spec_v1",
            "certification_status": "NOVEL_CANDIDATE",
            "request_id": self.request.get("request_id", "UNKNOWN"),
            "receipt_id": (
                self.receipt.get("receipt_id", "UNKNOWN") if self.receipt else "UNKNOWN"
            ),
            "probe_type": self.probe_type if self.probe_type in PROBES else "UNKNOWN",
            "status": status,
            "parent_audit": {
                "audit_id": (
                    self.parent_audit.get("audit_id") if self.parent_audit else None
                ),
                "content_sha256": (
                    self.parent_audit.get("content_sha256")
                    if self.parent_audit
                    else None
                ),
                "status": (
                    self.parent_audit.get("status") if self.parent_audit else None
                ),
            },
            "input_lineage": self.lineage,
            "protection": {
                "comparison": "LE",
                "protected_through": (
                    self.cutoff.isoformat(timespec="microseconds").replace("+00:00", "Z")
                    if self.cutoff
                    else None
                ),
                "baseline_key_count": len(baseline_keys),
                "baseline_keys_sha256": key_digest(baseline_keys),
                "probe_key_count": len(probe_keys),
                "probe_keys_sha256": key_digest(probe_keys),
            },
            "checks": list(self.checks.values()),
            "findings": findings,
            "limitations": [
                "This proves only the supplied hash-bound run pair, not all executions.",
                "Snapshot time and sample field meanings remain upstream semantic trust roots.",
                "This does not replace the fixed PIT audit or certify training/deployment.",
            ],
            "next_action": {
                PASS: "Preserve this pair as supplemental behavior evidence; keep the fixed PIT gate.",
                NEEDS: "Supply the smallest missing hash, receipt field, artifact, or protected population.",
                FAIL: "Isolate the first protected drift or binding contradiction and rerun a new pair.",
            }[status],
        }
        content_hash = sha_bytes(canonical_json(core).encode("utf-8"))
        manifest = {
            **core,
            "content_sha256": content_hash,
            "behavior_id": f"pit-behavior-{content_hash[:20]}",
        }
        report = render_report(manifest)
        manifest["report_sha256"] = sha_bytes(report.encode("utf-8"))
        return {"manifest": manifest, "report": report}


def render_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# PIT Behavior Proof",
        "",
        "Report: `pit_behavior_report_v1`",
        f"Behavior ID: `{manifest['behavior_id']}`",
        f"Status: **{manifest['status']}**",
        f"Certification: `{manifest['certification_status']}`",
        f"Probe: `{manifest['probe_type']}`",
        f"Content SHA-256: `{manifest['content_sha256']}`",
        "",
        "## Checks",
        "",
    ]
    for item in manifest["checks"]:
        lines.append(f"- `{item['id']}` {item['status']} — {item['name']}")
    lines.extend(
        [
            "",
            "## Protected prefix",
            "",
            f"- Through: `{manifest['protection']['protected_through']}`",
            f"- Baseline keys: {manifest['protection']['baseline_key_count']}",
            f"- Probe keys: {manifest['protection']['probe_key_count']}",
            "",
            "## Next action",
            "",
            manifest["next_action"],
            "",
            "_NOVEL_CANDIDATE: supplemental paired-run evidence only._",
            "",
        ]
    )
    return "\n".join(lines)


def publish(output: Path, result: dict[str, Any]) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("output directory already exists and is not empty")
        output.rmdir()
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        payloads = {
            "behavior_manifest.json": (
                json.dumps(
                    result["manifest"],
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            ),
            "behavior_report.md": result["report"],
        }
        for name, text in payloads.items():
            path = staging / name
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        if sha_file(staging / "behavior_report.md") != result["manifest"]["report_sha256"]:
            raise RuntimeError("report digest verification failed")
        os.replace(staging, output)
        directory_fd = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        text = args.request.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"invocation error: cannot read request: {exc}", file=sys.stderr)
        return 64
    initial_failure = ""
    try:
        request = strict_loads(text)
    except (ValueError, json.JSONDecodeError) as exc:
        request = {}
        initial_failure = f"malformed request JSON: {exc}"
    try:
        result = BehaviorAudit(args.request, request, initial_failure).run()
        publish(args.output_dir, result)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"execution error: {exc}", file=sys.stderr)
        return 64
    manifest = result["manifest"]
    print(
        canonical_json(
            {
                "behavior_id": manifest["behavior_id"],
                "output_dir": str(args.output_dir.resolve()),
                "status": manifest["status"],
            }
        )
    )
    return EXIT[manifest["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
