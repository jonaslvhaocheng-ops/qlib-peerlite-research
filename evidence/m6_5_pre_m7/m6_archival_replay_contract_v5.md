# M6 Archival Replay Contract V5

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_archival_replay_contract_v4.md`
- 模式：trusted operator未来运行一个fresh single-process Python command。

## 1. External identity and output

唯一authority是`m6_archival_replay_binding_v2.json`，content SHA
`a0620acceaa641a94f4e701d928c667c6025fde26d7ca3b0142d46887c35c17a`，file SHA由closure固定且
verifier source内固定。CLI只接binding和actual archive/extract/product/run/ledger/output/device
paths，不接caller-paired expected hashes。

output dir必须不存在且与inputs/project/ledger/final-OOS roots互不包含；唯一PASS output为
`archival_replay_receipt.json`，失败目录不复用。

## 2. Frozen tree and project modules

archive name/bytes/SHA、git commit、tree SHA/count、internal manifest SHA exact。safe extraction拒绝
absolute/`..`/duplicate/symlink/hardlink/device/FIFO/socket。manifest SHA、每entry path/size/SHA、
recursive regular file set、tree SHA/count必须exact；root/archive/manifest replay期间stat和bytes
不变。

start时任何`qlib_peerlite*`已loaded即FAIL；只把frozen `<root>/src`置import首位。结束时每个
loaded project module必须regular file、位于root、path/SHA在manifest；namespace/live/editable
或hash drift FAIL。

## 3. Generic reachable-object no-fit proof

在checkpoint load前：

1. 导入replay所需frozen modules，取得原始`PeerLiteModel.fit` function/code fingerprint；
2. 把canonical class attribute替换为共享guard，guard先`fit_calls+=1`再raise；
3. roots固定为全部loaded frozen module dictionaries、replay entrypoint callable、verifier-owned
   classes/instances及即将调用的model factory；
4. 从roots使用`gc.get_referents`做identity-deduplicated递归object-graph traversal；它覆盖
   globals、class/instance attrs、descriptors、methods、`__defaults__`、`__kwdefaults__`、
   closures、decorators、partials、callable objects及任意nested containers。bound external/
   stdlib module只作为ownership boundary：检查其直接referents；对其中任何project-owned object
   或包含project target的container继续递归，其他纯external object不展开；
5. 任何reachable function/method/code object与原fit fingerprint一致，或可调用object持有该
   target reference，立即FAIL；不得只靠名称；
6. 对entrypoint实际可达的frozen code graph静态拒绝fit fingerprint、backward、Optimizer
   construction和optimizer step；model training method本身在canonical attr被guard替换后不得从
   replay roots可达；
7. import后、model factory后、每checkpoint load前、每predict前后重跑object traversal；任何新
   target reference FAIL。

无法安全遍历的custom object、referent访问异常、graph size/depth超过冻结上限均fail-closed。
runtime receipt记录root count、visited object count、scanned code count、guard installs和fit calls；
fit_calls必须0。允许调用仅`load_state_dict/eval/to/predict/forward`。

## 4. External dependencies

binding固定pyproject/uv.lock SHA、Python3.11/Linux x86_64 marker、qlib extra。从lock形成唯一
distribution→version resolution。每个loaded nonstdlib/nonproject module用
`packages_distributions`映射唯一distribution；unmapped/ambiguous/not-in-lock/version mismatch/
editable-project path均FAIL。receipt exhaustive记录从实际modules映射出的全部third-party
distributions；所有必须exact locked。historical NumPy/Pandas/PyArrow/Qlib/Torch versions也exact。
stdlib由`sys.stdlib_module_names`识别并单列。

## 5. Runtime and 14 replay

exact runtime：

```text
Python3.11.14; bound Linux x86_64
numpy2.4.6 pandas2.3.3 pyarrow22.0.0 qlib0.9.7 torch2.7.1+cu126
CUDA12.6; RTX4090; capability[8,9]; one visible device
CUBLAS=:4096:8; deterministic=true; cudnn benchmark=false/deterministic=true
```

device仅cuda/cuda:N并规范cuda:0，无CPU fallback。models：

```text
K16 SHA 559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3 rows949014
K32 SHA 008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55 rows949014
```

各`wf_2018..wf_2024`，总14。columns/order exact。每fold验证historical/checkpoint/Qlib rows/keys；
load CUDA，只predict；parameter/buffer/input/pre-serialization prediction全CUDA并与saved exact。
datetime/instrument/finite binary64、MultiIndex/order/count/array bits和M6 frozen digests全exact。

## 6. PASS receipt V5

top-level exact：

```text
schema_version,status,claim_ceiling,binding,launcher,runtime,frozen_source,
imports,no_fit_proof,product,run,verifier,historical_verification,ledger,
candidates,checkpoint_replays,model_fit_calls,trial_ledger_mutated,
final_oos_market_partitions_opened,portfolio_backtests,
cost_adjusted_metrics_computed,content_sha256
```

binding/launcher/runtime/frozen source/product/run/verifier/historical/ledger/candidate/fold保持exact typed
paths, hashes, counts。imports exact：

```text
project_modules[{name,path,sha256}],
dependency_lock{project_sha256,lock_sha256,marker,extras,resolution_sha256},
dependencies[{distribution,version,module_names,paths}],
stdlib_modules,all_project_modules_frozen,all_dependencies_bound
```

no-fit exact：

```text
installed_before_checkpoint_load,fit_target_code_sha256,
object_graph_roots,object_graph_traversals,visited_objects,scanned_code_objects,
untraversable_objects,reachable_fit_references,static_call_graph_pass,fit_calls
```

terminal：PASS/M6 historical replay only；full tree/project/deps true；untraversable=0、
reachable_fit=0、static pass、fit=0；14 replay；ledger unchanged；OOS false；backtests0/cost metrics false；
product date_max<2025。canonical content SHA，最后atomic no-replace publish+fsync。本文不授权执行。
