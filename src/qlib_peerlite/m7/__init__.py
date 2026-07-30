"""Step-eight isolated CCC and market-state Gate engineering contracts."""

from __future__ import annotations


class M7ContractError(ValueError):
    """Raised before an M7 contract permits a prohibited or inconsistent effect."""


class M7StateError(ValueError):
    """Raised when an M7 run-state transition is illegal."""


__all__ = ["M7ContractError", "M7StateError"]
