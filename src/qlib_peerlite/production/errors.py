from __future__ import annotations

from typing import Any


class ProductionError(RuntimeError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qlib_peerlite_production_error_v1",
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
