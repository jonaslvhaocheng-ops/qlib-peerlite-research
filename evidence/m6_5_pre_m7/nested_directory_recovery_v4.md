# NestedDirectoryRecoveryV4

- 状态：`DESIGN_ONLY`
- Base：`nested_directory_recovery_v3.md`
- Base SHA：`0e527f208826a99d04e92a4710887a2d10a4501dcf1bfbde82d494dd4f714f83`
- 取代：V3。

## 1. Fixed paths

completion不再位于final root，全部transaction controls为siblings：

```text
publish_lock    = target_parent/("."+target_name+".publish.lock")
prepared_path   = target_parent/("."+target_name+".PREPARED.json")
target_root     = target_parent/target_name
completion_path = target_parent/("."+target_name+".PUBLISH_COMPLETE.json")
committed_path  = target_parent/("."+target_name+".COMMITTED.json")
```

因此final root全量no-follow scan必须exact等于payload logical paths，无内部control exclusion。
target parent只允许以上三个final controls、publish lock及当前fixed temp；其他target-prefixed
unknown entry HOLD。

## 2. Phase order

PREPARED继续只绑定STAGING_PHYSICAL和PAYLOAD_LOGICAL，不预报final inode。恢复状态机唯一顺序：

1. 以0700创建final dirs并hardlink files；全量scan exact payload；
2. 发布PRE_SEAL_FINAL_PHYSICAL，验证logical bijection、dirs0700、files0440、same file inodes；
3. descendant dirs bottom-up chmod0550+fsync，root chmod0550+fsync，fsync target parent；
4. 只读scan并发布SEALED_FINAL_PHYSICAL，验证dirs0550、files0440和same file inodes；
5. 发布sibling PUBLISH_COMPLETE，绑定PREPARED、PAYLOAD_LOGICAL、
   PRE_SEAL_FINAL_PHYSICAL、SEALED_FINAL_PHYSICAL；
6. 发布sibling DIRECTORY_COMMITTED，重复上述refs及root identity；
7. 释放parent lock，取得GC lock，发布Capacity COMMITTED；
8. POST_COMMIT unlink staging，发布CLEANUP与POST_CLEANUP_LINK receipts；
9. 发布RELEASED并seal reservation dirs。

completion/committed exact schemas采用V3但以
`pre_seal_final_physical_inventory`和`sealed_final_physical_inventory`替换单一final ref。
V8 §5 temp协议适用于全部JSON。

## 3. Long-term validation and recovery

completion前的crash按最后durable phase继续；若PRE_SEAL已存在而modes部分改变，则按其记录的
path/inode/content验证后幂等完成0550 seal，再发布SEALED；不得重写PRE_SEAL。

SEALED发布后final tree只读。staging cleanup前same-inode+nlink>=2；cleanup后通过
POST_CLEANUP_LINK逐path证明staging absent、final inode unchanged及post nlink=1。长期validation
使用SEALED dev/inode/size/hash/mode + cleanup/link receipts，不要求current nlink等于seal时值。
任一unknown final-root entry、phase倒序、inventory/path/hash/mode冲突均HOLD。
