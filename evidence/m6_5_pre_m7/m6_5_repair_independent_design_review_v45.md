# M6.5 v45 Independent Design Review

- Reviewer context: `/root/m65_v25_design_review`
- Independence: independent agent; read-only
- Subject SHA-256: `5eeb0350583d349f27f8eddb55c9fa502681dc74e7323020f83512cee1d066d3`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=4 / P2=2 / P3=0`

## Findings

1. Add frozen code/archive/tree identity to the static M6 authority; the static verifier cannot rely on an
   unbound source identity.
2. Make an existing receipt immutable across later legal ledger suffixes, and define original-commit versus
   recovery-observation counts and events.
3. Replace nondeterministic checkpoint-file-byte equality with a canonical state-dict and metadata digest.
4. Extend no-fit closure to private aliases, saved references and wrappers across all loaded frozen project
   modules.
5. Validate every journal event against the exact external candidate, seed, evaluation and fit-ID roster,
   not only the 8/60 totals.
6. Freeze revision-coverage field encodings, signed-zero handling and nonfinite intermediate failure.

The v45 closure hashes, three binding content hashes, stable sidecar direction, T-known state binding,
external replay identity, one-date-per-step CCC and screen-only boundary otherwise pass.
