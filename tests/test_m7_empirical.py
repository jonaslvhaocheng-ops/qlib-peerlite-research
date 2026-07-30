from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from qlib_peerlite.data.dataset import PanelDataset
from qlib_peerlite.data.market_state import aggregate_daily_state
from qlib_peerlite.m7 import M7ContractError
from qlib_peerlite.m7.checkpoint import M7CheckpointContext
from qlib_peerlite.m7.empirical import _state_binding_sha256, build_empirical_m7_fit
from qlib_peerlite.models.peerlite import PeerLiteModel


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _delegate_and_state() -> tuple[PanelDataset, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=12)
    instruments = ["A", "B", "C"]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(rng.normal(size=(len(index), 4)), index=index, columns=list("abcd"))
    frame["label"] = 0.2 * frame["a"] - 0.1 * frame["b"]
    delegate = PanelDataset(
        frame=frame,
        segments={
            "train": (dates[0], dates[5]),
            "valid": (dates[6], dates[8]),
            "test": (dates[9], dates[-1]),
        },
        feature_columns=list("abcd"),
        label_column="label",
    )
    population = pd.DataFrame(
        {
            "ret_mean_20": frame["a"],
            "ret_std_20": frame["b"].abs() + 0.01,
            "ret_1d": frame["c"],
            "turnover_mean_20": frame["d"].abs() + 0.01,
        },
        index=index,
    )
    return delegate, aggregate_daily_state(population)


def _date_hash(frame: pd.DataFrame) -> str:
    dates = pd.DatetimeIndex(frame.index.get_level_values("datetime")).unique().sort_values()
    return hashlib.sha256(
        "\n".join(date.isoformat() for date in dates).encode("ascii")
    ).hexdigest()


def _context(
    delegate: PanelDataset,
    state: pd.DataFrame,
    *,
    candidate: str,
) -> M7CheckpointContext:
    return M7CheckpointContext(
        family_id="QLIB_PEERLITE_M7_INITIAL_SCREEN_V1",
        run_id="m7-test",
        fit_id=f"{candidate}:screen:seed7:wf_2024",
        candidate_id=candidate,
        model_id=candidate,
        seed=7,
        fold_id="wf_2024",
        purpose="ROLLING_SCREEN_FIT",
        execution_spec_sha256=_sha("execution"),
        budget_sha256=_sha("budget"),
        prerequisite_bundle_sha256=_sha("prerequisites"),
        lease_event_sha256=_sha("lease"),
        authoritative_ledger_sha256=_sha("ledger"),
        training_dates_sha256=_date_hash(delegate.prepare("train", col_set="feature")),
        validation_dates_sha256=_date_hash(delegate.prepare("valid", col_set="feature")),
        state_binding_sha256=(
            _state_binding_sha256(state) if candidate == "PEERLITE_K16_MSE_GATE" else None
        ),
    )


@pytest.mark.parametrize(
    ("candidate", "loss", "gate"),
    [
        ("PEERLITE_K16_CCC", "ccc", False),
        ("PEERLITE_K16_MSE_GATE", "mse", True),
    ],
)
def test_empirical_fit_requires_factory_capability_and_replays(
    tmp_path, candidate: str, loss: str, gate: bool
) -> None:
    delegate, state = _delegate_and_state()
    context = _context(delegate, state, candidate=candidate)
    dataset, capability = build_empirical_m7_fit(
        delegate=delegate,
        state=state,
        candidate_id=candidate,
        context=context,
        dataset_binding_sha256=_sha("dataset"),
    )
    model = PeerLiteModel(
        input_dim=4,
        hidden_dim=64,
        num_peers=16,
        num_heads=4,
        dropout=0.1,
        market_dim=4 if gate else 0,
        market_gate=gate,
        loss=loss,
        seed=7,
        epochs=2,
        patience=1,
        cross_section_batch_size=2,
        device="cpu",
        model_id=candidate,
    )
    with pytest.raises(M7ContractError):
        model.fit(dataset)
    model.fit(dataset, m7_authority=capability)
    expected = model.predict(dataset)
    checkpoint = tmp_path / candidate
    model.save_checkpoint(checkpoint)
    replay = PeerLiteModel.load_checkpoint(checkpoint, device="cpu").predict(dataset)
    np.testing.assert_array_equal(expected.to_numpy(), replay.to_numpy())


def test_empirical_factory_rejects_wrong_candidate_or_state_binding() -> None:
    delegate, state = _delegate_and_state()
    context = _context(delegate, state, candidate="PEERLITE_K16_MSE_GATE")
    bad = M7CheckpointContext(
        **{**context.__dict__, "state_binding_sha256": _sha("wrong")}
    )
    with pytest.raises(M7ContractError, match="state binding"):
        build_empirical_m7_fit(
            delegate=delegate,
            state=state,
            candidate_id="PEERLITE_K16_MSE_GATE",
            context=bad,
            dataset_binding_sha256=_sha("dataset"),
        )


def test_empirical_wrapper_omits_none_data_key_for_qlib_compatibility() -> None:
    delegate, state = _delegate_and_state()
    missing = object()

    class StrictQlibDelegate:
        def prepare(
            self,
            segment: str,
            *,
            col_set: str | list[str],
            data_key: object = missing,
        ) -> pd.DataFrame:
            if data_key is None:
                raise KeyError(None)
            return delegate.prepare(segment, col_set=col_set)

    context = _context(delegate, state, candidate="PEERLITE_K16_MSE_GATE")
    dataset, _ = build_empirical_m7_fit(
        delegate=StrictQlibDelegate(),
        state=state,
        candidate_id="PEERLITE_K16_MSE_GATE",
        context=context,
        dataset_binding_sha256=_sha("dataset"),
    )
    assert dataset.prepare("train", col_set="feature").shape[1] == 4
    assert dataset.prepare("train", col_set="market_state").shape[1] == 4
