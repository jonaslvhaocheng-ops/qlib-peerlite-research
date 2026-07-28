from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def append_jsonl(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json_bytes(value) + b"\n"
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    fd = os.open(target, flags, 0o644)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)


def git_identity(root: str | Path) -> dict[str, Any]:
    workdir = Path(root)

    def run(*args: str) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(workdir), *args],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    status = run("status", "--porcelain")
    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "dirty": None if status is None else bool(status),
    }


def environment_report(project_root: str | Path) -> dict[str, Any]:
    packages: dict[str, str] = {}
    for package in ("numpy", "pandas", "pyarrow", "torch", "lightgbm", "qlib"):
        try:
            module = __import__(package)
            packages[package] = str(getattr(module, "__version__", "unknown"))
        except Exception:
            packages[package] = "NOT_INSTALLED"

    torch_info: dict[str, Any] = {}
    try:
        import torch

        torch_info = {
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "mps_available": bool(
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            ),
            "device_count": torch.cuda.device_count(),
        }
    except Exception:
        torch_info = {"available": False}

    return {
        "schema_version": "qlib_peerlite_environment_v1",
        "created_at": datetime.now(SHANGHAI).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": packages,
        "torch": torch_info,
        "git": git_identity(project_root),
    }
