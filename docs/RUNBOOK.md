# Runbook

## 1. Environment

```bash
uv python install 3.11
uv sync --extra dev
uv run qlib-peerlite environment-report --output evidence/environment/local.json
uv run pytest
```

The server uses the approved connector documented outside this project. Never
print `.env`, passwords or connection strings.

## 2. Source certificate

Upload `scripts/server/source_certificate.py` to the research server and run it
inside `/home/lvhc/abama/研究沙盒`. The script is read-only and emits JSON/Markdown.

```bash
uv run python source_certificate.py \
  --output-dir /home/lvhc/abama/研究沙盒/qlib_peerlite_source_certificate
```

Pull the resulting directory into `evidence/data_sources/`. Review the exact
columns and source locators. A readable table is not a PIT pass.

Freeze the matching public DataYes dictionary responses:

```bash
uv run python scripts/fetch_datayes_official_dictionary.py \
  --output-dir evidence/data_sources/datayes_public_dictionary_<run-id>
```

Build the source snapshot only through the sealed ingestion path. The command
does not print source values or compute labels/metrics:

```bash
uv run python scripts/server/build_sealed_source_snapshot.py \
  --output-dir data/raw/snapshots/source_snapshot_<run-id>

uv run python scripts/server/verify_sealed_source_snapshot.py \
  --snapshot-dir data/raw/snapshots/source_snapshot_<run-id> \
  --output-dir evidence/data_sources/sealed_snapshot_verify_<run-id>
```

The source snapshot remains `SEALED_NOT_PIT_QUALIFIED`; a hash pass is not a PIT
pass. Follow `contracts/oos_sealed_ingestion_policy.json`.

## 3. Research contract

The planned contract remains editable:

```bash
python /Users/jonas/.codex/skills/quant-research-contract/scripts/validate_contract.py \
  contracts/planned_contract.json
```

Only after source evidence is complete:

```bash
python /Users/jonas/.codex/skills/quant-research-contract/scripts/canonicalize_and_hash.py \
  freeze contracts/planned_contract.json \
  --output contracts/immutable/research_contract.json

python /Users/jonas/.codex/skills/quant-research-contract/scripts/validate_contract.py \
  contracts/immutable/research_contract.json \
  --strict \
  --receipt contracts/immutable/contract_validation.json
```

Never overwrite a frozen artifact.

## 4. PIT gate

PIT certification uses the installed official executor. Its output directory
must be new and empty. Runtime trust-anchor hashes must come from governance
outside the audit request.

```bash
python /Users/jonas/.codex/skills/point-in-time-data-audit/scripts/audit_pit.py \
  evidence/pit/audit_request.json \
  --output-dir evidence/pit/runs/<new-run-id> \
  --trusted-review-authority-sha256 <governance-hash> \
  --trusted-semantic-review-receipt-sha256 <governance-hash>
```

For derived features, run the separate behavior audit only after the parent
fixed PIT audit passes.

## 5. Real-data enablement

Empirical commands must refuse to run unless all of the following hold:

- `QLIB_PEERLITE_ALLOW_EMPIRICAL=true`
- frozen contract and strict receipt exist and verify
- PIT manifest is production `PASS/QUALIFIED`
- derived-feature behavior manifest is `PASS`
- input manifest hashes match the configured dataset

Synthetic mechanics never satisfy these requirements.
