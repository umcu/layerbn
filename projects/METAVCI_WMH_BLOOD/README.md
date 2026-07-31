# METAVCI_WMH_BLOOD

Bayesian-network subproject linking blood biomarkers to white-matter
hyperintensity (WMH) burden and downstream outcomes across the METAVCI
cohorts. Wired to the shared `core/` package.

## Quick start

1. **Edit `config.yml`** — set `project_root`, `raw_dir`, `output_dir`
   to your machine's paths.
2. **Run `00_preprocess.ipynb`** — TODO cells are marked; decide which
   raw files to load, which biomarkers and WMH scores to keep, how to
   derive outcomes.
3. **Run `01_bayesian_network.ipynb`** — reads the parquets from step
   2, learns the network, runs stability + sensitivity analyses.
   Update `outcomes`, `base_profile`, and `knob` to reflect the
   research question.

For the general workflow (template design, archival convention, folder
layout) see `projects/_TEMPLATE/README.md`.

## Contents

```
METAVCI_WMH_BLOOD/
├── 00_preprocess.ipynb          Raw data → cleaned parquet
├── 01_bayesian_network.ipynb    BN learning + inference + sensitivity
├── config.yml                   Paths and per-run knobs
├── outputs/
│   ├── graphs/                  Pipeline-generated network + MI plots
│   │   ├── bn_robust.pdf
│   │   └── mi_biomarker_wmh.pdf
│   └── tables/                  Conditional probability tables
│       ├── cpt_BNP.docx
│       ├── cpt_WMH_SFO.docx
│       └── cpt_WMH_SFO_adjusted.docx
└── docs/
    └── manuscript/
        ├── current/             Latest writing
        │   └── methods_BN.docx
        ├── archive/             Older dated versions
        └── supplement_figures/  Manuscript-facing figures (curated)
            ├── bn_legend.pdf
            ├── bn_manuscript.pdf
            └── bn_robust_edited.pdf
```

## Status

Scaffold applied. Existing manuscript, CPT, and figure outputs from
earlier analyses have been sorted into `outputs/` (pipeline-generated)
vs `docs/manuscript/supplement_figures/` (curated for the paper).
Analysis notebook decisions (`outcomes`, `layer_map`, `base_profile`,
`knob`) still to be re-filled — the placeholder notebooks that lived
here previously had no logic to preserve.
