# M6.5 external CI v2 — E2E acceptance

## Journey 1: public M7 RunIntent boundary

- Entry point:
  `python docs/quality/changes/m6-5-pre-m7-repair/evidence/run_intent_v2_acceptance.py`
- Expected: bound intent is deterministic and immutable; unbound/cyclic input
  is rejected; no persistent effect.
- Actual: `PASS`, `persistent_effects=0`, caller alias mutation isolated,
  snapshot read-only, NFC-equivalent identity, unbound M7 rejected, cycle
  rejected.
- Cleanup: none required.

This validates the public pre-execution boundary only.  It does not dispatch a
candidate or fit.

## Journey 2: clean-checkout M6 archive boundary

- Entry point:
  `pytest -q tests/test_m6_evidence.py tests/test_m6_archive.py
  tests/test_m6_archival_replay_script.py`
- Expected: frozen M6 gate, ledger prefixes, server replay receipt, negative
  tamper case and replay helper mechanics all verify without server assets or
  mutation.
- Actual: `7 passed`.
- Cleanup: pytest temporary directories only.

## Result

- Source digest:
  `sha256:6d60dec06440bc120ebf6c0195d91a6aa502229a1348040088f5776992383289`
- M7 candidates/fits dispatched: `0 / 0`
- Trial budget mutation: none
- Real-data access: none
- Final-OOS access: none
- Verdict: `PASS`

