# Public release pre-push audit

- Repository: `github.com/jonaslvhaocheng-ops/qlib-peerlite-research`
- Visibility: `PUBLIC`
- Audited at: `2026-07-29T14:19:02Z`
- Candidate source digest:
  `sha256:6d60dec06440bc120ebf6c0195d91a6aa502229a1348040088f5776992383289`

## Credential scan

`detect-secrets 1.5.0` scanned all candidate files with all
credential-specific detectors.  Hex/base64 high-entropy detectors were
disabled because immutable evidence intentionally contains thousands of
SHA-256 digests; the public-IP detector was separately handled by an explicit
pattern scan.  Excluded paths were only Git/virtual-environment/tool caches,
`mlruns`, and `uv.lock`.

Result: `{}` — no credential-specific findings.

Explicit patterns also found no private key header, GitHub/OpenAI/AWS token,
password, connection string, bearer token, or public IP address.

## Data and binary boundary

The candidate Git set contains no raw/processed Qlib market data, empirical
prediction parquet, checkpoint, private key, `.env`, behavior replay raw value,
or tracking-store file.

The only committed data binaries are:

- `evidence/qlib/analysis_mechanics_20260728_v1/synthetic_holdings.parquet`
- `evidence/qlib/analysis_mechanics_20260728_v1/synthetic_portfolio_returns.parquet`

Both are synthetic Qlib mechanics fixtures.

## Deliberate public metadata

Immutable audit evidence includes the host label `k8s-master04`, software/GPU
versions, data-vendor/table names and absolute research-server paths.  These are
provenance labels, not reachable network endpoints or credentials.  They are
retained to preserve evidence hashes and are declared in
`docs/PUBLICATION_POLICY.md`.

## Publication controls

- Proprietary/no-license-grant notice: present.
- CODEOWNERS for workflow and quality evidence: present.
- GitHub Actions permissions: `contents: read`.
- Checkout credentials: not persisted.
- All third-party Actions: pinned to immutable commits.
- Engineering-quality controller: external public repository and immutable
  commit `ecab972eb859044bb7545d43b6da8114b74b6fec`.

Verdict: `PASS` for first public push.

