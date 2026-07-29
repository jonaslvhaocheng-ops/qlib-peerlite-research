from __future__ import annotations

import inspect
import math
from collections import UserDict
from collections.abc import Mapping
from typing import Any, get_type_hints

import pytest

from qlib_peerlite.governance.trial_ledger import RunIntent

M7_FAMILY = "QLIB_PEERLITE_M7_INITIAL_SCREEN_V1"
V1_KNOWN_SHA256 = "9871f3ff1e9b35cb93f80e4ae54cdbc96eb4573bbb202098280a96a9e87abccb"
V2_KNOWN_SHA256 = "efef1bb588aac9ed37befdf411b2db872a46c35ac364338a2055454452d2f362"


def _budget_binding() -> dict[str, Any]:
    return {
        "limits": {"candidates": 8, "fits": 60},
        "models": ["CCC", "GATE"],
        "enabled": True,
        "note": None,
        "ratio": 0.5,
    }


def _state_binding() -> dict[str, Any]:
    return {
        "as_of": "2026-07-28T15:00:00+08:00",
        "source": {"name": "状态", "version": 1},
    }


def _intent(
    *,
    budget: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> RunIntent:
    return RunIntent(
        run_id="m7_v2_contract",
        family_id=M7_FAMILY,
        execution_spec_content_sha256="c" * 64,
        budget_limit_binding=_budget_binding() if budget is None else budget,
        market_state_authority_binding=_state_binding() if state is None else state,
    )


@pytest.mark.parametrize(
    ("budget", "state"),
    [
        (None, _state_binding()),
        (_budget_binding(), None),
        ("not-a-dict", _state_binding()),
        (_budget_binding(), "not-a-dict"),
    ],
)
def test_m7_authority_bindings_are_paired_top_level_dicts(
    budget: object,
    state: object,
) -> None:
    with pytest.raises(TypeError):
        RunIntent(
            run_id="m7_invalid_binding",
            family_id=M7_FAMILY,
            execution_spec_content_sha256="c" * 64,
            budget_limit_binding=budget,  # type: ignore[arg-type]
            market_state_authority_binding=state,  # type: ignore[arg-type]
        )


def test_v2_identity_matches_independent_known_hash_and_is_cached() -> None:
    intent = _intent()

    assert intent.content_sha256 == V2_KNOWN_SHA256
    assert intent.content_sha256 == V2_KNOWN_SHA256


def test_caller_owned_nested_mutation_cannot_change_snapshot_or_hash() -> None:
    budget = _budget_binding()
    state = _state_binding()
    intent = _intent(budget=budget, state=state)

    budget["limits"]["candidates"] = 99
    budget["models"].append("UNLISTED")
    state["source"]["version"] = 2

    assert intent.content_sha256 == V2_KNOWN_SHA256
    assert intent.budget_limit_binding["limits"]["candidates"] == 8
    assert intent.budget_limit_binding["models"] == ("CCC", "GATE")
    assert intent.market_state_authority_binding["source"]["version"] == 1


def test_exposed_v2_snapshot_is_recursively_read_only() -> None:
    intent = _intent()
    assert isinstance(intent.budget_limit_binding, Mapping)

    with pytest.raises(TypeError):
        intent.budget_limit_binding["new"] = "forbidden"
    with pytest.raises(TypeError):
        intent.budget_limit_binding["limits"]["candidates"] = 9
    with pytest.raises(TypeError):
        intent.budget_limit_binding["models"][0] = "OTHER"
    with pytest.raises(AttributeError):
        intent.budget_limit_binding["models"].append("OTHER")

    assert intent.content_sha256 == V2_KNOWN_SHA256


def test_recursive_nfc_equivalence_produces_one_snapshot_and_identity() -> None:
    decomposed_key = "cafe\u0301"
    decomposed_value = "re\u0301sume\u0301"
    composed_key = "café"
    composed_value = "résumé"
    first = _intent(
        budget={"nested": {decomposed_key: decomposed_value}},
        state={"label": decomposed_value},
    )
    second = _intent(
        budget={"nested": {composed_key: composed_value}},
        state={"label": composed_value},
    )

    assert first.content_sha256 == second.content_sha256
    assert first.budget_limit_binding["nested"][composed_key] == composed_value
    assert decomposed_key not in first.budget_limit_binding["nested"]
    assert first.market_state_authority_binding["label"] == composed_value


def test_nfc_key_collision_is_rejected_at_construction() -> None:
    with pytest.raises(TypeError, match="collision"):
        _intent(budget={"é": 1, "e\u0301": 2})


@pytest.mark.parametrize(
    "bad_value",
    [
        ("tuple",),
        {"set"},
        b"bytes",
        UserDict({"custom": "mapping"}),
        object(),
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_non_json_or_nonfinite_nested_values_fail_at_construction(
    bad_value: object,
) -> None:
    with pytest.raises(TypeError):
        _intent(budget={"bad": bad_value})


def test_non_string_nested_key_fails_at_construction() -> None:
    with pytest.raises(TypeError):
        _intent(budget={"nested": {1: "bad"}})


def test_direct_and_indirect_cycles_fail_at_construction() -> None:
    direct: dict[str, Any] = {}
    direct["self"] = direct
    with pytest.raises(TypeError, match="cycle"):
        _intent(budget=direct)

    first: dict[str, Any] = {}
    second: dict[str, Any] = {"first": first}
    first["second"] = second
    with pytest.raises(TypeError, match="cycle"):
        _intent(budget=first)


def test_repeated_noncyclic_child_is_valid() -> None:
    shared = {"value": 1}
    intent = _intent(budget={"left": shared, "right": shared})

    assert intent.budget_limit_binding["left"]["value"] == 1
    assert intent.budget_limit_binding["right"]["value"] == 1


def test_each_authority_materially_contributes_to_v2_identity() -> None:
    baseline = _intent().content_sha256
    changed_budget = _budget_binding()
    changed_budget["limits"]["candidates"] = 9
    changed_state = _state_binding()
    changed_state["source"]["version"] = 2

    assert _intent(budget=changed_budget).content_sha256 != baseline
    assert _intent(state=changed_state).content_sha256 != baseline


def test_historical_unbound_non_m7_v1_identity_is_byte_compatible() -> None:
    intent = RunIntent(
        run_id="m7_ccc_20260728_v1",
        family_id="qlib-peerlite-a-share-daily-v0",
        execution_spec_content_sha256="a" * 64,
    )

    assert intent.content_sha256 == V1_KNOWN_SHA256


def test_constructor_declares_exact_dict_inputs_and_exposes_read_only_mappings() -> None:
    constructor_hints = get_type_hints(RunIntent.__init__)

    assert constructor_hints["budget_limit_binding"] == dict[str, Any] | None
    assert (
        constructor_hints["market_state_authority_binding"]
        == dict[str, Any] | None
    )
    assert isinstance(
        inspect.getattr_static(RunIntent, "budget_limit_binding"),
        property,
    )
    assert isinstance(
        inspect.getattr_static(RunIntent, "market_state_authority_binding"),
        property,
    )
    assert (
        get_type_hints(RunIntent.budget_limit_binding.fget)["return"]
        == Mapping[str, Any] | None
    )
    assert (
        get_type_hints(RunIntent.market_state_authority_binding.fget)["return"]
        == Mapping[str, Any] | None
    )
