# M8 Change Design

## Goal

Retain the interrupted M8 starts exactly once, independently prove the retained
state, close M8 as an operational HOLD, and keep final OOS unopened.

## Inputs and bindings

- frozen M8 evaluation specification and derived contract;
- exact legacy journal SHA256;
- authoritative ledger prefix at 8 candidate evaluations / 61 fit starts;
- frozen final-OOS access-log SHA256.

## State transition

The exact seven-event legacy journal is validated. Its one candidate start and
three fit starts are converted into v2 counted events. Reconciliation verifies
the historical ledger prefix under a lock and atomically appends the four
events. The resulting totals must be 9/64.

The existing reconciliation receipt makes repeated recovery fail before ledger
mutation. The independent verifier checks every retained artifact, the missing
completion receipt for the interrupted fold, the 9/64 ledger state and the
unchanged OOS prefix. Both append-only authorities are checked as historical
prefixes, so a later authorized append cannot invalidate this M8 evidence.

The original frozen v1 runner remains readable for forensic comparison, but
its public `run` entry point now rejects unconditionally before creating an
output directory, journal, candidate start or fit.

The exact originally executed runner bytes are preserved under
`evidence/m8/forensics` with the SHA256 bound by the frozen specification. A
separate closure receipt binds those bytes to the intentionally different
fail-closed live entry point; the historical spec is not rewritten.

The M8 child contract's `decisive_outcomes_seen=false` attestation is retained
as a governance defect because M7 outcomes were already known. M8 therefore
does not rely on that child as a valid pre-outcome freeze and makes no
performance or promotion conclusion.

## Failure behavior

Any hash, event order, model, seed, fold, semantic identity, ledger prefix,
budget or OOS-log mismatch fails closed. No partial prediction is evaluated.
The frozen no-retry rule closes this run; no replacement fit is authorized.

## Non-goals

- no Alpha or superiority conclusion;
- no retry, new seed, parameter change or model selection;
- no final-OOS opening;
- no production, scheduling or order integration.
