# M6.5 架构确认 v6 — Control Plane 与 Replay Launch Grant 补充

状态：`PASS — bounded architecture amendment`  
替代关系：当前架构依据为 `architecture_confirmation_v5.md` 加本补充；本文件替代 v5 作为质量账本中的
当前 architecture artifact。它不改变 v5 的 legacy Gate deny、PIT `CERTIFY` data plane、6/44 new namespace
或 M7/OOS 封印。

## 1. 为什么需要此补充

v5 已确定 registry 和 trusted launcher 是外部信任根；实现设计进一步明确了两个必要条件：

1. registry 不能是 runner 可改的普通文件，也不能以可变 `current.json` 代表授权；它必须由冻结派生
   contract 指向的 control plane 单向部署。
2. launcher receipt 若离开 server governance root，只是可复制 JSON，须附有可独立验证的签名；launcher
   还必须绑定 runtime，而不只绑定 Python 源码。

它们细化同一 trust boundary，不扩大研究范围或引入新的模型/数据路径。

## 2. Authority control plane

```text
future FROZEN M7 derived contract
  -> immutable RunAuthorityRegistrySnapshot SHA
  -> governance-owned control-plane root (runner read-only)
  -> content-addressed Registry / Grant / Authority files
  -> authority lease + server-only ledger writer
```

- `RunAuthorityRegistry v1` 仅登记允许的 `RunAuthorityGrant v1`；grant 与 authority 是不同对象，前者是
  contract-rooted permission，后者是完整 event plan。二者逐字段绑定 budget/spec/parent/journal/output/plan。
- 生产 runner 仅可提供 authority ID。所有 path 从 grant 推导；registry/grant/authority/ledger 均在治理
  control-plane root，研究 runner 无写权限。
- 所有对象使用 content-addressed version file；禁止通过 mutable pointer 覆盖授权。安装器在 lock 下 atomically
  publish，校验 owner/mode/regular-file/`nlink==1`，并以 `openat` + `O_NOFOLLOW` 读取。
- 这一控制面缓解错误调用或一般调用方伪造对象；它不声称抵抗治理 root/内核被攻破。一旦后者发生，运行和证据
  均无效，需重新建立受信部署。

## 3. Replay launch control plane

```text
frozen M6ReplayLaunchGrant
  -> governance deployment bundle + runtime profile
  -> ReplayDeploymentReceipt
  -> FD-pinned staging launcher
  -> signed M6ReplayAcceptanceReceipt + child receipt
```

- `M6ReplayLaunchGrant v1` 固定 replay input binding、launcher/validator bundle、受控 interpreter/venv/lockfile、
  source identities、唯一新 output、14/0/OOS=false profile 与 Ed25519 public-key fingerprint。
- deployment installer 只从 governance root 读取 grant/binding；launcher 使用 same-FD hash-and-copy 的 staged
  verifier/archive、fixed `python -I`、environment allowlist、fixed cwd 和 read-only ledger shared lock，避免
  hash-to-exec 与 runtime/module injection。
- `M6ReplayAcceptanceReceipt` 由 launcher 而非 verifier 写出，绑定 staged bytes、runtime、sanitized argv/env、
  child result、output and ledger identities。若该 receipt 复制到本地 evidence，它需有治理 control plane 对
  canonical bytes 的 detached Ed25519 signature；`m6_archive` 必须验证 grant/binding/signature/child linkage。
- 新 output 必须不存在；复用或覆盖旧 PASS 输出不可接受。

## 4. 影响和仍未通过的事项

本补充要求 design/tests 覆盖 control-root substitution、owner/mode/link、registry/grant substitution、runtime
substitution、staged hash-to-exec、existing output 及 detached-signature failure。它仍不允许真实 M7 grant、
M7 fit、PIT 认证或 final OOS。下一关是独立 review change design v3；只有其 PASS 后可进入 test-first 实现。
