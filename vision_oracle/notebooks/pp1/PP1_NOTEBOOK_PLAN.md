# PP1 notebook plan and evidence inventory

Audit date: 21 October 2026. Scope: local checkpoints, recorded training configurations/logs, existing predictions, notebook sources and outputs. No new GPU evaluation or training was run. The machine-readable inventory is `pp1_evidence_inventory.json`; `pp1_evidence_preview.png` illustrates three figures from existing records.

## Recommendation

Build **two evidence notebooks alongside the existing `../C3_live_demo.ipynb`**. The live notebook demonstrates selected behaviours; the evidence notebooks explain what was trained and what measured improvement is supported. Do not present selected demo success as accuracy.

1. `01_model_training_and_experiments.ipynb`: what the model is, what LoRA changes, what each training run changed, and what the learning curves actually mean.
2. `02_model_progress_and_evaluation.ipynb`: paired baseline comparisons, validation/threshold selection, errors, localization, latency, and unresolved limitations.

If only two notebooks total are desired, keep notebook 1 and merge notebook 2 with the live demo as a final optional section. Default execution must render saved evidence without starting training or GPU inference.

## Verified inventory

### Model and training artifacts

All four inspected adapters have **18,464,768 stored adapter parameters**, 392 tensors, rank 16, alpha 32, and q/k/v/o/gate/up/down projections in the 28 language layers. No visual-module adapter tensors were found. Stored adapter tensors are FP32; do not describe them as universally FP16. The base safetensors contain 2,208,985,600 parameters; base plus adapter is 2,227,450,368, giving an adapter share of 0.8290%. Count parameter elements, not quantized bytes. Frozen pretrained weights were not all updated: trainable adapter matrices were added.

| Run | Location | Dataset / start | LR / dropout | Actual progress available |
|---|---|---|---|---|
| Local Qwen2-VL base | `../../models/Qwen2-VL-2B-Instruct` | pretrained base, no adapter | not applicable | base config, weight tensor shapes, saved baseline predictions |
| v1 stage 1 | `D:/university/Resesarch/results/c3_lora_clean_zero_leakage` | 1,470 records; starts from base | 1e-4 / 0 | 368 steps, 2 epochs, 36 logged loss points |
| v1 shipped adapter | `../../models/c3_qwen2vl_2b_lora_step246` | 980 defect-heavy records; continues stage 1 | 5e-5 / 0 | 246 additional steps, 2 additional epochs, 24 loss points; train loss 0.4723 |
| v2 first epoch | `D:/university/Resesarch/results/c3_lora_v2/checkpoint-173` | 1,377 filtered, compact-target records; starts from base | 1e-4 / .05 | checkpoint at 173 steps / 1 epoch; 17 loss points; original run later interrupted |
| v2 additional epoch | `D:/university/Resesarch/results/c3_lora_v2_epoch2` | same v2 data; starts from checkpoint-173 adapter | 5e-5 / .05 | 173 additional steps / 1 epoch; 17 loss points; train loss 0.2235 |
| v3 vision / fusion | external LLaMA-Factory v3 YAMLs and `../../evidence/12_dataset_v3` | app-grouped data and two prompt variants | proposed recipe | dataset/configuration artifacts found; no trained v3 checkpoint/results found in inspected model/result locations |

Common recorded settings: microbatch 1, accumulation 8 (effective batch 8 on one GPU), cutoff 1,024, image budget 262,144 pixels, cosine scheduler, NF4 base loading. v2 explicitly freezes the vision tower. Read exact optimizer and warmup values from the run evidence, not a generic default.

**Important provenance discrepancy:** archived `evidence/11_model_v2/training/qwen2vl_lora_c3_v2.yaml` says 3 epochs / warmup 26 and omits the optimizer. The actual log says 2 planned epochs / 346 steps; current external YAML says 2 epochs / warmup 17 / paged_adamw_8bit. Show archived recipe versus observed execution separately. Do not overwrite the original artifact to hide the discrepancy. The additional-epoch YAML loads adapter weights and starts a new schedule; do not call it an uninterrupted optimizer-state resume.

No inspected trainer state has logged evaluation loss or a `best_model_checkpoint`. Later validation-based checkpoint selection exists as a separate artifact. Do not draw nonexistent validation-loss curves.

### Recorded evaluation evidence

Primary folder: `../../evidence/11_model_v2/benchmarks/`. Each score run has per-image labels, defect scores, timings and input-contract metadata. The four test files have the same 316 image/label pairs in the same order. Values below were recomputed using thresholds from the corresponding **291-screen validation** files, not each test file's `best_threshold`.

| Recorded recipe | Validation AUC | Test AUC | Test precision | Test recall | Test binary F1 | Test accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Base, v2 prompt | .5951 | .5734 | .5064 | 1.0000 | .6723 | .5127 |
| v1, its training prompt | .7369 | .7504 | .6127 | .7911 | .6906 | .6456 |
| v2 first epoch | .7071 | .6799 | .5434 | .9114 | .6809 | .5728 |
| v2 additional epoch | .7088 | .7124 | .5438 | .9430 | .6898 | .5759 |

This is a **recipe comparison**, not a clean learning-rate or LoRA-only ablation. Base-v2 and v2 share the recorded prompt; base-v2 and v1 do not. All use the same recorded pixel budget. v2 changed training membership, target length, prompt, dropout and training history. The user's newer run is therefore not literally the same training dataset with only hyperparameters changed, based on the artifacts located here.

At its validation-selected threshold the base flags **312/316**, not literally every screen. F1 alone obscures this behaviour. Pair it with specificity, false-positive rate, AUC, and confusion matrices.

`final_test316_end_to_end.json` contains v1 full-output predictions: TP 124, FP 78, FN 34, TN 80; F1 .6889, 0 recorded invalid outputs, type correctness .3544 and IoU >= .5 recall .0823 against existing annotations. **78/158 = 49.4%** of clean screens are falsely flagged. Stored-score classification differs on two threshold-boundary cases (`13996.jpg`, `bug.4198.jpg`), both saved as .5351. Preserve this distinction; rounded stored scores are insufficient to reproduce every full-precision decision. Future records should save full scores and the actual decision.

The legacy test split is now inspected and used for demonstrations. Call these recorded historical test results; do not promise that this set is currently untouched or app-disjoint. Label quality limits type/localization claims. Historical files lack some weight/code hashes, so exact historical model provenance is not completely established by today's checkpoint hashes.

### Other reusable evidence

| Evidence | Use | Boundary on the claim |
|---|---|---|
| `11_model_v2/diagnosis/v1_adapter_app_input_val18.json` and first 18 matched training-input records | paired input-contract repair: 1/11 versus 9/11 defects caught; identities verified | prompt AND resolution changed; not a prompt-only experiment |
| `11_model_v2/training/train_v2*.log`, all `trainer_state.json` files | loss/LR schedules, steps, runtime, parameter counts, restart history | training loss is not detection accuracy; compact and verbose targets are not directly comparable loss scales |
| `11_model_v2/benchmarks/selection.json` | validation-based model selection and threshold provenance | inspect which selection metric was actually used; do not imply Trainer best-checkpoint selection |
| `11_model_v2/benchmarks/mcnemar_test316.json` | paired correctness differences, after matching images | recipe-level comparison; p-values do not isolate LoRA or eliminate dataset bias |
| `11_model_v2/data_audit/mut_visibility.json` | mutation visibility histogram and rejection rate | a visibility check is not a complete annotation-quality audit |
| `12_dataset_v3/dataset_v3_report.json`, provenance/split artifacts | source/type counts and app grouping: 1,700 train, 424 val, 425 test | v3 data progress, not measured v3 model progress; model-assisted OwlEye labels still need human review |
| `14_pipeline_audit/tile_ablation_val60.json` | global versus tiles: accuracy/false alarms/latency | same validation cohort; tiles are not an established improvement |
| `14_pipeline_audit/offline_inference_check.json`, backend/GUI smoke records | offline and integration functionality | functionality evidence, not an accuracy benchmark |
| `../../demo_inputs/results.json`, `../C3_live_demo.ipynb` | positive, clean, synthetic, and known-miss examples | selected examples; distinguish reviewed boxes from independently verified ground truth |
| `../../results/diagnostic_2026-10-20/base.json` | six-screen historical baseline and label-review trail | base arm complete; no matching adapter-arm file found there; old input regime, not a current comparison |
| `../../results/experiments/exp-*`, older benchmark folders | historical inventory only | summary-only high scores and superseded artifacts are not approved current evidence |

## Assessment of existing notebooks

- **Keep the new live demo**, with explicit reviewed-label provenance, success and failure cases, and a small optional live section. Its headline metrics are typed into markdown; replace these with computed values from the evidence loader. Do not describe model-assisted green boxes as unquestionable ground truth.
- **Refactor `build_pp1_notebook.py`**, rather than discard its useful evidence loading. It already has identity, learning curves, diagnosis, saved tests, demo, latency and tiling sections, but misses an intelligible configuration comparison and experiment history.
- **Reuse `c3_model_v2_review.ipynb`** for diagnosis/data-audit panels; it is an unexecuted analysis template, not new measured evidence.
- **Do not present `pp1/00_` through `06_`, `model_evaluation.ipynb`, or `c3_vision_oracle_master_evaluation.ipynb` as current results.** They already carry superseded notices.
- **Treat SAHI, interactive, visual_evaluator, oracle_demonstration and `test*.ipynb` as scratch/reference material** until each imported result and inference path is checked. Do not concatenate them into one long presentation.
- `train.ipynb` launches an external YAML and still mentions 900 test screens. It is not a sufficient training-history record for the current runs.

Specific changes needed in the PP1 builder:

1. Its opening promise that nothing is typed by hand is false: `TOTAL`, 0.83%, AUC/p-values, qualitative conclusions and speed expectations appear as constants/markdown. Derive numbers and label explanatory examples explicitly.
2. Replace “Base, same prompt” for the v1 comparison with the actual contract name; add the missing controlled baseline.
3. Separate v1 stages and v2 restart; include all available LR curves. Do not imply lower v2 loss proves better detection.
4. Separate decision-score, generated-output, and full application pipeline results. The saved end-to-end benchmark uses the backend; do not imply it includes device capture/UI/network time.
5. Replace “test run once, never used for choices” with documented historical protocol plus present exposure status; test files contain diagnostic best-threshold fields that must never drive reporting.
6. Fix base predicted-positive count, clean false-positive percentage and rounded-threshold discrepancies.
7. Do not equate the normalized true/false token score with a calibrated probability. Use “defect score”; calibration requires validation evidence.
8. Allow execution from repository root or notebook directory; remove personal absolute paths from notebook cells by using one explicit configuration/registry.
9. Scope “1.5 s achieved” to measured decision-only timing, not a complete inspection. Show p50/p95 and cold load separately.
10. Include failures and uncertainty. Existing evidence alone does not prove noisy labels are the sole reason v2 did not improve.

## Notebook 1: model, LoRA and training experiments

Each section should have one question, a short explanation, one artifact-backed visual, and a qualified takeaway.

| Section / panel question | Content | Visual and source |
|---|---|---|
| What is your contribution versus Qwen's? | pretrained vision/language model versus C3 data, adapters, input contract, decision policy and integration | architecture diagram; local config plus current code |
| Parameters versus hyperparameters? | parameters = learned weights; architecture settings = fixed dimensions; training hyperparameters = LR/batch/epochs; LoRA settings = rank/alpha/targets/dropout; inference settings = pixels/prompt/threshold/tiles | five-category table, with actual project values |
| What does LoRA learn? | frozen W plus scaled BA, alpha/r; compute parameter counts from saved tensor shapes | frozen/trainable proportional bar plus adapter-module bar; avoid implying pretrained W was updated |
| What did you train, in what order? | base -> stage1 -> v1; separate base -> v2 ep1 -> additional epoch; v3 pending | checkpoint lineage diagram and configuration-difference heatmap |
| How did LR affect the run? | scheduled LR over optimizer steps, warmup and restarts | LR line plots from logs; an observed schedule is not a learning-rate performance experiment |
| Did optimization converge? | loss within each run, target format and dataset annotated; no recorded eval loss | small-multiple training-loss plots; stage boundary markers |
| Did the newer recipe improve the model? | validation AUC/F1 with false alarms; current evidence favours v1 | validation-only comparison with uncertainty; failed hypothesis retained |
| What is not tested? | rank, alpha and target-module alternatives; isolated LR/dropout effects | experiment status matrix: measured / configured / proposed |

Optional educational rank slider may show the formula r*(d_in+d_out) and theoretical parameter cost. It must say **illustrative capacity calculation, not measured accuracy**. Do not create an accuracy-versus-rank chart when all real runs used r=16.

## Notebook 2: progress, evaluation and limits

| Section / panel question | Content | Visual |
|---|---|---|
| What data supports the result? | dataset version, source/defect counts, grouping, annotation provenance, split hashes | source-by-split bars; separate real-source/augmented and synthetic subsets |
| Is the comparison fair? | checkpoint/input contracts, same image IDs, resolution, quantization, decision rule, matched thresholds selected only on validation | pairwise comparability checklist generated from metadata |
| Did base-to-adapter performance improve? | controlled comparison when available; label existing mixed-prompt comparison as recipe-level | ROC/PR curves, AUC CI and paired metric-difference CI; binary confusion matrices |
| Why is F1 alone insufficient? | all-clean and all-defect trivial baselines derived from actual prevalence; base flags 312/316 | precision/recall/specificity + predicted-positive counts |
| Why this threshold? | score distributions and threshold trade-off on validation only | validation PR/threshold curves with frozen operating point; test never used to choose it |
| Which bugs work? | binary detection by class versus actual type classification, clearly separated | class confusion matrix with support; source-stratified metrics |
| Does localization work? | reliable annotations only; count misses and missing boxes; uncertain labels excluded with counts | IoU distribution/recall and reviewed box overlays; remaining annotation caveat |
| What improved without retraining? | same-image old/new input contract; global/tile policy | paired bars for catch rate, false alarms and latency |
| Is it practical on 4 GB? | cold load, decision, generated box/type, complete app latency, GPU memory | latency distributions/p50/p95 and memory bars, each with scope |
| Where does it fail? | one TP, TN, FP, FN, invalid case if present, class error and poor localization | saved-output gallery, no cherry-picked aggregate claim |
| Can I reproduce it? | versions, seeds, manifests, label revisions, checkpoint/contract/code hashes | provenance table; optional bounded live run disabled by default |

## Remaining experiments, in priority order

### PP1 essentials

1. **Evidence hygiene, CPU only:** freeze an artifact registry, recompute metrics from records, join pairs by image hash/ID, preserve full-precision scores and actual decisions, label test exposure, and resolve the YAML/log discrepancy. Recover original training invocation if available; otherwise report uncertain fields.
2. **Repair evaluator consistency before new runs:** `contract_benchmark.summarize` and `eval_stages.compute_metrics` currently convert invalid clean outputs into true negatives via boolean coercion. `evaluation_accounting.py` has explicit abstentions, but these newer paths do not use it. Saved full test has zero invalids, so that recorded run is not affected by this particular counting issue; future runs can be. Require strict schema/box validation and per-sample failure records. Add atomic checkpoints to staged evaluation; currently it writes the final run after the loop.
3. **Controlled base-v1 validation comparison:** same frozen reviewed validation set, exact v1 contract, same resolution/NF4/scoring method, and no LoRA for base. Reuse v1 predictions only if sample IDs, contract and code provenance agree; otherwise run both. A 24-image smoke then 96-image screen is sufficient for initial sanity/comparison, followed by full validation if needed. Do not conflate these validation estimates with historical test results.
4. **One controlled LR experiment if time allows:** choose an audited fixed training manifest; train two fresh adapters from the same base with LR 5e-5 versus 1e-4, holding rank/alpha/dropout/targets, steps, batch, seed, target format and preprocessing fixed. Compare validation only. Repeat seeds if making a stable superiority claim; a one-seed run is exploratory. Old chained stages are not this experiment.
5. **Human label review for localization claims:** verify representative validation positives and clean negatives, reconcile classes/boxes, record reviewer identity/agreement and ambiguous cases. Do not transfer model-assisted corrections into a trusted benchmark without disclosure.

### Optional / PP2

- Rank 8 versus 16 (32 only if memory permits), fixed alpha/r scaling and targets. No need for a full rank x LR x dropout grid.
- Target-module q/v-only versus seven projections; measured parameter count and validation trade-off.
- Resolution/pixel budget or prompt-only ablation with all other inputs fixed. These are inference experiments, not retraining gains.
- Train v3 vision and fusion arms on identical image/label memberships after label review; compare separately on Rico synthetic and appropriate real-source examples. No present claim of learned hierarchy fusion.
- Dataset-size learning curve, calibrated scores, FP-reduction operating points, held-out-app evaluation, independent natural-defect cohort.
- Quantization alternatives only where runnable; NF4 alone does not establish equivalence to full precision.

Use `eval_stages.py` as a starting runner, not as unquestioned proof of leakage freedom. It defaults to v3 validation (424), whereas historical results use v2 validation (291); pass the intended manifest explicitly. Its fixed stratified small subsets are screening cohorts, not population-prevalence samples. Final-test locking by filename/model identity alone does not prove an untouched test set. Once a set guides design, retain it as development evidence and establish a new independent final cohort for later claims.

## Build sequence and acceptance checks

1. Freeze registry and eligibility labels; preserve existing notebooks and raw evidence.
2. Build notebook 1 from current config, tensor headers and logs. Keep uncertain provenance visible.
3. Build notebook 2 from saved predictions first, with placeholders clearly marked for missing controlled comparisons.
4. Add the controlled validation comparator; replace only its placeholder with measured output.
5. Add LR/rank results only if actual controlled runs exist. Keep planned experiments in a separate section.
6. Execute both notebooks in a fresh kernel with live inference off; every displayed number must trace to a record/config or be labelled an illustrative calculation. Missing evidence should stop that result cell, not produce example scores.
7. Rehearse a short panel path: what is trained -> configuration history -> fair baseline -> gains and failures -> resource cost -> next experiment. Keep the live demonstration to a few contrasting examples, with saved fallback outputs explicitly labelled.

A defensible conclusion today: C3 has measured detection signal and substantial input/evaluation engineering progress; the newer v2 recipe did not beat v1 on recorded validation; localization and clean-screen rejection remain weak. A stronger claim that a specific LR, rank, or hierarchy method caused improvement needs the corresponding controlled experiment.
