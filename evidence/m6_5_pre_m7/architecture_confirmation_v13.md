# M6.5 架构确认 v13 — 有效 Python hash policy 的封闭启动

状态：`ARCHITECTURE_READY / 待独立设计审查`。本文件只修复 v12 中 `PYTHONHASHSEED` 与 isolated mode 的实际 CPython 语义矛盾；不改变冻结的研究治理 threat model，也不授权真实 M7、archive replay、CCC/Gate、final OOS 或 M6 history mutation。

## 1. Canonical composition

当前架构为：

1. `architecture_confirmation_v9.md` SHA-256 `e4e0bb71e12dea48d6fa3db4bb0331804240f55d505771810dfa3befbd312598` 的 §1、§2、§5；
2. `architecture_confirmation_v12.md` SHA-256 `f80ca2a93ecca804f0c8c7ecc604eee26d0ad2b08f93d5b8bbf71afc26aa38ad` 的 §2、§3、§4，以及 §6 的第一段（descriptor-bound publisher transaction）；
3. 本文件 §2 完整替代 v12 §5（M7 authoritative execution closure）和 v12 §6 的第二段（M6 replay startup/runtime policy）。

v12 其它 graph、post-exec claim/permit-close linearization、non-alias actor/ACL、publisher transaction 与 M6 input binding requirements 原样保留。`-I`/`-E` 在所有 hash-seeded authoritative launch 中不再是允许的启动选项。

## 2. `PythonStartupPolicy v1`: effective seed, not an environment string

M7 `RunnerExecutionClosure v2` 与 M6 `ReplayRuntimeClosure v3` 都包含一个 immutable `PythonStartupPolicy v1`。该 policy 在 CPython **初始化之前**由 approved FD-exec helper 兑现，字段包括：

```text
python_version = CPython 3.11.x exactly bound by closure
argv flags = -s -S -P (and no -I / -E)
environment = exact envp map, constructed by helper from scratch
allowed PYTHON* = only PYTHONHASHSEED=0
forbidden PYTHON* = every other Python startup variable
expected flags = isolated=0, ignore_environment=0, no_user_site=1,
                 no_site=1, safe_path=1, hash_randomization=0
hash probe = canonical hash("qlib-peerlite") under exact interpreter ABI
```

The helper uses `execveat(AT_EMPTY_PATH)` / `fexecve` on the measured staged interpreter FD and passes only this constructed `envp`; it does not inherit the supervisor's environment. Non-Python entries are also exact closure fields (locale/timezone, deterministic thread/CUDA/GPU/cache/temp/umask values); `PYTHONPATH`, `PYTHONHOME`, `PYTHONINSPECT`, virtualenv/conda variables, loader injection variables and any unlisted entry are absent before exec. `-s` suppresses user site, `-S` suppresses `site`/sitecustomize loading, and Python 3.11 `-P` forbids unsafe path prepending. The closure requires that `-P` is available; an interpreter without it fails closed.

This intentionally does **not** use `-I`: CPython isolated mode implies `-E` and ignores `PYTHONHASHSEED` before bootstrap. A bare `-s -S -P` would be insufficient if a caller could choose its environment, so the exact envp construction, FD execution, stage-root validation and import guard are mandatory parts of the same policy.

The stdlib-only bootstrap executes as the first staged script. Before importing runner/verifier/source or reading a snapshot it verifies: actual argv / executable / prefix / `sys.path`; exact environment map; all expected `sys.flags`; `os.environ["PYTHONHASHSEED"] == "0"`; `hash("qlib-peerlite") == expected_probe`; no site/usercustomize import; and no non-closure module origin. It then installs the closed import roots/guard. `EffectiveHashPolicyReceipt v1` records startup policy digest, actual flags, effective seed mode/value, probe result and observed interpreter ABI.

`RunnerExecutionReceipt v2`, `ReplayExecutionReceipt v5`, claim/dispatch/prepared/terminal receipts and archive acceptance bind this effective receipt—not merely the environment digest. A wrong seed, absent seed, `-I`/`-E`, unsupported `-P`, unexpected `PYTHON*`, flags/probe mismatch, or any pre-bootstrap source import fails before claim/permit (M7) or replay verification (M6). The exact policy also ensures two fresh staged processes show the same effective hash behavior; a deliberate hash-order-sensitive synthetic probe is part of the test seam.

## 3. Consequences and no-fallback rule

This is a Linux CPython 3.11 closure requirement. macOS synthetic adapters may unit-test policy parsing but cannot issue authoritative M6/M7 execution evidence. A server where measured Python cannot run `-s -S -P` with the exact startup policy is `BLOCKED` for authoritative execution; it must not silently fall back to `-I`, `-E`, path execution, an inherited environment or an environment-only receipt.

All earlier v12 controls remain unchanged: closure bootstrap still runs before runner/verifier imports; post-exec claim/permit still validates observed closure; actor ACL enforcement remains activation-time and operational; and M6 replay remains 14 replay / 0 fit / OOS=false until later quality stages authorize anything else.
