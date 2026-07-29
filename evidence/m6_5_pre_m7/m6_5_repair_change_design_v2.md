# M6.5 R3 修复设计 v2 — 可信 genesis、PIT 审计数据面与冻结 replay 输入

状态：`IMPLEMENTATION_READY / 待新的独立设计审查`  
质量变更：`m6-5-pre-m7-repair`  
风险：`R3`  
替代：本文件替代 `m6_5_repair_change_design_v1.md` 作为当前实现依据；v1 与两份否决审查保留为
历史证据。  
约束：不启动 M7 fit，不冻结 M7 derived research contract，不访问最终 OOS，不修改 M6 immutable
gate/spec/ledger 历史行。

## 1. 已验证问题与目标

本修复必须同时关闭以下可复现的高风险问题：

1. 当前服务器的 legacy `contracts/trial_ledger.jsonl` 仍是 M6 前 `4 candidate / 29 fit` 的
   `8d08…`；M7 不能从它计量预算。M6 的已验证 close prefix 是本地 `6 / 44`、`31a90…`。
2. 仅靠 state artifact 自报 `source_kind`、文件 hash 或选择后 population，无法证明未用 T+1
   label/execution/purge 过滤过 M3 横截面。
3. `allowed_source_event_ids` 不能冻结模型、fold、seed 或预算槽位；分散 CLI head/limit 参数也不能
   证明它们属于同一 authority chain。
4. archive-only replay 仍需要一个执行**前**冻结的 verifier/archive/tree input binding，不能由 replay
   receipt 自报。

结果目标是一个可审计但仍未开始 M7 实证的安全底座：所有真实 M7 data/train 操作继续被后续 PIT
VERIFY 和 derived contract gate 拦住。

## 2. 固定信任根与对象

### 2.1 `LedgerAuthorityGenesis v1`

新增两个新对象（不修改既有 M6 artifact）：

```text
contracts/immutable/m6_trial_ledger_close_20260728.jsonl
contracts/immutable/m7_authority_genesis_m6_close_v1.json
```

close snapshot 是 M6 archive verifier 已证明的 close-time 51-line prefix 的 byte-exact copy。Genesis
canonical JSON 固定：

```json
{
  "schema_version": "qlib_peerlite_ledger_authority_genesis_v1",
  "authority_id": "m7-authority-m6-close-v1",
  "m6_close_snapshot": {"path": "...", "sha256": "...", "bytes": 0,
    "candidate_evaluations": 6, "model_fits": 44},
  "m6_evidence": {"gate_sha256": "...", "archive_proof_sha256": "..."},
  "server_policy": {"authority_relpath": "governance/authorities/m7-authority-m6-close-v1.jsonl",
    "legacy_relpaths_rejected": ["contracts/trial_ledger.jsonl"]},
  "content_sha256": "..."
}
```

`scripts/server/install_trial_ledger_authority.py` is the only installer. It accepts a genesis file, a close snapshot
and a controlled server root; it never accepts an arbitrary target ledger path. Under an installation lock it:

1. verifies the close snapshot bytes/counts and the M6 gate/archive verifier bindings;
2. rejects a target that names a legacy path or exists with non-genesis bytes;
3. writes `close_snapshot_bytes + canonical LEDGER_AUTHORITY_GENESIS record + "\\n"` to a new sibling temporary
   file, fsyncs file and parent directory, then atomically renames it to the policy path;
4. writes an idempotent `LedgerAuthorityGenesisReceipt v1` with genesis SHA, source close prefix and exact
   `genesis_head` (SHA/bytes/counts after the genesis record).

The target is therefore a **new authority ledger**, not a modification of historical M6 files. A repeated install is
allowed only when target bytes and genesis record are exact; interrupted/competing install attempts leave no partial
target. Any `8d08…` legacy path/head fails before run registration.

### 2.2 `StateBuildBinding` and two data artifacts

Before state construction, governance freezes `StateBuildBinding v1` (synthetic in M6.5 tests; a real immutable
version only after the M7 data/PIT preparation gate). It fixes:

- snapshot bundle SHA and a named allowlist of source manifests/files/columns;
- source field → availability-clock mapping and pre-final-OOS date bound;
- exact builder, causal-feature, eligibility-predicate and state-schema blob hashes;
- frozen selection reason order and `state_input_audit` / population/daily artifact protocol;
- output path policy and atomic-publish protocol version.

The server builder's public interface becomes:

```text
build_m7_market_state_population.py
  --state-build-binding <binding.json>
  --snapshot-dir <sealed raw snapshot>
  --output-dir <new artifact directory>
```

It resolves every read through a manifest allowlist resolver: regular file only, no symlink/hard-link target escape,
realpath below snapshot directory, SHA/byte/schema/column match. It calls an extracted
`build_t_known_state_input()` that operates only on that resolver and raw daily/universe/master/status/action/calendar
sources. The extraction may not import/call label schedule, labels, open limit, execution halt, action-cross-label or
M3 data-product readers.

The builder publishes three linked files:

| File | Required row-level content |
| --- | --- |
| `state_input_audit.parquet` | `(datetime,instrument)`, source partition identity, the four source values, all seven eligibility flags (`universe_member`, `listing_age_eligible`, `is_active`, `special_status_forbidden`, `special_status_unknown`, `price_domain_valid`, `feature_eligible`), deterministic `selection_outcome` and first failure reason. |
| `population.parquet` | selected keys plus exactly four state source columns; no label/execution/purge fields. |
| `daily_state.parquet` | one daily row in fixed `DAILY_PRODUCT_COLUMNS`, including canonical keyset and state digests. |

The artifact manifest binds the build binding SHA, audit-file SHA/key digest/selection counts, population/daily file
inventories, source/field availability lineage, predicate and code hashes, canonical date/floating-point digest
algorithm and `status: BUILT_NOT_PIT_QUALIFIED`. Its last file is a `COMPLETED` marker containing the manifest SHA.
Writer protocol is new-only output → same-parent temporary directory → fsync each file → manifest → marker → fsync
directory → atomic rename → parent fsync. Loader rejects any absent marker, inventory mismatch or noncanonical
summary.

The future real M7 consumer has a separate `StateArtifactBinding v1` inside its immutable derived contract. It fixes
the `StateBuildBinding` SHA, PIT VERIFY package/manifest SHA, state-input-audit manifest SHA, final state artifact
manifest SHA, source/feature/predicate/schema hashes and OOS date bound. The only consumer API is:

```python
load_verified_market_state_artifact(artifact_dir, binding: StateArtifactBinding) -> pd.DataFrame
```

It compares each expected binding—not merely manifest self-hashes—and rejects `BUILT_NOT_PIT_QUALIFIED`. The M6.5
implementation may exercise synthetic `StateArtifactBinding` fixtures, but no real artifact can be given to an M7
Dataset until `point-in-time-data-audit` produces the bound passing VERIFY package.

### 2.3 `RunAuthority v1` and receipt chain

`LedgerPrefixBinding` remains M6-archive-only. New M7 preflight uses a canonical `RunAuthority`, not a loose intent:

```text
RunAuthority
  authority_genesis_sha256
  authority_ledger_id
  parent_kind = GENESIS | RECONCILIATION_RECEIPT
  parent_receipt_sha256 (for later runs)
  initial_ledger_head {sha256, bytes, candidates, fits}
  execution_spec_content_sha256 + immutable budget binding / fixed limits
  journal_relpath + output_relpath
  ordered EventPlanEntry[]

EventPlanEntry
  seq, source_event_id, event_type, count flags,
  evaluation_id, fit_id?, model_id, fold_id?, seed, purpose
```

The constructor rejects duplicate sequences/semantic IDs, count swaps and source IDs not derived from `run_id:seq`.
Its content hash binds both event plan and budget. Registration takes **only** a RunAuthority and its authority ledger:

- first run: lock-held ledger head must equal the authority's genesis-derived initial head;
- later run: parent reconciliation receipt SHA must be listed in the authority, receipt must validate under the same
  genesis/ledger, and current raw head must exactly equal its `head_after`;
- `RUN_AUTHORITY_REGISTERED` retained record carries authority/plan hash and yields a deterministic registration
  receipt/head.

The journal can contain only byte-equivalent planned events (except timestamp). Reconciliation takes the previous
registration/reconciliation receipt—not `--expected-head-*` or `--limit-*` flags—checks the receipt chain and raw
head under the lock, then adds only the next unretained plan entries. No new record means a same-journal no-op; any
unknown tail, H0/H1 substitution, authority reuse with different journal/output/spec/plan, payload mutation or
candidate/fit reallocation leaves ledger bytes unchanged. Limits are read from the authority's immutable budget
binding and never from caller arguments.

The public server CLI accepts `--run-authority`, `--previous-receipt`, journal root and authority root. It writes a
canonical receipt (authority/plan/parent hashes, before/after exact heads, retained source IDs, cumulative counts and
content hash). M6.5 provides and tests `run_authority_lease` plus synthetic preflight only. Future M7 runner must use
the lease-derived capability around `journal fsync → reconciliation → exact preflight → model.fit`; this later
fit-boundary proof is explicitly not claimed by M6.5.

### 2.4 `M6ReplayInputBinding v1`

Before any server replay, governance freezes a single replay input binding that resolves existing schema differences
instead of pretending they are one manifest:

```text
M6ReplayInputBinding
  transfer_manifest {path, sha256, schema = qlib_peerlite_m6_frozen_source_transfer_v1}
  archive {relative_path, sha256, bytes, single_root}
  internal_manifest {relative_path, sha256, schema = qlib_peerlite_frozen_source_v1}
  tree_inventory {algorithm = qlib_peerlite_tree_inventory_v1, sha256}
  m6_revision / execution_spec / gate / historical_verification bindings
  verifier {relative_path, sha256}
  server logical paths for product/run/legacy-read-only ledger
  execution_profile {checkpoint_replays: 14, model_fit_calls: 0, final_oos: false}
```

The archive-only verifier accepts `--replay-input-binding`, controlled root, output directory and device; it does not
accept source-root/archive/hash/product/run/ledger flags. It validates its own file SHA against the binding, archive
against transfer binding, safe-extracts one regular-file/directory tree, checks the internal manifest and canonical
tree inventory, removes prior `qlib_peerlite*` modules, imports only temporary-tree modules, asserts every imported
`__file__` remains in that tree, and restores import state. The v2 receipt includes the replay-binding SHA and every
actual input digest. `m6_archive` accepts a receipt only when it validates against the frozen binding; a self-hashed
receipt without that binding is no evidence.

## 3. Failure, compatibility and rollback rules

- No code path is allowed to reinterpret an M6 close prefix as the existing server legacy ledger. The genesis installer
  is the only migration, creates a new path and is idempotent/fail-closed.
- All state artifacts retain selection-before evidence. An M3 manifest/path, projected M3 DataFrame, future label,
  execution or purge artifact cannot satisfy the builder's allowlist or the consumer's external binding.
- Existing M6 static archive tests keep their historical prefix semantics; new v3 authority records are appended only
  to the new authority namespace.
- Safe state/replay publication does not overwrite an existing nonidentical output. Ledger operations retain
  temp+fsync+replace+directory fsync atomicity.
- Rollback stops the new M6.5/M7 namespace. It never deletes M6 history, opens OOS or recovers budget by erasing a
  started event.

## 4. Required verification obligations

1. Genesis tests: correct 6/44 install, `8d08…` rejection, bad snapshot/gate/archive proof, idempotency, existing
   wrong target, lock race, injected write/rename failure and no partial bytes.
2. State tests: raw allowlist/source clock contract, all seven flags/reasons, actual same-day instrument permutation,
   unknown/bad source/manifest recomputed self-hash, M3 projected-future-label regression, marker/inventory/digest
   mutation, atomic publish/retry and binding-required loader.
3. Authority tests: genesis and parent receipt chain, H0/H1/unknown-tail replacement, same run different journal/output,
   every event-plan field mutation, semantic candidate/fit swap, lease contention, atomic failure and crash retry.
4. Replay tests: replay-input binding success, verifier/archive/internal manifest/tree/schema mutation, tar path/link/
   duplicate/root rejection, imported-module origin isolation, receipt binding mutation and 14-fold real server replay.
5. The changed core modules and CLIs reach 100% line **and** branch coverage under a frozen per-file `coverage.py`
   include list. Receipt stores exact argv, source digest, raw JSON report and per-file percentages; no exclude or lower
   threshold is permitted.
6. E2E uses public CLIs on synthetic fixtures for genesis→authority→reconcile, sealed-binding→artifact→loader, and
   replay-binding→fake archive→receipt. Real M7 fit and final OOS are not E2E targets in this change.

## 5. Ordered implementation plan

1. Add immutable binding/value objects and canonical validators for genesis, state build/artifact, run authority and
   replay input; retain old M6 prefix APIs unchanged.
2. Add red tests for every P0/P1 route above, including recomputed-self-hash and H0/H1 adversarial cases.
3. Implement atomic genesis installer and receipt chain; then implement state audit/artifact builder/loader with
   synthetic sealed snapshot tests and exact `PanelDataset` state schema.
4. Implement run-authority registration/reconcile CLI and lease/preflight library, then safe archive-only verifier and
   `m6_archive` binding validator.
5. Complete coverage and CLI E2E evidence; upload verifier plus frozen replay-input binding to server and perform a
   fresh, read-only v3 14-fold replay.
6. Re-run independent design/code/test reviews. Only then may the separate Step 7 invoke the PIT audit skill, freeze
   a real state binding/derived contract, and decide whether to run M7.

## 6. Open decisions

None. The real state source's availability and PIT correctness are explicitly deferred to the later
`point-in-time-data-audit` VERIFY gate; this design refuses to manufacture an approval before that evidence exists.
