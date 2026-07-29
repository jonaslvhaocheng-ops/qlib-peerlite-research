# M7 CCC / 市场状态 Gate 设计 v18

- 状态：`DESIGN_ONLY / NOT_AUTHORIZED`
- Base：`m7_change_design_v17.md`
- Base SHA：`b776b3e05abccb9a8aaf2a72190c9defcb48f4815a326823f2283897f9a1337c`
- 取代：M7 v17。

## 1. Sandbox filesystem allowlist and execution receipts

除V17 deny set外，explicit DENY：

```text
openat2,creat,unlink,unlinkat,rename,renameat,renameat2,link,linkat,
symlink,symlinkat,mkdir,mkdirat,rmdir,truncate,ftruncate,chmod,fchmod,
fchmodat,chown,fchown,fchownat,mknod,mknodat,mount,umount,pivot_root
```

唯一写入是supervisor预先打开并授权的OUTPUT FDs；sandboxed parser/resolver本身无namespace/path
mutation syscall。platform不能实现完整allowlist和seccomp/sandbox-equivalent receipt时FAIL。

每次closure execution唯一`execution_id=sha256(invocation canonical SHA||0x1f||closure canonical
SHA||0x1f||field/domain||0x1f||input identity).hexdigest()`。receipt slot：

```text
<invocation_root>/runtime-closure-receipts/<closure_id>/<execution_id>.json
```

RuntimeClosureReceiptV3在V17 V2 exact新增`execution_id,field,domain_code,input_artifacts,
output_artifacts`，并绑定slot path。每个execution一receipt；arrays排序唯一；重复slot different
bytes HOLD。

## 2. One-way trusted equality

删除“policy authorization ref”比较。唯一DAG：

```text
ParentGovernanceAuthorization -> IssuerRegistryPolicy
IssuerAnchorRegistration -> both Authorization and Policy
FreezeReceipt -> Authorization + Policy + Registration + Commit
```

CLI authorization ref必须等于observed ParentGovernanceAuthorization；其
`authorized_issuer_registry_policy`必须等于observed policy ArtifactRef。policy不回引
authorization。root和validator closure继续按V17表逐字段相等。

## 3. JSONL evidence storage and manifest digests

采用JSONL方案，不使用row ArtifactRef。Observation row中的`evidence_record`替换为：

```text
evidence_kind=LIST|DELIST
evidence_artifact_file_sha256
evidence_record_id
evidence_record_canonical_sha256
```

record由artifact file SHA+record ID全量scan定位，ID在文件内唯一，canonical SHA重算；row全部
lineage fields与record exact equality。LIST/DELIST evidence artifacts按kind排序恰2个。
historical_source_manifests按path UTF-8排序、ArtifactRef unique、nonempty；每row的manifest ref
必须属于声明集合，声明集合每项至少被一row使用，无未声明/unused manifest。

Observation key bytes：

```text
key_bytes=LP(security_id UTF-8)||LP(field ASCII)||LP(observation_id ASCII)
value_bytes=canonical JSON bytes of exact row excluding the three key fields
schema_bytes=canonical JSON bytes of the exact ordered field-name/type/nullability schema
```

rows按key tuple排序唯一：

```text
key_digest=sha256(concat(LP(key_bytes)))
value_digest=sha256(concat(LP(value_bytes)))
logical_digest=sha256(LP(schema_bytes)||concat(LP(key_bytes)||LP(value_bytes)))
```

这取代V17欠完整digest prose并与AP schema-bound逻辑一致。empty rows非法。
