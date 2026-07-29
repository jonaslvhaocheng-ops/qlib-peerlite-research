# M6.5 R3 修复设计 v10 — 有效 hash seed 的启动合同

状态：`IMPLEMENTATION_READY / 待独立设计审查`  
Risk：`R3`  
Requirement：修复 v9 审查发现的唯一 P1：不能把被 `python -I` 忽略的 `PYTHONHASHSEED` 当作有效确定性证据。

本文件不授权真实 M7、CCC/Gate、server replay、final OOS、生产交易或任何 M6 immutable/history mutation。

## Canonical incorporation

这是唯一 canonical change-design artifact，按固定顺序组成：

1. `m6_5_repair_change_design_v6.md` SHA-256 `2130f8659f132fb637898d6ddfb78f8af4ccab1c7b4b52c12899111643a95f78` 的 §1、§2、§3、§4、§7 原样保留；
2. `m6_5_repair_change_design_v9.md` SHA-256 `11059be45e9ae8d5cc46dff2a5662e4d4001814b4b604ce862b4cb1c722d75f6` 的 §5.1、§5.2、§5.4、其它 non-runtime sections 原样保留；
3. 本文件 §3 完整替代 v9 §5.3，§4 完整替代 v9 §6；
4. 架构依据是 `architecture_confirmation_v13.md` 和 frozen `research_governance_threat_model_v1.md`。

所以 v9 已修复的 no-cycle Plan/QRC DAG、post-exec-only claim、CLOSING-versus-permit linearization、RunnerExecutionClosure/publisher binding、actor nonalias ACL policy 和 M6 v5 input inventory 全部保留；只有 Python 启动策略被替换。

## Problem and scope

`-I` implies `-E`, so CPython ignores every `PYTHON*` startup variable before bootstrap. The prior v9 design simultaneously demanded `PYTHONHASHSEED=0`, `-I -S`, and rejection of `PYTHON*`; strict implementation could not start, while a relaxed implementation could record a matching environment although effective hash randomization remained on. This is an ordinary launch-flag/configuration error inside the frozen threat model.

The needed behavior is a deterministic **effective** hash policy for M7 authoritative fit and M6 archival replay without reopening user site/path/environment injection. The bounded solution is not an embedded-Python framework: it reuses the approved Linux FD-exec helper and a new immutable `PythonStartupPolicy v1`.

## Repository evidence and options

The existing replay path already needs a native FD-exec helper/bootstrap because it stages a measured interpreter/runtime. `pyproject.toml` requires Python 3.11 for the project runtime; the local desktop Python may not support `-P` and remains synthetic-only, which reinforces the Linux CPython 3.11 authority boundary.

| Option | Decision |
|---|---|
| Keep `-I` and record environment seed | Rejected: seed is ignored before bootstrap |
| Remove hash seed and prove all code never depends on hash order | Rejected for M6.5: proving all frozen/external stack paths are hash-order independent is broader and less direct than a fixed startup contract |
| Embed CPython/PyConfig launcher | Viable but adds a linked-libpython/runtime build surface not needed for this project |
| Chosen: exact envp + `-s -S -P` + pre-import effective-policy assertion | Uses existing FD-exec/bootstrap boundary; keeps site/path isolation while making seed effective |

## Proposed design

### 1. Immutable `PythonStartupPolicy v1`

`RunnerExecutionClosure v2` (`purpose=AUTHORITATIVE_FIT`) and `ReplayRuntimeClosure v3` (`purpose=ARCHIVAL_REPLAY`) each embed an immutable `PythonStartupPolicy v1`:

```json
{
  "python_abi": "exact CPython-3.11 closure ABI",
  "argv_flags": ["-s", "-S", "-P"],
  "forbidden_flags": ["-I", "-E"],
  "effective_hash_policy": {
    "mode": "fixed",
    "pythonhashseed": "0",
    "expected_hash_randomization": 0,
    "probe_text": "qlib-peerlite",
    "expected_probe": "closure-construction integer result"
  },
  "expected_sys_flags": {
    "isolated": 0,
    "ignore_environment": 0,
    "no_user_site": 1,
    "no_site": 1,
    "safe_path": 1,
    "hash_randomization": 0
  },
  "allowed_python_environment": {"PYTHONHASHSEED": "0"},
  "environment": "exact complete key/value map and digest",
  "required_python_minor": "3.11"
}
```

The complete map includes only the policy-approved Python seed and fixed non-Python execution values: `TZ`, locale, deterministic OMP/MKL/OpenBLAS/NumExpr settings, GPU visibility/UUID, CUDA/cuDNN/cuBLAS identities, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, cache/temp roots and umask. All remaining `PYTHON*`, `PYTHONPATH`, `PYTHONHOME`, venv/conda variables, `LD_*`/`DYLD_*` injection variables and unspecified environment entries are forbidden. `required_python_minor=3.11` makes a missing `-P` an explicit rejection, not a platform fallback.

### 2. Launch and bootstrap sequence

1. supervisor verifies policy/interpreter/runtime/source tree by FD/hash and constructs a new `envp` vector from the policy; it never inherits parent env;
2. approved helper invokes the measured staged interpreter FD with canonical staged `argv[0]`, fixed cwd, exact `-s -S -P` flags and staged stdlib-only bootstrap path; helper records actual argv/env/FD identity;
3. bootstrap runs before runner/verifier/module import or snapshot read. It checks stage origin/prefix, exact envp, forbidden variables absent, `sys.flags`, `PYTHONHASHSEED`, fixed hash probe and supported `-P`; it validates no `site`, `sitecustomize` or `usercustomize` import and then installs only closure `sys.path`/import guard;
4. bootstrap publishes `EffectiveHashPolicyReceipt v1`; only after this does M7 worker derive post-exec ProcessIdentity/create claim, or M6 verifier resolve its sealed root;
5. execution receipt records policy digest, effective receipt, observed flags/probe/import/native maps. Claim/dispatch/prepared/terminal and archive acceptance require expected/observed equality.

The helper's clear environment plus `-s -S -P` replaces the rejected `-I` isolation layer: no user site, no automatic `site`, no unsafe script/cwd path prepending, no inherited `PYTHONPATH`/`PYTHONHOME`, and a bootstrap-import guard. Any implementation that uses `-I`, `-E`, bare path/PATH execution, inherited env or an environment digest without effective receipt fails closed.

### 3. Failure, compatibility and observability

Missing seed, another seed, unexpected `PYTHON*`, `-I`/`-E`, unsupported Python/minor/`-P`, flag mismatch, probe mismatch, unexpected site/module origin, tree/ABI/GPU/config drift or late native-map mismatch fails before M7 claim/permit or M6 verifier acceptance. `RunnerExecutionReceipt v2` and `ReplayExecutionReceipt v5` carry `startup_policy_digest`, `effective_hash_policy_receipt`, actual argv/env/flags/probe and expected/observed closure digests; publisher and `m6_archive` reject absent/mismatched fields.

This is Linux CPython 3.11 authority behavior. macOS or nonconforming environments may produce only synthetic test evidence. No result/budget/history is migrated or changed; a failed startup is pre-fit (unless event was already `START_RETAINED`, in which case normal conservative event accounting remains in force).

## Verification obligations

The later test-design matrix must prove:

- `-I`/`-E` with env-only seed is rejected rather than accepted as deterministic;
- two fresh staged `-s -S -P` processes have exact expected flags and fixed hash probe;
- missing/different seed, arbitrary `PYTHON*`, `PYTHONPATH`, sitecustomize, cwd path shadow, unsupported Python and runtime/ABI/native map changes fail before claim/permit or replay acceptance;
- a deliberately hash-order-sensitive synthetic runner produces a stable observed policy/behavior under this startup contract;
- effective-policy receipt substitution or mismatch prevents terminal publication and archive acceptance.

All obligations remain synthetic; they prove launch governance only, not alpha, M7 eligibility, server replay success or final-OOS performance.

## Ordered implementation update

1. Add strict `PythonStartupPolicy` / `EffectiveHashPolicyReceipt` schemas and closure parser validation.
2. Extend FD-exec helper to construct exact envp and reject `-I`/`-E`/unsupported `-P` before exec.
3. Extend staged bootstrap to validate effective flags/probe before imports and emit receipt.
4. Thread receipt equality through M7 dispatch/publisher and M6 replay/archive parsers.
5. Add router-approved synthetic red/green/E2E tests, then re-run independent code review; do not run real M7/replay/OOS.

## Open decisions

None. If Python 3.11 `-s -S -P` cannot be verified with exact effective policy, authority execution is blocked rather than weakened.
