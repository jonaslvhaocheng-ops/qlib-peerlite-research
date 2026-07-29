"""Durable, append-only accounting for preregistered empirical trials.

The server is the sole writer of the authoritative ledger.  A run writes a
durable local ``*_STARTED`` event first, then imports that event under the
ledger lock before it is permitted to call ``model.fit``.  Start events count
even if a process later crashes, so a retry cannot silently reclaim budget.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import stat
import tempfile
import unicodedata
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .artifacts import canonical_json_bytes, sha256_file


class TrialLedgerError(RuntimeError):
    """Raised when an append-only trial-ledger invariant is violated."""


_HEX_DIGEST_LENGTH = 64
_JOURNAL_SCHEMA = "qlib_peerlite_run_journal_event_v2"
_LEDGER_SCHEMA = "qlib_peerlite_trial_ledger_event_v2"
_M7_INITIAL_SCREEN_FAMILY = "QLIB_PEERLITE_M7_INITIAL_SCREEN_V1"
_COUNTED_EVENTS = {
    "CANDIDATE_EVALUATION_STARTED": "candidate",
    "MODEL_FIT_STARTED": "fit",
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _HEX_DIGEST_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TrialLedgerError(f"{name} must be a lowercase SHA256 hex digest")
    return value


def _require_nonempty_string(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TrialLedgerError(f"{name} must be a non-empty string")
    return value


def _require_integer(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise TrialLedgerError(f"{name} must be an integer >= {minimum}")
    return value


def _normalize_json_value(
    value: object,
    *,
    path: str,
    active_containers: set[int],
) -> Any:
    """Return an owned NFC-normalized JSON value or fail before side effects."""

    if value is None or type(value) in {bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise TypeError(f"{path} must contain only finite JSON numbers")
        return value
    if type(value) is str:
        return unicodedata.normalize("NFC", value)
    if type(value) is list:
        identity = id(value)
        if identity in active_containers:
            raise TypeError(f"{path} contains a JSON container cycle")
        active_containers.add(identity)
        try:
            return [
                _normalize_json_value(
                    item,
                    path=f"{path}[{index}]",
                    active_containers=active_containers,
                )
                for index, item in enumerate(value)
            ]
        finally:
            active_containers.remove(identity)
    if type(value) is dict:
        identity = id(value)
        if identity in active_containers:
            raise TypeError(f"{path} contains a JSON container cycle")
        active_containers.add(identity)
        normalized: dict[str, Any] = {}
        try:
            for key, item in value.items():
                if type(key) is not str:
                    raise TypeError(f"{path} JSON object keys must be strings")
                normalized_key = unicodedata.normalize("NFC", key)
                if normalized_key in normalized:
                    raise TypeError(
                        f"{path} contains an NFC-normalized JSON key collision"
                    )
                normalized[normalized_key] = _normalize_json_value(
                    item,
                    path=f"{path}.{normalized_key}",
                    active_containers=active_containers,
                )
        finally:
            active_containers.remove(identity)
        return normalized
    raise TypeError(f"{path} contains unsupported JSON value type {type(value).__name__}")


def _freeze_json_value(value: Any) -> Any:
    """Deep-freeze an already validated plain JSON value."""

    if type(value) is dict:
        return MappingProxyType(
            {key: _freeze_json_value(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze_json_value(item) for item in value)
    return value


@dataclass(frozen=True)
class LedgerPrefixBinding:
    """A historical ledger state that must remain a byte-exact prefix."""

    sha256: str
    candidate_evaluations: int
    model_fits: int
    prefix_bytes: int | None = None

    def __post_init__(self) -> None:
        _require_sha256(self.sha256, name="ledger prefix SHA256")
        _require_integer(
            self.candidate_evaluations,
            name="ledger prefix candidate_evaluations",
        )
        _require_integer(self.model_fits, name="ledger prefix model_fits")
        if self.prefix_bytes is not None:
            _require_integer(self.prefix_bytes, name="ledger prefix bytes")

    @classmethod
    def empty(cls) -> LedgerPrefixBinding:
        return cls(
            sha256=_sha256(b""),
            candidate_evaluations=0,
            model_fits=0,
            prefix_bytes=0,
        )


@dataclass(frozen=True)
class TrialLimits:
    """Immutable total caps, checked under the authoritative ledger lock."""

    candidate_evaluations: int
    model_fits: int

    def __post_init__(self) -> None:
        _require_integer(self.candidate_evaluations, name="candidate-evaluation limit")
        _require_integer(self.model_fits, name="model-fit limit")


@dataclass(frozen=True, init=False)
class RunIntent:
    """Immutable identity that binds one server journal to one M7 execution spec."""

    run_id: str
    family_id: str
    execution_spec_content_sha256: str
    _budget_limit_binding: Mapping[str, Any] | None = field(
        init=False,
        default=None,
        repr=False,
    )
    _market_state_authority_binding: Mapping[str, Any] | None = field(
        init=False,
        default=None,
        repr=False,
    )
    _budget_limit_binding_bytes: bytes | None = field(
        init=False,
        default=None,
        repr=False,
        compare=False,
    )
    _market_state_authority_binding_bytes: bytes | None = field(
        init=False,
        default=None,
        repr=False,
        compare=False,
    )
    _content_sha256: str = field(init=False, repr=False, compare=False)

    def __init__(
        self,
        run_id: str,
        family_id: str,
        execution_spec_content_sha256: str,
        budget_limit_binding: dict[str, Any] | None = None,
        market_state_authority_binding: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "family_id", family_id)
        object.__setattr__(
            self,
            "execution_spec_content_sha256",
            execution_spec_content_sha256,
        )
        object.__setattr__(self, "_budget_limit_binding", None)
        object.__setattr__(self, "_market_state_authority_binding", None)
        object.__setattr__(self, "_budget_limit_binding_bytes", None)
        object.__setattr__(self, "_market_state_authority_binding_bytes", None)

        _require_nonempty_string(self.run_id, name="run_id")
        _require_nonempty_string(self.family_id, name="family_id")
        _require_sha256(
            self.execution_spec_content_sha256,
            name="execution_spec_content_sha256",
        )
        if self.family_id == _M7_INITIAL_SCREEN_FAMILY and (
            budget_limit_binding is None
            or market_state_authority_binding is None
        ):
            raise TypeError(
                "M7 initial-screen RunIntent requires budget_limit_binding "
                "and market_state_authority_binding"
            )
        if (budget_limit_binding is None) is not (
            market_state_authority_binding is None
        ):
            raise TypeError(
                "budget_limit_binding and market_state_authority_binding "
                "must be supplied together"
            )
        if budget_limit_binding is None:
            object.__setattr__(
                self,
                "_content_sha256",
                _sha256(
                    canonical_json_bytes(
                        {
                            "schema_version": "qlib_peerlite_run_intent_v1",
                            "run_id": self.run_id,
                            "family_id": self.family_id,
                            "execution_spec_content_sha256": (
                                self.execution_spec_content_sha256
                            ),
                        }
                    )
                ),
            )
            return

        if type(budget_limit_binding) is not dict:
            raise TypeError("budget_limit_binding must be a dictionary")
        if type(market_state_authority_binding) is not dict:
            raise TypeError("market_state_authority_binding must be a dictionary")

        normalized_budget = _normalize_json_value(
            budget_limit_binding,
            path="budget_limit_binding",
            active_containers=set(),
        )
        normalized_market_state = _normalize_json_value(
            market_state_authority_binding,
            path="market_state_authority_binding",
            active_containers=set(),
        )
        budget_bytes = canonical_json_bytes(normalized_budget)
        market_state_bytes = canonical_json_bytes(normalized_market_state)
        content_sha256 = _sha256(
            canonical_json_bytes(
                {
                    "schema_version": "qlib_peerlite_run_intent_v2",
                    "run_id": self.run_id,
                    "family_id": self.family_id,
                    "execution_spec_content_sha256": (
                        self.execution_spec_content_sha256
                    ),
                    "budget_limit_binding": normalized_budget,
                    "market_state_authority_binding": normalized_market_state,
                }
            )
        )
        object.__setattr__(
            self,
            "_budget_limit_binding",
            _freeze_json_value(normalized_budget),
        )
        object.__setattr__(
            self,
            "_market_state_authority_binding",
            _freeze_json_value(normalized_market_state),
        )
        object.__setattr__(self, "_budget_limit_binding_bytes", budget_bytes)
        object.__setattr__(
            self,
            "_market_state_authority_binding_bytes",
            market_state_bytes,
        )
        object.__setattr__(self, "_content_sha256", content_sha256)

    @property
    def budget_limit_binding(self) -> Mapping[str, Any] | None:
        return self._budget_limit_binding

    @property
    def market_state_authority_binding(self) -> Mapping[str, Any] | None:
        return self._market_state_authority_binding

    @property
    def content_sha256(self) -> str:
        return self._content_sha256


@dataclass(frozen=True)
class LedgerPrefixSummary:
    prefix_bytes: int
    prefix_sha256: str
    candidate_evaluations: int
    model_fits: int


@dataclass(frozen=True)
class ReconciliationResult:
    appended_events: int
    candidate_evaluations_before: int
    model_fits_before: int
    candidate_evaluations_after: int
    model_fits_after: int
    ledger_sha256_before: str
    ledger_sha256_after: str


def _read_jsonl_bytes(raw: bytes, *, location: Path | str) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise TrialLedgerError(f"invalid JSONL (not newline terminated): {location}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(keepends=True), 1):
        if not line.strip():
            raise TrialLedgerError(f"blank JSONL line: {location}:{line_number}")
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TrialLedgerError(f"invalid JSONL event: {location}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise TrialLedgerError(f"JSONL event is not an object: {location}:{line_number}")
        events.append(value)
    return events


def _read_jsonl(path: Path, *, allow_missing: bool = False) -> list[dict[str, Any]]:
    if not path.is_file():
        if allow_missing:
            return []
        raise TrialLedgerError(f"JSONL file is missing: {path}")
    return _read_jsonl_bytes(path.read_bytes(), location=path)


def _count(events: list[dict[str, Any]]) -> tuple[int, int]:
    return (
        sum(event.get("counts_as_candidate_evaluation") is True for event in events),
        sum(event.get("counts_as_model_fit") is True for event in events),
    )


def _verify_ledger_prefix_bytes(
    raw: bytes,
    *,
    expected: LedgerPrefixBinding,
    location: Path | str,
) -> LedgerPrefixSummary:
    """Find and validate ``expected`` at a JSONL line boundary in ``raw``."""

    _read_jsonl_bytes(raw, location=location)
    digest = hashlib.sha256()
    prefix_bytes: int | None = 0 if digest.hexdigest() == expected.sha256 else None
    consumed = 0
    for line in raw.splitlines(keepends=True):
        digest.update(line)
        consumed += len(line)
        if digest.hexdigest() == expected.sha256:
            prefix_bytes = consumed
            break
    if prefix_bytes is None:
        raise TrialLedgerError("historical ledger prefix hash is not present at a line boundary")
    if expected.prefix_bytes is not None and prefix_bytes != expected.prefix_bytes:
        raise TrialLedgerError(
            "historical ledger prefix byte length mismatch: "
            f"expected {expected.prefix_bytes}, got {prefix_bytes}"
        )
    prefix_events = _read_jsonl_bytes(raw[:prefix_bytes], location=location)
    candidate_evaluations, model_fits = _count(prefix_events)
    if candidate_evaluations != expected.candidate_evaluations or model_fits != expected.model_fits:
        raise TrialLedgerError(
            "historical ledger counts mismatch: expected "
            f"{{'candidate_evaluations': {expected.candidate_evaluations}, "
            f"'model_fits': {expected.model_fits}}}, got "
            f"{{'candidate_evaluations': {candidate_evaluations}, 'model_fits': {model_fits}}}"
        )
    return LedgerPrefixSummary(
        prefix_bytes=prefix_bytes,
        prefix_sha256=expected.sha256,
        candidate_evaluations=candidate_evaluations,
        model_fits=model_fits,
    )


def verify_ledger_prefix(
    ledger_path: str | Path,
    *,
    expected_prefix_sha256: str,
    expected_counts: dict[str, int],
    expected_prefix_bytes: int | None = None,
) -> LedgerPrefixSummary:
    """Verify a historical ledger state without requiring later appends to vanish."""

    if set(expected_counts) != {"candidate_evaluations", "model_fits"}:
        raise TrialLedgerError("expected ledger counts must name candidate_evaluations/model_fits")
    binding = LedgerPrefixBinding(
        sha256=expected_prefix_sha256,
        candidate_evaluations=expected_counts["candidate_evaluations"],
        model_fits=expected_counts["model_fits"],
        prefix_bytes=expected_prefix_bytes,
    )
    ledger = Path(ledger_path)
    raw = ledger.read_bytes() if ledger.is_file() else b""
    return _verify_ledger_prefix_bytes(raw, expected=binding, location=ledger)


def _event_payload_without_hash(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key != "event_sha256"}


def _journal_relative_path(journal: Path, journal_root: Path) -> str:
    try:
        relative = journal.relative_to(journal_root)
    except ValueError as exc:
        raise TrialLedgerError("journal must be located under journal_root") from exc
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise TrialLedgerError("journal relative path is invalid")
    return relative.as_posix()


def _validate_journal_event(
    event: dict[str, Any],
    *,
    run_intent: RunIntent,
    journal_relpath: str,
) -> dict[str, Any]:
    """Validate and canonically retain one counted v2 journal start event."""

    event_type = event.get("event")
    kind = _COUNTED_EVENTS.get(event_type)
    if kind is None:
        raise TrialLedgerError(f"unsupported counted source event: {event_type!r}")
    allowed = {
        "schema_version",
        "run_id",
        "event_seq",
        "source_event_id",
        "run_intent_sha256",
        "event",
        "timestamp",
        "family_id",
        "execution_spec_content_sha256",
        "evaluation_id",
        "model_id",
        "seed",
        "counts_as_candidate_evaluation",
        "counts_as_model_fit",
        "event_sha256",
        "purpose",
    }
    if kind == "fit":
        allowed.update({"fit_id", "fold_id"})
    unexpected = set(event).difference(allowed)
    if unexpected:
        raise TrialLedgerError(f"journal event has forbidden fields: {sorted(unexpected)}")
    if event.get("schema_version") != _JOURNAL_SCHEMA:
        raise TrialLedgerError("journal event schema_version is not v2")
    if event.get("run_id") != run_intent.run_id:
        raise TrialLedgerError("journal event run_id does not match run intent")
    event_seq = _require_integer(event.get("event_seq"), name="event_seq", minimum=1)
    expected_source_id = f"{run_intent.run_id}:{event_seq:06d}"
    if event.get("source_event_id") != expected_source_id:
        raise TrialLedgerError("source_event_id does not match run_id/event_seq")
    if event.get("run_intent_sha256") != run_intent.content_sha256:
        raise TrialLedgerError("journal event run_intent_sha256 mismatch")
    if event.get("family_id") != run_intent.family_id:
        raise TrialLedgerError("journal event family_id does not match run intent")
    if event.get("execution_spec_content_sha256") != run_intent.execution_spec_content_sha256:
        raise TrialLedgerError("journal event execution spec does not match run intent")
    _require_nonempty_string(event.get("timestamp"), name="timestamp")
    _require_nonempty_string(event.get("evaluation_id"), name="evaluation_id")
    _require_nonempty_string(event.get("model_id"), name="model_id")
    _require_integer(event.get("seed"), name="seed")
    if "purpose" in event:
        _require_nonempty_string(event["purpose"], name="purpose")
    expected_candidate = kind == "candidate"
    expected_fit = kind == "fit"
    if (
        event.get("counts_as_candidate_evaluation") is not expected_candidate
        or event.get("counts_as_model_fit") is not expected_fit
    ):
        raise TrialLedgerError("count flags do not match the source event type")
    if kind == "fit":
        _require_nonempty_string(event.get("fit_id"), name="fit_id")
        _require_nonempty_string(event.get("fold_id"), name="fold_id")
    expected_event_sha256 = _sha256(canonical_json_bytes(_event_payload_without_hash(event)))
    if event.get("event_sha256") != expected_event_sha256:
        raise TrialLedgerError("journal event_sha256 mismatch")

    normalized: dict[str, Any] = {
        "schema_version": _LEDGER_SCHEMA,
        "event": (
            "CANDIDATE_EVALUATION_RECONCILED" if kind == "candidate" else "MODEL_FIT_RECONCILED"
        ),
        "source_event_id": event["source_event_id"],
        "source_event_sha256": _sha256(canonical_json_bytes(event)),
        "source_journal_relpath": journal_relpath,
        "source_event_seq": event_seq,
        "source_timestamp": event["timestamp"],
        "run_id": run_intent.run_id,
        "run_intent_sha256": run_intent.content_sha256,
        "family_id": run_intent.family_id,
        "execution_spec_content_sha256": run_intent.execution_spec_content_sha256,
        "counts_as_candidate_evaluation": expected_candidate,
        "counts_as_model_fit": expected_fit,
        "evaluation_id": event["evaluation_id"],
        "model_id": event["model_id"],
        "seed": event["seed"],
        "outcome": (
            "CANDIDATE_STARTED_RETAINED"
            if kind == "candidate"
            else "STARTED_OR_INTERRUPTED_RETAINED"
        ),
    }
    if "purpose" in event:
        normalized["purpose"] = event["purpose"]
    if kind == "fit":
        normalized["fit_id"] = event["fit_id"]
        normalized["fold_id"] = event["fold_id"]
    normalized["retained_event_sha256"] = _sha256(canonical_json_bytes(normalized))
    return normalized


def _normalized_started_events(
    journal: Path,
    *,
    run_intent: RunIntent,
    journal_root: Path,
) -> list[dict[str, Any]]:
    journal_relpath = _journal_relative_path(journal, journal_root)
    source_events = _read_jsonl(journal)
    normalized: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    seen_event_seq: set[int] = set()
    for event in source_events:
        if event.get("event") not in _COUNTED_EVENTS:
            continue
        retained = _validate_journal_event(
            event,
            run_intent=run_intent,
            journal_relpath=journal_relpath,
        )
        source_event_id = retained["source_event_id"]
        source_event_seq = retained["source_event_seq"]
        if source_event_id in seen_source_ids or source_event_seq in seen_event_seq:
            raise TrialLedgerError("journal contains duplicate source_event_id/event_seq")
        seen_source_ids.add(source_event_id)
        seen_event_seq.add(source_event_seq)
        normalized.append(retained)
    if not normalized:
        raise TrialLedgerError("journal contains no counted start events")
    return normalized


def _validate_existing_reconciled_record(event: dict[str, Any]) -> None:
    """Reject a modified v2 retained record before it can be treated as a no-op."""

    if "source_event_id" not in event:
        return
    if event.get("schema_version") != _LEDGER_SCHEMA:
        raise TrialLedgerError("existing source event has an unsupported ledger schema")
    supplied = _require_sha256(
        event.get("retained_event_sha256"),
        name="existing retained_event_sha256",
    )
    payload = {key: value for key, value in event.items() if key != "retained_event_sha256"}
    if supplied != _sha256(canonical_json_bytes(payload)):
        raise TrialLedgerError("existing retained ledger event hash mismatch")


def _assert_semantic_uniqueness(events: list[dict[str, Any]]) -> None:
    """One counted candidate/fit semantic identifier may appear only once."""

    candidate_ids: dict[str, str | None] = {}
    fit_ids: dict[str, str | None] = {}
    for event in events:
        source_event_id = event.get("source_event_id")
        identity = source_event_id if isinstance(source_event_id, str) else None
        if event.get("counts_as_candidate_evaluation") is True:
            evaluation_id = _require_nonempty_string(
                event.get("evaluation_id"), name="evaluation_id"
            )
            if evaluation_id in candidate_ids and candidate_ids[evaluation_id] != identity:
                raise TrialLedgerError("duplicate semantic evaluation_id in trial ledger")
            candidate_ids[evaluation_id] = identity
        if event.get("counts_as_model_fit") is True:
            fit_id = _require_nonempty_string(event.get("fit_id"), name="fit_id")
            if fit_id in fit_ids and fit_ids[fit_id] != identity:
                raise TrialLedgerError("duplicate semantic fit_id in trial ledger")
            fit_ids[fit_id] = identity


def _lock_path(ledger: Path) -> Path:
    return ledger.with_name(f".{ledger.name}.lock")


def _run_lock_path(ledger: Path) -> Path:
    return ledger.with_name(f".{ledger.name}.run.lock")


@contextmanager
def _exclusive_lock(lock_path: Path, *, nonblocking: bool = False) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        operation = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
        try:
            fcntl.flock(descriptor, operation)
        except BlockingIOError as exc:
            raise TrialLedgerError(f"ledger lock is already held: {lock_path.name}") from exc
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


@contextmanager
def exclusive_run_lease(ledger_path: str | Path) -> Iterator[None]:
    """Prevent concurrent real runs against the single server ledger authority."""

    ledger = Path(ledger_path).resolve()
    with _exclusive_lock(_run_lock_path(ledger), nonblocking=True):
        yield


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("unable to write trial-ledger replacement")
        offset += written


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_replace_bytes(path: Path, payload: bytes) -> None:
    """Publish an entire ledger batch or preserve the exact old ledger bytes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


def _ledger_raw(ledger: Path) -> bytes:
    return ledger.read_bytes() if ledger.is_file() else b""


def _existing_source_records(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    source_records: dict[str, dict[str, Any]] = {}
    for event in events:
        if "source_event_id" not in event:
            continue
        _validate_existing_reconciled_record(event)
        source_event_id = _require_nonempty_string(event["source_event_id"], name="source_event_id")
        if source_event_id in source_records:
            raise TrialLedgerError("existing ledger contains duplicate source_event_id")
        source_records[source_event_id] = event
    return source_records


def reconcile_started_events(
    journal_path: str | Path,
    ledger_path: str | Path,
    *,
    run_intent: RunIntent,
    journal_root: str | Path,
    expected_ledger_prefix: LedgerPrefixBinding,
    limits: TrialLimits,
) -> ReconciliationResult:
    """Atomically import durable starts into the server's authoritative ledger.

    Prefix verification, semantic uniqueness and the total budget caps are all
    checked while holding the same short ledger lock.  The ledger is published
    by same-directory atomic replacement, so a process kill cannot leave a
    partial line or a partial batch.
    """

    journal = Path(journal_path).resolve()
    ledger = Path(ledger_path).resolve()
    root = Path(journal_root).resolve()
    if not journal.is_file():
        raise TrialLedgerError(f"run journal is missing: {journal}")
    additions_source = _normalized_started_events(
        journal,
        run_intent=run_intent,
        journal_root=root,
    )

    with _exclusive_lock(_lock_path(ledger)):
        raw_before = _ledger_raw(ledger)
        _verify_ledger_prefix_bytes(raw_before, expected=expected_ledger_prefix, location=ledger)
        existing_events = _read_jsonl_bytes(raw_before, location=ledger)
        existing_by_source = _existing_source_records(existing_events)
        additions: list[dict[str, Any]] = []
        for normalized in additions_source:
            source_event_id = normalized["source_event_id"]
            existing = existing_by_source.get(source_event_id)
            if existing is None:
                additions.append(normalized)
            elif canonical_json_bytes(existing) != canonical_json_bytes(normalized):
                raise TrialLedgerError("conflicting source_event_id already exists in ledger")

        all_events = [*existing_events, *additions]
        _assert_semantic_uniqueness(all_events)
        candidates_before, fits_before = _count(existing_events)
        candidates_after, fits_after = _count(all_events)
        if candidates_after > limits.candidate_evaluations:
            raise TrialLedgerError(
                "candidate-evaluation limit exceeded: "
                f"{candidates_after} > {limits.candidate_evaluations}"
            )
        if fits_after > limits.model_fits:
            raise TrialLedgerError(f"model-fit limit exceeded: {fits_after} > {limits.model_fits}")
        if additions:
            if raw_before and not raw_before.endswith(b"\n"):
                raise TrialLedgerError("existing trial ledger is not newline terminated")
            payload = raw_before + b"".join(
                canonical_json_bytes(event) + b"\n" for event in additions
            )
            _atomic_replace_bytes(ledger, payload)
        raw_after = _ledger_raw(ledger)

    return ReconciliationResult(
        appended_events=len(additions),
        candidate_evaluations_before=candidates_before,
        model_fits_before=fits_before,
        candidate_evaluations_after=candidates_after,
        model_fits_after=fits_after,
        ledger_sha256_before=_sha256(raw_before),
        ledger_sha256_after=_sha256(raw_after),
    )


def assert_journal_starts_reconciled(
    journal_path: str | Path,
    ledger_path: str | Path,
    *,
    run_intent: RunIntent,
    journal_root: str | Path,
) -> None:
    """Fail closed unless every current run start is byte-exactly retained."""

    journal = Path(journal_path).resolve()
    ledger = Path(ledger_path).resolve()
    normalized = _normalized_started_events(
        journal,
        run_intent=run_intent,
        journal_root=Path(journal_root).resolve(),
    )
    with _exclusive_lock(_lock_path(ledger)):
        existing = _read_jsonl(ledger, allow_missing=True)
        by_source = _existing_source_records(existing)
        for event in normalized:
            retained = by_source.get(event["source_event_id"])
            if retained is None:
                raise TrialLedgerError(
                    f"journal start is not reconciled: {event['source_event_id']}"
                )
            if canonical_json_bytes(retained) != canonical_json_bytes(event):
                raise TrialLedgerError(
                    "reconciled ledger record does not match journal start: "
                    f"{event['source_event_id']}"
                )


def ledger_sha256(ledger_path: str | Path) -> str:
    """Expose the current authoritative digest for an external reconciliation receipt."""

    ledger = Path(ledger_path)
    return sha256_file(ledger) if ledger.is_file() else _sha256(b"")
