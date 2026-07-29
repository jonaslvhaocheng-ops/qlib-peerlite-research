# M6.5 R3 修复设计 v12 — Fresh output reservation amendment

状态：`IMPLEMENTATION_READY / 待独立设计审查`。本文件以 self-contained
`m6_5_repair_change_design_v11.md` SHA-256
`cdbcbff655d7e8de152d62e1d4aa33a1fa145ebb43ad8f7efde555ac39c52a21` 为唯一 base；v11 的 M6/PIT/Gate/genesis/authority/ACL/descriptor-v5/closure-v2/seed+umask/publisher/test-order requirements 原样保留。

本文件仅替代 v11 的 common `ArtifactRef` applicability 和 §6 M6 replay contract：已有 content remains `ArtifactRef`; future output uses reservation, not fake precomputed content hash. Architecture basis is `architecture_confirmation_v15.md`. No empirical M7/replay/OOS authorization is granted.

## 1. New schemas and ownership

`ReplayOutputNamespace v1` is an existing immutable `ArtifactRef` under replay-supervisor control. Closed fields define logical namespace, control-root-relative parent, expected owner/mode/POSIX ACL, writer identity, output-root mode `0700`, allowed output schema and no-reuse policy.

`FreshOutputReservation v1` is a closed non-content record embedded in `M6ReplayInputBinding v7`:

```text
reservation_id + binding-frozen nonce + derived basename
namespace-policy ArtifactRef digest
must_be_absent=true
expected output schema + 14 replay/0 fit/OOS=false profile
```

It intentionally has no SHA/bytes and exposes no path parameter to caller/verifier. At binding freeze supervisor reads namespace by root FD, validates policy/ACL and records that `fstatat(..., AT_SYMLINK_NOFOLLOW)` sees absence. This is not an output existence claim.

## 2. Full M6 replay replacement

`M6ReplayInputBinding v7` is frozen before launch and contains exact existing `ArtifactRef` entries for:

1. external transfer manifest, source archive, internal manifest, single root and full archive tree inventory;
2. immutable M6 spec, gate, close proof, historical verification receipt and approved frozen verifier source;
3. M3 product manifest and every consumed partition;
4. M6 run manifest, candidate list, all 14 fold receipts, all checkpoint metadata/state files, all candidate prediction partitions and K16 deterministic-refit receipt/reference score;
5. legacy read-only ledger plus before/after identity;
6. sealed-root verifier v3, FD-exec helper, bootstrap, ReplayRuntimeClosure v3, PythonStartupPolicy v1, ProcessStartupState v1 and fixed argv/cwd/import policy;
7. ReplayOutputNamespace v1 ArtifactRef and FreshOutputReservation v1.

It has no free source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter root. The output profile is exactly 14 replay / 0 fit / OOS=false.

Before verifier launch, replay supervisor rechecks every input/namespace, then under namespace lock repeats absence check and uses `mkdirat(parent_fd, derived_basename, 0700)`. Success is the single fresh-root claim; `EEXIST`, symlink/type, owner/mode/ACL, non-empty or parent mismatch fails. Supervisor fsyncs parent/root and emits `OutputReservationReceipt v1` containing binding digest, reservation/namespace policy, parent/root FD point-in-time identities, empty inventory, owner/mode and creator identity. It passes the reserved root only by sealed descriptor FD.

`ReplayExecutionReceipt v6` and child receipt bind the reservation receipt in addition to exact v7/runtime/seed/umask/bootstrap/stage/checkpoint/prediction facts. `m6_archive` accepts only exact v7 binding + reservation + supervisor + child agreement, a new reserved output and unchanged legacy ledger. Crash/rejection after reservation produces `QUARANTINED_UNPUBLISHED`; it is never deleted/recreated/promoted/reused.

## 3. Failure behavior and verification obligations

Synthetic tests must prove: output cannot be parsed as existing input artifact; wrong/pre-existing/caller root fails; parent replacement/ACL change/symlink/race fails; reservation receipt substitution/reuse fails; crash after mkdir before verifier leaves quarantine; correct Python startup or input inventory cannot compensate for wrong reservation; and v7 still rejects every omitted/substituted archive/product/run/checkpoint/prediction/ledger/runtime input or caller root. These tests do not perform server replay or M7 training.

## 4. Ordered implementation update

1. Add strict namespace/reservation/receipt schemas and root-FD absence/atomic-mkdir primitives.
2. Thread v7 reservation ref through staged descriptor, supervisor/child receipts and `m6_archive` validator.
3. Add synthetic red/green/E2E reservation race/crash/no-free-path coverage alongside existing v11 obligations.
4. Re-run independent code review/E2E only after the full router sequence; M7/CCC/Gate/final OOS stay sealed.
