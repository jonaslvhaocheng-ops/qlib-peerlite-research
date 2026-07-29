# ScoreReplayIdentityV3

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Base：`score_replay_identity_v2.md`
- Base SHA：`135344637dd0694526f657996a2ebd957f9a93951ad528c088d1401faef3e3c6`
- 取代：V2的transaction与execution evidence表述。

V2的固定M6 identities、2 merged files、14 pairs、五列、七fold windows、score equality及执行前
只绑定input与安全output slot的规则全部保留。

每pair执行前新增绑定：

```text
input_transaction: ReplayInputTransactionV1 canonical ref, status COMMITTED
reservation_invocation_slot: fixed safe slot
output target parent index/name
raw output relative slot
output manifest relative slot
execution receipt slot
pair receipt slot
```

运行后PairReceipt必须分别引用：

```text
input_transaction               # preexisting read-only committed snapshot
output_transaction              # reservation/PREPARED/PUBLISH_COMPLETE/COMMITTED closed chain
execution_receipt               # launcher/runtime/CUDA/no-fit/same-FD evidence
output_manifest                 # fixed transaction payload member
```

四者角色和schema不可互换。CUDA-only、zero-fit、trial-ledger unchanged和final-OOS false必须来自
execution receipt及独立重算，不能仅由PairReceipt自报。所有raw input必须通过冻结root FD
no-follow打开，manifest验证、hash/schema检查和实际模型消费复用同一open file description；
禁止验证后按path重新打开。

本文不授权replay、fit、真实数据、PIT、budget mutation或final-OOS。
