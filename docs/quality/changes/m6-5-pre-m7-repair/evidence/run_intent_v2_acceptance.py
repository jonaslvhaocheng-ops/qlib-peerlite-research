from __future__ import annotations

import json

from qlib_peerlite.governance.trial_ledger import RunIntent

FAMILY = "QLIB_PEERLITE_M7_INITIAL_SCREEN_V1"
SPEC_SHA256 = "f" * 64


budget = {
    "limits": {"candidates": 8, "fits": 60},
    "models": ["CCC", "GATE"],
    "label": "re\u0301sume\u0301",
}
state = {
    "as_of": "2026-07-28T15:00:00+08:00",
    "source": {"cafe\u0301": "known"},
}
intent = RunIntent(
    run_id="m65_public_acceptance",
    family_id=FAMILY,
    execution_spec_content_sha256=SPEC_SHA256,
    budget_limit_binding=budget,
    market_state_authority_binding=state,
)
identity_before = intent.content_sha256

budget["limits"]["candidates"] = 999
budget["models"].append("UNLISTED")
state["as_of"] = "2099-01-01T15:00:00+08:00"

assert intent.content_sha256 == identity_before
assert intent.budget_limit_binding["limits"]["candidates"] == 8
assert intent.budget_limit_binding["models"] == ("CCC", "GATE")
assert intent.market_state_authority_binding["as_of"] == "2026-07-28T15:00:00+08:00"

equivalent = RunIntent(
    run_id="m65_public_acceptance",
    family_id=FAMILY,
    execution_spec_content_sha256=SPEC_SHA256,
    budget_limit_binding={
        "limits": {"candidates": 8, "fits": 60},
        "models": ["CCC", "GATE"],
        "label": "résumé",
    },
    market_state_authority_binding={
        "as_of": "2026-07-28T15:00:00+08:00",
        "source": {"café": "known"},
    },
)
assert equivalent.content_sha256 == identity_before

snapshot_rejected_mutation = False
try:
    intent.budget_limit_binding["limits"]["candidates"] = 9
except TypeError:
    snapshot_rejected_mutation = True
assert snapshot_rejected_mutation

unbound_rejected = False
try:
    RunIntent(
        run_id="m65_public_acceptance_unbound",
        family_id=FAMILY,
        execution_spec_content_sha256=SPEC_SHA256,
    )
except TypeError:
    unbound_rejected = True
assert unbound_rejected

cycle: list[object] = []
cycle.append(cycle)
cycle_rejected = False
try:
    RunIntent(
        run_id="m65_public_acceptance_cycle",
        family_id=FAMILY,
        execution_spec_content_sha256=SPEC_SHA256,
        budget_limit_binding={"cycle": cycle},
        market_state_authority_binding={"state": "known"},
    )
except TypeError:
    cycle_rejected = True
assert cycle_rejected

print(
    json.dumps(
        {
            "schema_version": "qlib_peerlite_run_intent_v2_acceptance_v1",
            "status": "PASS",
            "identity_sha256": identity_before,
            "caller_alias_mutation_isolated": True,
            "snapshot_read_only": snapshot_rejected_mutation,
            "nfc_equivalent_identity": True,
            "unbound_m7_rejected": unbound_rejected,
            "cycle_rejected": cycle_rejected,
            "persistent_effects": 0,
        },
        sort_keys=True,
    )
)
