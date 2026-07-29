# M6.5 R3 修复设计 v7 — 完整 staged archive replay 补充

状态：`IMPLEMENTATION_READY / 待独立设计审查`。质量变更：`m6-5-pre-m7-repair`；风险：`R3`。架构依据：`architecture_confirmation_v9.md`、`architecture_confirmation_v10.md`、`research_governance_threat_model_v1.md`。

## Canonical incorporation rule

本文件是当前 canonical change-design artifact：它逐字纳入 `m6_5_repair_change_design_v6.md` 的 SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78`，其中 §1–§5 与 §7 不变；**只有 v6 §6 被下列完整 §6 replacement 取代**。Implementation/review must treat `v6-with-this-replacement` as one contract. Nothing here authorizes M7 QRC/fit, CCC/Gate, server replay, final OOS or M6 history mutation.

## §6 replacement — Frozen archive replay input and execution transaction

`M6ReplayInputBinding v3` is frozen before execution and has closed inventories for: external transfer manifest; source archive/internal manifest/single root/tree; M6 spec/gate/close proof/historical verification/verifier; M3 product manifest and every consumed partition; M6 run manifest/candidates/14 fold receipts/every checkpoint metadata+state/every prediction partition/K16 deterministic-refit receipt; legacy read-only ledger; approved launcher/runtime; fixed argv/cwd/import policy; new output; profile 14 replay/0 fit/OOS=false. Every entry has exact relative path/SHA/bytes/schema/role. Verifier receives no caller source/product/run/checkpoint/prediction/ledger/output paths and uses only a supervisor-created sealed staged root.

Supervisor FD-hashes every bound object, copies source/verifier/runtime plus all product/run/checkpoint/prediction/manifests into a new supervisor-owned immutable staged tree, fsyncs it and records tree digest. It launches only staged bytes via staged runtime, `env -i`, fixed cwd/fixed argv, `python -I -S` and bootstrap restricted to one staged import root. Bootstrap verifies every `qlib_peerlite` import origin is inside staged tree; no mutable deployment path may enter `sys.path`.

`ReplayExecutionReceipt v2` binds input binding, staged-tree digest, verifier/runtime FD hashes, cwd/argv/environment digest, PID/start, child exit, output identity and ledger before/after. Child receipt repeats staged identities plus exact 14 checkpoint/prediction identities. `m6_archive` requires all three identities to agree. Existing output refuses; output uses new directory/atomic marker. Inventory omission/extra/substitution, post-measure verifier/runtime change, import/cwd/environment injection, staged-tree mismatch, non-bound self-consistent receipt, or ledger write are hard failures.

## Verification addition

Red and E2E matrix must include all §6 replacement failures with public synthetic CLI, then existing v6 §7 coverage/full-suite/code/test review sequence. This addition remains synthetic until the quality gate passes.
