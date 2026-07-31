# METAVCI_COGNITION

Bayesian-network subproject investigating cognitive outcomes across the
METAVCI cohorts. Owned collaboratively — the notebooks are wired to
the shared `core/` package so most work is deciding *what* to model,
not writing pipeline code.

## Quick start

1. **Edit `config.yml`** — set `project_root`, `raw_dir`, `output_dir`
   to your machine's paths. Point `codebook_path` at
   `codebook/Cognition_BN_rules_to_fill_in.xltx` (or wherever you've
   put your final codebook).
2. **Fill in the codebook** — one row per variable, with a `LAYER`
   column that tells the network which variables can be parents of
   which. See `codebook/Cognition_BN_rules_to_fill_in.xltx`.
3. **Run `00_preprocess.ipynb`** — TODO cells are marked; you decide
   which raw files to load, which value labels to translate, which
   outcomes to derive, which variables to include. Generic transforms
   are provided by `core/`.
4. **Run `01_analysis.ipynb`** — reads the parquets from step 3,
   learns the network, runs stability + sensitivity analyses. Change
   `outcomes`, `base_profile`, `knob` to reflect the research question.

For the general workflow (how the template works, how to archive old
manuscripts, how folders relate) see `projects/_TEMPLATE/README.md`.

## Folders

```
METAVCI_COGNITION/
├── codebook/                    Variable → layer mapping (Excel)
├── outputs/
│   ├── graphs/                  BN structure/inference PDFs
│   └── tables/                  Per-run CSV/parquet tables
└── docs/
    └── manuscript/
        ├── current/             Latest manuscript version(s)
        ├── archive/             Older dated versions (ISO YYYY-MM-DD prefix)
        └── supplement_figures/  Figures that ship with the paper
```

## Status

Skeleton wired to `core/`. Codebook and analysis choices still to be
filled in by the domain expert.
