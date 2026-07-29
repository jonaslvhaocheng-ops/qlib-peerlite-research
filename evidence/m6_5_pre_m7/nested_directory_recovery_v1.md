# NestedDirectoryRecoveryV1

- 状态：`DESIGN_ONLY`
- 适用：PREPARED已发布后的input/output immutable directory transaction。

## 1. Fixed artifacts

```text
.<target>.publish.lock
.<target>.PREPARED.json
<target>/
<target>/PUBLISH_COMPLETE.json
.<target>.COMMITTED.json
```

PREPARED strict绑定target parent/name、attempt ID、schema/content UUID、payload directory/file
inventory ArtifactRef、staging inventory ArtifactRef、runtime policy/code SHA。payload inventory
不含internal/sibling markers。

PUBLISH_COMPLETE strict绑定PREPARED file/canonical SHA及payload inventory file/canonical SHA。
sibling COMMITTED strict绑定target、PREPARED、completion、payload inventory及final modes。
三者0440；payload files0440；final dirs0550。

## 2. Recovery locks and state machine

worker持attempt lease，再取target parent publish lock；不得同时持GC lock。读取全部paths用parent/
root FDs no-follow。

1. sibling COMMITTED存在：完整验证PREPARED/completion/inventory/modes/fsync evidence；valid返回
   COMMITTED，invalid HOLD，不改payload。
2. PREPARED不存在：本spec不适用，返回NOT_PREPARED。
3. PREPARED存在、completion不存在：
   - exact staging存在且inventory匹配：创建/验证root dirs0700，逐file no-follow hardlink；
     existing必须type/size/hash/inode-compatible；fsync files/dirs；发布completion；
   - staging缺失或不匹配：HOLD，不abort/删final。
4. completion存在、sibling缺失：验证payload exact；descendant dirs bottom-up chmod/fsync0550，
   root chmod/fsync0550，fsync parent；发布sibling COMMITTED并fsync parent。
5. sibling发布后只验证。

crash可从任一步按same PREPARED bytes重入。不同PREPARED、extra/missing payload、symlink/device/
FIFO/socket、mode/hash冲突均HOLD。无overwrite/delete/quarantine。

## 3. Capacity interaction

release parent publish lock后才取得GC lock；发布CapacityReservation COMMITTED，随后执行
POST_COMMIT unlink-only cleanup。recovery永不发布ABORTED。input/output各有独立transaction和
PREPARED/COMMITTED链。
