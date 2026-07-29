# M6.5 架构确认 v10 — Archive-only replay 的完整输入与执行闭环

状态：`PASS — bounded amendment to v9`。当前架构依据是 `architecture_confirmation_v9.md` 加本补充；本补充替代 v9 的 replay 段落，不改变研究治理威胁模型、6/44 genesis 或 M7/OOS 封印。

## 1. Complete replay input binding

`M6ReplayInputBinding v3` must lock every exact relative path, SHA, bytes, schema and logical role: external transfer manifest; source archive/internal manifest/single root/tree inventory; M6 immutable spec/gate/close proof/historical verification/approved verifier; M3 bound product manifest plus all consumed partitions; M6 run manifest/candidate list/14 fold receipts/every checkpoint metadata+state/every candidate prediction/K16 deterministic-refit receipt; legacy read-only ledger identity; approved launcher/runtime; fixed argv/cwd/import policy; new output root; and 14 replay/0 fit/OOS=false profile. It is frozen before execution. Verifier has no free source/product/run/checkpoint/prediction/ledger/output flags; it receives only sealed staged input derived from binding. Missing, extra, swapped or stale input fails even if receipt is self-consistent.

## 2. Measured bytes equal executed bytes

Supervisor opens every bound input with FD/type/hash checks, copies verifier, frozen source, product/run/checkpoint/prediction inventories and manifests into a new supervisor-owned immutable staging tree, fsyncs it and records its tree digest. It launches only staged bytes with verified staged runtime, `env -i`, fixed cwd, fixed argv, `python -I -S`, and bootstrap with a single staged import root that checks every imported `qlib_peerlite` origin remains inside staging. Mutable deployment paths never enter verifier `sys.path`.

`ReplayExecutionReceipt v2` binds binding SHA, staged-tree digest, verifier/runtime FD hashes, cwd/argv/environment digest, PID/start, child exit, output identity and ledger before/after. Child receipt repeats staged identities and exact 14 checkpoints/predictions. `m6_archive` validates binding + execution receipt + child receipt. Existing output is refused; new output publication uses atomic marker. Deployment rotation or module shadow cannot change actual replay after measurement.

## 3. Acceptance tests

Synthetic tests reject product/run/checkpoint/prediction omission/substitution/extra file; verifier/runtime change after measurement; cwd/PYTHONPATH/sitecustomize/loader injection; import origin outside staging; staged-tree mismatch; existing output; ledger mutation; and self-consistent receipt using non-bound input. Passing fake replay proves only 14/0/OOS=false, never M7/OOS eligibility.
