#!/usr/bin/env python3
"""Run positive and negative synthetic cases for audit_behavior.py."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).with_name("audit_behavior.py")
EXIT = {"PASS": 0, "NEEDS_EVIDENCE": 2, "FAIL": 3}
EXPECTED_CASE_COUNT = 18
PARENT_CHECK_IDS = [
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
]


def encoded(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(encoded(value))


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            ["sample_id", "prediction_time", "feature_name", "feature_value_json"]
        )
        writer.writerows(rows)


def record_sha(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def expected_digest(rows: list[list[str]]) -> str:
    keys = sorted(
        [row[0], row[1].replace("00:00:00Z", "00:00:00.000000Z"), row[2]]
        for row in rows
        if row[1] <= "2025-01-03T00:00:00Z"
    )
    return hashlib.sha256(
        json.dumps(keys, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def make_case(
    root: Path,
    case_id: str,
    probe: str,
    negative: bool = False,
    out_of_scope: bool = False,
    missing_scope: bool = False,
) -> Path:
    root.mkdir()
    baseline_rows = [
        ["asset-a", "2025-01-02T00:00:00Z", "f1", "1"],
        ["asset-a", "2025-01-05T00:00:00Z", "f1", "2"],
    ]
    probe_rows = [row[:] for row in baseline_rows]
    if probe == "FUTURE_POISON":
        probe_rows[1][3] = "999"
    elif probe == "REVISION_REPLAY":
        probe_rows[1][3] = "3.0"
    elif probe == "UNIVERSE_CANARY":
        probe_rows.append(["canary-x", "2025-01-05T00:00:00Z", "f1", "7"])
    if negative and probe in {"PREFIX_REPLAY", "FUTURE_POISON"}:
        probe_rows[0][3] = "9"
    elif negative and probe == "REVISION_REPLAY":
        probe_rows.pop(0)
    elif negative and probe == "UNIVERSE_CANARY":
        probe_rows.append(["canary-x", "2025-01-02T00:00:00Z", "f1", "7"])

    historical = {
        "raw_key": "raw-protected",
        "sample_id": "asset-a",
        "available_time": "2025-01-01T00:00:00Z",
        "revision_known_time": "2025-01-01T00:00:00Z",
        "universe_known_time": "2025-01-01T00:00:00Z",
        "payload": {"value": 1},
    }
    future = {
        "raw_key": "raw-future",
        "sample_id": "asset-a",
        "available_time": "2025-01-04T00:00:00Z",
        "revision_known_time": "2025-01-04T00:00:00Z",
        "universe_known_time": "2025-01-04T00:00:00Z",
        "payload": {"value": 2},
    }
    if out_of_scope and probe == "FUTURE_POISON":
        future["available_time"] = "2025-01-02T00:00:00Z"
    elif out_of_scope and probe == "REVISION_REPLAY":
        future["revision_known_time"] = "2025-01-02T00:00:00Z"
    if missing_scope and probe == "FUTURE_POISON":
        del future["available_time"]
    baseline_records = [historical, future]
    probe_records = json.loads(json.dumps(baseline_records))
    if probe in {"FUTURE_POISON", "REVISION_REPLAY"}:
        probe_records[1]["payload"]["value"] = 999
    elif probe == "UNIVERSE_CANARY":
        canary_known_time = (
            "2025-01-02T00:00:00Z"
            if out_of_scope
            else "2025-01-04T00:00:00Z"
        )
        probe_records.append(
            {
                "raw_key": "raw-canary",
                "sample_id": "canary-x",
                "available_time": "2025-01-04T00:00:00Z",
                "revision_known_time": "2025-01-04T00:00:00Z",
                "universe_known_time": canary_known_time,
                "payload": {"value": 7},
            }
        )
    write_json(
        root / "raw-before.json",
        {"snapshot_version": "pit_behavior_snapshot_v1", "records": baseline_records},
    )
    write_json(
        root / "raw-after.json",
        {"snapshot_version": "pit_behavior_snapshot_v1", "records": probe_records},
    )
    (root / "feature.sql").write_text("select feature from raw\n", encoding="utf-8")
    write_json(root / "parameters.json", {"window": 3})
    write_json(root / "environment.json", {"python": "synthetic", "tzdb": "test"})
    write_csv(root / "baseline.csv", baseline_rows)
    write_csv(root / "probe.csv", probe_rows)
    parent_core = {
        "schema_version": "pit_audit_manifest_v1",
        "status": "PASS",
        "pit_qualification": "QUALIFIED",
        "evidence_ceiling": "PASS",
        "coverage_matrix": {"scope": "FULL_TRAINING_INPUT"},
        "checks": [
            {"check_id": check_id, "status": "PASS"}
            for check_id in PARENT_CHECK_IDS
        ],
        "contract_binding": {
            "adapter": "quant_contract_v2",
            "execution_boundary": "PRODUCTION_CLI",
            "test_only_adapter": False,
        },
    }
    parent_content = hashlib.sha256(
        json.dumps(
            parent_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    parent_audit_id = f"pit-audit-v1-{parent_content[:32]}"
    write_json(
        root / "audit_manifest.json",
        {
            **parent_core,
            "audit_id": parent_audit_id,
            "content_sha256": parent_content,
        },
    )

    before_by_key = {record["raw_key"]: record for record in baseline_records}
    after_by_key = {record["raw_key"]: record for record in probe_records}
    entries = []
    scope_field = {
        "FUTURE_POISON": "available_time",
        "REVISION_REPLAY": "revision_known_time",
        "UNIVERSE_CANARY": "universe_known_time",
    }.get(probe)
    for raw_key in sorted(set(before_by_key) | set(after_by_key)):
        before = before_by_key.get(raw_key)
        after = after_by_key.get(raw_key)
        if before == after:
            continue
        scope_times = [
            record[scope_field]
            for record in (before, after)
            if (
                record is not None
                and scope_field is not None
                and scope_field in record
            )
        ]
        entries.append(
            {
                "raw_key": raw_key,
                "operation": (
                    "ADD" if before is None else "DELETE" if after is None else "UPDATE"
                ),
                "change_type": probe,
                "known_time": min(scope_times) if scope_times else "2025-01-04T00:00:00Z",
                "baseline_record_sha256": record_sha(before) if before else None,
                "probe_record_sha256": record_sha(after) if after else None,
            }
        )
    write_json(
        root / "ledger.json",
        {
            "ledger_version": "pit_perturbation_ledger_v1",
            "baseline_snapshot_sha256": sha(root / "raw-before.json"),
            "probe_snapshot_sha256": sha(root / "raw-after.json"),
            "entries": entries,
        },
    )

    file_names = {
        "baseline_raw_snapshot": "raw-before.json",
        "probe_raw_snapshot": "raw-after.json",
        "code_or_query": "feature.sql",
        "parameters": "parameters.json",
        "environment": "environment.json",
        "baseline_output": "baseline.csv",
        "probe_output": "probe.csv",
        "pit_audit_manifest": "audit_manifest.json",
        "perturbation_ledger": "ledger.json",
    }
    bindings = {name: sha(root / filename) for name, filename in file_names.items()}
    receipt = {
        "receipt_version": "pit_behavior_receipt_v1",
        "receipt_id": f"receipt-{case_id}",
        "request_id": case_id,
        "probe_type": probe,
        "baseline_run_id": f"{case_id}-before",
        "probe_run_id": f"{case_id}-after",
        "artifact_sha256": bindings,
        "parent_audit": {
            "audit_id": parent_audit_id,
            "content_sha256": parent_content,
            "status": "PASS",
        },
        "protection": {
            "comparison": "LE",
            "protected_through": "2025-01-03T00:00:00Z",
            "expected_key_count": 1,
            "expected_keys_sha256": expected_digest(baseline_rows),
        },
        "probe": {
            "mutation_type": probe,
            "mutation_time_min": (
                "2025-01-04T00:00:00Z"
                if probe in {"FUTURE_POISON", "REVISION_REPLAY"}
                else None
            ),
            "canary_sample_ids": ["canary-x"] if probe == "UNIVERSE_CANARY" else [],
        },
    }
    write_json(root / "receipt.json", receipt)
    artifacts = {
        name: {"path": filename, "sha256": bindings[name]}
        for name, filename in file_names.items()
    }
    artifacts["pipeline_receipt"] = {
        "path": "receipt.json",
        "sha256": sha(root / "receipt.json"),
    }
    request = {
        "request_version": "pit_behavior_request_v1",
        "request_id": case_id,
        "probe_type": probe,
        "artifacts": artifacts,
    }
    write_json(root / "request.json", request)
    return root / "request.json"


def rewrite_parent(
    request_path: Path,
    mutate: Any,
    *,
    recanonicalize: bool,
) -> None:
    """Mutate the parent while keeping every outer artifact hash honest."""
    root = request_path.parent
    parent_path = root / "audit_manifest.json"
    parent = json.loads(parent_path.read_text())
    mutate(parent)
    if recanonicalize:
        core = {
            key: value
            for key, value in parent.items()
            if key not in {"audit_id", "content_sha256", "report_sha256"}
        }
        content = hashlib.sha256(
            json.dumps(
                core,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        parent["content_sha256"] = content
        parent["audit_id"] = f"pit-audit-v1-{content[:32]}"
    write_json(parent_path, parent)

    receipt_path = root / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["artifact_sha256"]["pit_audit_manifest"] = sha(parent_path)
    receipt["parent_audit"] = {
        "audit_id": parent["audit_id"],
        "content_sha256": parent["content_sha256"],
        "status": parent["status"],
    }
    write_json(receipt_path, receipt)

    request = json.loads(request_path.read_text())
    request["artifacts"]["pit_audit_manifest"]["sha256"] = sha(parent_path)
    request["artifacts"]["pipeline_receipt"]["sha256"] = sha(receipt_path)
    write_json(request_path, request)


def run_case(request: Path, expected: str) -> dict[str, Any]:
    output = request.parent / "out"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(request), "--output-dir", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != EXIT[expected]:
        raise AssertionError(
            f"{request.parent.name}: exit {completed.returncode}, expected "
            f"{EXIT[expected]}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    manifest = json.loads((output / "behavior_manifest.json").read_text())
    report = (output / "behavior_report.md").read_bytes()
    assert manifest["status"] == expected
    assert manifest["certification_status"] == "NOVEL_CANDIDATE"
    assert len(manifest["checks"]) == 4
    assert {item["status"] for item in manifest["checks"]} <= set(EXIT)
    core = {
        key: value
        for key, value in manifest.items()
        if key not in {"behavior_id", "content_sha256", "report_sha256"}
    }
    content_sha = hashlib.sha256(
        json.dumps(
            core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    assert manifest["content_sha256"] == content_sha
    assert manifest["behavior_id"] == f"pit-behavior-{content_sha[:20]}"
    assert hashlib.sha256(report).hexdigest() == manifest["report_sha256"]
    return manifest


def main() -> int:
    cases = [
        ("prefix_pass", "PREFIX_REPLAY", False, "PASS"),
        ("prefix_drift", "PREFIX_REPLAY", True, "FAIL"),
        ("future_pass", "FUTURE_POISON", False, "PASS"),
        ("future_drift", "FUTURE_POISON", True, "FAIL"),
        ("revision_pass", "REVISION_REPLAY", False, "PASS"),
        ("revision_key_drop", "REVISION_REPLAY", True, "FAIL"),
        ("canary_pass", "UNIVERSE_CANARY", False, "PASS"),
        ("canary_leak", "UNIVERSE_CANARY", True, "FAIL"),
    ]
    passed = 0
    with tempfile.TemporaryDirectory(prefix="pit-behavior-tests-") as temporary:
        base = Path(temporary)
        for case_id, probe, negative, expected in cases:
            request = make_case(base / case_id, case_id, probe, negative)
            manifest = run_case(request, expected)
            if expected == "FAIL":
                assert manifest["checks"][-1]["status"] == "FAIL"
            passed += 1

        request = make_case(
            base / "future_scope_violation",
            "future_scope_violation",
            "FUTURE_POISON",
            out_of_scope=True,
        )
        manifest = run_case(request, "FAIL")
        assert manifest["checks"][1]["status"] == "FAIL"
        passed += 1

        request = make_case(
            base / "future_missing_scope",
            "future_missing_scope",
            "FUTURE_POISON",
            missing_scope=True,
        )
        manifest = run_case(request, "NEEDS_EVIDENCE")
        assert manifest["checks"][1]["status"] == "NEEDS_EVIDENCE"
        passed += 1

        request = make_case(
            base / "revision_scope_violation",
            "revision_scope_violation",
            "REVISION_REPLAY",
            out_of_scope=True,
        )
        manifest = run_case(request, "FAIL")
        assert manifest["checks"][1]["status"] == "FAIL"
        passed += 1

        request = make_case(
            base / "canary_scope_violation",
            "canary_scope_violation",
            "UNIVERSE_CANARY",
            out_of_scope=True,
        )
        manifest = run_case(request, "FAIL")
        assert manifest["checks"][1]["status"] == "FAIL"
        passed += 1

        request = make_case(base / "missing_ledger", "missing_ledger", "PREFIX_REPLAY")
        payload = json.loads(request.read_text())
        del payload["artifacts"]["perturbation_ledger"]
        write_json(request, payload)
        manifest = run_case(request, "NEEDS_EVIDENCE")
        assert manifest["checks"][1]["status"] == "NEEDS_EVIDENCE"
        passed += 1

        request = make_case(base / "missing_evidence", "missing_evidence", "PREFIX_REPLAY")
        payload = json.loads(request.read_text())
        del payload["artifacts"]["environment"]
        write_json(request, payload)
        manifest = run_case(request, "NEEDS_EVIDENCE")
        assert manifest["checks"][0]["status"] == "NEEDS_EVIDENCE"
        passed += 1

        parent_cases = (
            (
                "test_only_parent",
                lambda parent: parent.update(pit_qualification="TEST_ONLY"),
                True,
            ),
            (
                "synthetic_adapter_parent",
                lambda parent: parent["contract_binding"].update(
                    adapter="pit_contract_binding_v1",
                    execution_boundary="INTERNAL_TEST_ONLY",
                    test_only_adapter=True,
                ),
                True,
            ),
            (
                "tampered_parent_content",
                lambda parent: parent.update(unbound_mutation=True),
                False,
            ),
            (
                "incomplete_parent_check_inventory",
                lambda parent: parent["checks"].pop(),
                True,
            ),
        )
        for case_id, mutate, recanonicalize in parent_cases:
            request = make_case(
                base / case_id,
                case_id,
                "PREFIX_REPLAY",
            )
            rewrite_parent(
                request,
                mutate,
                recanonicalize=recanonicalize,
            )
            manifest = run_case(request, "FAIL")
            assert manifest["checks"][0]["status"] == "FAIL"
            passed += 1

    assert passed == EXPECTED_CASE_COUNT
    print(f"behavior tests: {passed}/{EXPECTED_CASE_COUNT} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
