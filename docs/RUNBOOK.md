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

The full consumed-value view has 82,926,250 long-form cells. The certified
reference executor is preserved at
`scripts/vendor/point_in_time_data_audit/audit_pit_reference.py`; it exceeded
the server's 300 GiB cgroup limit on this input. The default vendored entry
point is therefore the separately hash-pinned grouped exact executor. It keeps
all feature cells and 17 checks, and only collapses metadata repeated within a
rectangular sample.

```bash
python scripts/vendor/point_in_time_data_audit/audit_pit.py \
  evidence/pit/audit_request.json \
  --output-dir evidence/pit/runs/<new-run-id> \
  --trusted-review-authority-sha256 <governance-hash> \
  --trusted-semantic-review-receipt-sha256 <governance-hash>
```

Before production use of the grouped executor:

```bash
python scripts/vendor/point_in_time_data_audit/run_tests.py
python scripts/vendor/point_in_time_data_audit/run_behavior_tests.py
```

Expected results are fixed suite `163/163` and behavior suite `18/18`.
The adaptation receipt is
`evidence/oss/point_in_time_data_audit/grouped_executor_receipt.json`.

For derived features, build and audit the separate real-pipeline behavior pair
only after the parent fixed PIT audit passes:

```bash
python scripts/server/build_pit_behavior_package.py \
  --snapshot-dir data/raw/snapshots/source_snapshot_20260728_v1 \
  --data-product-dir data/processed/pit_data_product_2012_2024_v3 \
  --parent-audit-manifest evidence/pit/audits/pit_full_2012_2024_v2/audit_manifest.json \
  --feature-source src/qlib_peerlite/data/features.py \
  --schema-source src/qlib_peerlite/data/schema.py \
  --output-dir evidence/pit/behavior/packages/<new-run-id>

python scripts/vendor/point_in_time_data_audit/audit_behavior.py \
  evidence/pit/behavior/packages/<new-run-id>/behavior_request.json \
  --output-dir evidence/pit/behavior/audits/<new-run-id>
```

Every output directory must be new. The behavior result is supplemental
`NOVEL_CANDIDATE` evidence and never replaces the fixed audit.

## 5. Real-data enablement

Empirical commands must refuse to run unless all of the following hold:

- `QLIB_PEERLITE_ALLOW_EMPIRICAL=true`
- frozen contract and strict receipt exist and verify
- PIT manifest is production `PASS/QUALIFIED`
- derived-feature behavior manifest is `PASS`
- input manifest hashes match the configured dataset

Synthetic mechanics never satisfy these requirements.

Even after enablement, the guard must reject the 2025+ final-OOS partitions
until the M8 one-time opening procedure.

## 6. Qlib foundation gate

Run the real-data foundation check on the server. It loads the exact qualified
2012–2024 product, constructs all seven rolling folds and records the receipt,
but it must not fit a model or compute a signal/backtest metric:

```bash
QLIB_PEERLITE_ALLOW_EMPIRICAL=true \
uv run python scripts/server/verify_qlib_foundation.py \
  --project-root /home/lvhc/abama/研究沙盒/qlib模型框架 \
  --product-dir /home/lvhc/abama/研究沙盒/qlib模型框架/data/processed/pit_data_product_2012_2024_v3 \
  --output-dir /home/lvhc/abama/研究沙盒/qlib模型框架/evidence/qlib/foundation_<run-id> \
  --tracking-dir /home/lvhc/abama/研究沙盒/qlib模型框架/artifacts/qlib_tracking
```

Run signal-analysis and portfolio plumbing separately on synthetic data:

```bash
uv run python scripts/server/verify_qlib_analysis_mechanics.py \
  --project-root /home/lvhc/abama/研究沙盒/qlib模型框架 \
  --output-dir /home/lvhc/abama/研究沙盒/qlib模型框架/evidence/qlib/analysis_mechanics_<run-id> \
  --tracking-dir /home/lvhc/abama/研究沙盒/qlib模型框架/artifacts/qlib_tracking
```

After downloading both immutable evidence directories, independently verify
their content hashes, Recorder readback hashes, local source hashes and M3
bindings:

```bash
uv run python scripts/verify_m4_evidence.py
```

The verifier creates `evidence/gates/M4_qlib_foundation_gate.json` exclusively;
it refuses to overwrite an existing gate. Only an M4 `PASS` permits M5 baseline
training. Synthetic metrics must never be reported as empirical results.
