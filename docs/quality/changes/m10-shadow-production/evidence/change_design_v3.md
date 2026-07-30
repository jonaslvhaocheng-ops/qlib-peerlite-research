# Change design evidence v3

The second review findings are resolved:

- one terminal verifier now checks canonical manifest integrity, state,
  request digest, exact state-specific file inventory, symlink absence and
  every bound artifact hash before replay or index repair;
- terminal corruption fails closed and is retained;
- failures before trusted state/reservation are explicit preflight rejections
  with structured stderr and zero state mutation;
- only failures after reservation publish transactional `HALTED` evidence.

Verdict: PASS, ready for independent re-review.
