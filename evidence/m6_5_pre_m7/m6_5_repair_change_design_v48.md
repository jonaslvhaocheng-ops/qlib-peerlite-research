# M6.5 有界修复变更设计 v48

- 状态：`DESIGN_ONLY / READY_FOR_INDEPENDENT_R3_REVIEW`
- Architecture：`architecture_confirmation_v28.md`
- 风险：`R3`
- 取代：v47。

## 1. Normative bundle

```text
gate v2 609297714b832136a242cb07981e7493ec9780f49caa6f5bd6c2c3f84a0f1d13
budget binding v2 dd162de1565f887261cebbaef3eeec50c83697125a2acf5adb1546e8e819fcf4
static binding v2 a12cebd94a1bf0da6bbd607f7e95227de3573bd409d16a41ad84711faf5dfad1
replay binding v2 0c01c5eb95e71ad8644df09e2eba8d56fc8cb694f8e41ace0021e7f51913aa01
component v6 ab5a7d3feba7fd684ee489918f1f7378763a5fb321a3e7143d58e069ad5888f8
replay contract v5 524d182fbc701cc15be6e47b8c7d7d5043991d347a53538eb5e285eda1499146
M7 design v5 de4aa33331443f7e7e97470d401a79d8d8b1e631163800c36a2ddabffe9f6715
matrix v6 b7f8b475d8aeaa152eaae45fee54711e1246ebcc6b2eff85d763a627739870af
closure v6 bfd161ae21c8e81948c5d58e99103742397f47aa43a02be0d063cd83513385c2
```

## 2. Sole v47 repair

snapshot slot新增`ledger_before_sha256`。同run/journal下先枚举和验证全部immutable snapshots：
若旧missing set已提交则恢复；若完全未出现且另一合法journal已推进ledger，则以advanced
ledger-before创建新slot，旧snapshot不变；若partial/interleaved出现则FAIL。receipt slot绑定
selected snapshot slot和committed prefix。matrix新增precommit crash→other append→successful rebase、
partial conflict和multi-recovery ambiguity。

## 3. Boundary

没有改模型、数据口径、预算、screen规则或系统架构。仍是四个bounded workstreams；M6 PASS 6/44，
M7 NOT_RUN，ceiling8/60。当前仅允许read-only design review，不授权test/implementation/replay/
fit/PIT/real data/budget/final OOS。
