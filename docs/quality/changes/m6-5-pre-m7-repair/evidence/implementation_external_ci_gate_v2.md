# M6.5 external CI gate implementation v2

The first independent review's two P1 and two P2 findings are repaired:

1. The impossible no-argument server replay command is replaced by seven
   clean-checkout archival-evidence and replay-mechanics tests.
2. Public visibility is governed by a source-available/no-license-grant notice,
   explicit publication boundary, CODEOWNERS and a clean pre-push credential
   scan.
3. Every third-party Action is pinned to an immutable commit, and `uv` is fixed
   to `0.11.14`.
4. The custom same-PR verifier and incomplete digest duplication are removed.
   CI checks out the canonical engineering-quality controller from immutable
   commit `ecab972eb859044bb7545d43b6da8114b74b6fec` under the excluded quality
   namespace and runs its `check-ci --pre-merge` gate.

Local evidence:

- workflow contract: PASS;
- M6 archive tests: `7 passed`;
- complete suite: `86 passed`;
- project Ruff: PASS;
- canonical ledger validation: PASS;
- credential-specific public-release scan: no findings;
- diff whitespace check: PASS.

No M7 candidate, fit, budget, training data or final-OOS state was accessed.

