# M9 Change Design

## Goal

Close step nine with the strongest conclusion supported after the M8 retained
failure and the official rejection of a truthful reauthorization contract.

## Invariants

- Never rewrite or retry M8.
- Never change `decisive_outcomes_seen` back to false.
- Never train under a planned or failed contract.
- Never open or reuse the historical final OOS.
- Keep the authoritative trial ledger at 9 candidate evaluations and 64 fit
  starts.
- Keep final-OOS access count and selection uses at zero.
- Do not promote PeerLite or make an Alpha claim.

## Terminal behavior

The official contract rejection is retained as evidence. The project gate
closes as `HOLD_REAUTHORIZATION_CONTRACT_INVALID`; future work is a new research
cycle with a consistent child contract and disjoint prospectively accrued OOS,
not a retry. The closure does not claim that such a future path is impossible.

Design verdict: `PASS`.
