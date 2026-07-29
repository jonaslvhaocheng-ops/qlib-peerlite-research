# M6.5 v5 / v8 独立对抗式设计审查

审查结论：`NEEDS_CHANGES`  
审查方式：独立、只读、对抗式设计审查；未修改产品代码、测试、契约、gate 或质量 ledger，未运行训练、server replay 或访问最终 OOS。

审查对象：

- `evidence/m6_5_pre_m7/m6_5_repair_change_design_v5.md`，SHA-256 `6936ab070bdb5bc2045d1fac479300a7b1ba0964c49c5e16abd7d5824ac6275b`
- `evidence/m6_5_pre_m7/architecture_confirmation_v8.md`，SHA-256 `ff63cb6791743ec57207b19fd27fd33891e772c95c3991215d78272dc6bc2b5e`

对手模型不假设 governance control root、pinned signer 私钥或内核被攻破；但允许一个正常的 runner 身份进行
Python/CLI 调用、使用 native/`ctypes` fork、继承自己已获得的 descriptor/FD、改变自身启动环境，以及对其被授予
的输出路径进行普通文件操作。这正是 v5/v8 声称要 fail-closed 的边界。本报告只列可使未认证输入、第二次 fit、未知
输出或错误 replay 进入官方接受路径的 P0/P1。

## Findings

### [P1] `O_EXCL` 只选出 claim 创建者；claim 创建后的 native fork 仍可让父子跨越同一 `model.fit` 边界两次

**位置：** v5 §4，第 109–117 行；v8 §4.1，第 66–74 行。

**场景：** 合法 worker 已取得 sealed descriptor/FD，成功创建并 fsync event-specific `O_CREAT|O_EXCL` claim，且
尚未进入 `model.fit`。它随后通过普通 native extension 或下列 Python 调用执行 libc 的 raw `fork()`：

```bash
python3 -c 'import ctypes, os; os.register_at_fork(after_in_child=lambda: os.write(1,b"ATFORK_HANDLER\\n")); pid=ctypes.CDLL(None).fork(); (os.write(1, (b"CHILD\\n" if pid==0 else b"PARENT\\n")) if pid>=0 else None); (os._exit(0) if pid==0 else os.waitpid(pid,0))'
```

本次只读审查实际输出为 `PARENT`、`CHILD`，没有 `ATFORK_HANDLER`。因此 v5 的
`os.register_at_fork` child handler 不是一个对 raw/native fork 有效的执行边界。父子会继承同一已获胜 claim、
admission、sealed FDs 与内存状态；`O_EXCL` 已经完成，无法再把两者竞争为两个 claim。

设计要求 claim 记录 PID/process-start/boot identity，却没有规定 guard 在 **实际 call boundary** 强制把当前进程
identity 与 claim owner 比较；即使补上一次比较，攻击者仍可在该比较之后、`model.fit` 之前 fork。`Supervisor
prohibits fork` 也没有定义 syscall-level enforcement。于是一个完全合法的 parent/child pair 可以用同一已
`DISPATCHED` 事件分别抵达 model call；账本仍只有一项事件，预算与真实 fit 次数再次脱钩。

**影响：** v8 的“每 event 至多一次 observed fit call”不成立。它不需改 control root、签名或 ledger，只需在
合法 runner 里使用一个普通 native fork 路径。

**修复方向：** 将 at-most-once 从 Python callback 提升为不可绕过的执行边界：例如由独立、一次性的 execution
broker 持有唯一 lease 并实际调用模型，或在 dispatch 后以 OS 机制拒绝 `fork`/`vfork`/`clone`（并在 broker 侧验证
claim owner 的 pid/start identity）。仅在 guard 中做 pre-call PID 检查不足以消除“检查后 fork”的 race。红测必须
覆盖 `ctypes.CDLL(None).fork()` 在 claim 后和 pre-fit hook 中的情形，并由 call-boundary spy 证明总计恰好零或一次
`model.fit`，绝不能两次。

### [P1] fit 的 official-result 发布只有 Python 约定，没有与 runner 隔离的写入/签名能力；未认证 state 或未知输出可自洽地进入 resolver

**位置：** v5 §3，第 85–101 行；v5 §5，第 121–135 行；v8 §3，第 55–60 行；v8 §4.2，第 78–88 行。

**场景：** v5 把 `FitAdmissionDescriptor` 定义为 signed/opaque，但没有把 `PreparedResultReceipt`、
`TERMINAL_PUBLISHED` index record 或 final-root writer 定义为由 runner 无法伪造的签名/独立 Unix identity。相反，
同一 guard/worker 被要求写 staging、rename 到 final 并 append official-result index。`M7ResultSink inside
ModelFitExecutionGuard` 与 “direct private import fail”只是 Python 模块/调用约定；文档没有为它们给出 capability
object、独立进程、ACL、不可导入执行服务或签名验证。此处与 v5 §6 明确分离 replay grant issuer、launcher、acceptance
signer 的 Unix identities 形成直接对照。

一个正常 runner 身份已经合法持有有效 descriptor `D`（其中含 event root、descriptor identity 和输出 policy）时，
可以在同一解释器中直接调用模型/序列化私有实现，用任意 raw 或 synthetic state 产生输出，再以 `D` 的身份字段写出
自洽 inventory、prepared receipt、terminal receipt 和 `TERMINAL_PUBLISHED` record。没有独立 issuer 会证明这些字节
确实由 guard 用 descriptor 指定的 sealed state 构建。`OfficialResultResolver` 被要求接受“published-index record +
matching terminal receipt/inventory”，但没有要求一个非 runner 发行者、live `openat`/`O_NOFOLLOW`/regular-file rehash
或 final root 的不可变封存。因此此 record/receipt 对可以让错误 state 的 score 作为 official result 被解析。

同一缺口还允许 terminal 后的路径替换：final root 没有定义 chown/ACL transition、fs-verity/content-addressed seal、
禁止 symlink/hardlink，或每次 resolver 读取时的 live type/hash verification。即使初次 receipt 是真的，runner 身份仍
可替换 `predictions.parquet`（或让 staging inventory 接受指向可写外部目标的 link）；index/receipt 依然彼此匹配。

**影响：** v5/v8 对“direct private import、raw tensor 或 post-publication unknown output 不能产生 official artifact”
的承诺在普通调用路径上没有可执行的信任边界。该缺口既可把未认证 state 伪装成已认证 descriptor 的产物，也可让未知
score 进入模型选择、回测和报告。

**修复方向：** runner 不得拥有 final/index 的发布 authority。让一个与 runner 隔离的 supervisor/result broker 持有
terminal signing key 或仅它可写的 append authority；它必须从 sealed state/candidate FDs 自己执行/验证 guard 的输出，
然后对 descriptor、claim、exact regular-file inventory 和 final object 签名。final result 应在 publish 后变为
content-addressed、non-writable object，resolver 必须从 broker-signed record 以 `openat`/`O_NOFOLLOW` 读取并重新
验证 type、nlink 与 bytes hash。红测应证明：直接 import、构造 self-consistent receipt、替换 final file、symlink/
hardlink 注入和 terminal 后 mutation 都不能被 resolver 接受。

### [P1] replay 只测量 launcher/runtime 静态树，未固定实际 `execve` 环境与 loader/import 状态；正确 launcher 仍可运行错误 replay

**位置：** v5 §6，第 139–150 行；v8 §5，第 93–101 行。

**场景：** 调用者以经过授权的 launcher bundle、正确 entrypoint 与符合 grammar 的 argv 启动 replay，同时传入
`LD_PRELOAD=/path/to/shim.so`、`PYTHONPATH=/path/to/override`，或等价的 Python startup/dynamic-loader environment。
launcher 的 bytes/tree digest、entrypoint、argv、静态 interpreter/site-package inventory 都不会变化；但 shim 或
import override 可改变 launcher/child verifier 的 `open`、hash、import 或实际 replay 行为。它可以让 child 跳过真实
重放、复用旧输出，或对 verifier 的 input/output observation 做替换，同时保留被设计要求的静态 measurements。

v5 要求 acceptance service “verifies runtime”，但没有定义受签/allowlisted `execve` environment、动态 loader state、
`/proc/<pid>/maps`/effective import closure 的独立测量，亦没有规定 supervisor 使用 clean `execve`。因而一个完全符合
v5 已列出 launcher digest/argv/runtime-file checks 的实现仍可继承攻击环境。acceptance signer 隔离了签名 key，却看
不到一个受环境污染而仍报告预期 bundle identity 的已批准 launcher；签出的 payload 便可把错误 replay 接入官方 M6
acceptance path。

**影响：** 这保留了一个“正确 bootstrap bytes、错误实际 execution”的 replay 路径，绕过本轮刚补强的 launcher
identity chain，而不需要替换 launcher 文件、伪造 Ed25519 或更改 control root。

**修复方向：** grant/activation/runtime bundle 必须固定并签名实际执行环境（通常 supervisor 用 `execve` + `env -i`
和严格 allowlist），显式拒绝 `LD_PRELOAD`、`LD_LIBRARY_PATH`、`PYTHONPATH`、`PYTHONHOME`、site customization 及
未登记 loader flags。acceptance 还应独立验证受控 process 的 effective executable, loader map 与 import closure，或
在固定 OCI/隔离 runtime 中运行并将其 measurement 签入 payload。红测必须对上述每一种 environment injection 在 child
启动前或 acceptance 前 fail-closed，不能只测试 launcher 文件替换。

## Verdict

`NEEDS_CHANGES`。最早修复阶段为 `architecture`：三个问题分别决定真实 fit 的 at-most-once 边界、官方结果的
发布 authority，以及 replay 的实际执行身份；无法由后续 unit test 或 Python-private naming 补救。

在修复并通过新的独立 design review 前，M7 derived-contract freeze、真实 M7 fit、CCC/Gate、server replay 与最终
OOS 仍应保持禁止。

```json
{
  "schema_version": "1.0",
  "change_id": "m6-5-pre-m7-repair",
  "ledger_revision_observed": 42,
  "stage_id": "design-review",
  "skill": "eng-review-design",
  "mode": "independent-adversarial-read-only-review",
  "verdict": "NEEDS_CHANGES",
  "reason_code": "POST_CLAIM_FORK_AND_UNSEALED_RESULT_PUBLICATION_AND_EFFECTIVE_RUNTIME_GAP",
  "summary": "v5/v8 materially improve state evidence, descriptor binding, O_EXCL claims and launcher identity, but raw fork after a winning claim, Python-only official-result publication, and unmeasured execution environment still permit the prohibited outcomes through ordinary calls.",
  "issue_type": "architecture",
  "risk_tier": "R3",
  "unresolved_severity": {"P0": 0, "P1": 3, "P2": 0, "P3": 0},
  "reviewed_design": {
    "path": "evidence/m6_5_pre_m7/m6_5_repair_change_design_v5.md",
    "sha256": "6936ab070bdb5bc2045d1fac479300a7b1ba0964c49c5e16abd7d5824ac6275b"
  },
  "architecture_evidence": {
    "path": "evidence/m6_5_pre_m7/architecture_confirmation_v8.md",
    "sha256": "ff63cb6791743ec57207b19fd27fd33891e772c95c3991215d78272dc6bc2b5e"
  },
  "evidence_paths": [
    "evidence/m6_5_pre_m7/m6_5_repair_change_design_v5.md",
    "evidence/m6_5_pre_m7/architecture_confirmation_v8.md",
    ".engineering-quality/changes/m6-5-pre-m7-repair/ledger.json"
  ],
  "commands": [
    "read-only rg/nl/sed/shasum/jq",
    "python3 -c raw-libc-fork demonstration",
    "quality_ledger.py next"
  ],
  "independence": {
    "mode": "distinct_subagent_review",
    "reviewer_context_id": "/root/design_review_v5_adversary",
    "author_context_id": "/root",
    "limitations": [
      "No product/test/contract/gate/ledger mutation except this independent review artifact.",
      "No M7 training, server replay, budget consumption, real PIT certification, or final-OOS access."
    ]
  },
  "blockers": [
    "M7 derived-contract freeze, real M7 fit, CCC/Gate experiments, server replay, and final OOS remain prohibited."
  ]
}
```
