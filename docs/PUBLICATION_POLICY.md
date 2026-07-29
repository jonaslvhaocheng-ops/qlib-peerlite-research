# Public repository boundary

## Status

This repository is public and source-available for research transparency.  It
is not an open-source license grant.  See `LICENSE`.

The public release contains framework code, frozen research contracts,
manifests, hashes, synthetic fixtures, audit evidence and model-evaluation
receipts through M6.5.  It does not claim a production trading system or a
validated M7 Alpha result.

## Excluded material

The following material must never be committed:

- credentials, private keys, tokens, connection strings or `.env` files;
- raw or processed licensed market data;
- empirical prediction matrices;
- learned checkpoints or training-fold preprocessing values;
- live tracking stores;
- final-OOS data or outputs;
- private communications or personal contact/payment identifiers.

The repository `.gitignore` enforces the principal data, checkpoint, tracking
and secret exclusions.  CI and pre-push review must still inspect the actual
candidate tree.

## Deliberately retained metadata

Audit receipts retain data-vendor/table names, software and GPU versions,
research-server host labels, and absolute research-server paths.  These values
are provenance metadata, not network endpoints or credentials.  They are
intentionally public because removing them would break immutable evidence
hashes.  No IP address, password, token, SSH key or database connection string
is included.

Public DataYes dictionary excerpts and table/field identifiers are retained as
source-attribution and schema evidence.  Raw DataYes market values are excluded.

## First-publication checks

Before the first push:

1. run credential-specific secret scanning on all candidate files;
2. list candidate binary/data files and verify that every retained file is a
   synthetic fixture;
3. verify GitHub visibility and minimal Actions permissions;
4. pin third-party Actions and the engineering-quality controller to immutable
   commits;
5. run the complete tests, Ruff, M6 archival-evidence tests and canonical
   M6.5 pre-merge ledger check;
6. retain the result under the M6.5 quality evidence.

Any future relaxation of this boundary requires an explicit reviewed change.

