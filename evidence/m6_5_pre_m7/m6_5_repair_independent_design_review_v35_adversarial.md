# M6.5 v35 adversarial R3 design review

- Reviewer: `/root/m65_v24_adversarial_review`
- Mode: independent, read-only
- Subject SHA256:
  `46add10c455daf6e9c705e18dd5d2357e58a4b143ea5fd805a82195866ecd1c4`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=4 / P2=4 / P3=0`
- M7 v13: `NEEDS_CHANGES / NOT_AUTHORIZED`

## Findings

1. `P1 TRANSIENT_AND_CONTROL_CAPACITY`: payload expected cannot cover temp+final coexistence or
   reservation/marker/lease/target control entries. Separate payload and filesystem usage,
   reserve exact worst-case overhead, count sealed metadata until safely reclaimed, and perform
   floor deductions atomically under the capacity lock.
2. `P1 PAYLOAD_BIJECTION`: source, staging and final need an inode-free path/type/size/content
   projection with exact bijection; no missing, extra, rename or subset.
3. `P1 PARSER_CLOSURE`: parser ArtifactRef needs a closed manifest for entrypoint, imports/native
   dependencies, interpreter/runtime and domain-code mapping.
4. `P1 HISTORICAL_SOURCE_LINEAGE`: evidence records themselves must bind the historical source
   snapshot, locator, record hash and source clocks; compare common fields and recompute derived
   fields, permitting validated revisions.
5. `P2 TEMP_TRANSITION_TABLE`: freeze all temp/final absent/present, same/different inode/bytes
   states and crash-point recovery actions.
6. `P2 REGISTRATION_UNIQUENESS`: no-follow scan `registrations/<g20>.*`; require at most one for
   next generation and exactly one referenced registration for each committed generation.
7. `P2 ADVERSARIAL_MATRIX_GRAIN`: add explicit negative fixtures and zero-side-effect oracles for
   transient/control capacity, payload subsets, orphan registrations, parser drift and source
   revisions.
8. `P2 POINTER_COMPOSITION`: mark v34 as superseded, publish exact normative bundle path+SHA
   entries, and classify the compatibility addendum as informational or normative.

Confirmed: dual M7 qualification, purpose order, retained failed/interrupted events, PRE_LIST,
half-open intervals, future-delist behavior and the exact two merged plus fourteen singleton-fold
replay boundary remain intact. No execution was authorized or run.
