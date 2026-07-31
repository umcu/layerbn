# Contributing to VCI-Bayes

This guide is for anyone (usually a research colleague) who wants to
add a **new subproject** or contribute to an existing one. It focuses
on the folder conventions and the pipeline, not on the science.

If you're just running an existing analysis, follow the *Quick start*
in [README.md](README.md); this file is for structural changes.

---

## Table of contents

1. [Set up a dev environment](#1-set-up-a-dev-environment)
2. [Start a new subproject](#2-start-a-new-subproject)
3. [Fill in `00_preprocess.ipynb`](#3-fill-in-00_preprocessipynb)
4. [Fill in `01_analysis.ipynb`](#4-fill-in-01_analysisipynb)
5. [Folder & file conventions](#5-folder--file-conventions)
6. [Manuscript & figure archival](#6-manuscript--figure-archival)
7. [Committing safely](#7-committing-safely)
8. [Where should this code live? (`core/` vs project)](#8-where-should-this-code-live-core-vs-project)
9. [FAQ](#9-faq)

---

## 1. Set up a dev environment

```bash
# clone (or open) the repo
cd /path/to/04_VCI_BAYES

# create + activate a venv
python -m venv venv
source venv/bin/activate                   # Windows: venv\Scripts\activate

# minimal deps
pip install pandas numpy pyreadstat scikit-learn PyYAML pyagrum \
            matplotlib scipy ipywidgets pyarrow statsmodels
```

Verify `core/` is importable:

```bash
python -c "from core.risk_scores import score2; print(score2(risk_region='Low', age=65, gender='male', smoker=0, systolic_bp=140, diabetes=0, total_chol=5.5, total_hdl=1.4))"
# → 7.3
```

## 2. Start a new subproject

```bash
cp -r projects/_TEMPLATE projects/MY_NEW_PROJECT
cd    projects/MY_NEW_PROJECT
```

Then edit `config.yml`:

- `project_root` — absolute path to `projects/MY_NEW_PROJECT`
- `raw_dir` — where your raw data lives (typically **outside** the
  repo, next to the cohort files)
- `output_dir` — where processed parquet files will go
- `codebook_path` — Excel file listing each variable and its layer
- `risk_region` — only used if you compute SCORE2; otherwise ignore
- `seed` — anything reproducible

Anything else you add (e.g. `follow_up_years: 5`) is preserved on
`config.extra` and readable from any notebook cell.

## 3. Fill in `00_preprocess.ipynb`

The notebook has **16 cells**. The TODO cells are the only ones you
edit; the others just call `core.*` helpers.

| Cell | What you do |
| --- | --- |
| 1–3 | Nothing — imports and config loader are ready |
| 4 (TODO) | Load your raw data. Example patterns for SPSS/CSV/Excel are in the cell comments. |
| 5 (TODO) | Cohort-specific transforms — `coalesce`, `to_datetime`, `translate_labels`, custom columns. |
| 6 (TODO) | Derive outcomes. Encode censored/dropout cases with an explicit `"Unobserved"` state so imputation doesn't fabricate one. |
| 7 (TODO) | Build the `bn_vars` DataFrame from your codebook (or inline). |
| 8 | Runs imputation and writes the three parquet artefacts. |

**Output:** `df.parquet`, `df_imp.parquet`, `bn_vars.parquet` in
`config.output_dir`.

## 4. Fill in `01_analysis.ipynb`

The notebook has **24 cells**. You only edit a handful:

| Cell | What you do |
| --- | --- |
| 4 | Set `outcomes` (list of outcome column names) and optionally `exclude_layers` (layers to drop from structure learning, e.g. a biomarker layer). |
| 5 | Discretisation defaults are fine for most cohorts; tweak `n_bins` if needed. |
| 6 | Pick a scoring rule (`K2` / `BIC` / `BDeu`). |
| 10 | Define `scenario_profiles` and `target_outcomes` for scenario risks. |
| 11 | Define `base_profile` and `knob` for the single-knob sweep. |

Everything else — layer colours, MI ranking, bootstrap resampling, PDF
export — runs unchanged.

## 5. Folder & file conventions

```
projects/MY_NEW_PROJECT/
├── 00_preprocess.ipynb
├── 01_analysis.ipynb
├── config.yml
├── codebook/                    (optional) Excel with VARIABLE NAME → LAYER
├── outputs/
│   ├── graphs/                  BN structure, inference, MI plots (pipeline-generated)
│   └── tables/                  CSV/parquet tables, CPT exports
└── docs/
    └── manuscript/
        ├── current/             Latest manuscript version(s)
        ├── archive/             Older dated versions (ISO YYYY-MM-DD_)
        └── supplement_figures/  Curated figures shipped with the paper
```

**Distinction**: `outputs/graphs/` is *auto-generated* by the pipeline
(re-runnable). `docs/manuscript/supplement_figures/` is *curated* —
figures manually edited in Illustrator, hand-picked for the paper.

## 6. Manuscript & figure archival

- The **latest** working version lives in `docs/manuscript/current/`.
- When you finalise a round of revisions, move the previous version
  into `docs/manuscript/archive/` with an **ISO date prefix**:

  ```
  docs/manuscript/current/Manuscript_v3.docx
  docs/manuscript/archive/2026-05-22_Manuscript_v2.docx
  docs/manuscript/archive/2026-03-14_Manuscript_v1.docx
  ```

  Use `YYYY-MM-DD_` (not the Dutch `DDMMYYYY`) — everything sorts
  correctly and the older HBC files were renamed to this convention
  in commit [a6e3bbe](../../commit/a6e3bbe).

- Old figures and abstracts land under thematic subfolders
  (`archive/abstract_vascog/`, `archive/presentations/`, etc.) —
  categorise, don't dump.

## 7. Committing safely

- **Never `git add .` blindly.** Add specific files. `.gitignore`
  blocks common data (`*.sav`, `*.parquet`, `*.csv`, `*.xlsx`) and
  manuscripts (`*.docx`, `*.pdf`), but a mistyped path can still leak.
- **Never commit** a `config.yml` that contains confidential paths
  someone else shouldn't see. Local machines can have local variants.
- **`.gitkeep`** files preserve the folder scaffolding even though
  contents are ignored — leave them in place when you re-organise.
- Manuscript files are always ignored, so they never appear in
  `git status`. That's on purpose: version-control them via the
  archive convention (§6), not via git commits.

## 8. Where should this code live? (`core/` vs project)

Ask yourself: **would every subproject need this?**

- **Yes** → contribute to `core/`. Add a function, keep it
  cohort-agnostic (no hard-coded column names, layer names, or Dutch
  labels — pass them as parameters).
- **No** → keep it in your project's notebook or a small helper file
  under `projects/MY_NEW_PROJECT/`.

Design rules for `core/`:

- No import-time side effects (no logging setup, no `matplotlib.use`,
  no `gum.config[...]`).
- Heavy dependencies (`pyagrum`) are imported *inside* functions so
  someone can `import core.preprocess` on a machine without pyAgrum.
- Cohort-specific dictionaries (translations, layer maps, outcome
  labels) live in the project, not in `core/`.

## 9. FAQ

**Q: My cohort doesn't have Dutch labels — do I need `translate_labels`?**
No. `core.preprocess.translate_labels` takes any mapping you supply.
Skip the call if you don't need translation.

**Q: My layer names are different from HBC's `L0 – ...` scheme.**
Fine — `core.bn_utils.build_bn` reads whatever `layer_map` you give it.
If you use different substrings than `"Outcomes"` / `"Dropout"` for
your outcome and dropout layers, pass them via `outcome_patterns=` and
`dropout_patterns=`.

**Q: Can I add a new score function to `core.risk_scores`?**
Yes. Follow the SCORE2 shape: pure function, keyword-only args, one
return value, deterministic. Add a test-case comparison against a
reference implementation if you can.

**Q: The template's notebook cells parse but crash when I run them.**
Almost certainly a TODO you haven't filled in yet — cells 4 through 7
of `00_preprocess.ipynb` and cells 4, 10, 11 of `01_analysis.ipynb`
contain deliberate placeholders. See §3 and §4.

**Q: Where is the HBC preprocessing done — in `preprocess_data.py` or
`00_preprocess.ipynb`?**
Both. `preprocess_data.py` is the CLI script; the notebook is the
interactive equivalent. They share logic. Post-publication, HBC will
migrate to use `core/` like the METAVCI subprojects do; until then
it's kept as-is to preserve reproducibility of the manuscript figures.
