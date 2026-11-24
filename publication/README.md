# HEART Research Publication Package

**Conference**: 10th IEEE International Research Conference on Smart Computing and Systems Engineering (SCSE 2027)  
**Track**: Software Engineering  
**Venue**: Department of Industrial Management, Faculty of Science, University of Kelaniya, Sri Lanka  
**Publication**: IEEE Xplore Digital Library (h5-index: 22)  
**Submission Deadline**: 21st January 2027  
**Notification of Acceptance**: 28th February 2027  
**Camera-ready Deadline**: 15th March 2027  
**Conference Date**: 24th March 2027  

---

## Package Contents

| File / Folder | Purpose |
| :--- | :--- |
| [`HEART_IEEE_SCSE2027_Publication.docx`](file:///d:/J26-SE-334/publication/HEART_IEEE_SCSE2027_Publication.docx) | **Official IEEE 2-Column Word Manuscript** (.docx format). |
| [`main.tex`](file:///d:/J26-SE-334/publication/main.tex) | Complete IEEE Conference double-column LaTeX manuscript source. |
| [`references.bib`](file:///d:/J26-SE-334/publication/references.bib) | Academic bibliography file with complete citation keys. |
| [`PAPER_DRAFT.md`](file:///d:/J26-SE-334/publication/PAPER_DRAFT.md) | Human-readable Markdown preview with embedded figures and tables. |
| [`tables/table_empirical_results.tex`](file:///d:/J26-SE-334/publication/tables/table_empirical_results.tex) | Auto-generated LaTeX empirical evaluation table from live benchmark telemetry. |
| [`generate_latex_table.py`](file:///d:/J26-SE-334/publication/generate_latex_table.py) | Python script that converts `results/experiment_results.json` into LaTeX table format. |
| [`run_paper_benchmark.py`](file:///d:/J26-SE-334/publication/run_paper_benchmark.py) | Automated benchmark reproducibility script running tests against Android target. |
| [`figures/`](file:///d:/J26-SE-334/publication/figures/) | High-resolution publication diagrams and empirical charts: |
| &bull; `fig_pipeline_timeline.png` | End-to-end HEART execution timeline. |
| &bull; `fig_coupling_analysis.png` | Empirical coupling ablation chart ($p = 8.02 \times 10^{-8}$). |
| &bull; `fig_adaptive_timeline.png` | Frame latency distribution across stress transitions. |
| &bull; `fig_rotational_gaussian.png` | Biomechanical 2D kinematic dispersion model. |
| &bull; `fig_target_app.png` | Android target application testbench snapshot. |

---

## How to Compile / Submit

### Option 1: Overleaf (Recommended)
1. Compress the contents of `d:\J26-SE-334\publication` into a `.zip` archive.
2. In Overleaf, click **New Project** &rarr; **Upload Project** and select the `.zip`.
3. Select `main.tex` as the root document and click **Recompile**.

### Option 2: Local LaTeX Compilation
Run the standard IEEE compilation pipeline:
```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

### Option 3: Re-running Benchmarks
To refresh empirical evaluation data from new test runs on `emulator-5554`:
```powershell
python publication/run_paper_benchmark.py
```
This updates both `results/experiment_results.json` and `publication/tables/table_empirical_results.tex`.
