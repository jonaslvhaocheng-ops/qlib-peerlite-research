from __future__ import annotations

from typing import Any

import pytest

from qlib_peerlite.governance.trial_ledger import RunIntent


def test_v2_rejects_a_self_referential_json_list() -> None:
    cycle: list[Any] = []
    cycle.append(cycle)

    with pytest.raises(TypeError, match="cycle"):
        RunIntent(
            run_id="m7_list_cycle",
            family_id="QLIB_PEERLITE_M7_INITIAL_SCREEN_V1",
            execution_spec_content_sha256="d" * 64,
            budget_limit_binding={"cycle": cycle},
            market_state_authority_binding={"state": "known"},
        )


def test_non_m7_intent_still_rejects_a_partial_authority_pair() -> None:
    with pytest.raises(TypeError, match="supplied together"):
        RunIntent(
            run_id="non_m7_partial",
            family_id="historical-non-m7-family",
            execution_spec_content_sha256="e" * 64,
            budget_limit_binding={"budget": "present"},
        )
