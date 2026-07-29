# M6 Archival Replay Contract V4

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_archival_replay_contract_v3.md`
- 模式：trusted operator未来运行一个fresh single-process Python command。

## 1. Single external authority

唯一binding：

```text
evidence/m6_5_pre_m7/m6_archival_replay_binding_v2.json
content_sha256=a0620acceaa641a94f4e701d928c667c6025fde26d7ca3b0142d46887c35c17a
```

binding file SHA由closure固定，verifier source也固定path/file/content SHA。CLI只接受该binding及
actual archive/root/product/run/ledger/output/device paths；不得接受caller-paired expected hashes。
required roles：

```text
binding,frozen_source_archive,extract_parent,product_dir,run_dir,
ledger_path,output_dir,device
```

output dir开始必须不存在，且与input/project/ledger/final-OOS roots互不包含；唯一成功输出为
`archival_replay_receipt.json`，失败目录不复用。

## 2. Frozen tree

archive filename/bytes/SHA、git commit、tree SHA/count、internal manifest SHA必须等于binding。
解包拒绝absolute/`..`/duplicate member/symlink/hardlink/device/FIFO/socket。解包后：

1. internal manifest file SHA exact；
2. 每个manifest entry path/size/SHA exact；
3. 除manifest自身，recursive regular-file集合与manifest exact相等；
4. tree SHA/count exact；
5. root/archive/manifest replay期间stat identity和bytes不变。

command开始若任何`qlib_peerlite`已在`sys.modules`则FAIL；只把frozen `<root>/src`置于import
首位。结束枚举全部`qlib_peerlite*` modules：必须有regular `__file__`、位于frozen root、path/SHA
在manifest；namespace/live/editable/hash drift全部FAIL。

## 3. Exhaustive no-fit closure

在任何checkpoint load前完成以下闭包：

1. 导入replay entrypoint所需全部frozen project modules；
2. 以原始`PeerLiteModel.fit`的function object/code object为target，递归枚举所有loaded project
   module globals、所有class/MRO attributes（含private）、bound method `__func__`、
   `functools.partial.func`、decorator `__wrapped__`和closure cells；
3. direct alias统一替换为共享guard；guard先`fit_calls+=1`再raise；
4. closure/saved reference若不能安全替换即FAIL，不开始checkpoint load；
5. 对verifier entrypoint可达的全部frozen project function/code object构建静态call closure；任何
   direct/dynamic attribute path可解析到fit、backward、Optimizer construction或optimizer step，
   或wrapper/partial/closure可达这些target，均FAIL；
6. import后和每次checkpoint load前重扫，发现新alias/closure立即FAIL。

允许的model调用只有`load_state_dict/eval/to/predict/forward`。runtime记录guarded aliases、
rejected closures、scanned modules/code objects及`fit_calls`，终值必须0。该规则覆盖public/private
alias、saved bound method、partial和wrapper，不依赖call target最后一段拼写。

## 4. Exhaustive external dependency identity

binding固定`pyproject.toml`与`uv.lock` SHA、Python 3.11/Linux x86_64 marker和`qlib` extra。先从
lock按这些markers形成deterministic distribution→version map；ambiguous resolution即FAIL。
对`sys.modules`中每个非stdlib、非frozen-project module：

- 用`importlib.metadata.packages_distributions()`映射到唯一distribution；
- unmapped或ambiguous module FAIL；
- distribution必须在bound lock resolution内且installed version exact；
- module path不得位于project/frozen root或editable source；
- receipt记录**全部**loaded third-party distributions，集合必须等于从实际modules映射出的集合，
  不允许隐藏或环境自报的unbound transitive dependency。

historical environment的NumPy/Pandas/PyArrow/Qlib/Torch versions还必须逐项exact。stdlib set来自
该Python build的`sys.stdlib_module_names`，built-in/frozen stdlib单独记录。只有每个实际external
import都由bound lock给出exact version，才可`all_dependencies_bound=true`。

## 5. Runtime and exact 2×7

observed runtime exact：

```text
Python 3.11.14; Linux-6.8.0-106-generic-x86_64-with-glibc2.39
numpy 2.4.6; pandas 2.3.3; pyarrow 22.0.0; qlib 0.9.7; torch 2.7.1+cu126
CUDA 12.6; NVIDIA GeForce RTX 4090; capability [8,9]; one visible device
CUBLAS_WORKSPACE_CONFIG=:4096:8
deterministic algorithms=true; cudnn benchmark=false; cudnn deterministic=true
```

device仅`cuda|cuda:N`，规范为`cuda:0`且无CPU fallback。cuDNN/driver观察值记录但不替代binding。

M6 exact models：

```text
PEERLITE_K16_MSE SHA 559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3 rows 949014
PEERLITE_K32_MSE SHA 008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55 rows 949014
```

每model `wf_2018..wf_2024`，共14。merged columns/order：
`datetime,instrument,score,model_id,fold_id`。每fold验证historical receipt、checkpoint hashes、
Qlib rows/keys，load到bound CUDA，只调用predict，检查parameter/buffer/input/pre-serialization
prediction tensors全在CUDA并与保存score exact。

aware datetime转Asia/Shanghai date，naive必须midnight；instrument NFC nonempty；score finite
binary64；row count/MultiIndex/order/`np.array_equal`和M6 frozen key/score digests全exact。

## 6. PASS receipt V4

schema=`qlib_peerlite_m6_archival_checkpoint_replay_v4`，exact top-level：

```text
schema_version,status,claim_ceiling,binding,launcher,runtime,frozen_source,
imports,no_fit_guard,product,run,verifier,historical_verification,ledger,
candidates,checkpoint_replays,model_fit_calls,trial_ledger_mutated,
final_oos_market_partitions_opened,portfolio_backtests,
cost_adjusted_metrics_computed,content_sha256
```

nested exact：

```text
binding:{path,file_sha256,content_sha256}
launcher:{argv,working_directory,output_directory}
runtime:{python_version,platform,cuda_runtime_version,cudnn_version,driver_version,
 selected_device,device_name,compute_capability,visible_device_count,
 deterministic_algorithms,cudnn_benchmark,cudnn_deterministic,cublas_workspace_config,
 model_cuda_checks,input_cuda_checks,prediction_cuda_checks}
frozen_source:{root,archive,archive_sha256,archive_bytes,manifest_sha256,
 source_tree_sha256,source_file_count,git_commit,m6_execution_spec_sha256,
 m6_execution_spec_content_sha256,full_tree_exact}
imports:{project_modules:[{name,path,sha256}],
 dependency_lock:{project_sha256,lock_sha256,marker,extras,resolution_sha256},
 dependencies:[{distribution,version,module_names,paths}],
 stdlib_modules:[string],all_project_modules_frozen,all_dependencies_bound}
no_fit_guard:{installed_before_checkpoint_load,guarded_aliases,rejected_closures,
 scanned_project_modules,scanned_code_objects,static_call_closure_pass,fit_calls}
product:{path,manifest_sha256,date_max,final_oos_market_partitions_opened}
run:{path,run_manifest_sha256}
verifier:{path,sha256}
historical_verification:{path,sha256,content_sha256}
ledger:{path,sha256_before,sha256_after,mutated}
candidate:{model_id,prediction_sha256,prediction_rows,folds:[fold]}
fold:{fold_id,checkpoint_metadata_sha256,checkpoint_state_sha256,
 keys_sha256,scores_sha256,rows,exact_match}
```

arrays按name/year排序。terminal：

```text
PASS; claim=M6_HISTORICAL_ENGINEERING_REPLAY_ONLY
full_tree_exact=true; all_project_modules_frozen=true; all_dependencies_bound=true
installed_before_checkpoint_load=true; static_call_closure_pass=true
checkpoint_replays=14; model_fit_calls=0; ledger_mutated=false
OOS=false; portfolio_backtests=0; cost_adjusted_metrics=false
```

ledger before/after相等，product date_max<2025-01-01。content hash为canonical JSON。全部通过才
temp+fsync+atomic no-replace publish并fsync dir。本文不授权执行。
