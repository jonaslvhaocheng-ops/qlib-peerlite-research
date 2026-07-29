# M7 adapter coverage repair

- Status: `READY FOR INDEPENDENT REVIEW`
- Parent design:
  `change_design_v5_code_review_repairs.md`
- Trigger:
  `M7_ADAPTER_COVERAGE_NOT_MECHANICALLY_FROZEN`

## Decision

Add `src/qlib_peerlite/m7/adapter.py` and move every M7-specific PeerLite
policy branch into it:

- exact candidate recognition;
- frozen candidate configuration validation;
- synthetic capability/dataset authorization;
- synthetic checkpoint context creation;
- prediction dataset/binding validation;
- v1/v2 schema/model dispatch and v2 header validation.

`models.peerlite` may call these functions and retain M6 training mechanics,
but it may not contain a parallel candidate/authority/checkpoint policy.

Because `.engineering-quality/coverage-policy.json` inventories every `.py`
under `src/qlib_peerlite/m7`, the new adapter is automatically part of the
protected authored denominator. The exact requirement remains:

```text
all m7 files observed
line = 100%
branch = 100%
omit/exclude = none
```

There is no changed-line fallback, manually declared branch list, coverage
exception or review-only substitute.

## Verification

- mutation tests change each frozen candidate field;
- exact-type tests cover capability, dataset and lookalike rejection;
- v1/v2/unknown/mixed checkpoint dispatch covers every branch;
- the controller raw report must list `m7/adapter.py`;
- independent review confirms no duplicate M7 policy remains in PeerLite.

## Verdict

`PASS / READY FOR INDEPENDENT R3 REVIEW`

