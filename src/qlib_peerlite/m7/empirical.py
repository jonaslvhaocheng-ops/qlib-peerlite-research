from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import pandas as pd

from qlib_peerlite.data.market_state import (
    DAILY_STATE_COLUMNS,
    join_market_state,
    validate_state_product,
)
from qlib_peerlite.governance.artifacts import canonical_json_bytes

from . import M7ContractError
from .checkpoint import M7CheckpointContext
from .market_state import M7_CANDIDATES

EMPIRICAL_CLAIM_CEILING = "PRE_FINAL_OOS_SCREENING_ONLY"
_TOKEN = object()


def _dates_sha256(frame: pd.DataFrame) -> str:
    dates = pd.DatetimeIndex(frame.index.get_level_values("datetime")).unique().sort_values()
    return hashlib.sha256(
        "\n".join(date.isoformat() for date in dates).encode("ascii")
    ).hexdigest()


def _state_binding_sha256(state: pd.DataFrame) -> str:
    payload = {
        "columns": list(DAILY_STATE_COLUMNS),
        "dates": [date.isoformat() for date in state.index],
        "state_sha256": state["state_sha256"].tolist(),
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, init=False)
class EmpiricalFitCapability:
    candidate_id: str
    context: M7CheckpointContext
    dataset_binding_sha256: str
    claim_ceiling: str

    def __init__(
        self,
        candidate_id: str,
        context: M7CheckpointContext,
        dataset_binding_sha256: str,
        *,
        _token: object,
    ) -> None:
        if _token is not _TOKEN:
            raise M7ContractError("empirical capability must come from the M7 factory")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "dataset_binding_sha256", dataset_binding_sha256)
        object.__setattr__(self, "claim_ceiling", EMPIRICAL_CLAIM_CEILING)


class EmpiricalM7Dataset:
    """Final Qlib-like view bound to one authorized M7 fit and causal state product."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        del kwargs
        raise TypeError("EmpiricalM7Dataset is final")

    def __init__(
        self,
        delegate: object,
        state: pd.DataFrame,
        dataset_binding_sha256: str,
        lease_event_sha256: str,
        *,
        _token: object,
    ) -> None:
        if _token is not _TOKEN:
            raise M7ContractError("empirical dataset must come from the M7 factory")
        self._delegate = delegate
        self._state = state.copy(deep=True)
        self.dataset_binding_sha256 = dataset_binding_sha256
        self.fixture_sha256 = lease_event_sha256
        self.state_binding_sha256 = _state_binding_sha256(self._state)
        self.claim_ceiling = EMPIRICAL_CLAIM_CEILING

    def verify_integrity(self) -> None:
        validate_state_product(self._state)
        if _state_binding_sha256(self._state) != self.state_binding_sha256:
            raise M7ContractError("empirical market-state binding mismatch")

    def prepare(
        self,
        segment: str,
        col_set: str | list[str] = "all",
        data_key: str | None = None,
    ) -> pd.DataFrame:
        self.verify_integrity()
        def delegate_prepare(requested_col_set: str | list[str]) -> pd.DataFrame:
            if data_key is None:
                return self._delegate.prepare(segment, col_set=requested_col_set)
            return self._delegate.prepare(
                segment,
                col_set=requested_col_set,
                data_key=data_key,
            )

        if col_set == "market_state":
            model_rows = delegate_prepare("feature")
            return join_market_state(model_rows, self._state)
        return delegate_prepare(col_set)


def build_empirical_m7_fit(
    *,
    delegate: object,
    state: pd.DataFrame,
    candidate_id: str,
    context: M7CheckpointContext,
    dataset_binding_sha256: str,
) -> tuple[EmpiricalM7Dataset, EmpiricalFitCapability]:
    if candidate_id not in M7_CANDIDATES:
        raise M7ContractError("candidate is outside the isolated M7 scope")
    if (
        context.family_id != "QLIB_PEERLITE_M7_INITIAL_SCREEN_V1"
        or context.candidate_id != candidate_id
        or context.model_id != candidate_id
        or context.seed != 7
        or context.purpose not in {"ROLLING_SCREEN_FIT", "DETERMINISTIC_REFIT"}
    ):
        raise M7ContractError("empirical checkpoint context is outside frozen M7 scope")
    if (
        not isinstance(dataset_binding_sha256, str)
        or len(dataset_binding_sha256) != 64
        or any(character not in "0123456789abcdef" for character in dataset_binding_sha256)
    ):
        raise M7ContractError("empirical dataset binding is not a SHA256")
    validate_state_product(state)
    train = delegate.prepare("train", col_set="feature")
    valid = delegate.prepare("valid", col_set="feature")
    if (
        _dates_sha256(train) != context.training_dates_sha256
        or _dates_sha256(valid) != context.validation_dates_sha256
    ):
        raise M7ContractError("empirical fit dates do not match the authorized context")
    state_binding = _state_binding_sha256(state)
    if context.state_binding_sha256 != (
        state_binding if candidate_id == "PEERLITE_K16_MSE_GATE" else None
    ):
        raise M7ContractError("empirical state binding does not match the authorized context")
    dataset = EmpiricalM7Dataset(
        delegate,
        state,
        dataset_binding_sha256,
        context.lease_event_sha256,
        _token=_TOKEN,
    )
    capability = EmpiricalFitCapability(
        candidate_id,
        context,
        dataset_binding_sha256,
        _token=_TOKEN,
    )
    return dataset, capability


def require_empirical_authority(
    dataset: object,
    capability: object,
    candidate_id: str,
) -> EmpiricalM7Dataset:
    if type(dataset) is not EmpiricalM7Dataset or type(capability) is not EmpiricalFitCapability:
        raise M7ContractError("M7 empirical fit requires exact generated dataset and capability")
    if capability.candidate_id != candidate_id:
        raise M7ContractError("empirical capability candidate mismatch")
    if capability.context.lease_event_sha256 != dataset.fixture_sha256:
        raise M7ContractError("empirical capability lease mismatch")
    if capability.dataset_binding_sha256 != dataset.dataset_binding_sha256:
        raise M7ContractError("empirical capability dataset mismatch")
    dataset.verify_integrity()
    return dataset


__all__ = [
    "EMPIRICAL_CLAIM_CEILING",
    "EmpiricalFitCapability",
    "EmpiricalM7Dataset",
    "build_empirical_m7_fit",
    "require_empirical_authority",
]
