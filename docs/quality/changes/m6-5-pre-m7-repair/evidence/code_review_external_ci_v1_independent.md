# Independent code review — M6.5 external CI v1

- Reviewer context: `/root/m65_v25_design_review`
- Author context: `/root`
- Base: `82f19ec05deef809d5321568ef7b9aa279c384f6`
- Source digest: `sha256:d7a2c063201eed111716cc3a0b57ecf5e8ebd72fd698c1f583903995482f2fde`
- Verdict: `NEEDS_CHANGES`
- Findings: `P0=0 / P1=2 / P2=2 / P3=1`

## [P1] External CI must fail at M6 archival replay

Location: `.github/workflows/m65-external-quality-gate.yml:48`

The workflow invokes the server replay CLI with no arguments.  That CLI
requires nine bound asset arguments and exits `2` on a clean runner.  The
existing workflow-text assertion does not execute the failing command and is a
false positive.

Direction: on GitHub clean runners, execute the archived-evidence and
replay-mechanics tests:

```text
uv run pytest -q tests/test_m6_evidence.py tests/test_m6_archive.py tests/test_m6_archival_replay_script.py
```

True checkpoint replay remains an authorized-server operation with its bound
assets and is not replaced by CI.

## [P1] Public release state is not consistently governed

Locations:

- `docs/quality/changes/m6-5-pre-m7-repair/evidence/repository_identity_migration_20260729.md:8`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/implementation_external_ci_gate.md:8`
- `pyproject.toml:11`

The repository is now public, but earlier migration evidence records its
creation-time private state, and the candidate tree includes infrastructure
path metadata while declaring proprietary research code.

Direction: record the explicit public decision and credential scan; state the
no-license-grant publication policy; identify permitted infrastructure metadata
and confirm that raw vendor data, credentials, keys, checkpoints and final OOS
outputs are excluded before the first push.

## [P2] Third-party Actions use mutable major tags

Location: `.github/workflows/m65-external-quality-gate.yml:22`

Pin checkout, setup-python and setup-uv to immutable commits.  Preserve
`contents: read` and `persist-credentials: false`.

## [P2] The custom verifier trusts same-PR mutable quality evidence

Locations:

- `docs/quality/changes/m6-5-pre-m7-repair/evidence/ci_verify_m65.py:31`
- `docs/quality/changes/m6-5-pre-m7-repair/evidence/ci_verify_m65.py:153`

The custom verifier does not fully validate latest-run/stage/subject/evidence
consistency, and its own excluded location permits same-PR weakening.

Direction: use the canonical engineering-quality controller at an immutable
external commit and later make its required check part of main-branch
protection.

## [P3] The custom digest is not a complete canonical implementation

Location: `docs/quality/changes/m6-5-pre-m7-repair/evidence/ci_verify_m65.py:59`

The current no-submodule checkout produces the right digest, but gitlink,
symlink, executable-bit and non-UTF-8 handling are not exact.

Direction: remove the duplicate implementation and invoke the canonical
controller.

## Positive evidence

- Current canonical and custom digests agree.
- Workflow permissions are read-only and checkout credentials are not
  persisted.
- No M7, CCC, Gate, training, real-data, budget or final-OOS command exists in
  the workflow.
- Credential-specific `detect-secrets` scan returned an empty result set.

No files were modified by the independent reviewer.

