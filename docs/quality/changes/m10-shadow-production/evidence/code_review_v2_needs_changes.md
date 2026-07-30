# M10 Independent Code Re-review — NEEDS_CHANGES

Reviewer context: `/root/m10_independent_code_review`

Reviewed source digest:
`sha256:c3f0db7db40a34036587a2d112324412337c5713978f15383c7e28b0036ff33b`

Verdict: `NEEDS_CHANGES`

Closed from the first review:

- Forged LIVE/self-hashed terminal manifests are rejected.
- Trusted policy, gate, calendar, and source-manifest content is snapshot-bound.
- Timezone-naive `as_of` is rejected before state access.

Remaining findings:

1. P1 — A managed directory moved after the last binding check can still
   receive writes through its open descriptor before the later check detects
   the move. Add an enforceable trusted-root locking/ownership contract and an
   in-publication binding check.
2. P2 — POSIX directory rename can overwrite an existing empty terminal
   directory. Publication must use atomic no-replace semantics.
3. P2 — A hash-valid M9 gate containing a JSON list raises `AttributeError`
   instead of the structured `M9_GATE_INVALID` error.

Independent replay:

- M10 focused suite: 46 passed.
- M10 line and branch coverage: 100%.
- Full suite during the review: 236 passed, 1 failed because the active quality
  ledger was being rebound to the newly added workflow digest.
