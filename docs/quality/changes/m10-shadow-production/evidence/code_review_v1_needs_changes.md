# M10 Independent Code Review — NEEDS_CHANGES

Reviewer context: `/root/m10_independent_code_review`

Reviewed source digest:
`sha256:c9d01654ce20341d9dfd8abde97b1c4ccfa518fd2c72bab7d96a47f062234169`

Verdict: `NEEDS_CHANGES`

Findings:

1. P1 — The terminal verifier accepts a self-rehashed manifest that claims
   `capability=LIVE` and `live_execution_authorized=true`. The verifier must
   enforce the exact manifest schema and the fixed shadow-only authorization
   boundary.
2. P1 — Managed state directories are checked for symlinks only once. A
   post-check directory swap can redirect later path operations outside the
   state root. State mutation must use no-follow descriptor-relative directory
   handles, with a regression race test.
3. P2 — Policy, calendar, M9 gate, and source-manifest parsing and hashing can
   observe different file bytes. Each trusted input must be captured once with
   no-follow semantics, then parsed and hashed from that same byte snapshot.
4. P2 — A timezone-naive `as_of` fails after reservation acquisition, leaving
   no terminal HALTED record. It must be rejected before any state mutation.

Checks independently replayed:

- M10 focused suite: 36 passed.
- Full suite: 227 passed.
- M10 protected line and branch coverage: 100%.
- Ruff: passed.

The structural coverage result does not close the four missing security
obligations above.
