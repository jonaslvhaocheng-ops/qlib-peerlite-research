# M7 CCC / 市场状态 Gate 设计 v19

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v18.md`
- Base SHA：`3b82fb2c5518f2765505169697fe139ffa4165751a0675e0607293fe0319d37a`
- 取代：M7 v18。

## 1. Collision-safe execution identity and receipt slot

`LP(x)=len(x_bytes)的8-byte unsigned big-endian || x_bytes`。execution input identity为
`input_artifacts`按`(path UTF-8,file_sha256 ASCII,canonical_sha256 ASCII)`排序唯一后，将每个
exact canonical JSON row bytes作`LP`并concat所得SHA-256。禁止duplicate、unknown input或空
identity。

```text
execution_id = SHA256(
  LP(invocation canonical SHA ASCII) ||
  LP(closure canonical SHA ASCII) ||
  LP(field ASCII) ||
  LP(domain_code ASCII) ||
  LP(input_identity SHA ASCII)
).hexdigest()
```

`closure_segment`只能是去掉`sha256:`前缀的closure canonical SHA之64位小写hex，不使用
free-form `closure_id`。receipt固定slot：

```text
<invocation_root>/runtime-closure-receipts/<closure_segment>/<execution_id>.json
```

invocation root必须由trusted supervisor预先打开并记录path/device/inode；receipt path仅由root FD
逐段`openat2(RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS|RESOLVE_NO_XDEV)`或经证明等价的no-follow
resolver派生。任何absolute、`.`、`..`、separator、control character、symlink、hardlink alias、
device/inode drift或existing different bytes均FAIL closed。

## 2. Output-FD-only write oracle

`RuntimeClosureReceiptV4`以V18 V3为base，schema ID升级，并把`observed_fds`每row exact升级为：

```json
{
  "fd": "<canonical decimal>",
  "role": "INPUT|OUTPUT",
  "artifact": "<closed typed ref>",
  "device": "<canonical decimal>",
  "inode": "<canonical decimal>",
  "open_flags": "<canonical hexadecimal bitmask>",
  "access_mode": "READ_ONLY|WRITE_ONLY",
  "allowed_operations": ["READ"] 
}
```

OUTPUT的`allowed_operations` exact按ASCII排序、取自
`WRITE|PWRITE|WRITEV|PWRITEV|MMAP_SHARED_WRITE|FSYNC|FDATASYNC`子集；INPUT只能
`["READ"]`且必须以read-only flags打开。所有FD在sandbox进入前与退出后由supervisor独立
`fstat`，device/inode/flags/access mode必须相等；禁止`dup*`、`fcntl(F_DUPFD*)`、SCM_RIGHTS和
未登记FD。

write-like oracle覆盖`write,pwrite,pwritev,writev,mmap(PROT_WRITE|MAP_SHARED),msync,
fsync,fdatasync,ioctl,setxattr,fsetxattr,utime,utimes,utimensat,futimens`。只有已登记OUTPUT FD
且operation在其allowlist内才可执行；所有path-based mutation、INPUT FD write、unregistered FD、
shared writable mapping或metadata write一律deny并增加violation count，receipt不得PASS。
`truncate/ftruncate/chmod/chown/link/rename/unlink/mkdir`等继续全部deny。平台不能给出逐次
syscall→FD判定与完整receipt时FAIL closed。

## 3. Receipt exact additions

V4在V3 exact fields中增加：

```text
invocation_root_path,invocation_root_device,invocation_root_inode,
closure_segment,input_identity_sha256,fd_policy_digest
```

`fd_policy_digest=SHA256(concat(LP(canonical JSON bytes of each observed_fds row)))`，rows按FD数值
排序唯一。`execution_id`、slot path、closure segment、input identity、root identity和所有FD
identity均由supervisor重算；parser/resolver无receipt或目录写权限。任一collision、路径逃逸、
FD替换或operation mismatch均FAIL，且不发布业务输出或receipt。

## 4. Boundary

本文只冻结未来synthetic contract-test设计；不创建live authority，不运行M7、fit、replay、真实
数据、PIT、预算变更或final-OOS。
