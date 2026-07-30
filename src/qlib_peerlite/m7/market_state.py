from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from qlib_peerlite.data.dataset import PanelDataset
from qlib_peerlite.data.market_state import DAILY_STATE_COLUMNS
from qlib_peerlite.governance.artifacts import canonical_json_bytes

from . import M7ContractError

SYNTHETIC_CLAIM_CEILING = "SYNTHETIC_MECHANICS_ONLY"
SYNTHETIC_FIXTURE_VERSION = "m7-synthetic-v1"
M7_CANDIDATES = ("PEERLITE_K16_CCC", "PEERLITE_K16_MSE_GATE")
_TOKEN = object()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _frame_sha256(
    frame: pd.DataFrame, segments: dict[str, tuple[pd.Timestamp, pd.Timestamp]]
) -> str:
    digest = hashlib.sha256()
    digest.update(canonical_json_bytes({"columns": [str(value) for value in frame.columns]}))
    digest.update(pd.util.hash_pandas_object(frame.index, index=True).to_numpy().tobytes())
    digest.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
    digest.update(
        canonical_json_bytes(
            {
                key: [pd.Timestamp(start).isoformat(), pd.Timestamp(end).isoformat()]
                for key, (start, end) in sorted(segments.items())
            }
        )
    )
    return digest.hexdigest()


@dataclass(frozen=True)
class SyntheticFixtureSpec:
    fixture_version: str
    seed: int
    start_date: str
    trading_days: int
    instruments: int
    feature_count: int

    def __post_init__(self) -> None:
        if self.fixture_version != SYNTHETIC_FIXTURE_VERSION:
            raise M7ContractError("unsupported synthetic fixture version")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed != 7:
            raise M7ContractError("synthetic fixture seed must be 7")
        start = pd.Timestamp(self.start_date)
        if start != pd.Timestamp("2000-01-03"):
            raise M7ContractError("synthetic fixture start_date is outside the reserved interval")
        if not 8 <= self.trading_days <= 64:
            raise M7ContractError("synthetic trading_days must be between 8 and 64")
        if not 2 <= self.instruments <= 16:
            raise M7ContractError("synthetic instruments must be between 2 and 16")
        if not 1 <= self.feature_count <= 16:
            raise M7ContractError("synthetic feature_count must be between 1 and 16")


@dataclass(frozen=True, init=False)
class SyntheticFitCapability:
    fixture_sha256: str
    candidate_id: str | None
    claim_ceiling: str

    def __init__(
        self,
        fixture_sha256: str,
        candidate_id: str | None,
        *,
        _token: object,
    ) -> None:
        if _token is not _TOKEN:
            raise M7ContractError("synthetic capability must come from the fixture factory")
        object.__setattr__(self, "fixture_sha256", fixture_sha256)
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "claim_ceiling", SYNTHETIC_CLAIM_CEILING)

    def for_candidate(self, candidate_id: str) -> SyntheticFitCapability:
        if candidate_id not in M7_CANDIDATES:
            raise M7ContractError("candidate is outside the isolated M7 scope")
        return SyntheticFitCapability(self.fixture_sha256, candidate_id, _token=_TOKEN)


class SyntheticM7Dataset:
    """Final, owned and integrity-checked synthetic-only Qlib-like dataset."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        del kwargs
        raise TypeError("SyntheticM7Dataset is final")

    def __init__(
        self,
        delegate: PanelDataset,
        fixture_sha256: str,
        state_binding_sha256: str,
        *,
        _token: object,
    ) -> None:
        if _token is not _TOKEN:
            raise M7ContractError("synthetic dataset must come from the fixture factory")
        self._delegate = PanelDataset(
            frame=delegate.frame.copy(deep=True),
            segments=dict(delegate.segments),
            feature_columns=list(delegate.feature_columns),
            label_column=delegate.label_column,
            market_columns=list(delegate.market_columns or []),
            market_state_columns=list(delegate.market_state_columns or []),
        )
        self.fixture_sha256 = fixture_sha256
        self.state_binding_sha256 = state_binding_sha256
        self.claim_ceiling = SYNTHETIC_CLAIM_CEILING
        self._integrity_sha256 = _frame_sha256(self._delegate.frame, self._delegate.segments)

    @property
    def segments(self) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
        return dict(self._delegate.segments)

    def verify_integrity(self) -> None:
        actual = _frame_sha256(self._delegate.frame, self._delegate.segments)
        if actual != self._integrity_sha256:
            raise M7ContractError("synthetic dataset integrity mismatch")

    def prepare(
        self, segment: str, col_set: str | list[str] = "all", data_key: str | None = None
    ) -> pd.DataFrame:
        self.verify_integrity()
        return self._delegate.prepare(segment, col_set=col_set, data_key=data_key)


def build_synthetic_m7_fixture(
    spec: SyntheticFixtureSpec,
) -> tuple[SyntheticM7Dataset, SyntheticFitCapability]:
    if type(spec) is not SyntheticFixtureSpec:
        raise M7ContractError("synthetic fixture requires the exact specification type")
    rng = np.random.default_rng(spec.seed)
    dates = pd.bdate_range(spec.start_date, periods=spec.trading_days)
    instruments = [f"TEST{i:03d}" for i in range(spec.instruments)]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    feature_names = [f"f{i:02d}" for i in range(spec.feature_count)]
    features = rng.normal(size=(spec.trading_days, spec.instruments, spec.feature_count))
    daily_state = rng.normal(scale=0.25, size=(spec.trading_days, 4))
    features[:, :, 0] += daily_state[:, 0, None]
    labels = (
        0.4 * features[:, :, 0]
        - 0.2 * features[:, :, min(1, spec.feature_count - 1)]
        + 0.1 * daily_state[:, 2, None]
        + rng.normal(scale=0.2, size=(spec.trading_days, spec.instruments))
    )
    frame = pd.DataFrame(
        features.reshape(-1, spec.feature_count).astype(np.float32),
        index=index,
        columns=feature_names,
    )
    frame["label"] = labels.reshape(-1).astype(np.float32)
    for position, column in enumerate(DAILY_STATE_COLUMNS):
        frame[column] = np.repeat(daily_state[:, position].astype(np.float32), spec.instruments)
    train_count = max(1, int(spec.trading_days * 0.5))
    valid_count = max(train_count + 1, int(spec.trading_days * 0.75))
    segments = {
        "train": (dates[0], dates[train_count - 1]),
        "valid": (dates[train_count], dates[valid_count - 1]),
        "test": (dates[valid_count], dates[-1]),
    }
    delegate = PanelDataset(
        frame=frame,
        segments=segments,
        feature_columns=feature_names,
        label_column="label",
        market_state_columns=list(DAILY_STATE_COLUMNS),
    )
    frame_hash = _frame_sha256(delegate.frame, segments)
    state_hash = _sha256(frame.loc[:, list(DAILY_STATE_COLUMNS)].to_numpy(np.float32).tobytes())
    fixture_hash = _sha256(
        canonical_json_bytes(
            {"spec": asdict(spec), "frame_sha256": frame_hash, "state_sha256": state_hash}
        )
    )
    dataset = SyntheticM7Dataset(
        delegate,
        fixture_hash,
        state_hash,
        _token=_TOKEN,
    )
    capability = SyntheticFitCapability(fixture_hash, None, _token=_TOKEN)
    return dataset, capability


def require_synthetic_authority(
    dataset: object,
    capability: object,
    candidate_id: str,
) -> SyntheticM7Dataset:
    if type(dataset) is not SyntheticM7Dataset or type(capability) is not SyntheticFitCapability:
        raise M7ContractError("M7 synthetic fit requires exact generated dataset and capability")
    if capability.candidate_id != candidate_id:
        raise M7ContractError("synthetic capability candidate mismatch")
    if capability.fixture_sha256 != dataset.fixture_sha256:
        raise M7ContractError("synthetic capability fixture mismatch")
    dataset.verify_integrity()
    return dataset


__all__ = [
    "M7_CANDIDATES",
    "SYNTHETIC_CLAIM_CEILING",
    "SYNTHETIC_FIXTURE_VERSION",
    "SyntheticFitCapability",
    "SyntheticFixtureSpec",
    "SyntheticM7Dataset",
    "build_synthetic_m7_fixture",
    "require_synthetic_authority",
]
