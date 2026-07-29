from __future__ import annotations

import pytest

from qlib_peerlite.governance.trial_ledger import RunIntent


def test_m7_initial_screen_run_intent_requires_both_frozen_authorities() -> None:
    """RI-U1: an M7 intent cannot omit both frozen authorities."""

    with pytest.raises(TypeError):
        RunIntent(
            run_id="m7_unbound_expected_red",
            family_id="QLIB_PEERLITE_M7_INITIAL_SCREEN_V1",
            execution_spec_content_sha256="a" * 64,
        )


def test_run_intent_v2_owns_an_immutable_nested_authority_snapshot() -> None:
    """RI-U3: caller mutation cannot change one already-constructed identity."""

    budget = {"limits": {"candidates": 8}, "models": ["CCC", "GATE"]}
    market_state = {"as_of": "2026-07-28T15:00:00+08:00"}
    intent = RunIntent(
        run_id="m7_mutable_binding_expected_red",
        family_id="QLIB_PEERLITE_M7_INITIAL_SCREEN_V1",
        execution_spec_content_sha256="a" * 64,
        budget_limit_binding=budget,
        market_state_authority_binding=market_state,
    )
    identity_before_mutation = intent.content_sha256

    budget["limits"]["candidates"] = 9
    budget["models"].append("UNLISTED")
    market_state["as_of"] = "2026-07-29T15:00:00+08:00"

    assert intent.content_sha256 == identity_before_mutation
    assert intent.budget_limit_binding["limits"]["candidates"] == 8
    assert intent.budget_limit_binding["models"] == ("CCC", "GATE")
    assert (
        intent.market_state_authority_binding["as_of"]
        == "2026-07-28T15:00:00+08:00"
    )
