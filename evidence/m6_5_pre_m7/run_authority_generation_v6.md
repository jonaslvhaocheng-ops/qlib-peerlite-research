# RunAuthorityGenerationV6

- 状态：`DESIGN_ONLY`
- Base：`run_authority_generation_v5.md`
- Base SHA：`71c796270908598af7aab1b5c10aaf9fc65a4db76a244b47c1b006adad0b052c`
- 取代：V5。

## 1. Exact composition

V5 safe IDs、registry policy、purpose plans、dual qualification、object equality、role DAG和唯一commit
activation保留。V5 commit retained fields、global-budget算法、temp recovery和registration scan由
本文件§2–§5替换。

## 2. Budget is committed-authority reservation

M7 budget在generation commit激活时永久预留整个plan caps，不依赖event outcome。因此
FAILED、CLAIMED_INTERRUPTED、MANUAL_ABORT或从未claim都不会释放1/8，也不存在replacement。

扫描连续commits后：

```text
retained_candidate = 6 + sum(commit.authorized_increment.candidate_evaluations)
retained_fit       = 44 + sum(commit.authorized_increment.model_fits)
```

synthetic namespaceincrements必须0/0且不参与trial。trial purpose sequence只能
`[]`、`[M7_CCC_ISOLATED]`、`[M7_CCC_ISOLATED,M7_GATE_ISOLATED]`。每个trial commit increment
exact 1/8，ceiling exact 8/60。

`purpose_sequence_digest`唯一preimage：

```text
for commits in generation order:
  g20 || 0x1f || purpose || 0x1f || authority.canonical_sha256 || 0x0a
```

`budget_reservation_digest`唯一preimage：

```text
for commits in generation order:
  g20 || 0x1f || candidate_increment || 0x1f || fit_increment || 0x0a
```

空序列digest为SHA256(empty bytes)。所有token ASCII。

## 3. Generation commit V6 and registry scans

`AuthorityGenerationCommitV6` exact：

```json
{
  "schema_version": "qlib_peerlite_authority_generation_commit_v6",
  "namespace": "synthetic|trial",
  "generation_number": "<positive decimal>",
  "previous_generation_commit": "<ArtifactRefV1 or null>",
  "registration": "<ArtifactRefV1>",
  "authority": "<ArtifactRefV1>",
  "purpose": "M6_5_SYNTHETIC_TEST_ONLY|M7_CCC_ISOLATED|M7_GATE_ISOLATED",
  "run_id": "<safe ID>",
  "linear_event_plan": "<ArtifactRefV1>",
  "registry_policy": "<ArtifactRefV1>",
  "prior_terminal": "<ArtifactRefV1 or null>",
  "ledger_h0": "sha256:<64hex>",
  "m6_prefix": {
    "candidate_evaluations": "6",
    "model_fits": "44",
    "binding": "<ArtifactRefV1>"
  },
  "retained_before": {
    "candidate_evaluations": "<decimal>",
    "model_fits": "<decimal>",
    "purpose_sequence_digest": "sha256:<64hex>",
    "budget_reservation_digest": "sha256:<64hex>"
  },
  "authorized_increment": {
    "candidate_evaluations": "0|1",
    "model_fits": "0|8"
  },
  "retained_after": {
    "candidate_evaluations": "<decimal>",
    "model_fits": "<decimal>",
    "purpose_sequence_digest": "sha256:<64hex>",
    "budget_reservation_digest": "sha256:<64hex>"
  },
  "issuer_policy": "<ArtifactRefV1>",
  "canonical_sha256": "sha256:<64hex>"
}
```

retained before/after 全部由M6 close+commits独立重算，不能由caller自报。generation1
previous/prior terminal均null；后续previous指exact predecessor commit，trial Gate的prior terminal
必须是CCC exact valid `CLOSED|ABANDONED`；synthetic后继同样要求前代terminal。

持global lock后必须全量no-follow扫描：

```text
commits/<g20>.json
registrations/<g20>.<run_id>.json
authorities/<authority_id>.json
plans/<plan_id>.json
runs/<g20>/...
```

每个已commit generation必须恰一份registration且被commit引用；不得有第二个
`registrations/<g20>.*`。next generation允许0份，或恰1份且path/run/bytes与proposed完全相等；
不同run留下的orphan registration使整个generation HOLD。future generation registration/commit、
gap、duplicate、unknown file/temp均HOLD。

## 4. Closed event and terminal protocol

每generation固定：

```text
runs/<g20>/claims/<event_key>.json
runs/<g20>/outcomes/<event_key>.json
runs/<g20>/run-terminal.json
event_key = sha256(registration.canonical_sha256 ASCII || 0x1f || source_event_id UTF-8).hexdigest()
```

`EventClaimV1` exact：

```json
{
  "schema_version": "qlib_peerlite_authorized_event_claim_v1",
  "generation_commit": "<ArtifactRefV1>",
  "registration": "<ArtifactRefV1>",
  "linear_event_plan": "<ArtifactRefV1>",
  "event_key": "<64hex>",
  "seq": "<positive decimal>",
  "source_event_id": "<ASCII>",
  "event_type": "SYNTHETIC_OBSERVER|CANDIDATE|FIT|DETERMINISTIC_REFIT",
  "evaluation_id": "<ASCII>",
  "model_id": "<ASCII>",
  "fold_id": "<ASCII>",
  "seed": "<decimal>",
  "attempt_id": "<64hex>",
  "ledger_head_before": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

所有event字段与plan seq exact equality；同event只允许一份claim。claim durable即永久消费该
plan event，任何outcome不允许第二claim。

`EventOutcomeV1` exact：

```json
{
  "schema_version": "qlib_peerlite_authorized_event_outcome_v1",
  "claim": "<ArtifactRefV1>",
  "event_key": "<64hex>",
  "status": "COMPLETED|FAILED|CLAIMED_INTERRUPTED|MANUAL_ABORT",
  "result": "<ArtifactRefV1 or null>",
  "ledger_head_after": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

COMPLETED必须result nonnull；其他status必须null。claim存在但worker lease已释放且outcome缺失时，
reconciler只可发布CLAIMED_INTERRUPTED，永不重新执行。

`RunTerminalV2` exact：

```json
{
  "schema_version": "qlib_peerlite_authorized_run_terminal_v2",
  "generation_commit": "<ArtifactRefV1>",
  "registration": "<ArtifactRefV1>",
  "linear_event_plan": "<ArtifactRefV1>",
  "status": "CLOSED|ABANDONED",
  "events": [
    {
      "seq": "<positive decimal>",
      "source_event_id": "<ASCII>",
      "status": "COMPLETED|FAILED|CLAIMED_INTERRUPTED|MANUAL_ABORT|UNUSED",
      "claim": "<ArtifactRefV1 or null>",
      "outcome": "<ArtifactRefV1 or null>"
    }
  ],
  "event_partition_digest": "sha256:<64hex>",
  "final_ledger_head": "sha256:<64hex>",
  "canonical_sha256": "sha256:<64hex>"
}
```

events与plan一一对应且seq排序。digest preimage逐行：

```text
seq || 0x1f || source_event_id || 0x1f || status || 0x1f
|| (outcome.canonical_sha256 or "NONE") || 0x0a
```

全部COMPLETED才CLOSED；首个非COMPLETED claim outcome使ABANDONED，后续未claim events必须UNUSED；
claim/outcome refs按status严格null/non-null。terminal no-replace/fsync，identical resume、
different HOLD。下一generation只接受exact terminal，不从松散日志猜测。

## 5. Publication and crash recovery

plan、authority、registration、commit、receipt、claim、outcome、terminal都使用Capacity V7 §4
的closed temp/final transition table：hardlink后fsync parent、unlink temp、再次fsync parent；
temp+final absent/present及same/different inode/bytes无其他动作。

activation仍按V5顺序，但registration publish后立即全量scan确保该generation恰一registration；
commit publish前再次scan。commit durable后才激活。已存在commit时只允许补identical receipt；
任一orphan/different temp或registration、两个run争同generation均HOLD。
