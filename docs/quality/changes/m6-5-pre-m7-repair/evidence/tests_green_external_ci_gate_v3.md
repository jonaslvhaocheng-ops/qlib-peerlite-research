# External CI full-history test evidence

Source digest: `sha256:e4437de3fd16910b3ef5b298db094b164f4f9c543d3fc52eea0727f148d0fb9b`

## Results

- Complete repository suite: `86 passed`.
- M6 archival evidence and replay subset: `7 passed`.
- Ruff over self-authored source, tests, and scripts: `PASS`.
- Workflow contract: `PASS`.

The workflow contract proves that the primary checkout has `fetch-depth: 0`, credentials remain non-persistent, every Action reference is a 40-character commit, the canonical `check-ci --pre-merge` command remains active, and the M6 archival tests remain explicitly present.

No M7 training or final-OOS access occurred.
