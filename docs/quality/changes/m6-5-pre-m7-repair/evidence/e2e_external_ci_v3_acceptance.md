# External CI full-history end-to-end acceptance

Source digest: `sha256:e4437de3fd16910b3ef5b298db094b164f4f9c543d3fc52eea0727f148d0fb9b`

## Public-boundary acceptance

The clean-process RunIntent acceptance script returned `PASS`:

- caller alias mutation isolated;
- cyclic authority input rejected;
- NFC-equivalent identity stable;
- snapshots read-only;
- unbound M7 request rejected;
- persistent effects: `0`.

## Historical-boundary acceptance

The M6 evidence, archive, and replay-mechanics subset returned `7 passed`. The external workflow now retrieves the history these tests require rather than weakening their commit-bound checks.

No M7 dispatch, fit, budget mutation, real-data access, portfolio execution, selection, or final-OOS access occurred.
