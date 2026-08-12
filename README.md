# vcibayes

![VCI-Bayes Logo](logo-vci-bayes.png)

**vcibayes** learns knowledge-guided Bayesian networks from cohort data.

An expert-defined ordering of variable *layers* constrains structure learning,
so arcs may only run downstream through the layers
(**demographics → vascular risk → neuroimaging → function → outcomes**).
Non-random dropout is modelled explicitly as a *selection* layer downstream of
the outcomes, rather than being imputed away.

The analysis is declared in a YAML spec, not in code. A new cohort writes a
`spec.yml` describing its columns and layers; it does not edit this package.

Developed in the [Vascular Cognitive Impairment (VCI) research
group](https://research.umcutrecht.nl/research-groups/vascular-cognitive-impairment-vci/)
of UMC Utrecht, led by [Malin Overmars, PhD](https://github.com/loverma2).

## Install

```bash
pip install git+https://github.com/umcu/vci-bayes@v1.0.0
```

Requires Python ≥ 3.11. `pyagrum` supplies the structure learner and inference
engine.

## Use

```python
from vcibayes.spec import load_spec
from vcibayes.discretisation import make_type_processor
from vcibayes.bn_utils import build_bn, bootstrap_edge_frequencies, bootstrap_knob_sweep
from vcibayes.inference import mutual_information_scores
from vcibayes.plotting import default_layer_colors, build_node_colors, plot_knob_sweep

spec = load_spec("spec.yml")

type_processor = make_type_processor(
    method=spec.discretisation.method,
    n_bins=spec.discretisation.n_bins,
    threshold=spec.discretisation.threshold,
)

bn = build_bn(
    df,                                   # analysis-ready, fully imputed
    outcomes=list(spec.variant("joint").outcomes),
    layer_map=spec.layer_map,             # ordered; the order IS the constraint
    type_processor=type_processor,
    exclude_layers=list(spec.variant("joint").exclude_layers),
    score=spec.model.score,
    random_seed=spec.model.seed,
)
```

### The spec

```yaml
layers:                       # ORDER IS THE CONSTRAINT
  - name: "L0 – Demographics"
    role: covariate
    variables: [AGE, SEX]
  - name: "L8 – Outcomes"
    role: outcome
    variables: [OUTCOME_X]
  - name: "L9 – Dropout"
    role: selection           # downstream of the outcomes
    variables: [DROPOUT REASON]

discretisation: {method: quantile, n_bins: 4, threshold: 10}
model: {score: K2, use_tabu: true, max_indegree: 5, seed: 42}
bootstrap: {n: 200}

variants:
  - name: joint
    outcomes: [OUTCOME_X, DROPOUT REASON]
    exclude_layers: []
```

`load_spec` validates eagerly and names the offending key
(`layers[3].variables[1]: variable 'AGE' already appears in layers[0] …`), so
a typo surfaces before a 40-minute bootstrap rather than after it. A variable
must belong to exactly one layer.

## Modules

| Module | What it holds |
| --- | --- |
| `spec.py` | `load_spec`, `Spec`, `check_against_dataframe` — the declarative analysis spec |
| `bn_utils.py` | `build_bn` (layer-constrained structure learning), `bootstrap_edge_frequencies`, `bootstrap_scenario_risks`, `bootstrap_knob_sweep` |
| `discretisation.py` | `make_type_processor`, `state_for_value`, `describe_template` |
| `inference.py` | `mutual_information_scores`, `conditional_mutual_information_scores` |
| `plotting.py` | `default_layer_colors`, `build_node_colors`, `show_and_save_bn`, `plot_knob_sweep` |
| `preprocess.py` | `impute_dataframe`, `coalesce`, `to_datetime`, `translate_labels` |
| `config.py` | `load_project_config` — machine-specific paths, kept out of the spec |

## Scope

This package starts at an **analysis-ready dataframe**. Turning a cohort's raw
files into that dataframe — outcome derivation, censoring, dropout
canonicalisation, derived variables — is cohort-specific judgement that no
schema expresses usefully, and it belongs in the analysis repository.

Reference analysis: [`hbc-bayes`](https://github.com/umcu/hbc-bayes) (Heart-Brain
Connection cohort), which pins a released version of this package.

## Citation

Released under the [MIT License](LICENSE). See [CITATION.cff](CITATION.cff).

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17305046.svg)](https://doi.org/10.5281/zenodo.17305046)
