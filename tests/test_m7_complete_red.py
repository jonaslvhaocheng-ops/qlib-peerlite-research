from __future__ import annotations

import importlib


def test_m7_complete_engineering_contract_is_available() -> None:
    """Expected-red proof for the approved complete M7 package boundary."""

    market_state = importlib.import_module("qlib_peerlite.m7.market_state")
    run_state = importlib.import_module("qlib_peerlite.m7.run_state")
    checkpoint = importlib.import_module("qlib_peerlite.m7.checkpoint")

    spec = market_state.SyntheticFixtureSpec(
        fixture_version="m7-synthetic-v1",
        seed=7,
        start_date="2000-01-03",
        trading_days=12,
        instruments=4,
        feature_count=4,
    )
    dataset, capability = market_state.build_synthetic_m7_fixture(spec)

    assert dataset.claim_ceiling == "SYNTHETIC_MECHANICS_ONLY"
    assert capability.fixture_sha256 == dataset.fixture_sha256
    assert not hasattr(run_state, "fit_call_proven_absent")
    assert checkpoint.CHECKPOINT_V2_SCHEMA == "qlib_peerlite_checkpoint_v2"
