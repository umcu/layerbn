<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logo-layerbn-2.png">
  <img src="logo-layerbn.png" alt="layerbn" width="380">
</picture>


> [!NOTE]
> **About `layerbn`**
>
> Many research questions involve multiple outcomes and a range of interrelated factors, 
> which influence one another and the outcomes both directly and indirectly. A network-based 
> approach could be of added value here. Unconstrained structure learning infers directions 
> (i.e., arcs) from one factor to another from the data alone, which can produce arcs that 
> contradict a known temporal or causal ordering — an outcome pointing back to a baseline 
> characteristic, for instance.
>
> `layerbn` fixes that ordering instead of inferring it. Factors are assigned to
> layers, the layers are ordered by study design and prior knowledge, and arcs
> are permitted only in the specified direction. Estimation then answers three
> questions: which of the admissible arcs the data support, how stable each is
> under resampling, and how much each contributes to each outcome.
>
> The approach suits any study whose factors can be arranged into ordered
> layers ahead of one or more outcomes. It was first applied in a vascular
> cognitive impairment cohort and released as `vcibayes` through v1.2.1;
> `layerbn` generalises the same method. Networks are fitted with
> [pyAgrum](https://pyagrum.gitlab.io/).

Developed in the [Vascular Cognitive Impairment (VCI) research
group](https://research.umcutrecht.nl/research-groups/vascular-cognitive-impairment-vci/)
of UMC Utrecht, department Neurology and Neurosurgery, led by [Malin Overmars, PhD](https://research.umcutrecht.nl/researchers/malin-overmars/).

[![DOI](https://zenodo.org/badge/1067978388.svg)](https://doi.org/10.5281/zenodo.17302710)

---

## Getting started

Requires Python 3.11 or newer. 

**1. Install**

```bash
pip install "layerbn[notebook] @ git+https://github.com/umcu/layerbn@v2.0.0"
```

`[notebook]` adds JupyterLab and the Parquet reader. The quotes matter —
without them the shell eats the square brackets.

**2. Create a project**

```bash
python -m layerbn init my-study
cd my-study
```

This writes four files:

| File | What it is |
| --- | --- |
| `spec.yml` | **Settings for your specific analysis.** This file you'll edit |
| `config.yml` | **Specify where your data is stored** on this machine. Not shared |
| `analysis.ipynb` | Runs the analysis based on your settings |
| `.gitignore` | Keeps `config.yml` and results out of version control |

**3. Run it once, unchanged**

```bash
jupyter lab analysis.ipynb
```

Run every cell. If you wish, a built-in simulated cohort can be used, so you
see the whole analysis working before you change anything. 

**4. Point it at your own data**

This analysis requires a table with one row per participant, one column per variable, and **no missing values** ([see Scope](#scope)). Then:

1. Edit `spec.yml` — your variables, grouped into layers, in order.
2. Edit `config.yml` — where your data is stored
3. Check: `python -m layerbn check spec.yml`
4. In the notebook's first cell, set `USE_DEMO_DATA = False`.
5. Run from the top.

### What the notebook produces

| Section | Output |
| --- | --- |
| Discretisation | The number of bins every continuous variable is divided. |
| Network | The learned structure, with nodes coloured by the specified layer |
| Edge stability | The frequency, expressed as a percentage, with which each arc occurs across bootstrap runs, shown in a table and indicated by the colour and width of the arc in the figure |
| Variable importance | Every variable ranked by mutual information with each outcome, raw and conditional on the outcome's parents |
| Layer ablation | The same network learned with and without a specified layer |
| Scenario risks | Outcome probabilities for participant profiles you specify, with bootstrap intervals |
| Sensitivity sweep | How outcome probabilities respond as one node changes across its states |

Results are written to `outputs/` as CSV files, a PDF figure, and the network
itself in `.bifxml`, which can be reopened without repeating the analysis.

---

## The specification

In `spec.yml`, you specify every choice used in the analysis. This is an abbreviated
example; 

```yaml
spec_version: 2

layers:                        # THE ORDER OF THIS LIST IS THE CONSTRAINT
  - name: "L0 – Demographics"
    role: covariate
    variables: [AGE, SEX]

  - name: "L1 – Risk factors"
    role: covariate
    variables: [SMOKING STATUS, HYPERTENSION]

  - name: "L5 – Outcomes"
    role: outcome              # no arcs between outcomes
    variables: [OUTCOME DECLINE]

discretisation: {method: quantile, n_bins: 4, threshold: 10}
model: {score: K2, use_tabu: true, max_indegree: 5, seed: 42}
bootstrap: {n: 200}

variants:
  - name: joint
    outcomes: [OUTCOME DECLINE, OUTCOME EVENT]
    exclude_layers: []
```

### Constraints beyond the layer order

The layer order rules out every upstream arc. When you need to be
more specific about layer ordering, an optional `constraints` can be set:

```yaml
constraints:
  forbid:                                     # rule an arc out
    - {from: AGE, to: EDUCATION YEARS}
    - {from_layer: "L1 – Risk", to_layer: "L4 – Function"}
  require:                                    # insist on an arc
    - {from: SEX, to: OUTCOME EVENT}
  no_parents:  [AGE] 
  no_children: [DROPOUT REASON]   

  within_layers: true                         # arcs inside one layer
  arcs_between_outcomes: false                # one endpoint causing another
  selection_parents: outcomes                 # or: any
```

**Constraints can only narrow.** Nothing here can license an arc that runs
against the layer order, so the `layers` list on its own stays a complete
statement of what is possible. Requiring an upstream arc is an error that
tells you to reorder the layers instead:

```
INVALID: spec.yml: constraints.require[0]: OUTCOME EVENT -> AGE requires
'OUTCOME EVENT' -> 'AGE', but 'OUTCOME EVENT' is in layer 5 and 'AGE' is in
the earlier layer 0. Constraints may only narrow what the layer order
allows. Reorder `layers` if this arc should be possible.
```

Rules are also checked against each other, so an arc that is both required and
forbidden is reported rather than passed to the learner.

Using `constraints` requires an explicit `spec_version: 2` at the top of the
file. Version 1 specs remain valid and load unchanged, and a spec without
constraints need not declare a version.

The declaration has to be explicit rather than left to default, because a
loader older than version 2 assumes version 1. Given an undeclared file it
would accept it, ignore the constraints, and learn an unconstrained network
without reporting anything.

To check a spec without opening a notebook:

```bash
python -m layerbn check spec.yml
```

This validates the file and prints the layer order it will impose. Errors name
the exact key and suggest a correction:

```
INVALID: spec.yml: variants[0].exclude_layers[0]: 'L2 - Optional markers'
is not a declared layer. Did you mean 'L2 – Optional markers'?
```

---

## Scope

This package starts at an **analysis-ready dataframe**: one row per
participant, one column per variable, no missing values.

Turning a cohort's raw files into that table is deliberately out of scope.
Deriving outcomes, applying censoring rules, canonicalising dropout categories
and deciding how to impute are judgements specific to a cohort. 

---

## Using the functions directly

The notebook covers the usual path. If you are scripting, `Analysis` exposes
the same steps, reading every setting from the spec:

```python
from layerbn.analysis import Analysis

study = Analysis.from_files("spec.yml", "cohort.parquet")

study.bins("joint")             # the discretisation actually used
study.network("joint")          # the learned network
study.stable_edges("joint")     # bootstrap arc frequencies, as a table
study.information("joint")      # mutual information per outcome
study.scenarios("joint")        # posterior risks for the spec's profiles
study.knob_sweep("joint")       # sensitivity to one variable
study.draw("joint", stability=True, save_path="network.pdf")
```

The underlying functions are also available individually. Note that they take
the layer map, the score, the seed and the layer role patterns as separate
arguments, so calling them directly means keeping those consistent with the
spec yourself.

| Module | Contents |
| --- | --- |
| `analysis.py` | `Analysis`, the spec-driven entry point used by the notebook |
| `spec.py` | `load_spec`, `Spec`, `Constraints`, `check_against_dataframe` |
| `bn_utils.py` | `build_bn`, `bootstrap_edge_frequencies`, `bootstrap_scenario_risks`, `bootstrap_knob_sweep` |
| `discretisation.py` | `make_type_processor`, `state_for_value`, `describe_template` |
| `inference.py` | `mutual_information_scores`, `conditional_mutual_information_scores` |
| `plotting.py` | `default_layer_colors`, `build_node_colors`, `show_and_save_bn`, `plot_knob_sweep` |
| `preprocess.py` | `impute_dataframe`, `coalesce`, `to_datetime`, `translate_labels` |
| `config.py` | `load_project_config`, `ProjectConfig`, for machine-specific paths |
| `demo.py` | `make_demo_cohort`, the simulated cohort used by the template |

`pyagrum` supplies the structure learner and the inference engine.

---

## Documentation

- [`docs/troubleshooting.md`](docs/troubleshooting.md) — error messages, what
  each one means, and what to do about it.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed in each release. Read this
  before upgrading a running analysis.

---

## Development

```bash
git clone https://github.com/umcu/layerbn
cd layerbn
pip install -e ".[dev,notebook]"

pytest                  # the whole suite, about two minutes
pytest -m "not slow"    # skip the end-to-end notebook run
ruff check layerbn tests
```


## Citation

Released under the [MIT License](LICENSE). See [CITATION.cff](CITATION.cff) for
citation metadata.

Released as `vcibayes` up to version 1.2.1. The Zenodo concept DOI covers
every version under both names, so existing citations still resolve.
