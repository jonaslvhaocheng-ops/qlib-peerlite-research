from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from qlib_peerlite.governance.artifacts import sha256_bytes

from .errors import ProductionError

_FORBIDDEN_KEY_PARTS = (
    "bro" + "ker",
    "account",
    "creden" + "tial",
    "secret",
    "password",
    "token",
    "endpoint",
)


@dataclass(frozen=True)
class FileSnapshot:
    payload: bytes
    sha256: str


def capture_regular_file(
    path: str | Path,
    *,
    code: str,
    max_bytes: int = 8 * 1024 * 1024,
) -> FileSnapshot:
    source = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise ProductionError(code, "input must be an accessible regular file") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
            raise ProductionError(code, "input must be a bounded regular file")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > max_bytes:
                raise ProductionError(code, "input exceeds byte limit")
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    return FileSnapshot(payload=payload, sha256=sha256_bytes(payload))


class ShadowPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["qlib_peerlite_shadow_policy_v1"]
    capability: Literal["SHADOW_ONLY"]
    input_track: Literal["SYNTHETIC"]
    execution_mode: Literal["paper"]
    timezone: Literal["Asia/Shanghai"]
    session_close: str
    run_after: str
    rebalance_weekday: int = Field(ge=0, le=4)
    max_signal_age_minutes: int = Field(gt=0)
    future_skew_seconds: int = Field(ge=0)
    max_input_bytes: int = Field(gt=0)
    max_rows: int = Field(gt=0)
    max_instruments: int = Field(gt=0)
    top_fraction: float = Field(gt=0, le=1)
    max_name_weight: float = Field(gt=0, le=1)
    max_paper_intents: int = Field(gt=0)
    reservation_timeout_seconds: int = Field(gt=0)
    m9_gate_path: str
    m9_gate_sha256: str
    calendar_path: str
    calendar_sha256: str
    permitted_model_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_policy(self) -> ShadowPolicy:
        for value, name in (
            (self.session_close, "session_close"),
            (self.run_after, "run_after"),
        ):
            _parse_hhmm(value, name)
        for digest, name in (
            (self.m9_gate_sha256, "m9_gate_sha256"),
            (self.calendar_sha256, "calendar_sha256"),
        ):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if len(set(self.permitted_model_ids)) != len(self.permitted_model_ids):
            raise ValueError("permitted_model_ids must be unique")
        if any(not value.strip() for value in self.permitted_model_ids):
            raise ValueError("permitted_model_ids must be non-empty")
        return self


def _parse_hhmm(value: str, name: str) -> tuple[int, int]:
    pieces = value.split(":")
    if len(pieces) != 2 or not all(piece.isdigit() for piece in pieces):
        raise ValueError(f"{name} must use HH:MM")
    hour, minute = (int(piece) for piece in pieces)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"{name} must use HH:MM")
    return hour, minute


def _reject_unsafe_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _FORBIDDEN_KEY_PARTS):
                raise ProductionError(
                    "UNSAFE_POLICY_KEY",
                    "shadow policy contains a forbidden operational key",
                    path=f"{path}.{key}",
                )
            _reject_unsafe_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_unsafe_keys(child, f"{path}[{index}]")


def _read_mapping_bytes(payload_bytes: bytes, *, code: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(payload_bytes.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ProductionError(code, "input cannot be parsed") from exc
    if not isinstance(payload, dict):
        raise ProductionError(code, "input must contain an object")
    return payload


def load_shadow_policy_snapshot(path: str | Path) -> tuple[ShadowPolicy, FileSnapshot]:
    snapshot = capture_regular_file(path, code="INVALID_POLICY")
    payload = _read_mapping_bytes(snapshot.payload, code="INVALID_POLICY")
    _reject_unsafe_keys(payload)
    try:
        return ShadowPolicy.model_validate(payload), snapshot
    except ValidationError as exc:
        raise ProductionError("INVALID_POLICY", "shadow policy validation failed") from exc


def load_shadow_policy(path: str | Path) -> ShadowPolicy:
    return load_shadow_policy_snapshot(path)[0]


def _resolve_project_path(project_root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else project_root / candidate


def authorize_shadow(
    policy: ShadowPolicy,
    project_root: str | Path,
    *,
    gate_snapshot: FileSnapshot | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    gate_path = _resolve_project_path(root, policy.m9_gate_path)
    snapshot = gate_snapshot or capture_regular_file(gate_path, code="M9_GATE_MISSING")
    if snapshot.sha256 != policy.m9_gate_sha256:
        raise ProductionError("M9_GATE_HASH_MISMATCH", "configured M9 gate hash differs")
    try:
        gate = json.loads(snapshot.payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionError("M9_GATE_INVALID", "configured M9 gate cannot be parsed") from exc
    if not isinstance(gate, dict):
        raise ProductionError("M9_GATE_INVALID", "configured M9 gate must be an object")
    expected = (
        gate.get("gate_id") == "M9-STEP-NINE-TERMINAL-CLOSURE"
        and gate.get("status") == "HOLD"
        and gate.get("research_decision") == "HOLD_REAUTHORIZATION_CONTRACT_INVALID"
        and gate.get("promotion_authorized") is False
        and gate.get("production_authorized") is False
        and gate.get("final_oos_opened") is False
        and gate.get("final_oos_access_count") == 0
    )
    if not expected:
        raise ProductionError(
            "M9_NOT_SHADOW_AUTHORIZED",
            "M9 evidence does not authorize the bounded shadow capability",
        )
    return {
        "schema_version": "qlib_peerlite_shadow_authorization_v1",
        "capability": "SHADOW_ONLY",
        "production_authorized": False,
        "active_research_model": gate.get("active_candidate"),
        "m9_gate_sha256": policy.m9_gate_sha256,
        "research_decision": gate["research_decision"],
    }
