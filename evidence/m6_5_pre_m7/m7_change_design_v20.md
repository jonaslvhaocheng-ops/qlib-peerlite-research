# M7 CCC / 市场状态 Gate 设计 v20

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v19.md`
- Base SHA：`0a0bb3e6e17e98b52cc2e384743541fe30d7529e89a9f5eb1d295062d6cd7f09`
- 取代：M7 v19。

## 1. Default-deny syscall and opcode policy

V19的write-like列表是显式allowlist，不是deny-list。任何未列出的syscall、io_uring opcode、
ioctl command、shared-memory write、device operation或native escape默认DENY。以下全部显式DENY：

```text
pwritev2,copy_file_range,sendfile,splice,vmsplice,tee,fallocate,
aio_write,io_submit,io_uring_setup,io_uring_enter,io_uring_register,
process_vm_writev,ptrace,memfd_create,shm_open,shmget,mremap,
dup,dup2,dup3,fcntl(F_DUPFD),fcntl(F_DUPFD_CLOEXEC),SCM_RIGHTS
```

filesystem write allowlist仅适用于trusted supervisor；sandbox worker不持filesystem OUTPUT FD。
worker唯一write role为`SUPERVISOR_PIPE`，只允许`WRITE|WRITEV`到supervisor预建的anonymous pipe。
pipe row记录fd、pipe device/inode、flags、role、frame cap及total cap；不得成为ArtifactRef。

## 2. Same-FD finalization receipt

RuntimeClosureReceiptV5以V19 V4为base，schema ID升级并增加：

```text
supervisor_lease_identity
worker_pid_identity
worker_tree_reaped=true
pipe_eof=true
staged_outputs
```

`staged_outputs`每row exact：

```json
{
  "logical_role": "<fixed>",
  "relative_path": "<fixed event-local>",
  "device": "<canonical decimal>",
  "inode": "<canonical decimal>",
  "nlink_before_publish": "1",
  "open_flags": "<canonical hex>",
  "byte_count": "<canonical decimal>",
  "file_sha256": "sha256:<64hex>",
  "schema_sha256": "sha256:<64hex> or null",
  "key_digest": "sha256:<64hex> or null",
  "value_digest": "sha256:<64hex> or null",
  "logical_digest": "sha256:<64hex> or null",
  "sealed_mode": "0440",
  "final_path_device": "<same device>",
  "final_path_inode": "<same inode>"
}
```

所有hash/digest从supervisor写入的同一open file description在最后一次write后重算；其后
`fsync→fchmod0440→fsync→root-FD no-follow path lookup→device/inode equality→parent fsync`。
任何digest来自path reopen、worker仍存活、pipe非EOF、nlink异常、final path不等或unlisted
operation都使receipt FAIL且不得生成PASS artifact。

## 3. Boundary

这只是synthetic contract-test设计；不启动worker、M7、fit、replay、真实数据、PIT、budget或
final-OOS。
