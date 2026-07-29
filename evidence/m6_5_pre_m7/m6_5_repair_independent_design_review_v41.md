# M6.5 v41 Independent Design Review

- Reviewer context: `/root/m65_v25_design_review`
- Independence: independent agent; read-only; no file or ledger mutation
- Subject: `m6_5_repair_change_design_v41.md`
- Subject SHA-256: `a9724a5dc98a27710f7724aa306e25dd710b3135fa12133a56b1bbf8ae3ead4f`
- Verdict: `NEEDS_CHANGES`
- Severity count: `P0=0 / P1=4 / P2=1`

## Findings

1. **P1 — obsolete storage policy.** `score_replay_plan_v2.md` binds
   `RuntimeStoragePolicyV2`, while Capacity V11 requires the recursively current V5 policy. The plan,
   reservation and receipts must repeat one V5 ref and the replay target must be one policy target parent.
2. **P1 — output manifest has no fixed transactional slot.** The pair receipt contains an output manifest
   but the plan neither freezes its slot nor states that raw parquet and manifest are committed in one
   payload. Recovery cannot reconstruct unique receipt bytes.
3. **P1 — CUDA-only has no evidence object.** A self-reported `fit_count=0` and prose CUDA condition cannot
   prove the selected device, runtime, code closure or absence of fit calls. Add an exact execution receipt.
4. **P1 — OUTPUT FD to final ArtifactRef has a TOCTOU gap.** Require default-deny for unlisted write
   mechanisms, same-FD final hashes and digests, fsync/mode seal, and final path-to-device/inode equality.
5. **P2 — completion slot wording is stale.** The plan calls PUBLISH_COMPLETE a payload location even
   though Nested Recovery V4 makes it a sibling. Freeze the exact sibling formula.

## Closed items

Event-local typed refs, inner schema equality and the acyclic bytes-to-checkpoint-to-receipt DAG pass.
Continuous flock wording, LP execution identity, digest-derived receipt directory, reference classes,
matrix Base path, observation evidence, M6 `6/44` and all no-execution boundaries are preserved.

Passing a repaired design would authorize only synthetic test design.
