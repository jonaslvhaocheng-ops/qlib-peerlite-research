# M10 End-to-End Acceptance

Source digest:
`sha256:80550e913f9011649cffb2b8af3838073069885fd0422ace93d708215d2f26b7`

Verdict: `PASS`

Accepted journeys:

1. `shadow-cycle`
   - The shipped policy preflight returns `SHADOW_ONLY`.
   - A deterministic synthetic score cross-section reaches `COMPLETE`.
   - Replay, monitoring, paper intents, root locking, binding checks, and
     terminal no-replace behavior pass.
2. `live-order-rejection`
   - A live execution policy is rejected with a structured error.
   - A forged LIVE terminal is rejected.
   - No live execution adapter or operational connection is present.
3. `fail-closed-races`
   - A managed-directory move does not leave an external terminal.
   - An existing empty terminal is retained and blocks publication.

The journey is strictly local, synthetic, and paper-only. It does not claim
Alpha, production authorization, real-data signal validity, or broker readiness.
