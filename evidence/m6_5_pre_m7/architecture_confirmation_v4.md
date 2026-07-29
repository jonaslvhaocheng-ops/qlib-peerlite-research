# M6.5 架构确认 v4 — 加入可信 genesis 与外部绑定

状态：`PASS — revised bounded architecture confirmation`  
替代：`architecture_confirmation_v3.md` 作为当前质量变更的架构依据；v3 与其审查保留为历史证据。  
风险：`R3`；M7 fit、派生研究契约冻结和最终 OOS 仍封印。

## v3 被否决的两个缺口

1. 服务器仍持有 M6 开跑前 `4 candidate / 29 fit` 的 legacy ledger (`8d08…`)；它不能作为 M7
   authority 的起点。M6 已验证的 close state 是 `6 / 44` (`31a90…`)。
2. 自描述的 state artifact 不是信任根。若没有选择前 audit input 和由外部冻结 binding 传入的预期
   hashes，future-conditioned M3 表仍可伪造一份自洽 artifact。

## 新的可信对象与责任边界

```text
M6 immutable gate + archived close-ledger proof
       │
       ├──> LedgerAuthorityGenesis (6/44 close snapshot only)
       │          │ atomic one-time server install
       │          ▼
       │     new M7 authority ledger ──► parent reconciliation receipts ──► RunAuthority
       │                                                                   │
       │                                                             event plan / lease
       │                                                                   ▼
       │                                                                future fit
       │
sealed raw snapshot ─► StateBuildBinding ─► pre-selection state_input_audit
                                                   │             │
                                                   ▼             └── PIT VERIFY package
                                      market_state_population artifact
                                                   │
                                  StateArtifactBinding (future derived contract)
                                                   ▼
                                             future M7 adapter

M6 frozen-source transfer manifest + archive-internal manifest
       │
       └──> M6ReplayInputBinding ─► archive-only verifier ─► replay receipt validator
```

### A. Ledger authority genesis

`contracts/immutable/m6_trial_ledger_close_20260728.jsonl` is a new immutable copy of the verified M6 close-time
prefix, never a rewrite of historical evidence. `LedgerAuthorityGenesis v1` binds:

- exact source snapshot SHA, byte length and `6 candidate / 44 fit` counts;
- M6 gate SHA plus archive-verifier evidence hash that proves the same close prefix;
- a new server-only authority logical ID and target relative path under an authority namespace;
- an explicit prohibition on using legacy `contracts/trial_ledger.jsonl` (`8d08…`) as a target.

Only `install_trial_ledger_authority.py` may create that target. It verifies the genesis and source snapshot under a
dedicated install lock, creates a new target atomically if absent, returns an idempotent receipt if its bytes already
equal genesis, and otherwise fails without overwriting any target. The receipt binds genesis, source and target
bytes/hashes/counts. `register_run_authority` accepts only an authority ledger whose retained genesis record and
current genesis head satisfy that binding; a legacy M6-start ledger fails before any run record can be written.

### B. State provenance is a two-stage data plane

The state builder and consumer are deliberately split:

| Artifact | Owner | Required contents | Consumer rule |
| --- | --- | --- | --- |
| `StateBuildBinding` | pre-M7 governance | sealed snapshot bundle and allowed manifest inventory; raw field schema; availability clocks; causal feature/builder/predicate blobs; state schema; date bound and atomic-publish protocol | builder opens only the exact bound sources. |
| `state_input_audit` | server state builder | every raw candidate key, seven eligibility flags, four state sources, deterministic selection outcome/reason, source partition identity and field/availability lineage; input/file/key digests | direct input to PIT VERIFY; not an optional log. |
| `market_state_population` | server state builder | selected population, daily 4D state, selected key/count/state digests; links to the audit artifact and build binding | can only be derived from a verified audit artifact. |
| `StateArtifactBinding` | future immutable M7 derived contract | expected build-binding SHA, audit package/PIT-VERIFY SHA, audit input SHA, artifact manifest SHA, code/predicate/schema hashes and OOS date bound | loader accepts `artifact_dir + binding`, never a path-only self-description. |

`BUILT_NOT_PIT_QUALIFIED` is a construction state only. The real M7 adapter must reject it; only a binding that names a
passing PIT verification package can enable a training Dataset. The M6.5 implementation may test synthetic bindings,
but must never label them valid market data.

The server builder is the sole code that produces the audit artifact: it resolves manifest-listed regular files with
realpath containment and SHA validation, rebuilds the seven flags and causal features without calling label/execution
functions, writes a new sibling temporary directory, fsyncs files/directories, writes a canonical completed marker
last, then atomically renames. A loader requires that marker and hashes all inventory entries.

### C. RunAuthority, not a free-form run intent

`RunAuthority v1` is immutable and includes:

- authority genesis ID/SHA and either the exact genesis head (first run) or a named, hash-bound parent
  reconciliation receipt (later run);
- the exact authority ledger identity, budget/spec binding and non-substitutable candidate/fit limits;
- one journal relative path and output relative path;
- an ordered `EventPlanEntry` for every permitted start: sequence/source ID, event kind/count flags,
  evaluation/fit IDs, model, fold, seed and purpose;
- canonical authority/event-plan hashes.

There is no user-supplied `--expected-head-*` or `--limit-*` authority input. Registration reads the initial head
only from the authority and, under lock, requires byte-exact equality. Every reconciliation continuation accepts the
previous immutable receipt, verifies it belongs to the same authority and that its `head_after` is the current ledger
head before appending exactly the next planned event. Any unrecorded tail, H0/H1 replacement, journal replacement,
payload mutation, candidate/fit slot swap or differing limits fails closed.

`RunAuthority` library/synthetic preflight is the scope of M6.5. It is not a claim that a real model fit is already
unbypassable. Step 7's runner must hold the authority lease and obtain an authority capability from this boundary
before `model.fit`; it has its own multiprocess/interrupt E2E acceptance gate.

### D. Replay binding is external to the receipt

`M6ReplayInputBinding v1` is frozen before server execution and binds the transfer manifest, archive SHA/bytes,
expected single archive root, archive-internal manifest schema/path/SHA, canonical tree-inventory algorithm/version
and digest, M6 revision/spec/gate/historical receipt hashes, verifier source SHA and allowed execution profile.

The existing external transfer manifest (`qlib_peerlite_m6_frozen_source_transfer_v1`) and archive-internal manifest
(`qlib_peerlite_frozen_source_v1`) remain distinct, explicitly named inputs; neither is silently converted. The
archive-only verifier accepts the single replay-input binding, validates its own source SHA and the archive against it,
safely extracts, validates every imported `qlib_peerlite*.__file__` lies below the temporary tree, and returns a
receipt bound to the input-binding SHA. `m6_archive` validates the receipt against the same external binding; a receipt
that only self-reports hashes is not an acceptance artifact.

## Dependency and operational rules

1. `data` owns raw/audit/state transformations; it does not import ledger, portfolio, selection or OOS logic.
2. `governance` owns all immutable bindings, genesis, receipts and verification; it cannot derive data rows.
3. `scripts/server` are the only composition roots and are required to use path containment, source hash checks and
   atomic publication. They never read M3 data products for state construction.
4. Existing M6 static verifier continues to prove historical prefixes. New authority installation begins from a
   copied verified close snapshot in a different namespace, so later M7 entries cannot mutate or obscure M6 evidence.
5. Every binding/receipt contains only repository-relative logical paths or sanitised identifiers; no credentials,
   raw values or absolute server paths enter Git evidence.

## Architecture conclusion

`PASS`: the original package boundaries still contain the repair, but the architecture now requires four explicit
external trust roots—M6 close genesis, state build binding, state consumer binding, and replay input binding. The
earlier path-only / receipt-only forms are prohibited. This confirmation is bounded: it does not authorize actual
state construction or model training until the revised change design, PIT VERIFY and all remaining quality gates pass.
