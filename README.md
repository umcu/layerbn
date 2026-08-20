# layerbn

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

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17302710.svg)](https://doi.org/10.5281/zenodo.17302710)

---

## Getting started

Requires Python 3.11 or newer. Four commands, then a notebook.

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
| `spec.yml` | **What the analysis is.** The only file you normally edit |
| `config.yml` | **Where your data is** on this machine. Not shared |
| `analysis.ipynb` | Runs the analysis. You do not edit code in it |
| `.gitignore` | Keeps `config.yml` and results out of version control |

**3. Run it once, unchanged**

```bash
jupyter lab analysis.ipynb
```

Run every cell. It takes about a minute on a built-in simulated cohort, so you
see the whole analysis working before you change anything. The variable names
you see are placeholders and mean nothing.

**4. Point it at your own data**

You need a table with one row per participant, one column per variable, and
**no missing values** ([see Scope](#scope)). Then:

1. Edit `spec.yml` — your variables, grouped into layers, in order.
2. Edit `config.yml` — the folder holding your table.
3. Check it: `python -m layerbn check spec.yml`
4. In the notebook's first cell, set `USE_DEMO_DATA = False`.
5. Run from the top.

That is the whole loop. Your cohort will have different variables, a different
number of layers and different outcomes; none of it needs a code change.

> `python -m layerbn` and `layerbn` do the same thing. The bare `layerbn`
> command only works if pip's script directory is on your `PATH`, which it
> often is not — so the docs use the longer form, which always works.

### What the notebook produces

| Section | Output |
| --- | --- |
| Discretisation | The bins every continuous variable was cut into. Read this first; every later result depends on it |
| Network | The learned structure, with nodes coloured by layer |
| Edge stability | How often each arc survives resampling, as a table and as arc colour and width in the figure |
| Variable importance | Every variable ranked by mutual information with each outcome, raw and conditional on the outcome's parents |
| Layer ablation | The same network learned with and without a layer, compared on the outcomes' parents |
| Scenario risks | Outcome probabilities for participant profiles you specify, with bootstrap intervals |
| Sensitivity sweep | How the outcome probabilities respond as one variable moves across its states |

Results are written to `outputs/` as CSV files, a PDF figure, and the network
itself in `.bifxml`, which can be reopened without repeating the analysis.

---

## The specification

`spec.yml` holds every choice the analysis makes. This is an abbreviated
example; the file `python -m layerbn init` writes is fully commented.

```yaml
spec_version: 2

layers:                        # THE ORDER OF THIS LIST IS THE CONSTRAINT
  - name: "L0 – Demographics"
    role: covariate
    variables: [AGE, SEX]

  - name: "L5 – Outcomes"
    role: outcome              # no arcs between outcomes
    variables: [OUTCOME DECLINE]

  - name: "L6 – Dropout"
    role: selection            # downstream of the outcomes
    variables: [DROPOUT REASON]

discretisation: {method: quantile, n_bins: 4, threshold: 10}
model: {score: K2, use_tabu: true, max_indegree: 5, seed: 42}
bootstrap: {n: 200}

variants:
  - name: joint
    outcomes: [OUTCOME DECLINE, DROPOUT REASON]
    exclude_layers: []
```

The order of the `layers` list is the constraint. Nothing else determines it:
not the names, not the numbering, not how the file is sorted. Put the layers in
the order you would defend in a methods section, and reordering them changes
the analysis.

`role` marks the two layers that are treated specially. `outcome` layers hold
your endpoints, and arcs between endpoints are forbidden so that one is never
reported as a cause of another. A `selection` layer holds dropout: arcs into it
are allowed only from outcomes, and every outcome is connected to it after
learning.

### Constraints beyond the layer order

The layer order rules out every upstream arc. When you need to say something
more specific, an optional `constraints` block does it:

```yaml
constraints:
  forbid:                                     # rule an arc out
    - {from: AGE, to: EDUCATION YEARS}
    - {from_layer: "L1 – Risk", to_layer: "L4 – Function"}
  require:                                    # insist on an arc
    - {from: SEX, to: OUTCOME EVENT}
  no_parents:  [AGE]                          # pin a root
  no_children: [DROPOUT REASON]               # pin a sink

  within_layers: true                         # arcs inside one layer
  arcs_between_outcomes: false                # one endpoint causing another
  selection_parents: outcomes                 # or: any
```

Either end of a rule may name a variable or a whole layer, and the two can be
mixed, so one rule can stand for many arcs.

The last three settings are the conventions that were previously fixed in the
code: whether variables in the same layer may be connected, whether one
outcome may point at another, and whether anything other than an outcome may
point into the dropout layer. The values shown are the defaults, so a spec
that omits the block behaves exactly as before.

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
constraints need not declare a version at all.

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

Validation happens before any model is fitted, so a typo costs a second rather
than surfacing after a bootstrap has been running for half an hour.

Machine-specific paths stay out of the spec. They belong in `config.yml`, which
is not shared. That separation is what makes `spec.yml` publishable alongside a
manuscript: it records what the analysis was, and nothing about where it ran.

---

## Scope

This package starts at an **analysis-ready dataframe**: one row per
participant, one column per variable, no missing values.

Turning a cohort's raw files into that table is deliberately out of scope.
Deriving outcomes, applying censoring rules, canonicalising dropout categories
and deciding how to impute are judgements specific to a cohort, and no schema
expresses them usefully. They belong in the analysis repository, in a script
that runs before this one.

Reference analysis: [`hbc-bayes`](https://github.com/umcu/hbc-bayes) (Heart-Brain
Connection cohort), which pins a released version of this package.

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

The suite covers spec validation, the constraint solver, the layer
guarantees checked on networks that were actually learned, discretisation,
the CLI, `config.yml`, and the template notebook executed exactly as a new
user would run it. CI runs it on Python 3.11–3.13.

`tests/test_reproducibility.py` pins the demo cohort's bin edges. Every
number this package reports is conditional on the discretisation, and the
edges come from scikit-learn via pyAgrum — neither of which promises to keep
them fixed across versions. If a dependency upgrade moves them, that file
fails rather than letting results change quietly. `scikit-learn` is capped
below 1.9 for the same reason; lift the cap and the pinned edges together,
or not at all.

## Citation

Released under the [MIT License](LICENSE). See [CITATION.cff](CITATION.cff) for
citation metadata.

Released as `vcibayes` up to version 1.2.1. The Zenodo concept DOI covers
every version under both names, so existing citations still resolve.
