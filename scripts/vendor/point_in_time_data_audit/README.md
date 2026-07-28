# Vendored PIT executors

This directory preserves the certified fixed PIT executor as
`audit_pit_reference.py` and the exact behavior executor as
`audit_behavior.py`.

`audit_pit.py` points to the project-local `audit_pit_grouped.py`. The grouped
executor exists because the reference long-row representation exceeded the
research server's 300 GiB cgroup limit on the 82,926,250-cell training input.
It stores metadata once per rectangular sample while retaining every feature
name, value, row identifier, digest and all 17 fixed checks. Inputs that do not
satisfy the grouping preconditions fall back to the original long-row logic.

The fixed 163-case adversarial suite and the separate 18-case behavior suite
both pass against the grouped entry point. Exact hashes, the OOM trigger,
validation results and the production run are recorded in
`evidence/oss/point_in_time_data_audit/grouped_executor_receipt.json`.

This adaptation is project-local. It does not change the PIT specification,
upgrade the behavior executor beyond `NOVEL_CANDIDATE`, or prove that upstream
vendor and population authorities are complete.
