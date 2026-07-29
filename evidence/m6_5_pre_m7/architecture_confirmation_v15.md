# M6.5 架构确认 v15 — Fresh replay output reservation

状态：`ARCHITECTURE_READY / 待独立设计审查`。本文件的 canonical base 是
`architecture_confirmation_v14.md` SHA-256
`148490b9933be0311ff7c0b8626cdc5c3c268a2070cf6a6f49e9e26ac2af410f`：其 M6 `6/44`、PIT/state、public Gate、actor ACL、one-way authority、descriptor v5/closure v2、effective seed/umask、M7 publisher 和 all M6 replay controls 继续完整有效。

唯一替换如下：v14 的 common-object rule 对**已有 content**继续使用 `ArtifactRef v1`；v14 §6 的 M6 replay contract 由本文件 §2 完整替代。它不授权 M7、replay、OOS 或 M6 history mutation。

## 1. Existing input versus future output

`ArtifactRef v1(role,relative_path,schema_version,sha256,bytes)` only represents an existing measured artifact. A fresh output root is not an ArtifactRef and never gets invented SHA/bytes before it exists. `M6ReplayInputBinding v7` therefore contains two distinct objects:

- existing, immutable **`ReplayOutputNamespace v1` ArtifactRef**: supervisor-owned output parent policy, including control-root-relative parent path, logical namespace ID, expected owner/mode/ACL, creator identity `replay-supervisor`, output root mode `0700`, allowed output schema and `no_reuse=true`;
- non-content **`FreshOutputReservation v1`**: `reservation_id`, binding-frozen nonce, basename derived only from that nonce, exact namespace-policy digest, `must_be_absent=true`, expected `14 replay / 0 fit / OOS=false` profile and required output schema. It has no SHA/bytes/path supplied by a caller.

At binding freeze supervisor opens the namespace parent from the policy/root FD, validates its identity/ACL, and proves the reserved basename is absent with no-follow lookup. This is a precondition, not a claim of future-content hash. The verifier still accepts no output root/path argument.

## 2. Complete M6 replay binding v7 and atomic reservation

`M6ReplayInputBinding v7` is frozen before replay. All existing input roles are exact `ArtifactRef`s with relative path/SHA/bytes/schema/role:

1. external transfer manifest; source archive; internal manifest; single root; complete archive tree inventory;
2. M6 immutable execution spec, gate, close proof, historical verification receipt and approved frozen verifier source;
3. M3 bound product manifest and every consumed product partition;
4. M6 run manifest, candidate list, 14 fold receipts, every checkpoint `metadata.json` + `state_dict.pt`, every candidate prediction partition and K16 deterministic-refit receipt/reference score;
5. legacy read-only ledger identity plus before/after hash;
6. approved sealed-root verifier v3, FD-exec helper, bootstrap, `ReplayRuntimeClosure v3`, `PythonStartupPolicy v1`, `ProcessStartupState v1`, fixed argv/cwd/import policy;
7. existing `ReplayOutputNamespace v1` ArtifactRef plus the distinct `FreshOutputReservation v1` described above.

The binding fixes `14 replay / 0 fit / OOS=false`; verifier/launcher take no source/product/run/checkpoint/prediction/ledger/output/runtime/interpreter flags or caller-selected roots.

At execution, replay supervisor reopens and verifies every input/namespace by FD. Under namespace lock it repeats absence validation and calls `mkdirat(parent_fd, basename, 0700)`; successful `mkdirat` is the sole linear reservation point, and `EEXIST`/wrong type/symlink/ACL/owner/mode/non-empty root fails. It fsyncs parent/root and writes `OutputReservationReceipt v1`, binding v7 binding digest, reservation/namespace policy, parent and created-root point-in-time FD identities, owner/mode/empty inventory and supervisor identity. The verifier receives only the newly reserved root FD through its sealed staged descriptor.

`ReplayExecutionReceipt v6` and child receipt repeat reservation-receipt digest and output-root identity, in addition to all v7/runtime/startup/process/stage/checkpoint/prediction facts. `m6_archive` requires v7 binding + reservation receipt + supervisor receipt + child receipt agreement, new output and unchanged ledger. Any reserved root left after crash or rejected execution is `QUARANTINED_UNPUBLISHED`, never promoted, deleted/recreated or reused for a later binding.

Tests must reject pre-existing/foreign/caller output roots, parent substitution, binding-time/execution-time race, symlink/wrong ACL/owner/mode, stale reservation receipt, reservation reuse, crash after mkdir before verifier, correct startup receipt with wrong reservation and any caller output-path flag. Linux x86_64 CUDA remains the only authoritative replay platform; synthetic adapters cannot issue acceptance evidence.
