# E2E Acceptance — RunIntent V2 Public Python Contract

- Journey ID: `M65-RUNINTENT-V2-PUBLIC`
- Risk: `R3`
- Mode: public Python API in a clean process
- Runtime: CPython 3.11 project virtual environment
- Source digest:
  `sha256:8968e7b8e172ceea730e4251cb90a8d902e46ffa406da3fb4fe47b32e950f477`
- Result: `PASS`

## Preconditions

- Synthetic nested budget and market-state authority dictionaries only.
- M7 family ID and a syntactically valid synthetic execution-spec hash.
- No filesystem output, journal, ledger, model, database, Qlib data, PIT or OOS input.

## Public entry point

The clean process imports and constructs
`qlib_peerlite.governance.trial_ledger.RunIntent`, then uses only its constructor and public properties.

## Steps and observations

1. Construct a fully bound M7 intent from nested mutable dictionaries.
2. Capture its public identity.
3. Mutate every retained caller alias.
4. Observe unchanged identity and unchanged public read-only snapshot.
5. Construct an NFC-equivalent intent and observe the same identity.
6. Attempt public snapshot mutation and observe rejection.
7. Construct an unbound M7 intent and a cyclic authority input and observe both rejections.

Command:

```text
.venv/bin/python \
  docs/quality/changes/m6-5-pre-m7-repair/evidence/run_intent_v2_acceptance.py
```

Terminal output:

```json
{"caller_alias_mutation_isolated":true,"cycle_rejected":true,"identity_sha256":"d15247c780dbf384bcbbdce80fc8bbf2c878118fa7e78eb414ebc7cc85805a8f","nfc_equivalent_identity":true,"persistent_effects":0,"schema_version":"qlib_peerlite_run_intent_v2_acceptance_v1","snapshot_read_only":true,"status":"PASS","unbound_m7_rejected":true}
```

Exit code: `0`.

## Cleanup and forbidden effects

The journey is in-memory and reports `persistent_effects: 0`; no cleanup is required. It cannot create a
journal event, consume trial budget, replay M6, call `fit`, access PIT/real data, execute CCC/Gate or open final
OOS.

## Verdict

`PASS`: every v2 class-boundary acceptance outcome and critical rejection path completed from the public Python
contract to a deterministic terminal JSON result.
