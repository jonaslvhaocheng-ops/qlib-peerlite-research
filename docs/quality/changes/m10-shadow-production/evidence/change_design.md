# Change design evidence

- Risk tier: R3 because a production-shaped interface must never create a live
  trading path.
- Selected approach: in-process, fail-closed, local shadow control plane.
- Rejected: workflow/broker integration and documentation-only delivery.
- Scope, interfaces, state transitions, failure behavior, concurrency,
  rollback, observability and security are fixed in
  `docs/m10/CHANGE_DESIGN.md`.
- Verdict: PASS.
