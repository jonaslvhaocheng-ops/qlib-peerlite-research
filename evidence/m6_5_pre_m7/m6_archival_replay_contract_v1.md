# M6 Archival Replay Contract V1

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Architecture：`architecture_confirmation_v28.md`
- 执行模型：trusted operator调用一个single-process Python command。

## 1. Fixed inputs and write boundary

command只读接收：

```text
frozen source root + frozen source archive + expected archive SHA
expected frozen Git revision
pre-final-OOS product directory
historical M6 run directory
historical verification receipt + expected file SHA
trial ledger
device
```

唯一写参数是一个调用开始时不存在的`output_dir`。其realpath不得等于、包含或被任何input、
project、ledger、final-OOS root包含。command只可在该目录写：

```text
archival_replay_receipt.json
```

失败可以留下无PASS receipt的incomplete output directory，但不得自动删除、覆盖或复用；重试必须
使用另一个不存在的目录。任何input mismatch、output已存在、device不是CUDA、fold mismatch或
score mismatch均不得产生PASS receipt。

## 2. Exact replay identity

固定M6 execution spec：

```text
file SHA: 469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8
content SHA: 60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69
```

expected models和merged prediction files：

| model_id | file SHA | rows |
| --- | --- | --- |
| PEERLITE_K16_MSE | `559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3` | 949014 |
| PEERLITE_K32_MSE | `008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55` | 949014 |

每份exact columns/order：

```text
datetime,instrument,score,model_id,fold_id
```

每model exact七fold：`wf_2018`至`wf_2024`，总计14 checkpoint replays，不多不少。checkpoint
inventory必须逐文件等于historical fold receipt；fold keys/counts必须等于重建Qlib fold。

## 3. Score equality

datetime timezone-aware先转Asia/Shanghai local date；timezone-naive必须是midnight并按calendar
date解释。instrument必须NFC nonempty string，禁止隐式numeric conversion。score必须finite
float64。逐pair的model/fold列必须常量等于outer identity，key `(date,instrument)`唯一，按date
和instrument UTF-8排序。

expected merged file按fold过滤；replay只含该fold。比较：

```text
row_count
exact MultiIndex
np.array_equal(expected float64, replay float64)
key_sha256
score_sha256 using float.hex
```

任何一项不等立即失败，不写PASS receipt。

## 4. No-fit and runtime proof

正式命令的冻结launcher record写入receipt：

```text
absolute verifier path + file SHA
frozen source revision/archive/content hashes
exact argv
Python, PyTorch, CUDA runtime versions
selected CUDA device string and torch.cuda device name
output directory
```

入口要求`device`以`cuda`开头且`torch.cuda.is_available()`；禁止CPU fallback。静态测试解析
archival replay script AST，禁止任何attribute/name call target为`fit`；运行期只允许
`PeerLiteModel.load_checkpoint(...).predict(...)`。receipt固定
`checkpoint_replays=14, model_fit_calls=0`。

## 5. Ledger and OOS invariants

读取产品后先要求最大日期`<2025-01-01`。不接受final-OOS路径或2025+ rows。ledger在命令前后
分别SHA-256，必须相等；历史input文件的抽样/完整清单在前后hash相等。不得运行portfolio、
backtest或成本评估。

## 6. Receipt and failure semantics

PASS receipt schema升级为`qlib_peerlite_m6_archival_checkpoint_replay_v2`，保留现有frozen source、
product、run、historical verification、ledger、candidate/fold digest字段，新增`launcher`和
`runtime`对象。`content_sha256`为排除自身后canonical JSON SHA。

receipt只在14 fold全部exact、ledger unchanged、0 fit、CUDA、pre-OOS和all input bindings通过后
以same-directory temp + fsync + atomic no-replace rename写入。existing output directory始终拒绝，
不会覆盖旧receipt。

本文不授权实际replay；真实CUDA replay只在后续E2E gate显式放行一次。
