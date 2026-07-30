# Change design evidence v2

The design now resolves every independent-review finding:

- the terminal cycle-directory rename is the sole commit point;
- exclusive reservations, stale takeover and post-rename index repair define
  all concurrency/crash states;
- one cross-section is bound to one pinned calendar session, session close,
  schedule cutoff and manifest prediction time;
- cycle IDs, path containment, symlink rejection and immutable single-read
  prediction bytes define the filesystem trust boundary;
- pre-parse byte/row limits, post-parse cardinality limits and the
  `SYNTH_*` instrument namespace enforce the synthetic/resource ceiling.

Verdict: PASS, ready for independent re-review.
