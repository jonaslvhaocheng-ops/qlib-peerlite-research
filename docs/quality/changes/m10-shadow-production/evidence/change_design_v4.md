# Change design evidence v4

The third review findings are resolved:

- `alert.json` exists only inside the terminal cycle staging/commit boundary;
- there is no top-level alert path or second alert commit point;
- the idempotency index has a fixed schema and is validated before reservation;
- malformed, orphaned and mismatched indexes fail closed and remain unchanged;
- creation is exclusive/no-overwrite;
- repair is permitted only from a fully verified committed terminal when no
  index exists.

Verdict: PASS, ready for independent re-review.
