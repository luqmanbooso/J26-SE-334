# Notebooks

Present from this folder, in this order. All are executed and saved with their outputs.

| # | Notebook | What it shows | Needs GPU |
|---|---|---|---|
| 1 | [1_Adapter_Results.ipynb](1_Adapter_Results.ipynb) | The saved test results of each trained adapter (v1, v3 vision, v3 fusion) next to the untrained base model. | no |
| 2 | [2_SAHI_Tiling.ipynb](2_SAHI_Tiling.ipynb) | One tall screen cut into slices, and what the shipped model says about the whole screen versus each slice. | yes |
| 3 | [3_Base_Model.ipynb](3_Base_Model.ipynb) | The untrained base model on four screens, in its normal image process. | yes |
| 4 | [4_Each_Adapter.ipynb](4_Each_Adapter.ipynb) | The same four screens through each adapter, one after the other. | yes |

Extras:

| Notebook | What it shows |
|---|---|
| [Full_Statistics.ipynb](Full_Statistics.ipynb) | Every test in detail: significance tests, per-type results, leakage checks, speed and memory. Reads saved files only. |
| [Live_Demo.ipynb](Live_Demo.ipynb) | Nine held-out screens through the real app service. |
| [Live_Demo_Layout.ipynb](Live_Demo_Layout.ipynb) | Six Rico screens with their UI layout, with both v3 adapters. |
| [Base_vs_FineTuned_Speed.ipynb](Base_vs_FineTuned_Speed.ipynb) | One screen through the base model and a fine-tuned model, with timing. |

The 4 GB GPU holds one model at a time: close the HEART app and other notebooks before running 2, 3 or 4.

Rebuild any notebook with its script in [`build/`](build/), for example `python vision_oracle/notebooks/build/build_adapter_results_notebook.py`. Notebooks 2 to 4 come from `build_run_notebooks.py [sahi|base|adapters]`. The scripts are only needed to regenerate a notebook, not to open or run it.

[`old/`](old/) holds earlier notebooks (v1 and v2 models, scratch files). Their numbers are out of date: do not present them.
