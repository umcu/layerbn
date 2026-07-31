
# VCI-Bayes-Explore

![VCI-Bayes Logo](logo-vci-bayes.png)

**VCI-Bayes-Explore** packages the preprocessing and modelling workflow
behind Bayesian-network analyses in the [Vascular Cognitive Impairment
(VCI) research group](https://research.umcutrecht.nl/research-groups/vascular-cognitive-impairment-vci/)
of the UMC Utrecht, led by [Malin Overmars, PhD](https://github.com/loverma2).

The flagship analysis (`projects/HBC/`) turns raw Heart-Brain Connection
cohort data into a clinically-informed, layered Bayesian network —
**demographics → vascular risk → neuroimaging → function → outcomes** —
that learns dependencies among 566 participants, quantifies conditional
probabilities for cognitive decline and MACE, benchmarks emerging
biomarkers via mutual information, and explicitly models dropout.

Additional subprojects apply the same shared pipeline (`core/`) to
different research questions across the METAVCI cohorts.

For more on the Heart-Brain Connection study: https://hart-brein.nl/
(supported by the [Dutch Heart Foundation](https://www.hartstichting.nl)).
The accompanying manuscript for the HBC analysis is currently in
preparation 📄.

## License & Citation

Released under the [MIT License](LICENSE).

If you use this code, please cite:
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17305046.svg)](https://doi.org/10.5281/zenodo.17305046)

---

> ⚠️ **Important:** each subproject under `projects/` is tailored to a
> specific cohort. If you apply the code to a different dataset, start
> from `projects/_TEMPLATE/` and adapt the notebooks so the logic
> matches your cohort's structure, coding, and outcomes.

## Repository layout

```
04_VCI_BAYES/
├── README.md                    ← this file
├── CONTRIBUTING.md              How to add a new subproject / conventions
├── LICENSE
├── pyproject.toml               Package metadata (for future `pip install -e .`)
│
├── core/                        Shared helpers for every subproject
│   ├── config.py                YAML config loader + PreprocessConfig
│   ├── io.py                    SPSS + parquet I/O
│   ├── preprocess.py            Generic transforms (coalesce, imputation, ...)
│   ├── risk_scores.py           SCORE2 cardiovascular risk (verified vs HBC)
│   ├── discretisation.py        pyAgrum type-processor wrapper
│   ├── bn_utils.py              build_bn, bootstrap, knob-sweep sensitivity
│   ├── inference.py             MI and conditional-MI rankings
│   ├── plotting.py              Layer colours, BN export, knob plot
│   ├── tables.py                Grouped "Table 1" builder
│   └── README.md
│
├── config/                      Repo-wide defaults (mostly legacy)
│   ├── global.yml               Historical shared settings
│   ├── global.dcf               Legacy R config (kept for reference)
│   └── data_paths.example.yml   Template for local data paths
│
├── concept/                     High-level notes on the modelling approach
│   ├── 00_main_concept.ipynb
│   └── README.md
│
└── projects/                    One folder per analysis
    ├── _TEMPLATE/               Copy this to start a new subproject
    │   ├── README.md            Step-by-step guide
    │   ├── config.yml           Fully commented
    │   ├── 00_preprocess.ipynb  16 cells wired to core/, with TODOs
    │   ├── 01_analysis.ipynb    24 cells wired to core/, with TODOs
    │   ├── outputs/             graphs/, tables/
    │   └── docs/manuscript/     current/, archive/, supplement_figures/
    │
    ├── HBC/                     Heart-Brain Connection (near-publication)
    │   ├── 00_preprocess.ipynb
    │   ├── 01_bayesian_network.ipynb
    │   ├── preprocess_data.py   CLI equivalent of 00_preprocess
    │   ├── config.yml
    │   ├── bn_joint.bifxml      Persisted joint BN
    │   ├── outputs/             graphs/, tables/, archive/legacy-2025/
    │   └── docs/manuscript/     current/, archive/, supplement_figures/
    │
    ├── METAVCI_COGNITION/       Cognitive-outcome BN across METAVCI
    │   ├── 00_preprocess.ipynb
    │   ├── 01_analysis.ipynb
    │   ├── config.yml
    │   ├── codebook/            Variable → layer mapping (Excel)
    │   ├── outputs/
    │   └── docs/manuscript/
    │
    └── METAVCI_WMH_BLOOD/       Blood-biomarker → WMH BN
        ├── 00_preprocess.ipynb
        ├── 01_bayesian_network.ipynb
        ├── config.yml
        ├── outputs/graphs/      Robustness + MI plots
        ├── outputs/tables/      Conditional probability tables
        └── docs/manuscript/     Methods writeup + curated figures
```

## Quick start (HBC / any subproject)

1. **Install Python ≥ 3.11** and open a terminal in the repo root.
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate           # Windows: venv\Scripts\activate
   pip install pandas numpy pyreadstat scikit-learn PyYAML pyagrum \
               matplotlib scipy ipywidgets pyarrow
   ```
   (Or once the package is finalised: `pip install -e .` — see
   [pyproject.toml](pyproject.toml).)
3. **Point the subproject at your data.** Each subproject has its own
   `config.yml`. For HBC:
   ```yaml
   # projects/HBC/config.yml
   project_root: '/path/to/projects/HBC'
   raw_dir:      '/secure/location/hartbrein/raw'
   output_dir:   '/secure/location/hartbrein/processed'
   codebook_path:'/secure/location/hartbrein/meta/HBC_CODEBOOK_LABELS.xlsx'
   risk_region:  'Low'
   seed:         1234
   ```
4. **Preprocess** — open `projects/HBC/00_preprocess.ipynb`, run all.
   Produces `df.parquet`, `df_imp.parquet`, `bn_vars.parquet` in
   `output_dir`.
5. **Analyse** — open `projects/HBC/01_bayesian_network.ipynb`, run
   all. Reproduces the network structure, MI rankings, bootstrap
   stability, scenario probabilities, and PDF figures.

For a *new* subproject (different cohort / research question), start
from `projects/_TEMPLATE/`. See [CONTRIBUTING.md](CONTRIBUTING.md) for
the walk-through.

## Subproject index

| Folder | Research question | Status |
| --- | --- | --- |
| [`projects/HBC/`](projects/HBC/README.md) | Bayesian network in the Heart-Brain Connection cohort | Manuscript in preparation |
| [`projects/METAVCI_COGNITION/`](projects/METAVCI_COGNITION/README.md) | Cognitive outcomes across METAVCI cohorts | Scaffold wired to `core/`; codebook + analysis choices in progress |
| [`projects/METAVCI_WMH_BLOOD/`](projects/METAVCI_WMH_BLOOD/README.md) | Blood biomarkers → white-matter hyperintensities | Scaffold wired to `core/`; earlier analysis outputs archived under `outputs/` and `docs/manuscript/` |
| [`projects/_TEMPLATE/`](projects/_TEMPLATE/README.md) | Starter for new subprojects | — |

## Requirements

- Python ≥ 3.11
- `pandas` ≥ 2, `numpy`, `scipy`
- `pyreadstat` (SPSS files)
- `scikit-learn` (imputation)
- `pyagrum` including `pyagrum.lib.notebook`, `pyagrum.lib.discreteTypeProcessor`
- `matplotlib`, `ipywidgets`
- `pyarrow` (parquet)
- `PyYAML`

Optional: `statsmodels` (biomarker logistic regression cells in the
HBC analysis notebook).

## Data safety

`.gitignore` blocks common data and manuscript formats
(`*.sav`, `*.parquet`, `*.csv`, `*.xlsx`, `*.pdf`, `*.docx`, ...) so
sensitive files stay local. Folder scaffolding is preserved via
`.gitkeep` files that survive a clone.

Never commit `config.yml` if it contains confidential absolute paths;
edit locally per machine.
