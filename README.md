
# VCI-Bayes-Explore

![VCI-Bayes Logo](docs/figures/logo-vci-bayes.png)

**VCI-Bayes-Explore** packages the preprocessing and modelling workflow behind the Heart-Brain Connection Bayesian Network analysis led by [Malin Overmars, PhD](https://github.com/loverma2) within the [Vascular Cognitive Impairment (VCI) research group](https://research.umcutrecht.nl/research-groups/vascular-cognitive-impairment-vci/) of the UMC Utrecht. 

It turns raw data into a preprocessed dataset and reproduces a clinically informed, layered Bayesian network—**demographics → vascular risk → neuroimaging → function → outcomes**—that learns dependencies among 566 participants of the Heart-Brain Connection study.

The pipeline quantifies conditional probabilities for outcomes cognitive decline and major adverse cardiovasuclar events (MACE), benchmarks emerging biomarkers via mutual-information analyses, and supports patient-level inference while explicitly modelling dropout effects observed in the cohort.

Use this repository to:
- Keep sensitive file locations outside version control while configuring project-wide paths;
- Run the preprocessing pipeline that labels, engineers, and imputes cohort variables;
- Learn, constrain, and visualise the Bayesian network inside a ready-to-run notebook;
- Inspect the generated parquet outputs, figures, and companion documentation.

The layout is designed so collaborators, reviewers, and future cohort expansions can retrace each analysis step while still allowing adaptations for new datasets.

For more information about the Heart-Brain Connection study, check: https://hart-brein.nl/. This work is supported by the [Dutch Heart Foundation](https://www.hartstichting.nl).

The accompanying manuscript is currently in preparation 📄.

## License & Citation

This repository is released under the [MIT License](LICENSE).

If you use this code, please cite: [![DOI](https://zenodo.org/badge/1067978388.svg)] (https://doi.org/10.5281/zenodo.17302710). Thanks!

---

> ⚠️ **Important:** This code is tailored to the Heart-Brain Connection cohort and its definitions. If you apply it to a different dataset, review and adapt both the preprocessing notebook (`projects/HBC/00_preprocess.ipynb`) and the Bayesian-network notebook (`projects/HBC/01_bayesian_network.ipynb`) so the logic matches your cohort’s structure, coding, and requirements.

## Quick start

1. **Install Python 3.13+** (e.g. from [python.org](https://www.python.org/downloads/)) and open a terminal in the project folder.
2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate # Windows: venv\Scripts\activate
   pip install pandas numpy pyreadstat scikit-learn PyYAML pyagrum matplotlib scipy ipywidgets
   ```
3. **Tell the pipeline where your raw data live:**
   ```bash
   cp config/data_paths.example.yml config/data_paths.yml
   ```
   Edit `config/data_paths.yml` and fill in:
   - `raw_dir`: folder with the SPSS `.sav` files
   - `codebook_path`: path to `HBC_CODEBOOK_LABELS.xlsx`
   - `output_dir`: point to a project-local folder such as `data/` to keep processed data alongside the notebooks
4. **Preprocess the data:** launch Jupyter (or VS Code/JupyterLab), open `projects/HBC/00_preprocess.ipynb`, update the config cell to point to your data, and run all cells. The processed files (`df.parquet`, `df_imp.parquet`, `bn_vars.parquet`) appear in your chosen `output_dir` (e.g., `data/`).
5. **Run the analysis notebook:** open `projects/HBC/01_bayesian_network.ipynb`. The first configuration cell automatically reads the parquet files from your `output_dir`. Click “Run All” to reproduce the figures.

That’s it—you now have the same dataset and model that produced the manuscript figures.  Need more control? Jump to the sections below.

---

## Data preparation in detail

### 1. Configure file locations

`config/data_paths.yml` keeps sensitive paths out of version control (the file is git-ignored). It accepts the following keys:

| Key | Description |
| --- | --- |
| `raw_dir` | Folder containing the raw SPSS exports (`df.sav`, `fu_2.sav`, etc.). |
| `codebook_path` | Absolute path to `HBC_CODEBOOK_LABELS.xlsx`. |
| `output_dir` | Where processed parquet files are written (e.g., `data/`). |
| `risk_region` | SCORE2 region used for cardiovascular risk (defaults to `"Low"`). |

All paths may be relative to the repository root. Example:

```yaml
risk_region: Low
raw_dir: "/secure/location/hartbrein/raw"
codebook_path: "/secure/location/hartbrein/meta/HBC_CODEBOOK_LABELS.xlsx"
output_dir: "data"
```

### 2. Run the preprocessing notebook

Open `projects/HBC/00_preprocess.ipynb` in Jupyter/VS Code and execute all cells. The notebook:

* reads the raw SPSS tables and codebook,
* applies the SPSS value labels (Dutch → English),
* constructs the outcome variables (`OUTCOME_MACE`, `OUTCOME_CDR_INCREASE`),
* computes the SCORE2 cardiovascular risk score,
* imputes missing numeric values with `IterativeImputer`,
* writes `df.parquet`, `df_imp.parquet`, and `bn_vars.parquet` to the configured `output_dir` (for example `data/`).
---

## Running the Bayesian-network notebook

1. Start Jupyter (or VS Code, or JupyterLab) in the repository.
2. Open `projects/HBC/01_bayesian_network.ipynb`.
3. Execute the cells in order. The first cell auto-detects the processed data under your configured `output_dir` (e.g., `data/`) and loads:
   - `df.parquet`: the labelled, non-imputed dataset (categorical labels preserved).
   - `df_imp.parquet`: the imputed dataset used for learning.
   - `bn_vars.parquet`: metadata linking each variable to its expert-defined layer.
4. Subsequent sections:
   - **Discretisation** — uses `pyAgrum`’s `DiscreteTypeProcessor` with quantile-based binning.
   - **Structure learning** — enforces the layer constraints and adds explicit arcs from the outcome nodes to the dropout layer.
   - **Inference & visualisation** — produces network and posterior plots, CPT displays
---

## Repository layout

```
├── README.md                 Project guide (this file)
├── LICENSE
├── config/
│   ├── data_paths.example.yml
│   ├── global.dcf            Legacy config (kept for reference)
│   └── global.yml            Defaults and BN settings
├── core/                     Shared helpers (Python + legacy R)
│   ├── globals.R
│   ├── helpers.R
│   ├── io.py
│   ├── plotting.py
│   └── README.md
├── concept/
│   ├── 00_main_concept.ipynb
│   └── README.md
├── projects/
│   ├── HBC/
│   │   ├── 00_preprocess.ipynb
│   │   ├── 01_bayesian_network.ipynb
│   │   └── config.yml
│   ├── METAVCI_COGNITION/
│   │   ├── 00_preprocess.ipynb
│   │   ├── 01_analysis.ipynb
│   │   └── config.yml
│   └── METAVCI_WMH_BLOOD/
│       ├── 00_preprocess.ipynb
│       ├── 01_bayesian_network.ipynb
│       └── config.yml
├── outputs/
│   ├── graphs/
│   ├── tables/
│   └── manuscript/
├── docs/
│   ├── manuscript/
│   └── figures/
├── logs/
└── cache/
```

---

## Requirements

- Python ≥ 3.12
- pandas, numpy
- pyreadstat
- scikit-learn
- PyYAML
- matplotlib
- PyAgrum (including `pyagrum.skbn`, `pyagrum.lib.notebook`, etc.)
- SciPy
- ipywidgets

Install manually (`pip install …`) or via a requirements file if you maintain one.
