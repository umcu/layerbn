
# VCI-Bayes-Explore

![VCI-Bayes Logo](logo-vci-bayes.png)

Reproducible scripts for the Heart-Brain Connection Bayesian Network project by [Malin Overmars, PhD](https://github.com/loverma2). For more information about the Heart-Brain Connection study, check: https://hart-brein.nl/. 

The accompanying manuscript is currently in preparation 📄

## License & Citation

This repository is released under the [MIT License](LICENSE).

If you use this code, please cite: [![DOI](https://zenodo.org/badge/1067978388.svg)](https://doi.org/10.5281/zenodo.17302710). Thanks!

---

> ⚠️ **Important:** This code is tailored to the Heart-Brain Connection cohort and its definitions. If you apply it to a different dataset, review and adapt both the preprocessing (`src/preprocess_data.py`) and the Bayesian-network notebook (`src/bayesian_network.ipynb`) so the logic matches your cohort’s structure, coding, and requirements.

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
   - `output_dir`: leave as `src/out` to keep processed data inside the repo
4. **Preprocess the data:**
   ```bash
   python src/preprocess_data.py
   ```
   You should see log messages ending with “Wrote df.parquet …”. The processed files (`df.parquet`, `df_imp.parquet`, `bn_vars.parquet`) appear in `src/out/`.
5. **Open the analysis notebook:** launch Jupyter and run `src/bayesian_network.ipynb`. The first configuration cell automatically reads the parquet files from `src/out/`. Click “Run All” to reproduce the figures.

That’s it—you now have the same dataset and model that produced the manuscript figures.  Need more control? Jump to the sections below.

---

## Data preparation in detail

### 1. Configure file locations

`config/data_paths.yml` keeps sensitive paths out of version control (the file is git-ignored). It accepts the following keys:

| Key | Description |
| --- | --- |
| `raw_dir` | Folder containing the raw SPSS exports (`df.sav`, `fu_2.sav`, etc.). |
| `codebook_path` | Absolute path to `HBC_CODEBOOK_LABELS.xlsx`. |
| `output_dir` | Where processed parquet files are written. Default behaviour writes to `src/out`. |
| `risk_region` | SCORE2 region used for cardiovascular risk (defaults to `"Low"`). |

All paths may be relative to the repository root. Example:

```yaml
risk_region: Low
raw_dir: "/secure/location/hartbrein/raw"
codebook_path: "/secure/location/hartbrein/meta/HBC_CODEBOOK_LABELS.xlsx"
output_dir: "src/out"
```

### 2. Run the preprocessing script

```bash
python src/preprocess_data.py
```

The script:

* reads the raw SPSS tables and codebook,
* applies the SPSS value labels (Dutch → English),
* constructs the outcome variables (`OUTCOME_MACE`, `OUTCOME_CDR_INCREASE`)
* computes the SCORE2 cardiovascular risk score,
* imputes missing numeric values with `IterativeImputer`,
* writes `df.parquet`, `df_imp.parquet`, and `bn_vars.parquet` to `src/out/`.
---

## Running the Bayesian-network notebook

1. Start Jupyter (or VS Code, or JupyterLab) in the repository.
2. Open `src/bayesian_network.ipynb`.
3. Execute the cells in order. The first cell auto-detects the processed data under `src/out/` and loads:
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
├── logo-vci-bayes.png        Banner used in the README
├── config/
│   ├── data_paths.example.yml Template pointing to raw data
│   └── config.yaml           Extra notebook settings (optional)
├── src/
│   ├── preprocess_data.py    End-to-end data preparation script
│   ├── bayesian_network.ipynb Main analysis and figures
│   └── out/                  Default location for processed parquet files
└── docs/, graphs/, cache/, … Supporting material
```

---

## How the pipeline works (for the technically curious)

* **Value labels**: SPSS value labels are applied before any logic runs; Dutch strings such as `"Ja, Herseninfarct"` become `"Yes, ischemic stroke"`.
* **Outcome definitions**:
  - `OUTCOME_MACE` is “Yes” if **either** T2 or T4 indicates a stroke/cardiac event or the recorded cause of death mentions key terms (myocardial infarction, cerebral hemorrhage, etc.).
  - `OUTCOME_CDR_INCREASE` is “Yes” if the CDR score increases at T2 or T4 **or** the participant leaves follow-up with the reason (“Moved to Nursing Home”). Dropouts without recorded events are labelled “Unobserved”.
* **Layer metadata**: `bn_vars.parquet` strips whitespace and normalises the layer names (for consistent colouring in the notebook plots).
* **Risk score**: SCORE2 is calculated via a Python translation of the `RiskScorescvd::SCORE2` function.
* **Imputation**: Numeric features use `IterativeImputer` (sklearn). Categorical variables retain the translated labels.

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

