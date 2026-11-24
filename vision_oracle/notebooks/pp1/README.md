# PP1 evidence notebooks

Open the executed notebooks in this order:

1. [Model training and experiments](01_model_training_and_experiments.ipynb): architecture, parameters versus hyperparameters, LoRA size, actual training settings, logged loss/LR curves, and missing controlled experiments.
2. [Model progress and evaluation](02_model_progress_and_evaluation.ipynb): paired base/adapter comparisons, ROC/PR, confusion matrices, bootstrap uncertainty, bug types, boxes, input repair, tiling, latency and dataset progress.
3. [Live bug demo](../C3_live_demo.ipynb): separate screenshot demonstrations. This build does not change or run it.

The two notebooks have **15 saved figures** and run entirely on CPU from `evidence_bundle.json`. No original checkpoint, external dataset, download, model inference or training is needed to replay them. Install `numpy`, `pandas`, `matplotlib`, `nbformat`, `nbclient` and `ipykernel` in the notebook environment (NumPy must support `trapezoid`, i.e. NumPy 2+).

From the repository root:

```powershell
python vision_oracle/notebooks/pp1/build_pp1_notebook.py --execute
python -m unittest discover -s vision_oracle/notebooks/pp1 -p test_pp1_evidence.py
```

`build_pp1_notebook.py` now forwards to `build_evidence_notebooks.py`. Without `--execute`, the builder writes unexecuted notebooks. Use `--execute` to preserve presentation-ready outputs. The previous `C3_PP1_measured_results.ipynb` and older notebooks are historical, not the current presentation entry points.

To refresh the portable snapshot on the original evidence workstation:

```powershell
python vision_oracle/notebooks/pp1/build_pp1_notebook.py --refresh --execute
```

Refresh reads model locations from `pp1_evidence_inventory.json`, base tensor headers from `vision_oracle/models/Qwen2-VL-2B-Instruct`, and saved records under `vision_oracle/evidence`. Missing sources fail visibly. The bundle includes archived configurations, trainer states, tensor headers and prediction records; source paths/hashes are displayed in both notebooks. Its companion SHA-256 checks snapshot integrity, not independent authenticity or historical checkpoint identity. Tensor-header hashes do not hash weight values. Absolute image paths are record identifiers; images are not bundled here.

Presentation limits are intentional:

- v1 uses a different prompt from base/v2; recipe improvements cannot isolate a LoRA or learning-rate effect.
- All measured adapters have rank 16. Rank capacity curves are theoretical, with no invented rank-accuracy results.
- The archived v2 YAML conflicts with the actual training log/state; both are shown.
- Test thresholds come from validation. Rounded score-only decisions differ from two recorded full-output decisions.
- Historical test data has already been exposed. Future model selection needs validation and a newly frozen, human-reviewed holdout.
- The newest saved model does not outperform v1 on AUC. Type/localization quality and false positives remain weaknesses.

Suggested PP1 walkthrough: spend 3–4 minutes on notebook 1 sections 1–4 and 6; then 4–5 minutes on notebook 2 sections 2, 5–8 and 11. Use one success and one failure in the separate demo. The final notebook sections list exactly which experiments remain **NOT RUN**.
