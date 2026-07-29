# M6 Archival Replay Contract V3

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_archival_replay_contract_v2.md`
- 执行模型：trusted operator未来启动一个fresh single-process Python command。

## 1. One external binding, no paired self-report

唯一expected identity是：

```text
evidence/m6_5_pre_m7/m6_archival_replay_binding_v1.json
content_sha256=a26e0618f1391498b489a7ed81d38dea61c4b94aad0ae05e5b13cf6854c8745d
```

binding file SHA由normative closure固定。未来verifier source内也固定该path/file/content SHA；
CLI只接受`--binding <that exact path>`、实际archive/root/product/run/ledger/output/device paths，
不接受`expected_archive_sha256`、`expected_runtime_sha256`或任何可由调用者配对的expected hash。
binding/file/code任一不一致立即FAIL。

required roles：

```text
binding,frozen_source_archive,extract_parent,product_dir,run_dir,
ledger_path,output_dir,device
```

output_dir调用开始必须不存在，且与所有input/project/ledger/final-OOS roots互不包含。唯一成功写为
`<output_dir>/archival_replay_receipt.json`；失败目录无PASS receipt且不复用。

## 2. Full frozen tree and import closure

archive bytes/name/size/SHA、git commit、source tree SHA/file count及internal manifest SHA必须等于
external binding。安全解包拒绝absolute path、`..`、symlink、hardlink、device/FIFO/socket及重复
member。解包后：

1. internal `frozen_source_manifest.json` file SHA exact；
2. manifest列出的每个file path/size/SHA exact；
3. extracted root递归regular-file集合与manifest exact相等，除manifest自身外无多/少一项；
4. 重新计算source tree SHA和count等于binding；
5. root、archive和manifest在replay期间stat identity/bytes不变。

command开始时任何`qlib_peerlite` module已在`sys.modules`即FAIL。只把frozen `<root>/src`置于
import首位。checkpoint load前安装fail-fast fit guard：枚举`PeerLiteModel` MRO和所有公开alias，
任何解析为同一fit callable或attribute name=`fit`的入口都替换为共享guard；guard先
`fit_calls += 1`再raise。无法枚举/替换或load后alias逃逸即FAIL。

replay结束枚举全部loaded modules：

- 每个`qlib_peerlite`或`qlib_peerlite.*`必须有regular `__file__`，resolve位于frozen root，
  path和SHA在internal manifest中；
- `qlib,numpy,pandas,pyarrow,torch`必须来自非project/non-frozen dependency roots，version exact
  等于binding；其他版本、editable live copy或unbound namespace package均FAIL；
- live worktree任何project module、transitive project module或hash mismatch均FAIL。

static AST遍历verifier及其local helpers，禁止调用目标最后一段为
`fit|backward|step`，禁止Optimizer构造。runtime fit guard必须`fit_calls=0`。

## 3. Externally bound runtime

observed runtime必须逐项等于binding引用的M6 environment与server environment：

```text
Python 3.11.14
Linux-6.8.0-106-generic-x86_64-with-glibc2.39
numpy 2.4.6; pandas 2.3.3; pyarrow 22.0.0; qlib 0.9.7; torch 2.7.1+cu126
CUDA runtime 12.6
NVIDIA GeForce RTX 4090; compute capability [8,9]; one visible device
CUBLAS_WORKSPACE_CONFIG=:4096:8
deterministic algorithms=true; cudnn benchmark=false; cudnn deterministic=true
```

device grammar仅`cuda|cuda:<nonnegative decimal>`，`cuda`规范化`cuda:0`；只能是bound单卡，无CPU
fallback。Python/package/CUDA/device/determinism任一不符FAIL。observed cuDNN version和driver
version记录为evidence但不是替代binding。

## 4. Exact 2×7 no-fit replay

M6 execution spec file/content SHA固定为external binding。models：

```text
PEERLITE_K16_MSE predictions SHA 559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3 rows 949014
PEERLITE_K32_MSE predictions SHA 008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55 rows 949014
```

每model folds exact `wf_2018..wf_2024`，共14。merged columns/order exact
`datetime,instrument,score,model_id,fold_id`。每fold必须验证historical receipt、checkpoint
metadata/state hashes、Qlib row/key digests，load到selected CUDA，只调用predict，并比较保存分数。
每个parameter/buffer、model input和pre-serialization prediction tensor都必须在selected CUDA。

score规则：aware datetime转Asia/Shanghai local date；naive必须midnight；instrument NFC nonempty；
score finite native binary64；MultiIndex/order/row count exact且
`np.array_equal(binary64)`。key/score digests沿用M6 frozen verifier算法。任何one-bit/key/order差异FAIL。

## 5. Exact PASS receipt V3

schema ID=`qlib_peerlite_m6_archival_checkpoint_replay_v3`。top-level exact fields：

```text
schema_version,status,claim_ceiling,binding,launcher,runtime,frozen_source,
imports,no_fit_guard,product,run,verifier,historical_verification,ledger,
candidates,checkpoint_replays,model_fit_calls,trial_ledger_mutated,
final_oos_market_partitions_opened,portfolio_backtests,
cost_adjusted_metrics_computed,content_sha256
```

exact nested schemas：

```text
binding:{path:string,file_sha256:hex,content_sha256:hex}
launcher:{argv:[string],working_directory:string,output_directory:string}
runtime:{python_version:string,platform:string,packages:{name:string...},
         cuda_runtime_version:string,cudnn_version:uint,driver_version:string,
         selected_device:string,device_name:string,compute_capability:[uint,uint],
         visible_device_count:uint,deterministic_algorithms:boolean,
         cudnn_benchmark:boolean,cudnn_deterministic:boolean,
         cublas_workspace_config:string,model_cuda_checks:uint,
         input_cuda_checks:uint,prediction_cuda_checks:uint}
frozen_source:{root:string,archive:string,archive_sha256:hex,archive_bytes:uint,
               manifest_sha256:hex,source_tree_sha256:hex,source_file_count:uint,
               git_commit:hex,m6_execution_spec_sha256:hex,
               m6_execution_spec_content_sha256:hex,full_tree_exact:boolean}
imports:{project_modules:[{name:string,path:string,sha256:hex}],
         dependencies:[{name:string,version:string,path:string}],
         all_project_modules_frozen:boolean,all_dependencies_bound:boolean}
no_fit_guard:{guard_installed_before_checkpoint_load:boolean,
              guarded_aliases:[string],static_ast_pass:boolean,fit_calls:uint}
product:{path:string,manifest_sha256:hex,date_max:date,
         final_oos_market_partitions_opened:boolean}
run:{path:string,run_manifest_sha256:hex}
verifier:{path:string,sha256:hex}
historical_verification:{path:string,sha256:hex,content_sha256:hex}
ledger:{path:string,sha256_before:hex,sha256_after:hex,mutated:boolean}
candidate:{model_id:string,prediction_sha256:hex,prediction_rows:uint,folds:[fold]}
fold:{fold_id:string,checkpoint_metadata_sha256:hex,checkpoint_state_sha256:hex,
      keys_sha256:hex,scores_sha256:hex,rows:uint,exact_match:boolean}
```

candidates按model排序2项，folds按year排序7项，project modules按name排序，dependencies按name排序。
terminal values：

```text
status=PASS
claim_ceiling=M6_HISTORICAL_ENGINEERING_REPLAY_ONLY
full_tree_exact=true
all_project_modules_frozen=true
all_dependencies_bound=true
guard_installed_before_checkpoint_load=true
static_ast_pass=true
checkpoint_replays=14
model_fit_calls=0
trial_ledger_mutated=false
final_oos_market_partitions_opened=false
portfolio_backtests=0
cost_adjusted_metrics_computed=false
```

ledger before/after exact相等，product date_max `<2025-01-01`。content SHA排除自身后canonical JSON。
全部通过后才same-directory temp+fsync+atomic no-replace publish并fsync output dir。本文不授权执行。
