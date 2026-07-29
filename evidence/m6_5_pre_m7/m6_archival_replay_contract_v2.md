# M6 Archival Replay Contract V2

- 状态：`DESIGN_ONLY / REPLAY_NOT_AUTHORIZED`
- Architecture：`architecture_confirmation_v28.md`
- 取代：`m6_archival_replay_contract_v1.md`
- 执行模型：trusted operator启动一个新的single-process Python command。

## 1. Inputs, origin and output boundary

required inputs：

```text
frozen_source_root,frozen_source_archive,expected_archive_sha256,expected_git_revision,
frozen_runtime_manifest,expected_runtime_manifest_sha256,
product_dir,run_dir,historical_verification,expected_historical_verification_sha256,
ledger_path,output_dir,device
```

所有input roots/file paths resolve后彼此角色明确。output_dir调用开始时必须不存在，且不得等于、
包含或被任一input root、project root、ledger parent或final-OOS root包含。唯一写入是：

```text
<output_dir>/archival_replay_receipt.json
```

失败可留下无PASS receipt的incomplete目录；不自动删除/覆盖/复用。重试使用新的不存在目录。

command启动时`qlib_peerlite`相关module不得已在`sys.modules`。只把
`<frozen_source_root>/src`置于import首位后导入。导入后验证
`qlib_peerlite.data.qlib_dataset`、`data.splits`、`models.peerlite`的resolved `__file__`均位于
frozen source root，且file SHA等于`frozen_source_manifest.json`对应entry；live-worktree、
site-package或hash不同立即FAIL。

## 2. Frozen identities

M6 execution spec exact：

```text
file_sha256=469d67be0812e1acfa53301907f94c85bea2e799d17f2699edd8d508a2df20f8
content_sha256=60d0cf06307991f1fafea0dd5880b43fb929546c6757040e2c868cbb361f2f69
```

historical verification file SHA=`b605db0f43bf571f5f1cebaf1733b4801e2ea6fb944c65e35e4f6b85325c2d6e`，
content SHA=`853b9341c4b2c8a156a5d50265465ed134c4d843c5516105452f0704f8a27613`，
environment identity=`e4e6168405cc34ae20c21f8f883a326b8d4508115495b7a1a13460ba1659d870`。

`FrozenRuntimeManifestV1` exact fields：

```text
schema_version,environment_identity,python_version,torch_version,
cuda_runtime_version,cudnn_version,device_name,compute_capability,
deterministic_algorithms,cublas_workspace_config,content_sha256
```

environment identity必须等于historical receipt，manifest file SHA必须等于CLI expected SHA；
observed runtime逐字段exact等于manifest。device grammar仅`cuda|cuda:<nonnegative decimal>`，
`cuda`规范化为`cuda:0`。要求CUDA available，selected device name/capability相等，deterministic
algorithms enabled且CUBLAS workspace exact；无CPU fallback。

## 3. Exact 2×7 replay

models：

```text
PEERLITE_K16_MSE predictions SHA 559968e710e269775c67afa26f0e4f04713e43f3c5e07f877337a947a5fc99e3 rows 949014
PEERLITE_K32_MSE predictions SHA 008fd6cb2889efaa702313544feef00a35c5826ad130c347e8e1894e83722d55 rows 949014
```

每model exact folds `wf_2018..wf_2024`；总计14。merged columns/order exact
`datetime,instrument,score,model_id,fold_id`。每fold：

1. fold receipt status PASS、checkpoint replay PASS_EXACT、content hash valid、OOS false；
2. checkpoint `metadata.json/state_dict.pt` hashes exact；
3. reconstructed Qlib row_counts/key SHA exact；
4. load checkpoint on selected CUDA；
5. assert every model parameter/buffer device equalsselected CUDA；
6. forward probe记录每次model input tensor与pre-serialization prediction tensor在selected CUDA；
7. only call `predict` and compare saved fold scores.

script AST禁止call target name/attribute=`fit`、`backward`或optimizer `step`。runtime probe
`fit_calls=0`。

score canonicalization：timezone-aware转Asia/Shanghai local date；naive必须midnight；instrument
NFC nonempty string；score finite native float64；outer model/fold逐行相等；key unique并按date/
instrument UTF-8排序。比较row count、exact MultiIndex、`np.array_equal(float64)`及：

```text
key row = YYYY-MM-DD"T00:00:00" || 0x1f || instrument || 0x0a
score row = key without newline || 0x1f || float.hex(score) || 0x0a
```

concat后SHA-256。

## 4. Exact PASS receipt V2

schema ID=`qlib_peerlite_m6_archival_checkpoint_replay_v2`，exact top-level fields：

```text
schema_version,status,claim_ceiling,launcher,runtime,frozen_source,
product,run,verifier,historical_verification,ledger,candidates,
checkpoint_replays,model_fit_calls,trial_ledger_mutated,
final_oos_market_partitions_opened,portfolio_backtests,
cost_adjusted_metrics_computed,content_sha256
```

exact nested fields：

```text
launcher: argv,working_directory,output_directory
runtime: runtime_manifest_sha256,environment_identity,python_version,torch_version,
         cuda_runtime_version,cudnn_version,selected_device,device_name,
         compute_capability,deterministic_algorithms,cublas_workspace_config,
         model_cuda_checks,input_cuda_checks,prediction_cuda_checks,fit_calls
frozen_source: root,archive,archive_sha256,manifest_sha256,git_commit,
               m6_execution_spec_sha256,m6_execution_spec_content_sha256,module_origins
product: path,manifest_sha256,date_max,final_oos_market_partitions_opened
run: path,run_manifest_sha256
verifier: path,sha256
historical_verification: path,sha256,content_sha256,environment_identity
ledger: path,sha256_before,sha256_after,mutated
candidate: model_id,prediction_sha256,prediction_rows,folds
fold: fold_id,checkpoint_metadata_sha256,checkpoint_state_sha256,
      keys_sha256,scores_sha256,rows,exact_match
```

candidates按model排序exact2行；folds按year排序exact7行。fixed terminal values：

```text
status=PASS
claim_ceiling=M6_HISTORICAL_ENGINEERING_REPLAY_ONLY
checkpoint_replays=14
model_fit_calls=0
trial_ledger_mutated=false
final_oos_market_partitions_opened=false
portfolio_backtests=0
cost_adjusted_metrics_computed=false
```

product date_max `<2025-01-01`；ledger before/after exact相等。`content_sha256`排除自身后使用
UTF-8/NFC/sort_keys/no-whitespace/no-NaN canonical JSON SHA。只有全部条件满足，才用receipt
same-directory temp、fsync、atomic no-replace publish、fsync output dir。本文不授权真实replay。
