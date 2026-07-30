# M10 Security Hardening Implementation

Source digest:
`sha256:80550e913f9011649cffb2b8af3838073069885fd0422ace93d708215d2f26b7`

The independent-review findings were addressed without expanding the M10
scientific or operational scope:

- Terminal manifests now have an exact schema and must explicitly remain
  `SHADOW_ONLY` with `live_execution_authorized=false`.
- State-root mutations use no-follow, descriptor-relative operations against
  pinned managed-directory handles. Namespace bindings are revalidated before
  transactional writes and publication.
- Policy, M9 gate, calendar, and source manifest are each captured once as
  bounded regular-file byte snapshots. Parsing, authorization, and hashing use
  those same bytes.
- Timezone-naive `as_of` values are rejected before any state-root access or
  mutation.
- Focused regression tests cover forged authorization, managed-path swaps,
  source-manifest TOCTOU, pre-mutation time rejection, descriptor failures,
  stale reservations, unsafe existing state, and immutable input bounds.
- A pinned M10 GitHub Actions gate enforces ledger validation, static checks,
  the full suite, exact M10 line/branch coverage, and the absence of live
  execution authorization.
- State roots are current-user owned, non-group/world-writable, and held under
  a nonblocking exclusive process lock for the full cycle. Publication checks
  bindings inside the transaction and uses platform-native atomic no-replace.
- The final M10 gate and status documents bind the completed engineering result
  while retaining M9 HOLD, zero final-OOS access, and no live authorization.

Verification at this implementation checkpoint:

- Ruff: passed.
- M10 focused suite: 50 passed.
- Full suite: 241 passed.
