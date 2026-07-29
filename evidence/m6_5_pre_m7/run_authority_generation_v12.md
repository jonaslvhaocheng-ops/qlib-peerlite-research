# RunAuthorityGenerationV12

- 状态：`DESIGN_ONLY`
- Base：`run_authority_generation_v11.md`
- Base SHA：`9bf0fd64c8397e2630773fe9e029043d69c4ab020e123092cf7438aa49685b2e`
- 取代：V11中worker直接持lock和writable OUTPUT FD的表述。

## 1. Supervisor-owned lease

只有trusted supervisor取得并独占precreated event lease FD。唯一顺序：

1. supervisor以exclusive flock取得lease FD，`fstat`验证generation/event/path/device/inode；
2. 在同一lock内生成owner token并发布lease grant；
3. 创建worker process及anonymous unidirectional result pipe；
4. worker只接收no-follow打开的read-only input FDs和pipe write end；worker从不接收lease FD、
   filesystem OUTPUT FD、target/root FD或publication capability；
5. supervisor持续持有原始同一open file description的flock，消费pipe并写入private staging FDs；
6. supervisor关闭pipe read end并通过`pidfd_wait`或等价不可竞态机制确认worker已退出，确认所有
   worker child/descendant均不存在且pipe writer EOF；
7. 只有此后supervisor才hash、seal、publishinner artifacts、wrapper、OUTCOME及ledger receipt；
8. OUTCOME transition entry和receipt durable fsync后，supervisor最后释放flock。

worker不能close、unlock、继承或复制lease FD，因为该FD从未进入worker FD table。worker被kill、
crash或pipe异常时，supervisor先reap worker及全部descendant，确认pipe EOF，丢弃未提交private
staging，按合法terminal规则处理，最后才释放lock。不存在“worker失锁但仍持writable file FD”
状态。

## 2. Supervisor-mediated result stream

pipe wire format使用固定framed protocol：

```text
8-byte unsigned big-endian frame length || frame bytes
```

总bytes、frames、每frame bytes均由plan固定上限；超限、truncated、extra frame或worker非零退出
立即HOLD。worker write capability只指向anonymous pipe，不能解析为filesystem path或ArtifactRef。
supervisor是唯一能将stream bytes写入V11 event-local raw slots的进程。

supervisor对每个private staging FD执行：

```text
write from validated pipe -> fsync -> rewind ->
same-FD byte hash/schema/logical digest -> fchmod 0440 -> fsync ->
parent root-FD no-follow lookup -> path device/inode == same FD fstat ->
no-replace publication -> parent fsync -> reopen read-only and identity revalidation
```

未完成worker reap、same-FD验证、mode seal和parent/path equality前，不得生成任何manifest/ref。
inner artifact publication仍遵守V11单向DAG。所有未显式允许的worker syscall/opcode默认DENY。

## 3. Reconciler exclusion

reconciler只能在supervisor释放flock后取得该lock；取得后必须按V9全链重扫。因为supervisor释放
发生在worker已reap且所有worker-side pipe/FD关闭之后，reconciler发布
`CLAIMED_INTERRUPTED`时不存在stale writer。任何无法证明worker tree已终止、pipe EOF或lock FD
identity的情况均HOLD，不得发布terminal。

## 4. Boundary

本文是future implementation contract，不创建supervisor、process、FD、lease或run authority，
不授权M7、fit、replay、真实数据、PIT、budget mutation或final-OOS。
