# M6.5 repository identity migration

- Timestamp (UTC): `2026-07-29T14:06:55Z`
- Change ID: `m6-5-pre-m7-repair`
- Previous identity: `local:qlib模型框架`
- New identity: `github.com/jonaslvhaocheng-ops/qlib-peerlite-research`
- Remote: `git@github.com:jonaslvhaocheng-ops/qlib-peerlite-research.git`
- Visibility at creation: private
- Current visibility before first push: public, by explicit user instruction
- Baseline commit preserved: `82f19ec05deef809d5321568ef7b9aa279c384f6`

The identity changed only because the previously local repository received its
first authoritative GitHub remote for the independent external CI gate.  It was
created privately and changed to public before any push.  The public release
boundary and pre-push scan are recorded separately.  No research contract,
model, dataset, trial budget, or M7 execution state changed.  The source digest
is intentionally refreshed after the CI workflow is added, and all
source-bound stages are rerun according to the quality router.
