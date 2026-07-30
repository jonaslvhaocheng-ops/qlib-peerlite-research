# M9 Test Design

The test matrix covers:

1. Exact hashes for proposed changes, change request and planned contract.
2. Exact official validator failure codes and stop-before-training decision.
3. Canonical terminal-gate hash.
4. Exact bindings to M8 gate, validation receipt, trial ledger and OOS log.
5. Terminal state is completed `HOLD`, never `PASS`.
6. Zero new candidate evaluations, fit starts and OOS accesses.
7. The sole OOS-log event remains its untouched initialization record.
8. Expected-red probe exits nonzero when a rejected contract is presented as an
   authorization surface.

Test-design verdict: `PASS`.
