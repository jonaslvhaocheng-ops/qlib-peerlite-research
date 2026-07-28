# Research navigation modes

These modes govern research navigation and response behavior. They do not change the deterministic executor, its checks, or its `PASS`, `NEEDS_EVIDENCE`, and `FAIL` meanings.

## Select the mode

| Mode | Use when | Entry evidence | Positive ceiling |
| --- | --- | --- | --- |
| `DISCOVER` | The source, field, clock, universe, transformation, or claim is still a research choice. | A research objective and enough context to name candidate paths. No frozen contract or full matrix is required. | Candidate or unresolved; never `PASS` or `QUALIFIED`. |
| `VERIFY` | One or more candidates are concrete enough for targeted semantic, temporal, lineage, population, or sample checks. | The exact candidate and enough real documentation, metadata, or sampled values for the selected check. No frozen contract or full evidence chain is required. | Supported for the next decision, `NEEDS_EVIDENCE`, or `FAIL`; never `PASS` or `QUALIFIED`. |
| `CERTIFY` | The user needs a reusable PIT verdict before downstream empirical work. | One declared claim, an intact `FROZEN` contract and strict receipt, `FULL_TRAINING_INPUT`, every immutable artifact/binding required by `audit_spec.md`, and request-external review-authority, exact semantic-review-receipt and applicable interval-authority hashes. | The executor's exact `PASS`, `NEEDS_EVIDENCE`, or `FAIL`. |

Honor an explicit mode. Otherwise use `DISCOVER` when material choices remain open, `VERIFY` when a candidate can be tested but the certification gate is incomplete, and `CERTIFY` only when certification is requested and its gate can be evaluated. If a requested `CERTIFY` gate is incomplete, remain explicit about the attempted mode and return `NEEDS_EVIDENCE`; offer a labeled move to `VERIFY` only as a backup.

An executor result keeps its exact label. The navigation mode only limits what may be concluded from it: a diagnostic or `SAMPLE_ONLY` run in `VERIFY` may reveal `FAIL`, but no favorable result becomes `PASS`.

## Behavior contract

Treat a data path as the dependent tuple:

`source/version → raw field/meaning → transformation → availability and prediction clocks → population/identity → label definition → executable schedule → review authority → exact-interval authority or versioned calendar → split → claim`

In `DISCOVER` and `VERIFY`:

- Maintain an option ledger with each candidate path, decisive unknown, evidence locator, and state such as `OPEN`, `BLOCKED`, or `READY_FOR_CERTIFY`. These are navigation states, not audit verdicts.
- Prefer reversible probes that discriminate among options. Do not discard an untested alternative or freeze the first plausible source.
- Record what a finding actually depends on. Propagate a block only through downstream nodes that consume the failed node.
- Never use synthetic fixtures, convenient proxy tables, current constituent lists, or semantic guesses as empirical evidence.

In `CERTIFY`:

- Freeze the exact audit identity before execution and use only the specification's complete consumed-value and supporting-artifact interfaces.
- For every derived feature, load `behavior_spec.md`, complete the fixed PIT audit first, then execute the behavior-level proof against that parent. Hand off both immutable manifests; neither replaces or is silently folded into the other. Treat either missing proof as `NEEDS_EVIDENCE`. For a direct raw value, record an explicit `NOT_APPLICABLE` rationale rather than silently omitting the check.
- Do not fill an evidence gap by inference, borrow evidence from another input, or reinterpret a result under a weaker claim.
- Preserve the exact manifest/report pair and hashes for any downstream handoff.

## Highest-information next action

Every response gives one primary action and zero to two safe backups.

The primary action should be the smallest feasible observation most likely to separate the live choices or resolve the binding blocker. Name:

1. the exact artifact, locator, predicate, or row to inspect;
2. the competing outcomes it distinguishes;
3. the path and claim whose state would change.

Backups must be reversible, independently safe, and useful if the primary action is unavailable. Do not provide a backlog or ask for the whole certification bundle when one dictionary locator, historical receipt, or counterexample would decide the current branch.

## Failure containment and continuation

A contradiction or executor `FAIL` blocks the exact affected path, the declared claim for that audit identity, and conclusions that depend on it. It does not prove unrelated candidates invalid. An unaffected candidate remains unassessed until it has its own evidence, and cannot inherit `PASS`.

Safe continuations include:

- obtain the decisive missing evidence or repair the offending data, then hash new inputs and run a new audit;
- select an independent candidate path, routing any frozen-contract change through a Change Request before a new audit;
- use conspicuously labeled synthetic data only to debug parsing, schema handling, predicates, or orchestration;
- explicitly change `SYSTEM_REPLAYABLE` to `MARKET_RECONSTRUCTIBLE` only in a new request and audit.

Choose at most two continuations as backups. Never silently downgrade the mode or claim, erase the failed audit, or treat synthetic success as support for an empirical claim.
