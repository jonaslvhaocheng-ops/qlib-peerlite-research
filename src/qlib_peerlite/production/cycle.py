from __future__ import annotations

import ctypes
import errno
import fcntl
import json
import os
import re
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from qlib_peerlite.governance.artifacts import canonical_json_bytes, sha256_bytes

from .errors import ProductionError
from .orders import build_paper_intents
from .policy import (
    ShadowPolicy,
    authorize_shadow,
    capture_regular_file,
    load_shadow_policy_snapshot,
)
from .schedule import evaluate_schedule, load_calendar
from .signals import (
    PredictionSnapshot,
    capture_prediction,
    validate_signal_frame,
    validate_source_manifest,
)

CYCLE_ID = re.compile(r"^m10s-\d{8}-\d{6}-[0-9a-f]{12}$")
TERMINAL_SCHEMA = "qlib_peerlite_shadow_cycle_v1"
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _json_payload(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ).encode("utf-8") + b"\n"


def _parse_json(payload: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionError(code, "required JSON input cannot be parsed") from exc
    if not isinstance(value, dict):
        raise ProductionError(code, "required JSON input must be an object")
    return value


def _safe_json_file(path: Path, code: str) -> dict[str, Any]:
    captured = capture_regular_file(path, code=code)
    return _parse_json(captured.payload, code)


def _read_fd_file(directory_fd: int, name: str, code: str) -> bytes:
    try:
        descriptor = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
    except OSError as exc:
        raise ProductionError(code, "required file cannot be opened safely") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ProductionError(code, "required file is not regular")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_exclusive_fd(directory_fd: int, name: str, payload: bytes, code: str) -> None:
    try:
        descriptor = os.open(
            name,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o644,
            dir_fd=directory_fd,
        )
    except FileExistsError as exc:
        raise ProductionError(code, "exclusive state record already exists") from exc
    except OSError as exc:
        raise ProductionError(code, "state record cannot be created safely") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _open_directory(path: Path, code: str) -> int:
    try:
        descriptor = os.open(path, _DIRECTORY_FLAGS)
    except OSError as exc:
        raise ProductionError(code, "directory cannot be opened safely") from exc
    return descriptor


def _open_child_directory(parent_fd: int, name: str, code: str) -> int:
    try:
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        raise ProductionError(code, "managed directory cannot be opened safely", path=name) from exc
    return descriptor


def _exclusive_json(path: Path, value: dict[str, Any], code: str) -> None:
    directory_fd = _open_directory(path.parent, code)
    try:
        _write_exclusive_fd(directory_fd, path.name, _json_payload(value), code)
    finally:
        os.close(directory_fd)


def _entry_kind(directory_fd: int, name: str) -> str | None:
    try:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if stat.S_ISDIR(info.st_mode):
        return "dir"
    if stat.S_ISREG(info.st_mode):
        return "file"
    return "unsafe"


@dataclass
class _StateStore:
    root_fd: int
    root_path: Path
    cycles_fd: int | None = None
    reservations_fd: int | None = None
    idempotency_fd: int | None = None

    @classmethod
    def open(cls, state_root: Path, cycle_id: str) -> _StateStore:
        if not CYCLE_ID.fullmatch(cycle_id):
            raise ProductionError("INVALID_CYCLE_ID", "cycle ID does not match safe grammar")
        root_fd = _open_directory(state_root, "UNSAFE_STATE_ROOT")
        root_info = os.fstat(root_fd)
        if root_info.st_uid != os.geteuid() or root_info.st_mode & 0o022:
            os.close(root_fd)
            raise ProductionError(
                "UNSAFE_STATE_ROOT",
                "state root must be owned by the current user and not group/world writable",
            )
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(root_fd)
            raise ProductionError("STATE_LOCKED", "state root is already in use") from exc
        store = cls(root_fd, state_root)
        try:
            for name, attribute in (
                ("cycles", "cycles_fd"),
                ("reservations", "reservations_fd"),
                ("idempotency", "idempotency_fd"),
            ):
                kind = _entry_kind(root_fd, name)
                if kind is None:
                    continue
                if kind != "dir":
                    raise ProductionError(
                        "UNSAFE_STATE_ROOT", "managed state path is unsafe", path=name
                    )
                setattr(store, attribute, _open_child_directory(root_fd, name, "UNSAFE_STATE_ROOT"))
            return store
        except Exception:
            store.close()
            raise

    def ensure_managed(self) -> None:
        for name, attribute in (
            ("cycles", "cycles_fd"),
            ("reservations", "reservations_fd"),
            ("idempotency", "idempotency_fd"),
        ):
            if getattr(self, attribute) is not None:
                continue
            try:
                os.mkdir(name, 0o755, dir_fd=self.root_fd)
            except FileExistsError:
                pass
            setattr(
                self,
                attribute,
                _open_child_directory(self.root_fd, name, "UNSAFE_STATE_ROOT"),
            )

    def assert_bound(self) -> None:
        try:
            named_root = os.stat(self.root_path, follow_symlinks=False)
        except OSError as exc:
            raise ProductionError(
                "UNSAFE_STATE_ROOT", "state root binding disappeared"
            ) from exc
        opened_root = os.fstat(self.root_fd)
        if (
            not stat.S_ISDIR(named_root.st_mode)
            or (named_root.st_dev, named_root.st_ino)
            != (opened_root.st_dev, opened_root.st_ino)
        ):
            raise ProductionError("UNSAFE_STATE_ROOT", "state root binding changed")
        for name, attribute in (
            ("cycles", "cycles_fd"),
            ("reservations", "reservations_fd"),
            ("idempotency", "idempotency_fd"),
        ):
            descriptor = getattr(self, attribute)
            if descriptor is None:
                continue
            try:
                named = os.stat(name, dir_fd=self.root_fd, follow_symlinks=False)
            except OSError as exc:
                raise ProductionError(
                    "UNSAFE_STATE_ROOT", "managed state binding disappeared", path=name
                ) from exc
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(named.st_mode)
                or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                raise ProductionError(
                    "UNSAFE_STATE_ROOT", "managed state binding changed", path=name
                )

    def close(self) -> None:
        for attribute in ("cycles_fd", "reservations_fd", "idempotency_fd", "root_fd"):
            descriptor = getattr(self, attribute, None)
            if descriptor is not None:
                os.close(descriptor)
                setattr(self, attribute, None)


def _validate_state_root(state_root: Path, cycle_id: str) -> None:
    store = _StateStore.open(state_root, cycle_id)
    store.close()


def _manifest_content_hash(manifest: dict[str, Any]) -> str:
    content = dict(manifest)
    content.pop("content_sha256", None)
    return sha256_bytes(canonical_json_bytes(content))


def _verify_terminal_fd(
    terminal_fd: int,
    expected_cycle_id: str | None = None,
    expected_request_digest: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    manifest_bytes = _read_fd_file(terminal_fd, "cycle_manifest.json", "TERMINAL_CORRUPTION")
    manifest = _parse_json(manifest_bytes, "TERMINAL_CORRUPTION")
    expected_keys = {
        "schema_version",
        "cycle_id",
        "state",
        "request_digest",
        "created_at",
        "capability",
        "live_execution_authorized",
        "artifacts",
        "content_sha256",
    }
    expected_artifacts = {
        "COMPLETE": {"signal_manifest.json", "monitoring.json", "paper_intents.json"},
        "HALTED": {"monitoring.json", "alert.json"},
        "NOT_DUE": set(),
    }
    state = manifest.get("state")
    valid_header = (
        set(manifest) == expected_keys
        and manifest.get("schema_version") == TERMINAL_SCHEMA
        and state in expected_artifacts
        and manifest.get("content_sha256") == _manifest_content_hash(manifest)
        and isinstance(manifest.get("request_digest"), str)
        and isinstance(manifest.get("cycle_id"), str)
        and isinstance(manifest.get("artifacts"), dict)
        and manifest.get("capability") == "SHADOW_ONLY"
        and manifest.get("live_execution_authorized") is False
    )
    try:
        created_at = datetime.fromisoformat(manifest["created_at"])
        valid_time = created_at.tzinfo is not None and created_at.utcoffset() is not None
    except (KeyError, TypeError, ValueError):
        valid_time = False
    if not valid_header or not valid_time:
        raise ProductionError("TERMINAL_CORRUPTION", "terminal manifest header is invalid")
    if expected_cycle_id is not None and manifest["cycle_id"] != expected_cycle_id:
        raise ProductionError("TERMINAL_CORRUPTION", "terminal cycle ID differs")
    if (
        expected_request_digest is not None
        and manifest["request_digest"] != expected_request_digest
    ):
        raise ProductionError("IDEMPOTENCY_COLLISION", "terminal request digest differs")
    actual_files = set(os.listdir(terminal_fd))
    expected_files = expected_artifacts[state] | {"cycle_manifest.json"}
    if actual_files != expected_files or set(manifest["artifacts"]) != expected_artifacts[state]:
        raise ProductionError("TERMINAL_CORRUPTION", "terminal file inventory differs")
    for name, record in manifest["artifacts"].items():
        payload = _read_fd_file(terminal_fd, name, "TERMINAL_CORRUPTION")
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "bytes", "sha256"}
            or record["path"] != name
            or record["bytes"] != len(payload)
            or record["sha256"] != sha256_bytes(payload)
        ):
            raise ProductionError("TERMINAL_CORRUPTION", "terminal artifact binding differs")
    return manifest, manifest_bytes


def _open_terminal(cycles_fd: int, cycle_id: str) -> int:
    return _open_child_directory(cycles_fd, cycle_id, "TERMINAL_CORRUPTION")


def verify_terminal_cycle(
    terminal_dir: str | Path,
    expected_cycle_id: str | None = None,
    expected_request_digest: str | None = None,
) -> dict[str, Any]:
    descriptor = _open_directory(Path(terminal_dir), "TERMINAL_CORRUPTION")
    try:
        return _verify_terminal_fd(
            descriptor, expected_cycle_id, expected_request_digest
        )[0]
    finally:
        os.close(descriptor)


def _index_value(
    cycle_id: str,
    request_digest: str,
    terminal: Path,
    manifest: dict[str, Any],
    committed_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "qlib_peerlite_idempotency_index_v1",
        "cycle_id": cycle_id,
        "request_digest": request_digest,
        "terminal_state": manifest["state"],
        "terminal_manifest": f"cycles/{cycle_id}/cycle_manifest.json",
        "terminal_manifest_sha256": sha256_bytes((terminal / "cycle_manifest.json").read_bytes()),
        "committed_at": committed_at.isoformat(),
    }


def _index_value_fd(
    cycle_id: str,
    request_digest: str,
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    committed_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "qlib_peerlite_idempotency_index_v1",
        "cycle_id": cycle_id,
        "request_digest": request_digest,
        "terminal_state": manifest["state"],
        "terminal_manifest": f"cycles/{cycle_id}/cycle_manifest.json",
        "terminal_manifest_sha256": sha256_bytes(manifest_bytes),
        "committed_at": committed_at.isoformat(),
    }


def _validate_index_fd(
    index_fd: int,
    cycles_fd: int,
    cycle_id: str,
    request_digest: str,
) -> dict[str, Any]:
    try:
        index_bytes = _read_fd_file(index_fd, f"{cycle_id}.json", "IDEMPOTENCY_INDEX_CORRUPTION")
        index = _parse_json(index_bytes, "IDEMPOTENCY_INDEX_CORRUPTION")
        expected_keys = {
            "schema_version",
            "cycle_id",
            "request_digest",
            "terminal_state",
            "terminal_manifest",
            "terminal_manifest_sha256",
            "committed_at",
        }
        if (
            set(index) != expected_keys
            or index["schema_version"] != "qlib_peerlite_idempotency_index_v1"
            or index["cycle_id"] != cycle_id
            or index["terminal_manifest"] != f"cycles/{cycle_id}/cycle_manifest.json"
        ):
            raise ProductionError("IDEMPOTENCY_INDEX_CORRUPTION", "idempotency index differs")
        terminal_fd = _open_terminal(cycles_fd, cycle_id)
        try:
            manifest, manifest_bytes = _verify_terminal_fd(
                terminal_fd, cycle_id, index["request_digest"]
            )
        finally:
            os.close(terminal_fd)
        if (
            index["terminal_state"] != manifest["state"]
            or index["terminal_manifest_sha256"] != sha256_bytes(manifest_bytes)
        ):
            raise ProductionError("IDEMPOTENCY_INDEX_CORRUPTION", "index binding differs")
        committed_at = datetime.fromisoformat(index["committed_at"])
        if committed_at.tzinfo is None or committed_at.utcoffset() is None:
            raise ValueError("committed_at must be timezone-aware")
        if index["request_digest"] != request_digest:
            raise ProductionError("IDEMPOTENCY_COLLISION", "cycle ID has a different request")
        return manifest
    except (KeyError, TypeError, ValueError) as exc:
        raise ProductionError(
            "IDEMPOTENCY_INDEX_CORRUPTION", "idempotency index is malformed"
        ) from exc


def _validate_index(
    index_path: Path,
    state_root: Path,
    cycle_id: str,
    request_digest: str,
) -> dict[str, Any]:
    index_fd = _open_directory(index_path.parent, "IDEMPOTENCY_INDEX_CORRUPTION")
    cycles_fd = _open_directory(state_root / "cycles", "TERMINAL_CORRUPTION")
    try:
        return _validate_index_fd(index_fd, cycles_fd, cycle_id, request_digest)
    finally:
        os.close(index_fd)
        os.close(cycles_fd)


def _write_or_validate_index_fd(
    index_fd: int,
    cycles_fd: int,
    cycle_id: str,
    request_digest: str,
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    committed_at: datetime,
) -> None:
    value = _index_value_fd(
        cycle_id, request_digest, manifest, manifest_bytes, committed_at
    )
    try:
        _write_exclusive_fd(
            index_fd,
            f"{cycle_id}.json",
            _json_payload(value),
            "INDEX_ALREADY_EXISTS",
        )
    except ProductionError as exc:
        if exc.code != "INDEX_ALREADY_EXISTS":
            raise
        _validate_index_fd(index_fd, cycles_fd, cycle_id, request_digest)


def _write_or_validate_index(
    index_path: Path,
    state_root: Path,
    cycle_id: str,
    request_digest: str,
    terminal: Path,
    manifest: dict[str, Any],
    committed_at: datetime,
) -> None:
    index_fd = _open_directory(index_path.parent, "IDEMPOTENCY_INDEX_CORRUPTION")
    cycles_fd = _open_directory(state_root / "cycles", "TERMINAL_CORRUPTION")
    terminal_fd = _open_directory(terminal, "TERMINAL_CORRUPTION")
    try:
        _, manifest_bytes = _verify_terminal_fd(
            terminal_fd, cycle_id, request_digest
        )
        _write_or_validate_index_fd(
            index_fd,
            cycles_fd,
            cycle_id,
            request_digest,
            manifest,
            manifest_bytes,
            committed_at,
        )
    finally:
        os.close(terminal_fd)
        os.close(cycles_fd)
        os.close(index_fd)


def _reservation_value(
    cycle_id: str,
    request_digest: str,
    owner_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "qlib_peerlite_cycle_reservation_v1",
        "cycle_id": cycle_id,
        "request_digest": request_digest,
        "owner_id": owner_id,
        "created_at": as_of.isoformat(),
    }


def _acquire_reservation_fd(
    directory_fd: int,
    cycle_id: str,
    request_digest: str,
    owner_id: str,
    as_of: datetime,
    timeout_seconds: int,
) -> None:
    name = f"{cycle_id}.json"
    value = _reservation_value(cycle_id, request_digest, owner_id, as_of)
    if _entry_kind(directory_fd, name) is not None:
        existing = _parse_json(
            _read_fd_file(directory_fd, name, "RESERVATION_CORRUPTION"),
            "RESERVATION_CORRUPTION",
        )
        if set(existing) != set(value) or existing.get("cycle_id") != cycle_id:
            raise ProductionError("RESERVATION_CORRUPTION", "reservation schema differs")
        if existing["request_digest"] != request_digest:
            raise ProductionError("IDEMPOTENCY_COLLISION", "reservation digest differs")
        try:
            created_at = datetime.fromisoformat(existing["created_at"])
            if created_at.tzinfo is None or created_at.utcoffset() is None:
                raise ValueError("timezone required")
        except (TypeError, ValueError) as exc:
            raise ProductionError("RESERVATION_CORRUPTION", "reservation time is invalid") from exc
        if (as_of - created_at).total_seconds() <= timeout_seconds:
            raise ProductionError("CYCLE_IN_PROGRESS", "matching cycle reservation is fresh")
        stale_name = f".{name}.stale.{owner_id}"
        try:
            os.rename(
                name,
                stale_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
        except OSError as exc:
            raise ProductionError("CYCLE_IN_PROGRESS", "stale reservation takeover lost") from exc
    _write_exclusive_fd(
        directory_fd,
        name,
        _json_payload(value),
        "CYCLE_IN_PROGRESS",
    )


def _acquire_reservation(
    path: Path,
    cycle_id: str,
    request_digest: str,
    owner_id: str,
    as_of: datetime,
    timeout_seconds: int,
) -> None:
    value = _reservation_value(cycle_id, request_digest, owner_id, as_of)
    if path.exists():
        existing = _safe_json_file(path, "RESERVATION_CORRUPTION")
        if set(existing) != set(value) or existing.get("cycle_id") != cycle_id:
            raise ProductionError("RESERVATION_CORRUPTION", "reservation schema differs")
        if existing["request_digest"] != request_digest:
            raise ProductionError("IDEMPOTENCY_COLLISION", "reservation digest differs")
        try:
            created_at = datetime.fromisoformat(existing["created_at"])
            if created_at.tzinfo is None or created_at.utcoffset() is None:
                raise ValueError("timezone required")
        except (TypeError, ValueError) as exc:
            raise ProductionError("RESERVATION_CORRUPTION", "reservation time is invalid") from exc
        if (as_of - created_at).total_seconds() <= timeout_seconds:
            raise ProductionError("CYCLE_IN_PROGRESS", "matching cycle reservation is fresh")
        stale_path = path.with_name(f".{path.name}.stale.{owner_id}")
        try:
            os.rename(path, stale_path)
        except OSError as exc:
            raise ProductionError("CYCLE_IN_PROGRESS", "stale reservation takeover lost") from exc
    directory_fd = _open_directory(path.parent, "RESERVATION_CORRUPTION")
    try:
        _write_exclusive_fd(
            directory_fd,
            path.name,
            _json_payload(value),
            "CYCLE_IN_PROGRESS",
        )
    finally:
        os.close(directory_fd)


def _rename_directory_noreplace(
    source_fd: int,
    source_name: str,
    destination_fd: int,
    destination_name: str,
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    source = os.fsencode(source_name)
    destination = os.fsencode(destination_name)
    if sys.platform == "darwin":
        operation = library.renameatx_np
        operation.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = operation(source_fd, source, destination_fd, destination, 0x00000004)
    elif hasattr(library, "renameat2"):
        operation = library.renameat2
        operation.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = operation(source_fd, source, destination_fd, destination, 1)
    else:
        raise ProductionError(
            "ATOMIC_NOREPLACE_UNAVAILABLE",
            "platform lacks atomic no-replace directory publication",
        )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise ProductionError(
                "TERMINAL_ALREADY_EXISTS", "terminal destination already exists"
            )
        raise ProductionError(
            "TERMINAL_PUBLISH_FAILED",
            "atomic no-replace terminal publication failed",
            errno=error_number,
        )


def _publish_terminal_fd(
    cycles_fd: int,
    cycle_id: str,
    request_digest: str,
    state: str,
    created_at: datetime,
    artifacts: dict[str, Any],
    binding_check: Callable[[], None] | None = None,
) -> tuple[dict[str, Any], bytes]:
    check = binding_check or (lambda: None)
    check()
    staging_name = f".{cycle_id}.{uuid4().hex}"
    try:
        os.mkdir(staging_name, 0o755, dir_fd=cycles_fd)
    except OSError as exc:
        raise ProductionError(
            "TERMINAL_PUBLISH_FAILED", "staging directory creation failed"
        ) from exc
    staging_fd = _open_child_directory(cycles_fd, staging_name, "TERMINAL_PUBLISH_FAILED")
    published = False
    try:
        check()
        records: dict[str, dict[str, Any]] = {}
        for name, value in sorted(artifacts.items()):
            check()
            payload = _json_payload(value)
            _write_exclusive_fd(staging_fd, name, payload, "TERMINAL_PUBLISH_FAILED")
            records[name] = {
                "path": name,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        manifest = {
            "schema_version": TERMINAL_SCHEMA,
            "cycle_id": cycle_id,
            "state": state,
            "request_digest": request_digest,
            "created_at": created_at.isoformat(),
            "capability": "SHADOW_ONLY",
            "live_execution_authorized": False,
            "artifacts": records,
        }
        manifest["content_sha256"] = _manifest_content_hash(manifest)
        manifest_bytes = _json_payload(manifest)
        check()
        _write_exclusive_fd(
            staging_fd,
            "cycle_manifest.json",
            manifest_bytes,
            "TERMINAL_PUBLISH_FAILED",
        )
        os.fsync(staging_fd)
        try:
            check()
            _rename_directory_noreplace(
                cycles_fd, staging_name, cycles_fd, cycle_id
            )
            published = True
        except ProductionError as exc:
            if _entry_kind(cycles_fd, cycle_id) == "dir":
                terminal_fd = _open_terminal(cycles_fd, cycle_id)
                try:
                    return _verify_terminal_fd(terminal_fd, cycle_id, request_digest)
                finally:
                    os.close(terminal_fd)
            raise exc
        terminal_fd = _open_terminal(cycles_fd, cycle_id)
        try:
            return _verify_terminal_fd(terminal_fd, cycle_id, request_digest)
        finally:
            os.close(terminal_fd)
    finally:
        os.close(staging_fd)
        if not published and _entry_kind(cycles_fd, staging_name) == "dir":
            cleanup_fd = _open_child_directory(
                cycles_fd, staging_name, "TERMINAL_PUBLISH_FAILED"
            )
            try:
                for name in os.listdir(cleanup_fd):
                    os.unlink(name, dir_fd=cleanup_fd)
            finally:
                os.close(cleanup_fd)
            os.rmdir(staging_name, dir_fd=cycles_fd)


def _publish_terminal(
    cycles_dir: Path,
    cycle_id: str,
    request_digest: str,
    state: str,
    created_at: datetime,
    artifacts: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    cycles_fd = _open_directory(cycles_dir, "TERMINAL_PUBLISH_FAILED")
    try:
        manifest, _ = _publish_terminal_fd(
            cycles_fd, cycle_id, request_digest, state, created_at, artifacts
        )
        return cycles_dir / cycle_id, manifest
    finally:
        os.close(cycles_fd)


def _remove_owned_reservation_fd(
    directory_fd: int,
    cycle_id: str,
    owner_id: str,
    request_digest: str,
) -> None:
    name = f"{cycle_id}.json"
    if _entry_kind(directory_fd, name) is None:
        return
    reservation = _parse_json(
        _read_fd_file(directory_fd, name, "RESERVATION_CORRUPTION"),
        "RESERVATION_CORRUPTION",
    )
    if (
        reservation.get("owner_id") == owner_id
        and reservation.get("request_digest") == request_digest
    ):
        os.unlink(name, dir_fd=directory_fd)


def _remove_owned_reservation(path: Path, owner_id: str, request_digest: str) -> None:
    if not path.exists():
        return
    reservation = _safe_json_file(path, "RESERVATION_CORRUPTION")
    if (
        reservation.get("owner_id") == owner_id
        and reservation.get("request_digest") == request_digest
    ):
        path.unlink()


def _source_manifest_snapshot(
    path: str | Path,
    snapshot: PredictionSnapshot,
    policy: ShadowPolicy,
) -> tuple[dict[str, Any], str]:
    captured = capture_regular_file(path, code="SOURCE_MANIFEST_INVALID")
    manifest = _parse_json(captured.payload, "SOURCE_MANIFEST_INVALID")
    validate_source_manifest(manifest, snapshot, policy)
    return manifest, captured.sha256


def run_shadow_cycle(
    *,
    policy_path: str | Path,
    predictions_path: str | Path,
    source_manifest_path: str | Path,
    state_root: str | Path,
    cycle_id: str,
    as_of: datetime,
    project_root: str | Path,
    owner_id: str | None = None,
) -> dict[str, Any]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ProductionError("INVALID_AS_OF", "as_of must be timezone-aware")
    if not CYCLE_ID.fullmatch(cycle_id):
        raise ProductionError("INVALID_CYCLE_ID", "cycle ID does not match safe grammar")

    policy, policy_snapshot = load_shadow_policy_snapshot(policy_path)
    gate_path = Path(policy.m9_gate_path)
    if not gate_path.is_absolute():
        gate_path = Path(project_root) / gate_path
    gate_snapshot = capture_regular_file(gate_path, code="M9_GATE_MISSING")
    authorize_shadow(policy, project_root, gate_snapshot=gate_snapshot)
    calendar_snapshot = capture_regular_file(policy.calendar_path, code="CALENDAR_MISSING")
    calendar = load_calendar(policy, snapshot=calendar_snapshot)
    snapshot = capture_prediction(predictions_path, policy)
    source_manifest, source_digest = _source_manifest_snapshot(
        source_manifest_path, snapshot, policy
    )
    decision = evaluate_schedule(policy, calendar, as_of)
    request_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "cycle_id": cycle_id,
                "policy_sha256": policy_snapshot.sha256,
                "source_manifest_sha256": source_digest,
                "predictions_sha256": snapshot.sha256,
                "as_of": as_of.isoformat(),
            }
        )
    )

    store = _StateStore.open(Path(state_root), cycle_id)
    try:
        if store.idempotency_fd is not None:
            index_kind = _entry_kind(store.idempotency_fd, f"{cycle_id}.json")
            if index_kind is not None:
                if index_kind != "file" or store.cycles_fd is None:
                    raise ProductionError(
                        "IDEMPOTENCY_INDEX_CORRUPTION", "idempotency index is unsafe"
                    )
                return _validate_index_fd(
                    store.idempotency_fd,
                    store.cycles_fd,
                    cycle_id,
                    request_digest,
                )
        if store.cycles_fd is not None:
            terminal_kind = _entry_kind(store.cycles_fd, cycle_id)
            if terminal_kind is not None:
                if terminal_kind != "dir":
                    raise ProductionError(
                        "TERMINAL_CORRUPTION", "terminal cycle path is unsafe"
                    )
                terminal_fd = _open_terminal(store.cycles_fd, cycle_id)
                try:
                    manifest, manifest_bytes = _verify_terminal_fd(
                        terminal_fd, cycle_id, request_digest
                    )
                finally:
                    os.close(terminal_fd)
                store.ensure_managed()
                store.assert_bound()
                assert store.idempotency_fd is not None
                assert store.cycles_fd is not None
                _write_or_validate_index_fd(
                    store.idempotency_fd,
                    store.cycles_fd,
                    cycle_id,
                    request_digest,
                    manifest,
                    manifest_bytes,
                    as_of,
                )
                return manifest

        store.ensure_managed()
        store.assert_bound()
        assert store.cycles_fd is not None
        assert store.reservations_fd is not None
        assert store.idempotency_fd is not None
        owner = owner_id or uuid4().hex
        _acquire_reservation_fd(
            store.reservations_fd,
            cycle_id,
            request_digest,
            owner,
            as_of,
            policy.reservation_timeout_seconds,
        )
        store.assert_bound()
        if not decision.due:
            manifest, manifest_bytes = _publish_terminal_fd(
                store.cycles_fd,
                cycle_id,
                request_digest,
                "NOT_DUE",
                as_of,
                {},
                store.assert_bound,
            )
        else:
            try:
                frame = validate_signal_frame(
                    snapshot, source_manifest, policy, decision, as_of
                )
            except ProductionError as exc:
                monitoring = {
                    "schema_version": "qlib_peerlite_monitoring_v1",
                    "status": "FAIL",
                    "check_code": exc.code,
                }
                alert = {
                    "schema_version": "qlib_peerlite_alert_v1",
                    "severity": "ERROR",
                    "cycle_id": cycle_id,
                    "code": exc.code,
                    "message": exc.message,
                }
                manifest, manifest_bytes = _publish_terminal_fd(
                    store.cycles_fd,
                    cycle_id,
                    request_digest,
                    "HALTED",
                    as_of,
                    {"monitoring.json": monitoring, "alert.json": alert},
                    store.assert_bound,
                )
            else:
                intents = build_paper_intents(frame, policy, cycle_id)
                signal_manifest = {
                    "schema_version": "qlib_peerlite_validated_signal_v1",
                    "signal_date": decision.session_date,
                    "row_count": len(frame),
                    "model_id": source_manifest["model_id"],
                    "predictions_sha256": snapshot.sha256,
                }
                monitoring = {
                    "schema_version": "qlib_peerlite_monitoring_v1",
                    "status": "PASS",
                    "checks": [
                        "M9_SHADOW_AUTHORIZED",
                        "SCHEDULE_DUE",
                        "SIGNAL_VALID",
                        "PAPER_ONLY",
                    ],
                }
                manifest, manifest_bytes = _publish_terminal_fd(
                    store.cycles_fd,
                    cycle_id,
                    request_digest,
                    "COMPLETE",
                    as_of,
                    {
                        "signal_manifest.json": signal_manifest,
                        "monitoring.json": monitoring,
                        "paper_intents.json": {
                            "schema_version": "qlib_peerlite_paper_intents_v1",
                            "items": intents,
                        },
                    },
                    store.assert_bound,
                )
        _write_or_validate_index_fd(
            store.idempotency_fd,
            store.cycles_fd,
            cycle_id,
            request_digest,
            manifest,
            manifest_bytes,
            as_of,
        )
        store.assert_bound()
        _remove_owned_reservation_fd(
            store.reservations_fd, cycle_id, owner, request_digest
        )
        return manifest
    finally:
        store.close()
