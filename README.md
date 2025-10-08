![VCI-Bayes Logo](logo-vci-bayes.png)

# VCI-Bayes-Explore

## Data setup

1. Copy `config/data_paths.example.yml` to `config/data_paths.yml`.
2. Fill in the absolute paths to your raw SPSS/Excel files and the codebook.
3. Run preprocessing with `python src/preprocess_data.py` (the script reads the config automatically, or you can pass `--config`/`--raw-dir` overrides).
4. The generated parquet files stay under `data/`, which is already ignored by git.

Required Python packages: pandas, numpy, pyreadstat, scikit-learn, PyYAML.

## Overview

This repository contains the analysis pipeline for the VCI Bayesian network exploration. The workflow builds a Bayesian network from clinical, imaging, and biomarker data to evaluate outcome trajectories and layer-wise dependencies.

The project consists of:
- `src/preprocess_data.py`: Python port of the original R preprocessing pipeline, producing the parquet datasets consumed by the notebook.
- `src/bayesian_network.ipynb`: Structured notebook that fits Bayesian networks, runs inference, and generates figures used in the manuscript.
- `config/data_paths.example.yml`: Template for pointing to raw inputs stored outside the repository.

## Running the pipeline

1. **Install dependencies**
   ```bash
   pip install pandas numpy pyreadstat scikit-learn PyYAML
   ```
2. **Configure data locations**
   ```bash
   cp config/data_paths.example.yml config/data_paths.yml
   # edit config/data_paths.yml with absolute paths to your raw SPSS/Excel files
   ```
   The file supports keys: `risk_region`, `raw_dir`, `codebook_path`, and `output_dir`. All paths may be absolute or relative to the project root.

3. **Generate processed datasets**
   ```bash
   python src/preprocess_data.py
   # optional overrides
   python src/preprocess_data.py --config /path/to/custom.yml
   python src/preprocess_data.py --raw-dir /secure/raw/ --output-dir /tmp/data
   ```
   The script creates `df.parquet`, `df_imp.parquet`, and `bn_vars.parquet` in the configured `output_dir` (defaults to `<project>/data/`).

4. **Run the Bayesian network notebook**
   - Open `src/bayesian_network.ipynb`.
   - Ensure `PROJECT_ROOT` in the first configuration cell points to the repository root (default is fine when opening from the repo).
   - Execute the notebook sequentially to reproduce figures, inference tables, and ROC plots.

## How it works

1. `preprocess_data.py`
   - Reads raw SPSS baseline/follow-up tables and joins compound score Excel/CSV files.
   - Engineers outcome variables (MACE events, CDR increase, dropout reasons) and harmonises variable names with the metadata codebook.
   - Calculates SCORE2 cardiovascular risk (translated from the `RiskScorescvd` R package).
   - Converts key categorical labels to English, imputes missing numeric values with `IterativeImputer`, and saves the analysis-ready parquet files.

2. `bayesian_network.ipynb`
   - Imports the processed datasets and expert-defined layer metadata.
   - Configures discretisation, constructs constrained Bayesian networks, and assesses edge stability via bootstrapping.
   - Generates posterior inference visualisations, ROC/PR curves, and scenario explorations used in the manuscript.

## Data considerations

- Raw data directories and codebooks live outside the repository and are referenced via `config/data_paths.yml` (git-ignored).
- Generated parquet files remain under `data/`, which is also ignored, ensuring sensitive information never enters version control.
