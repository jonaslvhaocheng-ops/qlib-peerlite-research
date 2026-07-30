from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qlib_peerlite.governance.artifacts import canonical_json_bytes

from . import M7ContractError


@dataclass(frozen=True)
class PrerequisiteRule:
    name: str
    path: str
    required_status: str
    expected_schema: str | None = None


_EVIDENCE = "evidence/prerequisites/m7"
M7_PREREQUISITE_REGISTRY_V1 = (
    PrerequisiteRule("official_fee_receipt", f"{_EVIDENCE}/official_fee_receipt.json", "PASS"),
    PrerequisiteRule(
        "cost_spec",
        "contracts/immutable/m7_cost_spec_v1.json",
        "FROZEN",
        "qlib_peerlite_cost_spec_v1",
    ),
    PrerequisiteRule(
        "benchmark_source_certificate", f"{_EVIDENCE}/benchmark_source_certificate.json", "PASS"
    ),
    PrerequisiteRule(
        "benchmark_spec",
        "contracts/immutable/m7_benchmark_spec_v1.json",
        "FROZEN",
        "qlib_peerlite_benchmark_spec_v1",
    ),
    PrerequisiteRule("exchange_calendar", f"{_EVIDENCE}/exchange_calendar.json", "PASS"),
    PrerequisiteRule(
        "weekly_rebalance_mapper", f"{_EVIDENCE}/weekly_rebalance_mapper.json", "PASS"
    ),
    PrerequisiteRule("score_to_position_rule", f"{_EVIDENCE}/score_to_position_rule.json", "PASS"),
    PrerequisiteRule(
        "execution_unfilled_rule", f"{_EVIDENCE}/execution_unfilled_rule.json", "PASS"
    ),
    PrerequisiteRule("adv_capacity_rule", f"{_EVIDENCE}/adv_capacity_rule.json", "PASS"),
    PrerequisiteRule("cost_implementation", f"{_EVIDENCE}/cost_implementation.json", "PASS"),
    PrerequisiteRule(
        "portfolio_implementation", f"{_EVIDENCE}/portfolio_implementation.json", "PASS"
    ),
    PrerequisiteRule(
        "benchmark_implementation", f"{_EVIDENCE}/benchmark_implementation.json", "PASS"
    ),
    PrerequisiteRule("ir_implementation", f"{_EVIDENCE}/ir_implementation.json", "PASS"),
    PrerequisiteRule("m6_k16_outputs", f"{_EVIDENCE}/m6_k16_outputs.json", "PASS"),
    PrerequisiteRule("m6_reference_portfolio", f"{_EVIDENCE}/m6_reference_portfolio.json", "PASS"),
    PrerequisiteRule(
        "m7_market_state_product",
        f"{_EVIDENCE}/m7_market_state_product.json",
        "PASS",
    ),
    PrerequisiteRule("development_folds", f"{_EVIDENCE}/development_folds.json", "PASS"),
    PrerequisiteRule("final_oos_seal", f"{_EVIDENCE}/final_oos_seal.json", "PASS"),
)


@dataclass(frozen=True)
class M7ScreeningPrerequisiteBundleV1:
    artifact_sha256: tuple[tuple[str, str], ...]
    bundle_sha256: str
    claim_ceiling: str = "PRECHECK_ONLY_NOT_FIT_AUTHORITY"


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise M7ContractError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _strict_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise M7ContractError(f"{path} contains a forbidden UTF-8 BOM")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                M7ContractError(f"non-finite JSON number: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M7ContractError(f"{path} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise M7ContractError(f"{path} must contain a JSON object")
    return value


def validate_screening_prerequisites(
    repo_root: str | Path,
) -> M7ScreeningPrerequisiteBundleV1:
    root = Path(repo_root).resolve()
    failures: list[str] = []
    hashes: list[tuple[str, str]] = []
    for rule in M7_PREREQUISITE_REGISTRY_V1:
        path = root / rule.path
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            failures.append(f"{rule.name}: missing")
            continue
        if not resolved.is_relative_to(root) or path.is_symlink() or not resolved.is_file():
            failures.append(f"{rule.name}: unsafe path")
            continue
        try:
            payload = _strict_json(resolved)
        except M7ContractError as exc:
            failures.append(f"{rule.name}: {exc}")
            continue
        if (
            rule.expected_schema is not None
            and payload.get("schema_version") != rule.expected_schema
        ):
            failures.append(f"{rule.name}: schema mismatch")
        if payload.get("status") != rule.required_status:
            failures.append(
                f"{rule.name}: status={payload.get('status')!r}, expected={rule.required_status!r}"
            )
        semantic_version = payload.get("semantic_version", payload.get("schema_version"))
        if not isinstance(semantic_version, str) or not semantic_version:
            failures.append(f"{rule.name}: semantic version missing")
        hashes.append((rule.name, hashlib.sha256(resolved.read_bytes()).hexdigest()))
    if failures:
        raise M7ContractError("M7 prerequisites are not satisfied: " + "; ".join(failures))
    ordered = tuple(hashes)
    bundle_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "schema_version": "qlib_peerlite_m7_prerequisite_bundle_v1",
                "artifacts": [{"name": name, "sha256": digest} for name, digest in ordered],
            }
        )
    ).hexdigest()
    return M7ScreeningPrerequisiteBundleV1(ordered, bundle_hash)


__all__ = [
    "M7_PREREQUISITE_REGISTRY_V1",
    "M7ScreeningPrerequisiteBundleV1",
    "PrerequisiteRule",
    "validate_screening_prerequisites",
]
