"""Historical M6 evidence-chain verification after later ledger append-only use.

M6's original gate remains byte-for-byte immutable.  This module does not
rewrite it or reinterpret its close-time ledger hash as a current-file hash;
instead it verifies the frozen M6 states as exact prefixes of the live ledger.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import canonical_json_bytes, sha256_file
from .trial_ledger import TrialLedgerError, verify_ledger_prefix


class M6ArchiveError(RuntimeError):
    """Raised when the closed M6 evidence chain cannot be verified historically."""


@dataclass(frozen=True)
class M6ArchiveSummary:
    status: str
    pre_run_ledger_prefix_bytes: int
    close_ledger_prefix_bytes: int
    ledger_candidate_evaluations: int
    ledger_model_fits: int
    m6_journal_candidate_starts: int
    m6_journal_fit_starts: int
    pre_run_code_commit: str
    verifier_fix_commit: str

    @property
    def ledger_prefix_bytes(self) -> int:
        """Compatibility alias for the M6 close-time prefix length."""

        return self.close_ledger_prefix_bytes


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M6ArchiveError(f"cannot read JSON evidence: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise M6ArchiveError(f"JSON evidence root is not an object: {path}")
    return value


def _content_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _require_content_hash(value: dict[str, Any], *, name: str) -> None:
    if value.get("content_sha256") != _content_hash(value):
        raise M6ArchiveError(f"M6 historical receipt content hash mismatch: {name}")


def _relative_path(path: str, expected: str) -> str:
    if path != expected:
        raise M6ArchiveError(f"unexpected historical evidence path: {path!r}")
    return path


def _git_blob_sha256(project_root: Path, revision: str, relative_path: str) -> str:
    try:
        blob = subprocess.check_output(
            ["git", "-C", str(project_root), "show", f"{revision}:{relative_path}"],
            stderr=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise M6ArchiveError(f"cannot read frozen Git blob {revision}:{relative_path}") from exc
    return hashlib.sha256(blob).hexdigest()


def _read_jsonl_prefix(path: Path, *, prefix_bytes: int) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if prefix_bytes > len(raw):
        raise M6ArchiveError("M6 ledger prefix is longer than the live ledger")
    prefix = raw[:prefix_bytes]
    if prefix and not prefix.endswith(b"\n"):
        raise M6ArchiveError("M6 historical ledger prefix does not end at a JSONL boundary")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(prefix.splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise M6ArchiveError(
                f"invalid M6 historical ledger event at line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise M6ArchiveError(f"M6 historical ledger event {line_number} is not an object")
        events.append(value)
    return events


def _verify_static_evidence(
    root: Path,
    *,
    evidence: dict[str, Any],
) -> dict[str, Path]:
    expected_paths = {
        "execution_spec": "contracts/immutable/m6_peerlite_execution_spec_v1.json",
        "mechanics": "evidence/peerlite/mechanics_20260728_v2/mechanics_receipt.json",
        "run_manifest": "evidence/m6/runs/m6_peerlite_20260728_v1/run_manifest.json",
        "verification": (
            "evidence/m6/verifications/m6_peerlite_20260728_v1/verification_receipt.json"
        ),
        "run_journal": "evidence/m6/runs/m6_peerlite_20260728_v1/ledger_events.jsonl",
        "cumulative_trial_ledger": "contracts/trial_ledger.jsonl",
    }
    artifacts: dict[str, Path] = {}
    for name, expected_path in expected_paths.items():
        item = evidence.get(name)
        if not isinstance(item, dict):
            raise M6ArchiveError(f"M6 gate evidence is missing: {name}")
        relative_path = _relative_path(str(item.get("path", "")), expected_path)
        artifact = root / relative_path
        if not artifact.is_file():
            raise M6ArchiveError(f"M6 historical evidence is missing: {relative_path}")
        artifacts[name] = artifact
        if name == "cumulative_trial_ledger":
            continue
        if item.get("sha256") != sha256_file(artifact):
            raise M6ArchiveError(f"M6 historical evidence hash mismatch: {name}")
        if "content_sha256" in item:
            receipt = _load_json(artifact)
            if receipt.get("content_sha256") != item["content_sha256"]:
                raise M6ArchiveError(f"M6 historical receipt binding mismatch: {name}")
            _require_content_hash(receipt, name=name)
    return artifacts


def _verify_pre_run_budget(
    root: Path,
    *,
    ledger_path: Path,
    execution_spec: dict[str, Any],
) -> int:
    budget_path = root / "contracts/immutable/m6_trial_budget_start.json"
    budget = _load_json(budget_path)
    _require_content_hash(budget, name="m6_trial_budget_start")
    budget_binding = execution_spec.get("bindings", {}).get("trial_budget_start")
    if not isinstance(budget_binding, dict):
        raise M6ArchiveError("M6 execution spec does not bind its pre-run trial budget")
    if (
        budget_binding.get("path") != "contracts/immutable/m6_trial_budget_start.json"
        or budget_binding.get("sha256") != sha256_file(budget_path)
        or budget_binding.get("content_sha256") != budget.get("content_sha256")
    ):
        raise M6ArchiveError("M6 pre-run trial-budget binding mismatch")
    trial_ledger = budget.get("trial_ledger")
    consumed = budget.get("consumed_before_m6")
    if not isinstance(trial_ledger, dict) or not isinstance(consumed, dict):
        raise M6ArchiveError("M6 pre-run budget is malformed")
    if trial_ledger.get("path") != "contracts/trial_ledger.jsonl":
        raise M6ArchiveError("M6 pre-run budget targets an unexpected ledger")
    try:
        prefix = verify_ledger_prefix(
            ledger_path,
            expected_prefix_sha256=str(trial_ledger.get("sha256_at_freeze", "")),
            expected_counts={
                "candidate_evaluations": int(consumed.get("candidate_evaluations")),
                "model_fits": int(consumed.get("model_fits")),
            },
        )
    except (TrialLedgerError, TypeError, ValueError) as exc:
        raise M6ArchiveError(f"M6 pre-run ledger prefix mismatch: {exc}") from exc
    return prefix.prefix_bytes


def _read_m6_journal(path: Path, *, expected_pre_terminal_hash: str) -> tuple[set[str], set[str]]:
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    if not lines or not raw.endswith(b"\n"):
        raise M6ArchiveError("M6 run journal is not newline-terminated JSONL")
    try:
        events = [json.loads(line) for line in lines]
    except json.JSONDecodeError as exc:
        raise M6ArchiveError("M6 run journal contains invalid JSON") from exc
    if not all(isinstance(item, dict) for item in events):
        raise M6ArchiveError("M6 run journal contains a non-object event")
    counts = Counter(item.get("event") for item in events)
    expected = Counter(
        {
            "M6_RUN_STARTED": 1,
            "CANDIDATE_EVALUATION_STARTED": 2,
            "MODEL_FIT_STARTED": 15,
            "MODEL_FIT_COMPLETED": 15,
            "CANDIDATE_EVALUATION_COMPLETED": 2,
            "M6_RUN_COMPLETED": 1,
        }
    )
    if counts != expected:
        raise M6ArchiveError(f"unexpected M6 run journal event counts: {dict(counts)}")
    if events[-1].get("event") != "M6_RUN_COMPLETED":
        raise M6ArchiveError("M6 run journal terminal event is not last")
    if hashlib.sha256(b"".join(lines[:-1])).hexdigest() != expected_pre_terminal_hash:
        raise M6ArchiveError("M6 run-manifest pre-terminal journal chain mismatch")
    candidates = {
        _require_m6_id(item.get("evaluation_id"), name="M6 candidate evaluation_id")
        for item in events
        if item.get("event") == "CANDIDATE_EVALUATION_STARTED"
    }
    fits = {
        _require_m6_id(item.get("fit_id"), name="M6 fit_id")
        for item in events
        if item.get("event") == "MODEL_FIT_STARTED"
    }
    if len(candidates) != 2 or len(fits) != 15:
        raise M6ArchiveError("M6 journal start identifiers are not unique")
    return candidates, fits


def _require_m6_id(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("m6_peerlite_20260728_v1:"):
        raise M6ArchiveError(f"{name} is not in the frozen M6 run namespace")
    return value


def _verify_journal_to_ledger_mapping(
    ledger_events: list[dict[str, Any]],
    *,
    journal_candidates: set[str],
    journal_fits: set[str],
) -> None:
    retained_candidates = {
        event.get("evaluation_id")
        for event in ledger_events
        if event.get("counts_as_candidate_evaluation") is True
        and isinstance(event.get("evaluation_id"), str)
        and event["evaluation_id"].startswith("m6_peerlite_20260728_v1:")
    }
    retained_fits = {
        event.get("fit_id")
        for event in ledger_events
        if event.get("counts_as_model_fit") is True
        and isinstance(event.get("fit_id"), str)
        and event["fit_id"].startswith("m6_peerlite_20260728_v1:")
    }
    if retained_candidates != journal_candidates:
        raise M6ArchiveError("M6 candidate journal starts do not exactly match close ledger IDs")
    if retained_fits != journal_fits:
        raise M6ArchiveError("M6 fit journal starts do not exactly match close ledger IDs")


def _verify_frozen_code(
    root: Path,
    *,
    gate_evidence: dict[str, Any],
    execution_spec: dict[str, Any],
    verification_receipt: dict[str, Any],
) -> tuple[str, str]:
    revision = gate_evidence.get("pre_run_code_commit")
    if not isinstance(revision, str) or not revision:
        raise M6ArchiveError("M6 pre-run code commit is missing")
    bindings = execution_spec.get("code_binding", {}).get("files")
    if not isinstance(bindings, dict) or not bindings:
        raise M6ArchiveError("M6 code binding is missing")
    for relative_path, expected_sha256 in bindings.items():
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise M6ArchiveError("M6 code binding entry is malformed")
        if _git_blob_sha256(root, revision, relative_path) != expected_sha256:
            raise M6ArchiveError(f"M6 frozen Git code hash mismatch: {relative_path}")

    verifier_commit = gate_evidence.get("verifier_fix_commit")
    verifier = verification_receipt.get("verifier")
    if (
        not isinstance(verifier_commit, str)
        or not verifier_commit
        or not isinstance(verifier, dict)
    ):
        raise M6ArchiveError("M6 historical verifier binding is missing")
    verifier_path = verifier.get("path")
    verifier_hash = verifier.get("sha256")
    if not isinstance(verifier_path, str) or not isinstance(verifier_hash, str):
        raise M6ArchiveError("M6 historical verifier binding is malformed")
    if _git_blob_sha256(root, verifier_commit, verifier_path) != verifier_hash:
        raise M6ArchiveError("M6 frozen verifier Git code hash mismatch")
    return revision, verifier_commit


def verify_archived_m6_evidence(
    project_root: str | Path,
    *,
    gate_path: str | Path | None = None,
) -> M6ArchiveSummary:
    """Verify M6 after later ledger appends without rewriting historical evidence."""

    root = Path(project_root).resolve()
    gate_file = (
        root / "evidence/gates/M6_peerlite_gate.json"
        if gate_path is None
        else Path(gate_path).resolve()
    )
    gate = _load_json(gate_file)
    if gate.get("status") != "PASS" or gate.get("passed") is not True:
        raise M6ArchiveError("M6 gate is not a historical PASS")
    _require_content_hash(gate, name="M6 gate")
    evidence = gate.get("evidence")
    if not isinstance(evidence, dict):
        raise M6ArchiveError("M6 gate evidence is missing")
    artifacts = _verify_static_evidence(root, evidence=evidence)

    execution_spec = _load_json(artifacts["execution_spec"])
    if execution_spec.get("content_sha256") != evidence["execution_spec"].get("content_sha256"):
        raise M6ArchiveError("M6 execution spec content hash mismatch")
    _require_content_hash(execution_spec, name="M6 execution spec")

    ledger_item = evidence["cumulative_trial_ledger"]
    try:
        close_prefix = verify_ledger_prefix(
            artifacts["cumulative_trial_ledger"],
            expected_prefix_sha256=str(ledger_item.get("sha256", "")),
            expected_counts={"candidate_evaluations": 6, "model_fits": 44},
        )
    except TrialLedgerError as exc:
        raise M6ArchiveError(f"M6 close-time ledger prefix mismatch: {exc}") from exc
    pre_run_prefix_bytes = _verify_pre_run_budget(
        root,
        ledger_path=artifacts["cumulative_trial_ledger"],
        execution_spec=execution_spec,
    )

    run_manifest = _load_json(artifacts["run_manifest"])
    _require_content_hash(run_manifest, name="M6 run manifest")
    manifest_journal = run_manifest.get("ledger_events")
    if not isinstance(manifest_journal, dict):
        raise M6ArchiveError("M6 run manifest does not bind its run journal")
    expected_pre_terminal_hash = manifest_journal.get("sha256_before_terminal_event")
    if not isinstance(expected_pre_terminal_hash, str):
        raise M6ArchiveError("M6 run manifest pre-terminal journal hash is missing")
    journal_candidates, journal_fits = _read_m6_journal(
        artifacts["run_journal"],
        expected_pre_terminal_hash=expected_pre_terminal_hash,
    )
    close_events = _read_jsonl_prefix(
        artifacts["cumulative_trial_ledger"],
        prefix_bytes=close_prefix.prefix_bytes,
    )
    _verify_journal_to_ledger_mapping(
        close_events,
        journal_candidates=journal_candidates,
        journal_fits=journal_fits,
    )

    verification = _load_json(artifacts["verification"])
    _require_content_hash(verification, name="M6 verification receipt")
    pre_run_commit, verifier_commit = _verify_frozen_code(
        root,
        gate_evidence=evidence,
        execution_spec=execution_spec,
        verification_receipt=verification,
    )
    return M6ArchiveSummary(
        status="PASS",
        pre_run_ledger_prefix_bytes=pre_run_prefix_bytes,
        close_ledger_prefix_bytes=close_prefix.prefix_bytes,
        ledger_candidate_evaluations=close_prefix.candidate_evaluations,
        ledger_model_fits=close_prefix.model_fits,
        m6_journal_candidate_starts=len(journal_candidates),
        m6_journal_fit_starts=len(journal_fits),
        pre_run_code_commit=pre_run_commit,
        verifier_fix_commit=verifier_commit,
    )
