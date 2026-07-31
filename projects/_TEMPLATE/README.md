# New project template

Copy this folder to start a new VCI-Bayes subproject. The template is
wired to the shared helpers in `core/`, so most of your work is
**deciding** (which variables, which layers, which outcomes) rather
than writing pipeline code.

```bash
cp -r projects/_TEMPLATE projects/MY_NEW_PROJECT
```

---

## Step 1 — Fill in `config.yml`

Open `projects/MY_NEW_PROJECT/config.yml` and set:

| Key | What it is |
| --- | --- |
| `project_root` | Absolute path to this project folder |
| `raw_dir` | Where your raw data files live (SPSS `.sav`, CSV, etc.) |
| `output_dir` | Where processed parquet files will be written (usually a folder outside this repo, next to the raw data) |
| `codebook_path` | *(optional)* Excel file mapping variable names to layers |
| `risk_region` | *(only if you use SCORE2)* `Low`, `Moderate`, `High`, `Very high` |
| `seed` | Random seed for reproducibility |

Anything else you add to `config.yml` (e.g. `follow_up_years: 5`) is
preserved in `PreprocessConfig.extra` and available in the notebook.

**Data paths stay out of git** because `config.yml` may point to
project-specific locations. Do not commit paths that are secret; keep
`config.yml` per-machine if you work on multiple environments.

---

## Step 2 — Preprocess: `00_preprocess.ipynb`

This notebook turns raw data into three parquet artefacts:

- `df.parquet` — cleaned, labelled dataset (non-imputed)
- `df_imp.parquet` — imputed version used for structure learning
- `bn_vars.parquet` — variable → layer metadata

The notebook has clear TODO cells where you decide:

1. Which raw files to load (SPSS/CSV/Excel).
2. Which value labels to translate to English.
3. Which outcome variables to derive (and how).
4. Which columns to keep in the final dataset.
5. Which layer each variable belongs to.

Generic transforms (`coalesce`, `impute_dataframe`, ...) come from
`core/` — you should not need to reimplement them.

---

## Step 3 — Analysis: `01_analysis.ipynb`

Given the three parquets from Step 2, this notebook:

1. Loads the data and metadata.
2. Discretises continuous variables (quantile bins by default).
3. Learns a layered Bayesian network with the constraints your
   `layer_map` defines (arcs only go downward through layers).
4. Renders the structure and saves it as a PDF (editable in Illustrator).
5. Ranks variables by mutual information with each outcome.
6. Bootstrap-quantifies edge stability.
7. Runs a single-knob sensitivity sweep for one variable of interest.
8. Persists the network as `bn.bifxml` for external tools.

You should mostly need to set your `outcomes`, `layer_map` (already
loaded from `bn_vars.parquet`), and the `base_profile` for the
sensitivity analysis. Everything else is a parameter you can tune.

---

## Step 4 — Iterate

- Manuscript drafts live in `docs/manuscript/current/`.
- Older drafts move to `docs/manuscript/archive/` with an ISO date
  prefix (`2026-05-22_...`).
- Figures/tables from the pipeline are written into `outputs/`.
- Anything not tracked by git (PDFs, DOCX, data) is documented via
  `.gitkeep` files so the folder scaffolding survives a clone.

---

## Common questions

**Do I need to change any code in `core/`?**
No. Everything cohort-specific goes into your project folder as
parameters, dictionaries, or notebook cells. If you find yourself
wanting to change something in `core/`, first check whether adding a
parameter to the relevant function would let you do it from your project.

**What if my cohort doesn't use SCORE2?**
Ignore `risk_region` in `config.yml` and don't import
`core.risk_scores`. Nothing else in `core/` requires SCORE2.

**What if my layer structure is different from HBC's?**
That's fine — `core.bn_utils.build_bn` reads whatever `layer_map` you
pass in, and the outcome/dropout patterns can be overridden with
`outcome_patterns=` and `dropout_patterns=`.
